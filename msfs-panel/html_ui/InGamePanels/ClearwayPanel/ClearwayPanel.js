/* Clearway MSFS toolbar panel.
   Talks to the Clearway companion on this PC (http://localhost:8787).
   Written in plain ES2015 for the sim's Coherent GT browser; also runs in a normal browser for testing. */
(function () {
  "use strict";

  var API = "http://localhost:8787";
  var POLL_MS = 2000;
  var POSITION_MS = 10000;

  var el = function (id) { return document.getElementById(id); };
  var state = null;
  var version = 0;
  var lastUnacked = 0;
  var reachable = true;
  var expanded = false;
  var reqOpen = false;
  var reqKind = "logon";
  var wxKind = "metar";
  var started = false;

  // ------------------------------------------------------------ storage (sim or browser)
  function load(key, fallback) {
    try {
      var v = (typeof GetStoredData === "function") ? GetStoredData(key) : window.localStorage.getItem(key);
      return v ? JSON.parse(v) : fallback;
    } catch (e) { return fallback; }
  }
  function save(key, value) {
    try {
      var s = JSON.stringify(value);
      if (typeof SetStoredData === "function") SetStoredData(key, s); else window.localStorage.setItem(key, s);
    } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------ HTTP
  function request(method, path, body, done) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, API + path, true);
    xhr.timeout = 4000;
    // text/plain keeps this a "simple" request (no CORS preflight)
    if (body) xhr.setRequestHeader("Content-Type", "text/plain");
    xhr.onload = function () {
      var data = {};
      try { data = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
      if (done) done(xhr.status >= 200 && xhr.status < 300 && data.ok !== false, data);
    };
    xhr.onerror = xhr.ontimeout = function () { if (done) done(false, { error: "Clearway companion not reachable" }); };
    xhr.send(body ? JSON.stringify(body) : null);
  }

  function act(path, body, okHint) {
    request("POST", "/api/" + path, body || {}, function (ok, data) {
      hint(ok ? (okHint || "") : (data.error || "Failed"), !ok);
      poll(true);
    });
  }

  function poll(force) {
    request("GET", "/api/state?panel=1&since=" + (force ? 0 : version), null, function (ok, data) {
      if (!ok) {
        if (reachable) { reachable = false; render(); }
        return;
      }
      if (!reachable) { reachable = true; force = true; }
      if (data.unchanged) return;
      version = data.version;
      state = data;
      render();
    });
  }

  function sendPosition() {
    if (typeof SimVar === "undefined" || !reachable) return;
    try {
      var lat = SimVar.GetSimVarValue("PLANE LATITUDE", "degree latitude");
      var lon = SimVar.GetSimVarValue("PLANE LONGITUDE", "degree longitude");
      var alt = SimVar.GetSimVarValue("PLANE ALTITUDE", "feet");
      if (typeof lat === "number" && (lat !== 0 || lon !== 0)) {
        request("POST", "/api/position", { lat: lat, lon: lon, alt: alt }, null);
      }
    } catch (e) { /* sim not ready */ }
  }

  // ------------------------------------------------------------ helpers
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(t) {
    return esc(t).replace(/@([^@\n]*)@/g, function (_, v) { return v.trim() ? "<span class=\"cw-var\">" + v + "</span>" : ""; }).replace(/@/g, " ");
  }
  function utc(ms) {
    var d = new Date(ms);
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    return p(d.getUTCHours()) + p(d.getUTCMinutes()) + "z";
  }
  function findMsg(id) {
    if (!state) return null;
    for (var i = 0; i < state.messages.length; i++) if (state.messages[i].id === id) return state.messages[i];
    return null;
  }

  function hint(text, err) {
    var h = el("cw-hint");
    h.textContent = text || "";
    h.style.color = err ? "var(--rose)" : "var(--muted)";
  }

  // ------------------------------------------------------------ render
  function render() {
    if (state && state.settings) el("cw-root").classList.toggle("light", state.settings.theme === "light");
    var bubble = el("cw-bubble");
    var status = !reachable ? "offline" : (state ? state.status : "offline");
    var unacked = reachable && state ? state.unacked : 0;

    bubble.className = "";
    if (status === "online") bubble.classList.add("online");
    if (status === "error" || !reachable) bubble.classList.add("error");
    if (unacked > 0) bubble.classList.add("alert");
    if (unacked > lastUnacked) {
      // brief flash, then the amber "alert" colour stays until acknowledged
      bubble.classList.add("flash");
      setTimeout(function () { el("cw-bubble").classList.remove("flash"); }, 2900);
    }
    lastUnacked = unacked;
    el("cw-count").textContent = unacked > 9 ? "9+" : String(unacked);

    var dot = el("cw-dot");
    dot.className = "cw-dot " + (state && reachable ? (state.status === "online" && state.error ? "connecting" : state.status) : "");
    el("cw-callsign").textContent = state && state.callsign && reachable ? state.callsign : "Clearway";

    var unit = el("cw-unit");
    if (state && reachable && (state.current_unit || state.pending_logon)) {
      unit.classList.remove("hidden");
      unit.className = "cw-pill" + (state.current_unit ? "" : " pending");
      unit.textContent = state.current_unit || (state.pending_logon + "…");
    } else {
      unit.classList.add("hidden");
    }

    var notice = el("cw-notice");
    if (!reachable) {
      notice.innerHTML = "Start <b>Clearway</b> on this PC to use CPDLC.";
      notice.classList.remove("hidden");
    } else if (state && state.status !== "online") {
      notice.innerHTML = state.error ? esc(state.error) : "Not connected. Open Clearway's Settings and press <b>Connect</b>.";
      notice.classList.remove("hidden");
    } else {
      notice.classList.add("hidden");
    }

    updateSendLabel();
    renderList();
  }

  function renderList() {
    var list = el("cw-list");
    if (!state || !reachable) { list.innerHTML = ""; return; }
    var msgs = state.messages.slice(-30).reverse();
    if (!msgs.length) {
      list.innerHTML = "<div class=\"cw-empty\">No messages yet.</div>" + trashHtml();
      return;
    }
    var html = "";
    for (var i = 0; i < msgs.length; i++) {
      var m = msgs[i];
      if (m.dir === "sys") { html += "<div class=\"cw-sys\">" + esc(m.text) + " <span class=\"cw-del\" data-del=\"" + m.id + "\">&#215;</span></div>"; continue; }
      var unread = m.dir === "in" && !m.acked;
      var label = m.kind === "cpdlc" ? "CPDLC" : (m.kind === "telex" ? "TELEX" : "INFO");
      var actions = "";
      for (var j = 0; j < m.options.length; j++) {
        actions += "<div class=\"cw-btn " + m.options[j] + "\" data-reply=\"" + m.options[j] + "\" data-id=\"" + m.id + "\">" + m.options[j] + "</div>";
      }
      if (unread && !m.options.length) actions += "<div class=\"cw-btn\" data-ack=\"" + m.id + "\">Got it</div>";
      var st = "";
      if (m.dir === "in" && m.reply) st = "Answered " + esc(m.reply);
      if (m.dir === "in" && m.status === "standby") st = "STANDBY sent";
      if (m.dir === "out" && m.status === "awaiting") st = "Awaiting reply…";
      if (m.dir === "out" && m.status === "answered") st = "ATC: " + esc(String(m.reply).replace(/@/g, ""));
      if (m.dir === "out" && m.status === "failed") st = "Not delivered";
      html += "<div class=\"cw-msg " + m.dir + (unread ? " unread" : "") + (m.collapsed ? " collapsed" : "") + "\" data-msg=\"" + m.id + "\">" +
        "<div class=\"cw-bar\"></div>" +
        "<div class=\"cw-meta\"><span class=\"cw-chip " + m.kind + "\">" + label + "</span>" +
        "<span class=\"cw-station\">" + (m.dir === "out" ? "→ " : "") + esc(m.station) + "</span>" +
        "<span class=\"cw-time\">" + utc(m.ts) + "</span>" +
        "<span class=\"cw-fold\" data-fold=\"" + m.id + "\" title=\"" + (m.collapsed ? "Expand" : "Collapse") + "\"></span>" +
        "<span class=\"cw-del\" data-del=\"" + m.id + "\" title=\"Delete\">&#215;</span></div>" +
        "<div class=\"cw-text\">" + fmt(m.text) + "</div>" +
        (st ? "<div class=\"cw-state\">" + st + "</div>" : "") +
        (actions ? "<div class=\"cw-actions\">" + actions + "</div>" : "") +
        "</div>";
    }
    list.innerHTML = html + trashHtml();
  }

  // Messages deleted this session (kept by the companion until it quits).
  var trashOpen = false;
  function trashHtml() {
    var t = (state && state.trash) || [];
    if (!t.length) { trashOpen = false; return ""; }
    var html = "<div class=\"cw-trash-bar\"><span>" + t.length + " deleted</span>" +
      "<span class=\"cw-link\" data-trash-toggle=\"1\">" + (trashOpen ? "Hide" : "Show") + "</span></div>";
    if (trashOpen) {
      for (var i = 0; i < t.length && i < 15; i++) {
        var m = t[i];
        html += "<div class=\"cw-trash-row\"><span class=\"cw-trash-text\">" + esc((m.dir === "out" ? "→ " : "") + m.station + " · " + String(m.text).replace(/@/g, "")) +
          "</span><span class=\"cw-link\" data-restore=\"" + m.id + "\">Restore</span></div>";
      }
      html += "<div class=\"cw-trash-all\"><span class=\"cw-link\" data-restore-all=\"1\">Restore all</span></div>";
    }
    return html;
  }

  // ------------------------------------------------------------ layout: icon + card
  var scale = 1;
  function applyScale() {
    var h = window.innerHeight || 1080;
    scale = h / 1080;
    el("cw-root").style.fontSize = (14 * scale) + "px";
    var pos = load("CLEARWAY_POS", null);
    if (!pos) pos = { x: 0.03, y: 0.25 };
    placeBubble(pos.x * window.innerWidth, pos.y * window.innerHeight, false);
  }

  function placeBubble(x, y, persist) {
    var b = el("cw-bubble");
    var size = b.offsetWidth || 48;
    x = Math.max(4, Math.min(window.innerWidth - size - 4, x));
    y = Math.max(4, Math.min(window.innerHeight - size - 4, y));
    b.style.left = x + "px";
    b.style.top = y + "px";
    if (persist) save("CLEARWAY_POS", { x: x / window.innerWidth, y: y / window.innerHeight });
    placeCard();
  }

  function placeCard() {
    var b = el("cw-bubble"), c = el("cw-card");
    var bx = b.offsetLeft, by = b.offsetTop, bs = b.offsetWidth || 48;
    var cw = c.offsetWidth || 350, ch = c.offsetHeight || 300;
    var gap = 10 * scale;
    // open towards the middle of the screen
    var x = bx + bs / 2 < window.innerWidth / 2 ? bx + bs + gap : bx - cw - gap;
    var y = Math.max(4, Math.min(window.innerHeight - ch - 4, by));
    c.style.left = x + "px";
    c.style.top = y + "px";
  }

  function setExpanded(v) {
    expanded = v;
    el("cw-card").classList.toggle("hidden", !expanded);
    save("CLEARWAY_EXPANDED", expanded);
    if (expanded) { placeCard(); poll(true); }
  }

  // Drag the icon (or the card header) anywhere on screen.
  function makeDraggable(handle, onClick) {
    var startX, startY, originX, originY, moved;
    handle.addEventListener("mousedown", function (e) {
      if (e.button !== 0) return;
      if (e.target.closest && e.target.closest(".cw-icon-btn")) return;
      var b = el("cw-bubble");
      startX = e.clientX; startY = e.clientY;
      originX = b.offsetLeft; originY = b.offsetTop;
      moved = false;
      var cap = el("cw-capture");
      cap.classList.add("on");
      function move(ev) {
        var dx = ev.clientX - startX, dy = ev.clientY - startY;
        if (!moved && Math.abs(dx) + Math.abs(dy) < 5) return;
        moved = true;
        placeBubble(originX + dx, originY + dy, false);
      }
      function up() {
        cap.classList.remove("on");
        document.removeEventListener("mousemove", move);
        document.removeEventListener("mouseup", up);
        if (moved) placeBubble(el("cw-bubble").offsetLeft, el("cw-bubble").offsetTop, true);
        else if (onClick) onClick();
      }
      document.addEventListener("mousemove", move);
      document.addEventListener("mouseup", up);
      e.preventDefault();
    });
  }

  // ------------------------------------------------------------ text input (keep keys away from the sim)
  function wireInput(input) {
    input.addEventListener("focus", function () {
      if (typeof Coherent !== "undefined") Coherent.trigger("FOCUS_INPUT_FIELD", input.id, "", "", "", false);
    });
    input.addEventListener("blur", function () {
      if (typeof Coherent !== "undefined") Coherent.trigger("UNFOCUS_INPUT_FIELD", input.id);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.keyCode === 13) send();
      e.stopPropagation();
    });
  }

  // Request forms. Each field: k = key, ph = placeholder, half = takes half the width.
  var FORMS = {
    logon: [{ k: "station", ph: "ATC station, e.g. EGGX" }],
    level: [{ k: "fl", ph: "Flight level, e.g. 370" }],
    direct: [{ k: "fix", ph: "Waypoint" }],
    text: [{ k: "text", ph: "Free text to current ATC" }],
    pdc: [
      { k: "station", ph: "Station, e.g. EGLL", half: true }, { k: "type", ph: "Aircraft", half: true },
      { k: "dep", ph: "From", half: true }, { k: "arr", ph: "To", half: true },
      { k: "stand", ph: "Stand", half: true }, { k: "atis", ph: "ATIS letter", half: true }
    ],
    oceanic: [
      { k: "station", ph: "Station, e.g. EGGX", half: true }, { k: "entry", ph: "Entry point", half: true },
      { k: "eta", ph: "ETA UTC, e.g. 1430", half: true }, { k: "mach", ph: "Mach, e.g. 84", half: true },
      { k: "fl", ph: "FL, e.g. 370", half: true }, { k: "rmk", ph: "Remarks (optional)", half: true }
    ],
    telex: [{ k: "station", ph: "Station or callsign" }, { k: "text", ph: "Message" }],
    wx: [{ k: "icao", ph: "Airport ICAO, e.g. EGLL" }]
  };
  var formVals = {};

  function prefill(kind) {
    var f = (state && state.flight) || {};
    var v = formVals[kind] || (formVals[kind] = {});
    if (kind === "pdc") {
      if (!v.station && f.departure) v.station = f.departure;
      if (!v.type && f.aircraft) v.type = f.aircraft;
      if (!v.dep && f.departure) v.dep = f.departure;
      if (!v.arr && f.arrival) v.arr = f.arrival;
    }
    if (kind === "oceanic" && !v.fl && f.cruise) v.fl = String(f.cruise).replace(/^FL/i, "").slice(0, 3);
    return v;
  }

  function renderFields() {
    var vals = prefill(reqKind);
    var html = "";
    var fields = FORMS[reqKind];
    for (var i = 0; i < fields.length; i++) {
      var fd = fields[i];
      html += "<input id=\"cw-f-" + fd.k + "\" data-k=\"" + fd.k + "\" class=\"cw-input cw-field" + (fd.half ? " half" : "") +
        "\" type=\"text\" placeholder=\"" + fd.ph + "\" value=\"" + esc(vals[fd.k] || "") + "\"/>";
    }
    var box = el("cw-fields");
    box.innerHTML = html;
    var inputs = box.getElementsByTagName("input");
    for (var j = 0; j < inputs.length; j++) wireInput(inputs[j]);
    placeCard();
  }

  function setReqKind(v) {
    reqKind = v;
    ["cw-req-kind", "cw-req-kind2"].forEach(function (id) {
      var btns = el(id).children;
      for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("on", btns[i].getAttribute("data-v") === v);
    });
    el("cw-wx-kind").classList.toggle("hidden", v !== "wx");
    renderFields();
    updateSendLabel();
    hint("");
  }

  function updateSendLabel() {
    var logged = state && reachable && (state.current_unit || state.pending_logon);
    var label = { logon: logged ? "Log off" : "Log on", wx: "Get", pdc: "Request", oceanic: "Request" }[reqKind] || "Send";
    el("cw-send").textContent = label;
  }

  function field(k) {
    var input = el("cw-f-" + k);
    return input ? input.value.trim().toUpperCase() : "";
  }

  function send() {
    var cs = state ? state.callsign : "";
    var logged = state && (state.current_unit || state.pending_logon);
    var clear = [];
    if (reqKind === "logon") {
      var st = field("station");
      if (logged && !st) return act("logoff", {}, "Logged off");
      if (!st) return hint("Enter a station", true);
      act("logon", { station: st }, "Logon request sent to " + st);
    } else if (reqKind === "level") {
      var fl = field("fl").replace(/\D/g, "");
      if (!fl) return hint("Enter a flight level", true);
      act("cpdlc", { text: "REQUEST FL" + fl }, "Request sent");
    } else if (reqKind === "direct") {
      if (!field("fix")) return hint("Enter a waypoint", true);
      act("cpdlc", { text: "REQUEST DIRECT TO " + field("fix") }, "Request sent");
    } else if (reqKind === "text") {
      if (!field("text")) return hint("Type a message", true);
      act("cpdlc", { text: field("text"), ra: "Y" }, "Sent");
      clear = ["text"];
    } else if (reqKind === "pdc") {
      if (!field("station") || !field("type") || !field("dep") || !field("arr") || !field("stand") || !field("atis")) {
        return hint("Fill in all clearance fields", true);
      }
      act("telex", { station: field("station"), text: "REQUEST PREDEP CLEARANCE " + cs + " " + field("type") + " TO " + field("arr") +
        " AT " + field("dep") + " STAND " + field("stand") + " ATIS " + field("atis") }, "Clearance requested");
    } else if (reqKind === "oceanic") {
      if (!field("station") || !field("entry") || !field("eta") || !field("mach") || !field("fl")) {
        return hint("Fill in station, entry, ETA, Mach and FL", true);
      }
      act("telex", { station: field("station"), text: "OCEANIC CLEARANCE REQUEST CALLSIGN: " + cs + " ENTRY POINT: " + field("entry") +
        " AT: " + field("eta") + " REQ: M." + field("mach").replace(/\D/g, "") + " FL" + field("fl").replace(/\D/g, "") +
        " RMKS: " + (field("rmk") || "NIL") }, "Oceanic clearance requested");
    } else if (reqKind === "telex") {
      if (!field("station") || !field("text")) return hint("Enter a station and a message", true);
      act("telex", { station: field("station"), text: field("text") }, "Telex sent");
      clear = ["text"];
    } else if (reqKind === "wx") {
      if (field("icao").length !== 4) return hint("Enter a 4-letter ICAO", true);
      act("inforeq", { what: wxKind, icao: field("icao") }, "Requested");
    }
    for (var i = 0; i < clear.length; i++) {
      var input = el("cw-f-" + clear[i]);
      if (input) input.value = "";
      if (formVals[reqKind]) formVals[reqKind][clear[i]] = "";
    }
  }
  // ------------------------------------------------------------ start
  function start() {
    if (started) return;
    started = true;

    // MSFS 2024 adds classes that hide custom toolbar panels; remove them.
    var frame = document.querySelector("ingame-ui");
    if (frame && frame.classList) { frame.classList.remove("hide"); frame.classList.remove("panelInvisible"); }

    applyScale();
    window.addEventListener("resize", applyScale);

    makeDraggable(el("cw-bubble"), function () { setExpanded(!expanded); });
    makeDraggable(el("cw-head"), null);
    el("cw-min").addEventListener("click", function () { setExpanded(false); });

    el("cw-req-toggle").addEventListener("click", function () {
      reqOpen = !reqOpen;
      el("cw-req").classList.toggle("hidden", !reqOpen);
      el("cw-req-chev").classList.toggle("closed", !reqOpen);
      save("CLEARWAY_REQ_OPEN", reqOpen);
      placeCard();
    });
    ["cw-req-kind", "cw-req-kind2"].forEach(function (id) {
      el(id).addEventListener("click", function (e) {
        var v = e.target.getAttribute && e.target.getAttribute("data-v");
        if (v) setReqKind(v);
      });
    });
    // remember what was typed when switching between request types
    el("cw-fields").addEventListener("input", function (e) {
      var k = e.target.getAttribute && e.target.getAttribute("data-k");
      if (k) { (formVals[reqKind] || (formVals[reqKind] = {}))[k] = e.target.value; }
    });
    el("cw-clear").addEventListener("click", function () { act("clear", {}, ""); });
    el("cw-wx-kind").addEventListener("click", function (e) {
      var v = e.target.getAttribute && e.target.getAttribute("data-v");
      if (!v) return;
      wxKind = v;
      var btns = el("cw-wx-kind").children;
      for (var i = 0; i < btns.length; i++) btns[i].classList.toggle("on", btns[i] === e.target);
    });
    el("cw-send").addEventListener("click", send);

    el("cw-list").addEventListener("click", function (e) {
      var t = e.target;
      var r = t.getAttribute && t.getAttribute("data-reply");
      if (r) return act("reply", { id: +t.getAttribute("data-id"), text: r }, r + " sent");
      var a = t.getAttribute && t.getAttribute("data-ack");
      if (a) return act("ack", { id: +a });
      var d = t.getAttribute && t.getAttribute("data-del");
      if (d) return act("delete", { id: +d });
      var fo = t.getAttribute && t.getAttribute("data-fold");
      if (fo) {
        var fm = findMsg(+fo);
        return act("collapse", { id: +fo, collapsed: !(fm && fm.collapsed) });
      }
      if (t.getAttribute && t.getAttribute("data-trash-toggle")) { trashOpen = !trashOpen; renderList(); return placeCard(); }
      var rs = t.getAttribute && t.getAttribute("data-restore");
      if (rs) return act("restore", { id: +rs }, "");
      if (t.getAttribute && t.getAttribute("data-restore-all")) return act("restore", {}, "");
      var folded = t.closest ? t.closest(".cw-msg.collapsed") : null;
      if (folded) return act("collapse", { id: +folded.getAttribute("data-msg"), collapsed: false });
      var card = t.closest ? t.closest(".cw-msg.unread") : null;
      if (card && state) {
        var id = +card.getAttribute("data-msg");
        for (var i = 0; i < state.messages.length; i++) {
          if (state.messages[i].id === id && !state.messages[i].options.length) return act("ack", { id: id });
        }
      }
    });

    reqOpen = load("CLEARWAY_REQ_OPEN", false);
    el("cw-req").classList.toggle("hidden", !reqOpen);
    el("cw-req-chev").classList.toggle("closed", !reqOpen);
    setReqKind("logon");
    setExpanded(load("CLEARWAY_EXPANDED", false));

    render();
    poll(true);
    setInterval(function () { poll(false); }, POLL_MS);
    setInterval(sendPosition, POSITION_MS);
  }

  // Register as a toolbar panel inside the sim; plain start in a normal browser.
  if (typeof TemplateElement !== "undefined" && window.customElements) {
    class ClearwayPanel extends TemplateElement {
      connectedCallback() {
        super.connectedCallback();
        start();
      }
    }
    window.customElements.define("ingamepanel-clearway", ClearwayPanel);
    if (typeof checkAutoload === "function") checkAutoload();
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
