/* Clearway web app: phone + desktop UI for the local companion. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const REASONS = [
    ["", "No reason"],
    ["DUE TO WEATHER", "Due to weather"],
    ["DUE TO AIRCRAFT PERFORMANCE", "Due to performance"],
    ["DUE TO TURBULENCE", "Due to turbulence"],
  ];

  // ---------- pairing key (from ?k= in the QR link) ----------
  let key = "";
  try { key = localStorage.getItem("clearway.key") || ""; } catch (e) {}
  const params = new URLSearchParams(location.search);
  // The key stays in the address on purpose: an iPhone home-screen app keeps its own
  // storage, so "Add to Home Screen" must save the link including ?k=.
  if (params.get("k")) {
    key = params.get("k");
    try { localStorage.setItem("clearway.key", key); } catch (e) {}
  } else if (key && !["localhost", "127.0.0.1"].includes(location.hostname)) {
    history.replaceState(null, "", `${location.pathname}?k=${encodeURIComponent(key)}${location.hash}`);
  }

  let state = null;
  let version = 0;
  let firstLoad = true;
  let knownIds = new Set();
  let settingsDirty = false;

  // ---------- API ----------
  async function api(path, body) {
    const res = await fetch("/api/" + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Clearway-Key": key },
      body: JSON.stringify(body || {}),
    });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401) { $("pairBanner").hidden = false; throw new Error("This device isn't paired."); }
    if (!res.ok || data.ok === false) throw new Error(data.error || "Request failed");
    poll(true);
    return data;
  }

  async function act(path, body, okText) {
    try {
      await api(path, body);
      if (okText) toast(okText);
      return true;
    } catch (e) {
      toast(e.message, true);
      return false;
    }
  }

  async function poll(force) {
    try {
      const res = await fetch(`/api/state?since=${force ? 0 : version}`, { headers: { "X-Clearway-Key": key }, cache: "no-store" });
      if (res.status === 401) { $("pairBanner").hidden = false; return; }
      $("pairBanner").hidden = true;
      const data = await res.json();
      if (data.unchanged) return;
      version = data.version;
      state = data;
      render();
    } catch (e) {
      setDot("error");
      $("sub").textContent = "Companion not reachable";
    }
  }

  // ---------- helpers ----------
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const utc = (ms) => { const d = new Date(ms); return String(d.getUTCHours()).padStart(2, "0") + String(d.getUTCMinutes()).padStart(2, "0") + "z"; };
  // Hoppie marks variable fields with @…@; show them as soft highlights.
  const fmt = (t) => esc(t).replace(/@([^@\n]*)@/g, (_, v) => v.trim() ? `<span class="var">${v}</span>` : "").replace(/@/g, "\n");

  function toast(text, err) {
    const t = $("toast");
    t.textContent = text;
    t.className = "toast" + (err ? " err" : "");
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => (t.hidden = true), 2800);
  }
  function setDot(s) { $("statusDot").className = "dot " + s; }

  // ---------- rendering ----------
  function render() {
    const s = state;
    setDot(s.status === "online" && s.error ? "connecting" : s.status);
    const route = s.flight && s.flight.departure ? ` · ${s.flight.departure}→${s.flight.arrival}` : "";
    $("sub").textContent = s.status === "online" ? s.callsign + route : s.status === "connecting" ? "Connecting…" : "Not connected";

    const pill = $("unitPill");
    if (s.current_unit) { pill.hidden = false; pill.className = "pill"; pill.textContent = s.current_unit; }
    else if (s.pending_logon) { pill.hidden = false; pill.className = "pill pending"; pill.textContent = s.pending_logon + "…"; }
    else pill.hidden = true;

    $("badge").hidden = !s.unacked;
    $("badge").textContent = s.unacked;
    document.title = s.unacked ? `(${s.unacked}) Clearway` : "Clearway";

    renderMessages();
    renderRequests();
    renderSettings();
    firstLoad = false;
  }

  function renderMessages() {
    const list = $("messageList");
    const msgs = state.messages.slice().reverse();
    $("emptyState").hidden = msgs.length > 0;
    $("emptyHint").textContent = state.status === "online"
      ? (state.current_unit ? `Logged on to ${state.current_unit}. Messages will appear here.` : "Connected. Log on to an ATC station from Requests.")
      : "Connect in Settings, then log on to an ATC station from Requests.";

    list.innerHTML = msgs.map((m) => {
      if (m.dir === "sys") return `<div class="sys">${esc(m.text)} · ${utc(m.ts)}</div>`;
      const unread = m.dir === "in" && !m.acked;
      const label = m.kind === "cpdlc" ? "CPDLC" : m.kind === "telex" ? "Telex" : "Info";
      const arrow = m.dir === "out" ? "To" : "From";
      let foot = "";
      if (m.options.length || (m.dir === "in" && m.status !== "closed" && (m.kind === "cpdlc" || m.kind === "telex"))) {
        foot += m.options.map((o) => `<button class="reply ${o}" data-reply="${o}" data-id="${m.id}">${o}</button>`).join("");
        if (m.kind === "cpdlc" && (m.status === "open" || m.status === "standby")) foot += `<button class="reply" data-free="${m.id}">Free text</button>`;
        if (m.kind === "telex") foot += `<button class="reply" data-free="${m.id}">Reply</button>`;
      }
      if (unread && !m.options.length) foot += `<button class="reply" data-ack="${m.id}">Got it</button>`;
      let st = "";
      if (m.dir === "in" && m.reply) st = `Answered <b>${esc(m.reply)}</b>`;
      if (m.dir === "in" && m.status === "standby") st = `<b>STANDBY</b> sent, answer when ready`;
      if (m.dir === "out" && m.status === "awaiting") st = "Awaiting reply…";
      if (m.dir === "out" && m.status === "answered") st = `ATC replied <b>${esc(m.reply.replace(/@/g, ""))}</b>`;
      if (m.dir === "out" && m.status === "failed") st = `<span style="color:var(--rose)">Not delivered</span>`;
      return `<article class="msg ${m.dir} ${unread ? "unread" : ""}" id="m${m.id}" data-msg="${m.id}">
        <div class="msg-head"><span class="chip ${m.kind}">${label}</span><span>${arrow}</span><span class="msg-station">${esc(m.station)}</span><span class="msg-time">${utc(m.ts)}</span></div>
        <div class="msg-text">${fmt(m.text)}</div>
        ${st || foot ? `<div class="msg-foot">${st ? `<span class="state">${st}</span>` : ""}${foot}</div>` : ""}
      </article>`;
    }).join("");

    // flash newly arrived inbound messages
    const ids = new Set(state.messages.map((m) => m.id));
    if (!firstLoad) {
      state.messages.filter((m) => m.dir === "in" && !knownIds.has(m.id)).forEach((m) => {
        const el = $("m" + m.id); if (el) el.classList.add("flash");
      });
    }
    knownIds = ids;

    if (firstLoad && location.hash.startsWith("#m")) {
      const el = document.querySelector(location.hash);
      if (el) { el.scrollIntoView({ block: "center" }); el.classList.add("flash"); }
    }
  }

  function renderRequests() {
    const s = state;
    $("logonNote").textContent = s.current_unit ? `On ${s.current_unit}` : s.pending_logon ? `Pending ${s.pending_logon}` : "Not logged on";
    $("logoffBtn").hidden = !(s.current_unit || s.pending_logon);
    const f = s.flight || {};
    const fill = (id, v) => { const el = $(id); if (el && !el.value && v) el.value = v; };
    fill("pdcType", f.aircraft); fill("pdcDep", f.departure); fill("pdcArr", f.arrival); fill("pdcStation", f.departure);
    fill("ocnLevel", (f.cruise || "").replace(/^FL/i, "").slice(0, 3));
  }

  function applyTheme(theme) {
    const light = theme === "light";
    if (light) document.documentElement.dataset.theme = "light";
    else delete document.documentElement.dataset.theme;
    $("themeColor").content = light ? "#f5f6fa" : "#0e1117";
    try { localStorage.setItem("clearway.theme", light ? "light" : "dark"); } catch (e) {}
  }

  function renderSettings() {
    const s = state, st = s.settings;
    applyTheme(st.theme);
    $("setLight").checked = st.theme === "light";
    const titles = { offline: "Offline", connecting: "Connecting…", online: "Connected", error: "Couldn't connect" };
    $("statusTitle").textContent = titles[s.status] + (s.status === "online" ? ` as ${s.callsign}` : "");
    let detail = s.error || "Enter your details below, then connect.";
    if (s.status === "online" && !s.error) {
      const next = Math.max(0, Math.round((s.next_poll - Date.now()) / 1000));
      detail = `Checking Hoppie for messages · next check in ${next}s`;
      if (s.contracts.length) detail += ` · ADS-C: ${s.contracts.map((c) => c.station).join(", ")}`;
    }
    $("statusDetail").textContent = detail;
    const btn = $("connectBtn");
    const on = s.status === "online" || s.status === "connecting";
    btn.textContent = on ? "Disconnect" : "Connect";
    btn.classList.toggle("danger", on);

    if (!settingsDirty) {
      $("setLogon").placeholder = st.hoppie_logon_set ? `Saved (${st.hoppie_logon_hint})` : "From hoppie.nl/acars";
      $("setCid").value = st.vatsim_cid || "";
      $("setCallsign").value = st.callsign_override || "";
    }
    $("setNtfy").checked = st.ntfy_enabled;
    $("setMute").checked = st.mute_phone_when_panel_open;
    $("setAdsc").checked = st.adsc_enabled;
    $("setBrowser").checked = st.open_browser_on_start;
    $("topic").textContent = st.ntfy_topic;
    $("panelState").textContent = s.panel_active ? "(panel open now)" : "";

    const isLocal = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    $("pairCard").hidden = !isLocal || !s.base_url;
    if (isLocal && s.base_url && typeof qrcode === "function") {
      // The pairing key only exists on the PC; ask the local API for it via the settings snapshot.
      renderPairQr(s.base_url);
    }
  }

  let lastQr = "";
  async function renderPairQr(base) {
    if (!renderPairQr.key) {
      try { const r = await fetch("/api/pair", { method: "POST" }); const d = await r.json(); renderPairQr.key = d.key; } catch (e) { return; }
    }
    const url = `${base}/?k=${renderPairQr.key}`;
    if (url === lastQr) return;
    lastQr = url;
    const qr = qrcode(0, "M");
    qr.addData(url); qr.make();
    $("pairQr").innerHTML = qr.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
    $("pairUrl").textContent = url;
  }

  // ---------- events ----------
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === t));
    document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "view-" + t.dataset.view));
    window.scrollTo({ top: 0 });
  }));

  $("messageList").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b && b.dataset.reply) return act("reply", { id: +b.dataset.id, text: b.dataset.reply }, `${b.dataset.reply} sent`);
    if (b && b.dataset.free) return openSheet(+b.dataset.free);
    if (b && b.dataset.ack) return act("ack", { id: +b.dataset.ack });
    const card = e.target.closest(".msg.unread");
    if (card && !b) {
      const m = state.messages.find((x) => x.id === +card.dataset.msg);
      if (m && !m.options.length) act("ack", { id: m.id });
    }
  });
  $("ackAll").onclick = () => act("ack", {});
  $("clearBtn").onclick = () => { if (confirm("Clear the message history? Messages still waiting for an answer are kept.")) act("clear"); };

  // reply sheet
  let sheetId = null;
  function openSheet(id) {
    const m = state.messages.find((x) => x.id === id);
    if (!m) return;
    sheetId = id;
    $("sheetTitle").textContent = `Reply to ${m.station}`;
    $("sheetQuote").textContent = m.text.replace(/@/g, "");
    $("sheetText").value = "";
    $("sheet").hidden = false;
    setTimeout(() => $("sheetText").focus(), 50);
  }
  $("sheetClose").onclick = () => ($("sheet").hidden = true);
  $("sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") $("sheet").hidden = true; });
  $("sheetSend").onclick = async () => {
    const text = $("sheetText").value.trim();
    if (!text) return;
    if (await act("reply", { id: sheetId, text }, "Reply sent")) $("sheet").hidden = true;
  };

  // segmented controls
  document.querySelectorAll(".seg").forEach((seg) => seg.addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    seg.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    if (seg.id === "speedUnit") $("reqSpeed").placeholder = b.dataset.v === "M" ? ".84" : "280";
  }));
  const segVal = (id) => document.querySelector(`#${id} .on`).dataset.v;

  ["reqLevelReason", "reqDirectReason", "reqSpeedReason"].forEach((id) => {
    $(id).innerHTML = REASONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
  });
  $("wcw").onchange = () => { $("wcwValue").hidden = !$("wcw").value.endsWith("FL"); };

  const val = (id) => $(id).value.trim().toUpperCase();
  const withReason = (text, id) => (val(id) ? `${text} ${val(id)}` : text);

  const senders = {
    level: () => { const fl = val("reqLevel").replace(/\D/g, ""); if (!fl) throw new Error("Enter a flight level."); return ["cpdlc", { text: withReason(`REQUEST FL${fl}`, "reqLevelReason") }]; },
    direct: () => { const fix = val("reqDirect"); if (!fix) throw new Error("Enter a waypoint."); return ["cpdlc", { text: withReason(`REQUEST DIRECT TO ${fix}`, "reqDirectReason") }]; },
    speed: () => {
      let v = val("reqSpeed").replace(/[^\d.]/g, ""); if (!v) throw new Error("Enter a speed.");
      const spd = segVal("speedUnit") === "M" ? "M" + v.replace(/^0?\./, "").replace(/^\./, "") : v + "KT";
      return ["cpdlc", { text: withReason(`REQUEST ${spd}`, "reqSpeedReason") }];
    },
    wcw: () => {
      let w = $("wcw").value;
      if (w.endsWith("FL")) { const fl = val("wcwValue").replace(/\D/g, ""); if (!fl) throw new Error("Enter a flight level."); w += fl; }
      return ["cpdlc", { text: `WHEN CAN WE EXPECT ${w}` }];
    },
    free: () => { const t = val("cpdlcText"); if (!t) throw new Error("Type a message."); return ["cpdlc", { text: t, ra: "Y" }]; },
    pdc: () => {
      const need = ["pdcStation", "pdcType", "pdcDep", "pdcArr", "pdcStand", "pdcAtis"];
      if (need.some((id) => !val(id))) throw new Error("Fill in all clearance fields.");
      return ["telex", { station: val("pdcStation"), text: `REQUEST PREDEP CLEARANCE ${state.callsign} ${val("pdcType")} TO ${val("pdcArr")} AT ${val("pdcDep")} STAND ${val("pdcStand")} ATIS ${val("pdcAtis")}` }];
    },
    oceanic: () => {
      const need = ["ocnStation", "ocnEntry", "ocnTime", "ocnMach", "ocnLevel"];
      if (need.some((id) => !val(id))) throw new Error("Fill in station, entry point, time, Mach and level.");
      const rmk = val("ocnRmk") || "NIL";
      return ["telex", { station: val("ocnStation"), text: `OCEANIC CLEARANCE REQUEST CALLSIGN: ${state.callsign} ENTRY POINT: ${val("ocnEntry")} AT: ${val("ocnTime")} REQ: M.${val("ocnMach").replace(/\D/g, "")} FL${val("ocnLevel").replace(/\D/g, "")} RMKS: ${rmk}` }];
    },
    telex: () => { if (!val("telexStation") || !val("telexText")) throw new Error("Enter a station and a message."); return ["telex", { station: val("telexStation"), text: val("telexText") }]; },
    wx: () => { if (val("wxIcao").length !== 4) throw new Error("Enter a 4-letter ICAO code."); return ["inforeq", { what: segVal("wxKind"), icao: val("wxIcao") }]; },
  };

  document.querySelectorAll("[data-send]").forEach((b) => b.addEventListener("click", async () => {
    let call;
    try { call = senders[b.dataset.send](); } catch (e) { return toast(e.message, true); }
    b.disabled = true;
    const ok = await act(call[0], call[1], "Sent");
    b.disabled = false;
    if (ok && ["free", "telex"].includes(b.dataset.send)) { $("cpdlcText").value = ""; $("telexText").value = ""; }
  }));

  $("logonBtn").onclick = () => { const st = val("logonStation"); if (!st) return toast("Enter a station.", true); act("logon", { station: st }, `Logon request sent to ${st}`); };
  $("logoffBtn").onclick = () => act("logoff", {}, "Logged off");

  $("connectBtn").onclick = () => {
    const on = state && (state.status === "online" || state.status === "connecting");
    act(on ? "disconnect" : "connect");
  };

  ["setLogon", "setCid", "setCallsign"].forEach((id) => $(id).addEventListener("input", () => (settingsDirty = true)));
  $("saveSettings").onclick = async () => {
    const ok = await act("settings", { hoppie_logon: $("setLogon").value.trim(), vatsim_cid: $("setCid").value.trim(), callsign_override: $("setCallsign").value.trim() }, "Saved");
    if (ok) { settingsDirty = false; $("setLogon").value = ""; }
  };
  const toggles = { setNtfy: "ntfy_enabled", setMute: "mute_phone_when_panel_open", setAdsc: "adsc_enabled", setBrowser: "open_browser_on_start" };
  Object.entries(toggles).forEach(([id, k]) => $(id).addEventListener("change", (e) => act("settings", { [k]: e.target.checked })));
  $("setLight").addEventListener("change", (e) => { applyTheme(e.target.checked ? "light" : "dark"); act("settings", { theme: e.target.checked ? "light" : "dark" }); });

  $("copyTopic").onclick = async () => {
    try { await navigator.clipboard.writeText(state.settings.ntfy_topic); toast("Topic copied"); }
    catch (e) { toast("Select the topic and copy it manually", true); }
  };
  $("testNotif").onclick = () => act("test-notification", {}, "Test sent. Check your phone.");
  $("newTopic").onclick = () => { if (confirm("Create a new topic? You'll need to subscribe to it again in the ntfy app.")) act("new-topic", {}, "New topic created"); };

  // ---------- loop ----------
  poll(true);
  setInterval(() => poll(false), 1500);
  // refresh countdown text once per second without a network call
  setInterval(() => { if (state && state.status === "online") renderSettings(); }, 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(true); });
})();
