// Fake vPilot for testing the Clearway plugin without the real vPilot or network.
// Loads Clearway.vPilot.dll exactly like vPilot does, fires the same events (connect, nearby
// controllers, private/frequency/broadcast messages, SELCAL) and answers the plugin's requests
// (connect, disconnect, Mode C, ident, ATIS, METAR, private and frequency messages).
//
// Build:  dotnet build tools/fake-vpilot -c Release      (needs vPilot installed for its plugin interface)
// Run:    set CLEARWAY_PORT=8797  (point the plugin at a test Clearway, e.g. tools/dev_run.py)
//         FakeVpilot.exe path\to\Clearway.vPilot.dll [seconds]

using System;
using System.Collections.Generic;
using System.Threading;
using RossCarlson.Vatsim.Vpilot.Plugins;
using RossCarlson.Vatsim.Vpilot.Plugins.Events;
using RossCarlson.Vatsim.Vpilot.Plugins.Exceptions;

class FakeBroker : IBroker
{
    public event EventHandler SessionEnded;
    public event EventHandler<NetworkConnectedEventArgs> NetworkConnected;
    public event EventHandler NetworkDisconnected;
    public event EventHandler<PrivateMessageReceivedEventArgs> PrivateMessageReceived;
    public event EventHandler<RadioMessageReceivedEventArgs> RadioMessageReceived;
    public event EventHandler<BroadcastMessageReceivedEventArgs> BroadcastMessageReceived;
    public event EventHandler<MetarReceivedEventArgs> MetarReceived;
    public event EventHandler<AtisReceivedEventArgs> AtisReceived;
    public event EventHandler<ControllerAddedEventArgs> ControllerAdded;
    public event EventHandler<ControllerDeletedEventArgs> ControllerDeleted;
    public event EventHandler<ControllerFrequencyChangedEventArgs> ControllerFrequencyChanged;
    public event EventHandler<ControllerLocationChangedEventArgs> ControllerLocationChanged;
    public event EventHandler<SelcalAlertReceivedEventArgs> SelcalAlertReceived;
    public event EventHandler<AircraftAddedEventArgs> AircraftAdded;
    public event EventHandler<AircraftUpdatedEventArgs> AircraftUpdated;
    public event EventHandler<AircraftDeletedEventArgs> AircraftDeleted;

    static void Log(string s) { Console.WriteLine("BROKER " + s); }

    public void RequestConnect(string callsign, string type, string selcal)
    {
        Log("CONNECT " + callsign + " " + type + " " + selcal);
        new Thread(() => { Thread.Sleep(500); Connect(callsign, type, selcal); }).Start();
    }
    public void RequestConnectAsObserver(string c) { }
    public void RequestDisconnect() { Log("DISCONNECT"); NetworkDisconnected?.Invoke(this, EventArgs.Empty); }
    public void RequestMetar(string s) { Log("METAR " + s); MetarReceived?.Invoke(this, new MetarReceivedEventArgs(s + " 151450Z 24012KT 9999 FEW030 12/06 Q1018")); }
    public void RequestAtis(string c)
    {
        Log("ATIS " + c);
        AtisReceived?.Invoke(this, new AtisReceivedEventArgs(c, new List<string> { c + " - London Heathrow", "Information C, runways 27L/27R in use", "Charts at chartfox.org" }));
    }
    public void SendPrivateMessage(string to, string m) { Log("PM " + to + ": " + m); }
    public void SendRadioMessage(string m)
    {
        if (m.Contains("FAIL")) throw new NotTransmittingException();
        Log("RADIO: " + m);
    }
    public void PostDebugMessage(string m) { Console.WriteLine("[vPilot debug] " + m); }
    public void SetModeC(bool m) { Log("MODEC " + m); }
    public void SquawkIdent() { Log("IDENT"); }
    public void SetPtt(bool p) { }

    public void Connect(string callsign, string type, string selcal)
    {
        NetworkConnected?.Invoke(this, new NetworkConnectedEventArgs("1234567", callsign, type, selcal, false));
        ControllerAdded?.Invoke(this, new ControllerAddedEventArgs("EGLL_TWR", 18500, 51.47, -0.46));
        ControllerAdded?.Invoke(this, new ControllerAddedEventArgs("EGLL_N_APP", 19725, 51.47, -0.46));
        ControllerAdded?.Invoke(this, new ControllerAddedEventArgs("LON_S_CTR", 29425, 51.15, -0.18));
    }

    public void StartupTraffic()
    {
        PrivateMessageReceived?.Invoke(this, new PrivateMessageReceivedEventArgs("EGLL_TWR", "Hello BAW117, contact me on 118.5 when ready"));
        RadioMessageReceived?.Invoke(this, new RadioMessageReceivedEventArgs(new[] { 18500 }, "EGLL_TWR", "BAW117 cleared to land 27L"));
        RadioMessageReceived?.Invoke(this, new RadioMessageReceivedEventArgs(new[] { 18500 }, "EGLL_TWR", "AFR123 line up 27R"));
        BroadcastMessageReceived?.Invoke(this, new BroadcastMessageReceivedEventArgs("SUP", "Network maintenance at 0300z"));
        SelcalAlertReceived?.Invoke(this, new SelcalAlertReceivedEventArgs(new[] { 28500 }, "EGGX_FSS"));
    }
}

static class Program
{
    static void Main(string[] args)
    {
        if (args.Length < 1) { Console.WriteLine("Usage: FakeVpilot.exe path\\to\\Clearway.vPilot.dll [seconds]"); return; }
        var broker = new FakeBroker();
        IPlugin plugin = null;
        foreach (var t in System.Reflection.Assembly.LoadFrom(args[0]).GetTypes())
            if (typeof(IPlugin).IsAssignableFrom(t) && !t.IsAbstract) plugin = (IPlugin)Activator.CreateInstance(t);
        Console.WriteLine("Loaded plugin: " + plugin.Name);
        plugin.Initialize(broker);
        broker.Connect("BAW117", "B77W", "ABCD");
        Thread.Sleep(300);
        broker.StartupTraffic();
        Console.WriteLine("Fake vPilot running.");
        Thread.Sleep(1000 * int.Parse(args.Length > 1 ? args[1] : "600"));
    }
}
