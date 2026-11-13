// Clearway plugin for vPilot.
// Shares vPilot with the Clearway companion (http://127.0.0.1:<port>):
//   vPilot -> Clearway: network state, private/frequency/broadcast messages, SELCAL,
//                       nearby controllers, controller info (ATIS) and METARs.
//   Clearway -> vPilot: private and frequency messages, connect/disconnect, Mode C,
//                       ident, controller info and METAR requests.
//
// Install: copy Clearway.vPilot.dll into vPilot's Plugins folder and restart vPilot.

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using RossCarlson.Vatsim.Vpilot.Plugins;
using RossCarlson.Vatsim.Vpilot.Plugins.Events;
using RossCarlson.Vatsim.Vpilot.Plugins.Exceptions;

namespace Clearway.Vpilot
{
    public class ClearwayPlugin : IPlugin
    {
        private IBroker _broker;
        private SynchronizationContext _ui;
        private string _api;
        private readonly JavaScriptSerializer _json = new JavaScriptSerializer();
        private readonly BlockingCollection<Dictionary<string, object>> _events =
            new BlockingCollection<Dictionary<string, object>>(new ConcurrentQueue<Dictionary<string, object>>(), 500);

        private volatile bool _connected;
        private volatile string _callsign = "";
        private volatile string _cid = "";
        private volatile bool _companionReachable = true;
        private int _outboxFailures;

        private class Controller { public string Callsign; public int Frequency; public double Lat; public double Lon; }
        private readonly ConcurrentDictionary<string, Controller> _controllers = new ConcurrentDictionary<string, Controller>();
        private volatile bool _controllersDirty = true;

        public string Name => "Clearway";

        public void Initialize(IBroker broker)
        {
            _broker = broker;
            _ui = SynchronizationContext.Current;
            _api = "http://127.0.0.1:" + ReadPort() + "/api/vpilot/";

            broker.NetworkConnected += (s, e) =>
            {
                _connected = !e.ObserverMode;
                _callsign = e.Callsign ?? "";
                _cid = e.Cid ?? "";
                Enqueue("connected", "callsign", e.Callsign, "cid", e.Cid, "type_code", e.TypeCode,
                        "selcal", e.SelcalCode, "observer", e.ObserverMode);
            };
            broker.NetworkDisconnected += (s, e) =>
            {
                _connected = false;
                _controllers.Clear();
                _controllersDirty = true;
                Enqueue("disconnected");
            };
            broker.PrivateMessageReceived += (s, e) => Enqueue("pm", "from", e.From, "message", e.Message);
            broker.RadioMessageReceived += (s, e) =>
                Enqueue("radio", "from", e.From, "message", e.Message, "frequencies", FormatFrequencies(e.Frequencies));
            broker.BroadcastMessageReceived += (s, e) => Enqueue("broadcast", "from", e.From, "message", e.Message);
            broker.SelcalAlertReceived += (s, e) =>
                Enqueue("selcal", "from", e.From, "frequencies", FormatFrequencies(e.Frequencies));
            broker.AtisReceived += (s, e) =>
                Enqueue("atis", "from", e.From, "lines", e.Lines == null ? new string[0] : e.Lines.ToArray());
            broker.MetarReceived += (s, e) => Enqueue("metar", "metar", e.Metar);

            broker.ControllerAdded += (s, e) =>
            {
                _controllers[e.Callsign] = new Controller { Callsign = e.Callsign, Frequency = e.Frequency, Lat = e.Latitude, Lon = e.Longitude };
                _controllersDirty = true;
            };
            broker.ControllerDeleted += (s, e) => { _controllers.TryRemove(e.Callsign, out _); _controllersDirty = true; };
            broker.ControllerFrequencyChanged += (s, e) =>
            {
                if (_controllers.TryGetValue(e.Callsign, out var c)) { c.Frequency = e.NewFrequency; _controllersDirty = true; }
            };
            broker.ControllerLocationChanged += (s, e) =>
            {
                if (_controllers.TryGetValue(e.Callsign, out var c)) { c.Lat = e.NewLatitude; c.Lon = e.NewLongitude; _controllersDirty = true; }
            };

            StartThread(SendEventsLoop, "Clearway events");
            StartThread(PollOutboxLoop, "Clearway outbox");
            broker.PostDebugMessage("Clearway plugin loaded. Messages are shared with Clearway on " + _api);
        }

        // ------------------------------------------------------------------ helpers

        private static string ReadPort()
        {
            var env = Environment.GetEnvironmentVariable("CLEARWAY_PORT");   // for development/testing
            if (!string.IsNullOrEmpty(env)) return env;
            try
            {
                var path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Clearway", "config.json");
                if (File.Exists(path))
                {
                    var m = Regex.Match(File.ReadAllText(path), "\"port\"\\s*:\\s*(\\d+)");
                    if (m.Success) return m.Groups[1].Value;
                }
            }
            catch { /* fall back to the default */ }
            return "8787";
        }

        private static string FormatFrequency(int f)
        {
            // vPilot drops the leading 1 and the dot: 23725 -> 123.725
            var s = (100000 + f).ToString();
            return s.Substring(0, 3) + "." + s.Substring(3);
        }

        private static string FormatFrequencies(int[] freqs)
        {
            return freqs == null ? "" : string.Join(" ", freqs.Select(FormatFrequency));
        }

        private static void StartThread(ThreadStart body, string name)
        {
            new Thread(body) { IsBackground = true, Name = name }.Start();
        }

        private void Enqueue(string type, params object[] kv)
        {
            var evt = new Dictionary<string, object> { ["type"] = type };
            for (int i = 0; i + 1 < kv.Length; i += 2) evt[(string)kv[i]] = kv[i + 1] ?? "";
            _events.TryAdd(evt);   // drops events if Clearway has been unreachable for a long time
        }

        private string Http(string method, string url, string body, int timeoutMs = 3000)
        {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Method = method;
            req.Timeout = timeoutMs;
            req.ReadWriteTimeout = timeoutMs;
            req.Proxy = null;
            req.KeepAlive = false;   // Clearway closes connections after each reply; never reuse a stale one
            req.UserAgent = "Clearway-vPilot/0.4";
            if (body != null)
            {
                var bytes = Encoding.UTF8.GetBytes(body);
                req.ContentType = "application/json";
                req.ContentLength = bytes.Length;
                using (var s = req.GetRequestStream()) s.Write(bytes, 0, bytes.Length);
            }
            using (var resp = (HttpWebResponse)req.GetResponse())
            using (var reader = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                return reader.ReadToEnd();
        }

        private void SetReachable(bool ok)
        {
            if (ok == _companionReachable) return;
            _companionReachable = ok;
            if (ok) _controllersDirty = true;   // Clearway (re)started: send it the controller list again
            Post(ok ? "Clearway connected." : "Clearway isn't running, so messages won't reach your phone or panel until it's started.");
        }

        private void Post(string text) { OnUi(() => _broker.PostDebugMessage(text)); }

        private void OnUi(Action action)
        {
            if (_ui != null) _ui.Send(_ => action(), null);
            else action();
        }

        private static string Str(Dictionary<string, object> d, string key)
        {
            return d.ContainsKey(key) && d[key] != null ? d[key].ToString() : "";
        }

        // ------------------------------------------------------------------ loops

        private void SendEventsLoop()
        {
            while (true)
            {
                if (_events.TryTake(out var evt, 1000))
                {
                    for (int attempt = 0; attempt < 3; attempt++)
                    {
                        try { Http("POST", _api + "event", _json.Serialize(evt)); SetReachable(true); break; }
                        catch (Exception) { SetReachable(false); Thread.Sleep(2000); }
                    }
                }
                if (_controllersDirty && _companionReachable)
                {
                    _controllersDirty = false;
                    var list = _controllers.Values.Select(c => new Dictionary<string, object>
                    {
                        ["callsign"] = c.Callsign, ["frequency"] = FormatFrequency(c.Frequency), ["lat"] = c.Lat, ["lon"] = c.Lon
                    }).ToArray();
                    try { Http("POST", _api + "event", _json.Serialize(new Dictionary<string, object> { ["type"] = "controllers", ["list"] = list })); }
                    catch (Exception) { _controllersDirty = true; }
                }
            }
        }

        private void PollOutboxLoop()
        {
            while (true)
            {
                // Clearway holds this request open until it has a command (or ~4 s pass),
                // so commands arrive instantly without hammering it with polls.
                Thread.Sleep(50);
                string text;
                try
                {
                    var url = _api + "outbox?connected=" + (_connected ? "1" : "0") +
                              "&callsign=" + Uri.EscapeDataString(_callsign) + "&cid=" + Uri.EscapeDataString(_cid);
                    text = Http("GET", url, null, 10000);
                    SetReachable(true);
                }
                catch (Exception)
                {
                    // one quick retry before treating Clearway as gone
                    if (_outboxFailures++ > 0) { SetReachable(false); Thread.Sleep(2000); }
                    continue;
                }
                _outboxFailures = 0;

                Dictionary<string, object> data;
                try { data = _json.Deserialize<Dictionary<string, object>>(text); }
                catch { continue; }
                // JavaScriptSerializer returns JSON arrays as ArrayList
                if (data == null || !data.ContainsKey("items") || !(data["items"] is System.Collections.IEnumerable items)) continue;

                foreach (var raw in items)
                {
                    if (!(raw is Dictionary<string, object> item)) continue;
                    var id = Convert.ToInt32(item["id"]);
                    string error = null;
                    try { Execute(item); }
                    catch (NotConnectedException) { error = "vPilot isn't connected to the network."; }
                    catch (NotTransmittingException) { error = "No COM radio is set to transmit."; }
                    catch (AlreadyConnectedException) { error = "vPilot is already connected."; }
                    catch (SimNotReadyException) { error = "The simulator isn't ready yet."; }
                    catch (Exception ex) { error = ex.Message; }

                    try
                    {
                        Http("POST", _api + "sent", _json.Serialize(new Dictionary<string, object>
                        {
                            ["id"] = id, ["ok"] = error == null, ["error"] = error ?? ""
                        }));
                    }
                    catch { /* Clearway will mark it failed after a timeout */ }
                }
            }
        }

        private void Execute(Dictionary<string, object> item)
        {
            var kind = Str(item, "type");
            switch (kind)
            {
                case "radio": { var m = Str(item, "text"); OnUi(() => _broker.SendRadioMessage(m)); break; }
                case "pm": { var to = Str(item, "to"); var m = Str(item, "text"); OnUi(() => _broker.SendPrivateMessage(to, m)); break; }
                case "connect":
                {
                    var cs = Str(item, "callsign"); var type = Str(item, "type_code"); var selcal = Str(item, "selcal");
                    OnUi(() => _broker.RequestConnect(cs, type, selcal));
                    break;
                }
                case "disconnect": OnUi(() => _broker.RequestDisconnect()); break;
                case "modec": { var on = Str(item, "on") == "True" || Str(item, "on") == "true"; OnUi(() => _broker.SetModeC(on)); break; }
                case "ident": OnUi(() => _broker.SquawkIdent()); break;
                case "atis": { var cs = Str(item, "callsign"); OnUi(() => _broker.RequestAtis(cs)); break; }
                case "metar": { var st = Str(item, "station"); OnUi(() => _broker.RequestMetar(st)); break; }
                default: throw new InvalidOperationException("Unknown command " + kind);
            }
        }
    }
}
