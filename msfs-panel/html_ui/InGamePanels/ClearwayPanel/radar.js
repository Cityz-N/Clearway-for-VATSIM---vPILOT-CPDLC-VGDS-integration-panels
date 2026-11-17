/* Clearway Radar: a minimal online-traffic radar, hosted by the Clearway MSFS panel (Radar tab, or its own
   detached window). Plain ES5 + canvas 2D (no map library) so it runs in the sim's Coherent GT browser and in a
   normal browser. Data comes from the Clearway companion (/api/radar/...). The map only redraws when something
   changes, and nothing is polled or drawn while the radar is hidden.

   ClearwayRadar.mount({ api: "http://localhost:8787", capture: <element shown during drags>, onDetach: fn }) */
(function () {
  "use strict";

  function start(o) {
  var IN_SIM = window.location.protocol.indexOf("http") !== 0;
  var UI = 1;                  // UI scale (see resize)
  var qs = window.location.search || "";
  var API = (o.api || "") + "/api/radar";
  var POLL_MS = 15000;
  var MIN_Z = 2, MAX_Z = 15, TILE_MAX_Z = 16;
  var GROUND_MIN_Z = 10;       // planes on the ground only show at this zoom and closer

  var el = function (id) { return document.getElementById("rd-" + id); };   // all radar elements are rd-*
  var canvas = el("map");
  var ctx = canvas.getContext("2d");

  // ------------------------------------------------------------ state
  var W = 0, H = 0, DPR = 1;
  var view = load("radar.view", { x: 0.5, y: 0.33, z: 4 });      // centre in normalised Web Mercator
  var opts = load("radar.opts", { labels: true, atc: true, ground: true, depLines: true, arrLines: true, track: false, size: "auto" });
  // display size: "auto" follows the screen height (1080p = 1x, 1440p = 1.33x, 4K = 2x); the others force a size
  var SIZES = { "1080p": 1, "1440p": 1.333, "4K": 2 }, SIZE_ORDER = ["auto", "1080p", "1440p", "4K"];
  var SIZE_LABEL = { "auto": "AUTO", "1080p": "1080", "1440p": "1440", "4K": "4K" };
  var pilots = [];        // {cs, mx, my, alt, gs, hdg, type, freq, dep, arr, sq, kind}
  var atc = null;         // processed controller data
  var atcVer = "";
  var trafficAps = {};    // ICAO -> airport used by traffic {mx, my, name, nArr, nDep}
  var apHits = [];        // faint airport dots from the last draw
  var mineCs = null;      // your callsign on the network, when found
  var manualCs = ((/[?&]me=([^&]+)/.exec(qs) || [])[1] || "").toUpperCase() || null;   // browser testing
  var lastFeed = 0, feedOk = false, loadingMsg = "";
  var serverMe = null;    // { cs: your callsign, obs: observer } when the vPilot plugin is connected
  var selected = null;    // {kind: "pilot"|"sector"|"airport", key}
  var me = null;          // own aircraft from SimVars {mx, my, hdg}
  var follow = false;
  var dirty = true;
  var hits = [];          // aircraft screen positions from the last draw
  var badgeHits = [];     // airport badge rects from the last draw
  var perf = { on: /[?&]perf=1/.test(qs), last: 0, total: 0, n: 0, draws: [], planes: 0 };

  function load(key, fallback) {
    try {
      var v = (typeof GetStoredData === "function") ? GetStoredData(key) : window.localStorage.getItem(key);
      if (!v) return fallback;
      var o = JSON.parse(v), k;
      for (k in fallback) if (!(k in o)) o[k] = fallback[k];
      return o;
    } catch (e) { return fallback; }
  }
  function save(key, value) {
    try {
      var s = JSON.stringify(value);
      if (typeof SetStoredData === "function") SetStoredData(key, s); else window.localStorage.setItem(key, s);
    } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------ projection
  function mercX(lon) { return (lon + 180) / 360; }
  function mercY(lat) {
    if (lat > 85) lat = 85; else if (lat < -85) lat = -85;
    var s = Math.sin(lat * Math.PI / 180);
    return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI);
  }
  // World size in layout pixels. Divided by the UI scale so a zoom level always shows the same area of map
  // whatever the display size (AUTO / 1080 / 1440 / 4K only make text and icons bigger), and tiles stay
  // at one tile pixel per screen pixel.
  function worldSize() { return 256 * Math.pow(2, view.z) / UI; }
  function wrapDx(dx) { return dx > 0.5 ? dx - 1 : (dx < -0.5 ? dx + 1 : dx); }

  // ------------------------------------------------------------ HTTP
  function getJSON(path, done) {
    var xhr = new XMLHttpRequest();
    xhr.open("GET", API + path, true);
    xhr.timeout = 10000;
    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4) return;
      if (xhr.status === 200) {
        var d = null;
        try { d = JSON.parse(xhr.responseText); } catch (e) { d = null; }
        done(d);
      } else done(null);
    };
    xhr.send();
  }

  // ------------------------------------------------------------ aircraft categories
  var HEAVY = /^(A30|A31|A33|A34|A35|A38|B74|B76|B77|B78|MD11|DC10|IL96|IL76|A124|A225|C5|C17|KC10|B52|L101|A400|BLCF)/;
  var HELI = /^(EC|H1|H2|H5|H6|H7|AS3|AS5|AS6|B06|B05|B407|B412|B429|B47G|S76|S92|R22|R44|R66|A109|A119|A129|A139|A149|A169|A189|AW|BK17|EH10|NH90|UH|CH|AH|MI8|MI24|K32|EXPL|GAZL|LYNX|PUMA|H47|H60|V22)/;
  var PROP = /^(C1|C2|C3|C4|PA|P28|P32|P46|DA2|DA4|DA5|DA6|DV2|SR2|BE|M20|DR4|TB|AT4|AT7|AT9|ATP|DH8|DHC|C208|PC6|PC7|PC9|PC12|PC21|TBM|SF34|J31|J32|J41|D228|D328|F27|F50|L410|AN2|AN24|AN26|SW4|E110|E120|SB20|Q4|GLID|AAT|ULAC|ZZZZ|PTS|P180|PA4|AC|SUBA|RV|DIMO|C17P|BN2|DHC6|DH2|EUPA|AQUI|CUB|J3|PA18|PA22|TOBA|TAMP|DG|ASK|LS)/;

  function kindOf(type) {
    if (!type) return "jet";
    if (HELI.test(type)) return "heli";
    if (HEAVY.test(type)) return "heavy";
    if (PROP.test(type)) return "prop";
    return "jet";
  }

  // shapes: nose points up (negative y); right half, mirrored when drawn
  var SHAPE_JET = [[0, -1], [0.11, -0.8], [0.11, -0.28], [0.95, 0.18], [0.95, 0.32], [0.11, 0.1], [0.09, 0.6], [0.38, 0.8], [0.38, 0.93], [0, 0.84]];
  var SHAPE_PROP = [[0, -1], [0.1, -0.82], [0.1, -0.42], [1, -0.36], [1, -0.16], [0.1, -0.12], [0.07, 0.58], [0.36, 0.66], [0.36, 0.82], [0, 0.8]];

  function addShape(pts) {
    var i;
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    for (i = pts.length - 1; i >= 0; i--) ctx.lineTo(-pts[i][0], pts[i][1]);
    ctx.closePath();
  }
  function addHeli() {
    ctx.moveTo(0.42, 0);
    ctx.arc(0, 0, 0.42, 0, Math.PI * 2);
    ctx.moveTo(0.06, 0.3); ctx.lineTo(0.06, 1); ctx.lineTo(-0.06, 1); ctx.lineTo(-0.06, 0.3); ctx.closePath();
  }

  // ------------------------------------------------------------ data
  function pollTraffic() {
    getJSON("/traffic", function (d) {
      if (d && d.loading) { loadingMsg = d.loading; updateStatus(); return; }    // companion still loading radar data
      loadingMsg = "";
      if (d && d.pilots) {
        serverMe = d.me || null;    // from the vPilot plugin: { cs, obs }
        var out = [], i, p;
        for (i = 0; i < d.pilots.length; i++) {
          p = d.pilots[i];
          out.push({ cs: p[0], mx: mercX(p[2]), my: mercY(p[1]), lat: p[1], lon: p[2], alt: p[3], gs: p[4], hdg: p[5],
                     type: p[6], freq: p[7], dep: p[8], arr: p[9], sq: p[10], kind: kindOf(p[6]) });
        }
        pilots = out;
        // airports used as departure or destination, with counts
        var aps = {}, k, a;
        for (k in (d.aps || {})) {
          a = d.aps[k];
          aps[k] = { icao: k, lat: a[0], lon: a[1], name: a[2], mx: mercX(a[1]), my: mercY(a[0]), nArr: 0, nDep: 0 };
        }
        for (i = 0; i < out.length; i++) {
          if (aps[out[i].arr]) aps[out[i].arr].nArr++;
          if (aps[out[i].dep]) aps[out[i].dep].nDep++;
        }
        trafficAps = aps;
        findMine();
        trackNow();
        lastFeed = Date.now();
        feedOk = true;
        dirty = true;
        if (selected && (selected.kind === "pilot" || selected.kind === "airport")) showCard();
      } else feedOk = false;
      updateStatus();
    });
  }

  function pollAtc() {
    getJSON("/atc?v=" + atcVer, function (d) {
      if (!d || d.same) return;
      var i, j, s, poly, mp, k, bb;
      for (i = 0; i < d.sectors.length; i++) {
        s = d.sectors[i];
        s.polys = [];
        for (j = 0; j < s.p.length; j++) {
          poly = s.p[j];
          mp = [];
          bb = [9, 9, -9, -9];
          for (k = 0; k < poly.length; k += 2) {
            var x = mercX(poly[k + 1]), y = mercY(poly[k]);
            mp.push(x, y);
            if (x < bb[0]) bb[0] = x; if (y < bb[1]) bb[1] = y; if (x > bb[2]) bb[2] = x; if (y > bb[3]) bb[3] = y;
          }
          s.polys.push({ pts: mp, bb: bb });
        }
        s.p = null;
        s.lx = mercX(s.lab[1]); s.ly = mercY(s.lab[0]);
      }
      for (i = 0; i < d.airports.length; i++) {
        var a = d.airports[i];
        a.mx = mercX(a.lon); a.my = mercY(a.lat);
        a.types = {};
        for (j = 0; j < a.c.length; j++) a.types[a.c[j].t] = true;
      }
      for (i = 0; i < d.circles.length; i++) {
        var c = d.circles[i];
        d.circles[i] = { mx: mercX(c[1]), my: mercY(c[0]), lat: c[0], cs: c[2] };
      }
      atc = d;
      atcVer = String(d.v);
      dirty = true;
      updateStatus();
    });
  }

  function updateStatus() {
    var s = el("status");
    if (loadingMsg) { s.textContent = loadingMsg; s.className = ""; return; }
    if (!feedOk && !pilots.length) { s.textContent = "no data from Clearway"; s.className = "err"; return; }
    var age = lastFeed ? Math.round((Date.now() - lastFeed) / 1000) : 0;
    var nAtc = atc ? atc.sectors.length + atc.airports.length : 0;
    s.textContent = pilots.length + " pilots | " + (atc ? countAtc() : 0) + " ATC | " + (feedOk ? age + " s ago" : "offline");
    s.className = feedOk ? "" : "err";
  }
  function countAtc() {
    var n = atc.sectors.length + atc.unplaced.length, i, j;   // ATIS not counted
    for (i = 0; i < atc.airports.length; i++)
      for (j = 0; j < atc.airports[i].c.length; j++) if (atc.airports[i].c[j].t !== "ATIS") n++;
    return n;
  }

  // ------------------------------------------------------------ tiles
  var tiles = {}, tileOrder = [], loading = 0, queue = [];
  function tileImg(z, x, y, request) {
    var key = z + "/" + x + "/" + y, t = tiles[key];
    if (t && t.ok && !(t.img.width > 0 && t.img.height > 0)) {
      // the sim's browser can drop the pixels of images loaded a while ago (size becomes 0):
      // drawing one throws "IndexSizeError", so forget it and load it again
      delete tiles[key]; t = null;
    }
    if (t) return t.ok ? t.img : null;
    if (!request) return null;
    t = tiles[key] = { img: new Image(), ok: false, key: key };
    queue.push(t);
    tileOrder.push(key);
    if (tileOrder.length > 250) {               // keep the sim's image memory small
      var old = tileOrder.shift();
      if (tiles[old] && !tiles[old].ok) tileOrder.push(old); else delete tiles[old];
    }
    pump();
    return null;
  }
  function pump() {
    while (loading < 8 && queue.length) {
      (function (t) {
        loading++;
        t.img.onload = function () {
          loading--;
          if (t.img.width > 0) { t.ok = true; dirty = true; } else delete tiles[t.key];   // empty image: retry later
          pump();
        };
        t.img.onerror = function () { loading--; delete tiles[t.key]; pump(); };
        t.img.src = API + "/tiles/" + t.key + ".png?s=esri";
      })(queue.shift());
    }
  }

  function drawTiles(ws) {
    var tz = Math.max(1, Math.min(TILE_MAX_Z, Math.round(view.z)));
    var n = Math.pow(2, tz);
    var size = 256 * Math.pow(2, view.z - tz);
    var x0 = view.x - W / 2 / ws, y0 = view.y - H / 2 / ws;
    var tx0 = Math.floor(x0 * n), ty0 = Math.max(0, Math.floor(y0 * n));
    var tx1 = Math.floor((view.x + W / 2 / ws) * n), ty1 = Math.min(n - 1, Math.floor((view.y + H / 2 / ws) * n));
    var tx, ty;
    // only load what is on screen now: forget tiles still waiting from an older view
    for (var q = 0; q < queue.length; q++) delete tiles[queue[q].key];
    queue.length = 0;
    for (ty = ty0; ty <= ty1; ty++) {
      for (tx = tx0; tx <= tx1; tx++) {
        var dx = Math.round((tx / n - x0) * ws), dy = Math.round((ty / n - y0) * ws);
        var sz = Math.round(((tx + 1) / n - x0) * ws) - dx;
        var wx = ((tx % n) + n) % n;
        var img = tileImg(tz, wx, ty, true);
        // one broken tile must not abort the whole frame (that blanked the map when zoomed out)
        if (img) { try { ctx.drawImage(img, dx, dy, sz, sz); continue; } catch (e) { delete tiles[tz + "/" + wx + "/" + ty]; } }
        // fall back to a lower zoom tile already loaded
        for (var up = 1; up <= 4 && tz - up >= 1; up++) {
          var f = Math.pow(2, up), pimg = tileImg(tz - up, Math.floor(wx / f), Math.floor(ty / f), false);
          if (pimg) {
            var sub = 256 / f;
            try { ctx.drawImage(pimg, (wx % f) * sub, (ty % f) * sub, sub, sub, dx, dy, sz, sz); } catch (e) { continue; }
            break;
          }
        }
      }
    }
    perf.tiles = tileOrder.length;
  }

  // ------------------------------------------------------------ drawing
  function hexA(hex, a) {
    var h = (hex || "#5aa0ff").replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    return "rgba(" + parseInt(h.substr(0, 2), 16) + "," + parseInt(h.substr(2, 2), 16) + "," + parseInt(h.substr(4, 2), 16) + "," + a + ")";
  }

  // simple label collision grid
  var grid = {};
  function gridFree(x, y, w, h) {
    var c0 = Math.floor(x / 80), c1 = Math.floor((x + w) / 80), r0 = Math.floor(y / 40), r1 = Math.floor((y + h) / 40), c, r, i, b;
    for (c = c0; c <= c1; c++) for (r = r0; r <= r1; r++) {
      b = grid[c + "," + r];
      if (b) for (i = 0; i < b.length; i++) {
        var q = b[i];
        if (x < q[0] + q[2] && x + w > q[0] && y < q[1] + q[3] && y + h > q[1]) return false;
      }
    }
    return true;
  }
  function gridAdd(x, y, w, h) {
    var c0 = Math.floor(x / 80), c1 = Math.floor((x + w) / 80), r0 = Math.floor(y / 40), r1 = Math.floor((y + h) / 40), c, r;
    for (c = c0; c <= c1; c++) for (r = r0; r <= r1; r++) (grid[c + "," + r] = grid[c + "," + r] || []).push([x, y, w, h]);
  }

  function draw() {
    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    dirty = false;
    var ws = worldSize();
    grid = {};
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = "#0b0e13";
    ctx.fillRect(0, 0, W, H);
    ctx.globalAlpha = 0.55;                    // tiles drawn half-transparent over the dark fill = darker basemap
    drawTiles(ws);
    ctx.globalAlpha = 1;
    drawTrafficAirports(ws);
    if (opts.atc && atc) drawAtc(ws);
    if (selected && selected.kind === "airport") drawRoutes(ws, selected.key);
    drawPilots(ws);
    if (me && !mineCs) drawMe(ws);    // not connected: outline of your sim position only
    var t1 = (window.performance && performance.now) ? performance.now() : Date.now();
    perf.last = t1 - t0; perf.total += perf.last; perf.n++;
    var nowMs = Date.now();
    perf.draws.push(nowMs);
    while (perf.draws.length && perf.draws[0] < nowMs - 10000) perf.draws.shift();   // was a slow leak: only trimmed with the readout open
    if (perf.on) showPerf();
  }

  function sx(mx, ws) { return (wrapDx(mx - view.x)) * ws + W / 2; }
  function sy(my, ws) { return (my - view.y) * ws + H / 2; }

  function drawAtc(ws) {
    var x0 = view.x - W / 2 / ws, x1 = view.x + W / 2 / ws, y0 = view.y - H / 2 / ws, y1 = view.y + H / 2 / ws;
    var i, j, k, s, p, pts;
    var secs = atc.sectors;
    var minStep = view.z < 5 ? 3 : (view.z < 6.5 ? 2.5 : 1.5);   // coarser sector outlines when zoomed out (invisible difference)
    perf.sectorPts = 0;
    for (i = 0; i < secs.length; i++) {
      s = secs[i];
      var any = false;
      ctx.beginPath();
      for (j = 0; j < s.polys.length; j++) {
        p = s.polys[j];
        if (p.bb[2] < x0 || p.bb[0] > x1 || p.bb[3] < y0 || p.bb[1] > y1) continue;
        // skip polygons smaller than ~2 px and points closer than 1.5 px to the previous one
        if ((p.bb[2] - p.bb[0]) * ws < 2 && (p.bb[3] - p.bb[1]) * ws < 2) continue;
        pts = p.pts;
        any = true;
        var px = (pts[0] - view.x) * ws + W / 2, py = (pts[1] - view.y) * ws + H / 2, qx, qy;
        ctx.moveTo(px, py);
        perf.sectorPts++;
        for (k = 2; k < pts.length; k += 2) {
          qx = (pts[k] - view.x) * ws + W / 2; qy = (pts[k + 1] - view.y) * ws + H / 2;
          if (Math.abs(qx - px) + Math.abs(qy - py) < minStep) continue;
          ctx.lineTo(qx, qy); px = qx; py = qy;
          perf.sectorPts++;
        }
        ctx.closePath();
      }
      if (!any) continue;
      var sel = selected && selected.kind === "sector" && selected.key === s.k;
      ctx.fillStyle = hexA(s.c, sel ? 0.30 : 0.16);
      ctx.fill();
      ctx.lineWidth = sel ? 2 : 1;
      ctx.strokeStyle = hexA(s.c, sel ? 0.95 : 0.55);
      ctx.stroke();
    }
    // approach circles for approach controllers VATGlasses does not cover
    if (ctx.setLineDash) ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "rgba(255,184,77,0.7)";
    ctx.lineWidth = 1.2;
    for (i = 0; i < atc.circles.length; i++) {
      var c = atc.circles[i];
      var r = (30 / 60) / 360 * ws / Math.cos(c.lat * Math.PI / 180);
      var cx = sx(c.mx, ws), cy = sy(c.my, ws);
      if (cx + r < 0 || cx - r > W || cy + r < 0 || cy - r > H) continue;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    }
    if (ctx.setLineDash) ctx.setLineDash([]);
    drawAirports(ws);
    // sector labels (after the airport badges, so they avoid them)
    if (view.z >= 5) {
      ctx.font = "600 10px 'Roboto-Regular', Roboto, 'Segoe UI', Arial, sans-serif";
      ctx.textBaseline = "middle";
      for (i = 0; i < secs.length; i++) {
        s = secs[i];
        var lx = sx(s.lx, ws), ly = sy(s.ly, ws);
        if (lx < -60 || lx > W + 60 || ly < -20 || ly > H + 20) continue;
        var t1 = s.cs, t2 = s.f;
        var w = Math.max(ctx.measureText(t1).width, ctx.measureText(t2).width) + 10, h = 26;
        var bx = Math.round(lx - w / 2), by = Math.round(ly - h / 2);
        if (!gridFree(bx, by, w, h)) continue;
        gridAdd(bx, by, w, h);
        ctx.fillStyle = "rgba(11,14,19,0.82)";
        ctx.fillRect(bx, by, w, h);
        ctx.strokeStyle = hexA(s.c, 0.9); ctx.lineWidth = 1;
        ctx.strokeRect(bx + 0.5, by + 0.5, w - 1, h - 1);
        ctx.fillStyle = "#e6edf5"; ctx.textAlign = "center";
        ctx.fillText(t1, lx, by + 8);
        ctx.fillStyle = "#7fe0a0";
        ctx.fillText(t2, lx, by + 19);
      }
      ctx.textAlign = "left";
    }
  }

  // faint dot (and ICAO when zoomed in) for every airport with arriving traffic
  function drawTrafficAirports(ws) {
    apHits = [];
    var k, a, x, y, showText = view.z >= 6;
    ctx.fillStyle = "rgba(200,214,230,0.75)";
    ctx.beginPath();
    for (k in trafficAps) {
      a = trafficAps[k];
      if (!a.nArr) continue;
      x = sx(a.mx, ws); y = sy(a.my, ws);
      if (x < -30 || x > W + 30 || y < -20 || y > H + 20) continue;
      ctx.moveTo(x + 2.5, y);
      ctx.arc(x, y, 2.5, 0, Math.PI * 2);
      a.x = x; a.y = y;
      apHits.push(a);
    }
    ctx.fill();
    if (!showText) return;
    ctx.font = "9px 'Roboto-Regular', Roboto, 'Segoe UI', Arial, sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillStyle = "rgba(170,188,208,0.5)";
    for (var i = 0; i < apHits.length; i++) {
      a = apHits[i];
      if (opts.atc && atc && findAtcAirport(a.icao)) continue;   // the ATC badge already names it
      ctx.fillText(a.icao, a.x, a.y + 4);
    }
    ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
  }

  // great-circle points between two lat/lon positions, as screen coordinates kept continuous across the map edge
  function gcLine(lat1, lon1, lat2, lon2, ws) {
    var r = Math.PI / 180, p1 = lat1 * r, l1 = lon1 * r, p2 = lat2 * r, l2 = lon2 * r;
    var d = 2 * Math.asin(Math.sqrt(Math.pow(Math.sin((p2 - p1) / 2), 2) + Math.cos(p1) * Math.cos(p2) * Math.pow(Math.sin((l2 - l1) / 2), 2)));
    var n = d < 0.05 ? 1 : Math.min(48, Math.ceil(d / 0.02)), pts = [], i, px = null;
    for (i = 0; i <= n; i++) {
      var f = i / n, lat, lon;
      if (n === 1 || d === 0) { lat = lat1 + (lat2 - lat1) * f; lon = lon1 + (lon2 - lon1) * f; }
      else {
        var A = Math.sin((1 - f) * d) / Math.sin(d), B = Math.sin(f * d) / Math.sin(d);
        var x = A * Math.cos(p1) * Math.cos(l1) + B * Math.cos(p2) * Math.cos(l2);
        var y = A * Math.cos(p1) * Math.sin(l1) + B * Math.cos(p2) * Math.sin(l2);
        var z = A * Math.sin(p1) + B * Math.sin(p2);
        lat = Math.atan2(z, Math.sqrt(x * x + y * y)) / r; lon = Math.atan2(y, x) / r;
      }
      var X = sx(mercX(lon), ws);
      if (px !== null) { while (X - px > ws / 2) X -= ws; while (px - X > ws / 2) X += ws; }
      px = X;
      pts.push(X, sy(mercY(lat), ws));
    }
    return pts;
  }

  function strokeLines(list, colour) {
    if (!list.length) return;
    ctx.beginPath();
    for (var i = 0; i < list.length; i++) {
      var pts = list[i];
      ctx.moveTo(pts[0], pts[1]);
      for (var k = 2; k < pts.length; k += 2) ctx.lineTo(pts[k], pts[k + 1]);
    }
    ctx.strokeStyle = colour; ctx.lineWidth = 1.3;
    ctx.stroke();
  }

  // departures (red) and arrivals (green) of the selected airport
  function drawRoutes(ws, icao) {
    var a = trafficAps[icao];
    if (!a) return;
    var dep = [], arr = [], i, p;
    for (i = 0; i < pilots.length; i++) {
      p = pilots[i];
      if (opts.depLines && p.dep === icao) dep.push(gcLine(a.lat, a.lon, p.lat, p.lon, ws));
      else if (opts.arrLines && p.arr === icao) arr.push(gcLine(p.lat, p.lon, a.lat, a.lon, ws));
    }
    strokeLines(dep, "rgba(255,92,92,0.75)");
    strokeLines(arr, "rgba(86,226,128,0.75)");
  }

  var BADGES = [["DEL", "D", "#4fa3ff"], ["GND", "G", "#48c774"], ["TWR", "T", "#ff6363"], ["APP", "A", "#ffb84d"], ["ATIS", "i", "#3cc6c6"]];
  function drawAirports(ws) {
    badgeHits = [];
    if (view.z < 3.5) return;
    var i, j, a, list, bx, by;
    ctx.font = "700 9px 'Roboto-Regular', Roboto, 'Segoe UI', Arial, sans-serif";
    ctx.textBaseline = "middle";
    ctx.textAlign = "center";
    for (i = 0; i < atc.airports.length; i++) {
      a = atc.airports[i];
      var x = sx(a.mx, ws), y = sy(a.my, ws);
      if (x < -40 || x > W + 40 || y < -20 || y > H + 20) continue;
      list = [];
      for (j = 0; j < BADGES.length; j++) {
        var b = BADGES[j];
        if (a.types[b[0]] || (b[0] === "APP" && a.types.DEP) || (b[0] === "GND" && a.types.RMP)) list.push(b);
      }
      var w = list.length * 12 + 2;
      bx = Math.round(x - w / 2); by = Math.round(y - 6);
      ctx.fillStyle = "rgba(11,14,19,0.9)";
      ctx.fillRect(bx - 1, by - 1, w + 2, 14);
      for (j = 0; j < list.length; j++) {
        ctx.fillStyle = list[j][2];
        ctx.fillRect(bx + 1 + j * 12, by + 1, 11, 10);
        ctx.fillStyle = "#0b0e13";
        ctx.fillText(list[j][1], bx + 6.5 + j * 12, by + 6.5);
      }
      if (view.z >= 6) {
        ctx.fillStyle = "#c7d2df";
        ctx.fillText(a.icao, x, by + 20);
      }
      gridAdd(bx - 1, by - 1, w + 2, view.z >= 6 ? 26 : 14);
      badgeHits.push([bx - 2, by - 2, w + 4, 16, a]);
    }
    ctx.textAlign = "left";
  }

  function iconSize() { return Math.max(5, Math.min(11, 5 + (view.z - 4) * 0.9)); }

  function drawPilots(ws) {
    hits = [];
    var size = iconSize();
    var groups = { air: [], gnd: [], sel: [], mine: [] };
    var i, p, x, y;
    for (i = 0; i < pilots.length; i++) {
      p = pilots[i];
      var isMine = p.cs === mineCs;
      var onGround = p.gs < 50;
      if (onGround && !isMine && (!opts.ground || view.z < GROUND_MIN_Z) &&
          !(selected && selected.kind === "pilot" && selected.key === p.cs)) continue;
      if (isMine && me) {        // in the sim: use the live sim position instead of the 15 s old feed one
        x = sx(me.mx, ws); y = sy(me.my, ws); p.hdgLive = me.hdg;
      } else { x = sx(p.mx, ws); y = sy(p.my, ws); p.hdgLive = null; }
      if (x < -20 || x > W + 20 || y < -20 || y > H + 20) continue;
      p.x = x; p.y = y;
      hits.push(p);
      if (isMine) groups.mine.push(p);
      else if (selected && selected.kind === "pilot" && selected.key === p.cs) groups.sel.push(p);
      else if (onGround) groups.gnd.push(p); else groups.air.push(p);
    }
    perf.planes = hits.length;
    fillPlanes(groups.gnd, size * 0.85, "#7d8a9a");
    fillPlanes(groups.air, size, "#ffcf4a");
    fillPlanes(groups.sel, size * 1.2, "#4fd1ff");
    var mineSel = selected && selected.kind === "pilot" && selected.key === mineCs;
    fillPlanes(groups.mine, size * 1.25, "#5dff9b");
    if (mineSel) groups.sel = groups.mine;     // your plane clicked: expanded label, still green
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (opts.labels) drawLabels(groups, size);
  }

  // Each icon (kind x colour x size) is drawn once into a small canvas with its outline,
  // then stamped rotated for every plane: much cheaper than filling and stroking a path per plane.
  var sprites = {};
  function sprite(kind, size, colour) {
    var key = kind + colour + size.toFixed(1) + DPR;
    var sp = sprites[key];
    if (sp) return sp;
    var s = size * (kind === "heavy" ? 1.3 : (kind === "jet" ? 1 : 0.85)) * DPR;
    var half = Math.ceil(s * 1.1) + 2;
    var cv = document.createElement("canvas");
    cv.width = cv.height = half * 2;
    var c2 = cv.getContext("2d");
    var save = ctx; ctx = c2;          // reuse the shape helpers on the sprite canvas
    c2.setTransform(s, 0, 0, s, half, half);
    c2.beginPath();
    if (kind === "heli") addHeli(); else addShape(kind === "prop" ? SHAPE_PROP : SHAPE_JET);
    ctx = save;
    c2.fillStyle = colour; c2.fill();
    c2.lineWidth = 0.9 / s * DPR; c2.strokeStyle = "rgba(0,0,0,0.7)"; c2.stroke();
    sp = sprites[key] = { cv: cv, half: half };
    return sp;
  }

  function fillPlanes(list, size, colour) {
    if (!list.length) return;
    size = Math.round(size * 2) / 2;
    var i;
    if (view.z < 5.5 && list.length > 40) {
      // zoomed out: hundreds of planes, each only a few pixels. Draw them as heading-pointing triangles,
      // batched a few dozen per fill: far fewer draw calls than one icon per plane. (One single path with
      // every plane made the sim's renderer draw long "spikes" between triangles in busy areas.)
      ctx.fillStyle = colour;
      ctx.beginPath();
      for (i = 0; i < list.length; i++) {
        var q = list[i], h = (q.hdgLive != null ? q.hdgLive : q.hdg) * Math.PI / 180;
        if (!isFinite(h) || !isFinite(q.x) || !isFinite(q.y)) continue;
        var cs = Math.cos(h), sn = Math.sin(h), L = size * 1.1, B = size * 0.7;
        ctx.moveTo(q.x + sn * L, q.y - cs * L);                              // nose
        ctx.lineTo(q.x - sn * L * 0.6 + cs * B, q.y + cs * L * 0.6 + sn * B);  // right tail
        ctx.lineTo(q.x - sn * L * 0.6 - cs * B, q.y + cs * L * 0.6 - sn * B);  // left tail
        ctx.closePath();
        if (i % 24 === 23) { ctx.fill(); ctx.beginPath(); }
      }
      ctx.fill();
      return;
    }
    for (i = 0; i < list.length; i++) {
      var p = list[i], sp = sprite(p.kind, size, colour);
      var a = (p.hdgLive != null ? p.hdgLive : p.hdg) * Math.PI / 180, c = Math.cos(a), n = Math.sin(a);
      ctx.setTransform(c, n, -n, c, DPR * p.x, DPR * p.y);
      ctx.drawImage(sp.cv, -sp.half, -sp.half);
    }
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function altText(p) {
    if (p.alt >= 18000) { var fl = Math.round(p.alt / 100); return "FL" + (fl < 100 ? "0" : "") + fl; }
    return (Math.round(p.alt / 100) * 100) + "ft";
  }

  function drawLabels(groups, size) {
    // show labels when zoomed in, or when few aircraft are on screen
    // your own plane always gets a label, even when the others are hidden
    var top = groups.sel === groups.mine ? groups.sel : groups.sel.concat(groups.mine);
    var list = top.concat(groups.air, groups.gnd);
    if (view.z < 5.5 && hits.length > 120) list = top;
    if (!list.length) return;
    ctx.textBaseline = "alphabetic";
    var lh = 11, i, p;
    var BOLD = "700 10px 'Roboto-Regular', Roboto, 'Segoe UI', Arial, sans-serif", REG = "10px 'Roboto-Regular', Roboto, 'Segoe UI', Arial, sans-serif";
    for (i = 0; i < list.length; i++) {
      p = list[i];
      var isSel = groups.sel.length && p === groups.sel[0];
      // compact:  CALLSIGN (bold)  TYPE            / DESTINATION
      // expanded (clicked plane): CALLSIGN  TYPE  FREQUENCY / DESTINATION  ALTITUDE  SPEED
      var cs = p.cs, typ = p.type ? "  " + p.type : "";
      var fr = isSel && p.freq ? "  " + p.freq.split(" ")[0] : "";
      var l2 = isSel ? (p.arr ? p.arr + "  " : "") + altText(p) + "  " + p.gs + "kt" : (p.arr || "");
      ctx.font = BOLD;
      var wCs = ctx.measureText(cs).width;
      ctx.font = REG;
      var wTyp = ctx.measureText(typ).width, wFr = ctx.measureText(fr).width;
      var w = Math.max(wCs + wTyp + wFr, l2 ? ctx.measureText(l2).width : 0) + 4, h = l2 ? lh * 2 + 3 : lh + 3;
      var off = size + 4, spots = [[off, -h / 2], [-off - w, -h / 2], [-w / 2, -off - h], [-w / 2, off]];
      for (var k = 0; k < spots.length; k++) {
        var bx = Math.round(p.x + spots[k][0]), by = Math.round(p.y + spots[k][1]);
        if (!isSel && !gridFree(bx, by, w, h)) continue;
        gridAdd(bx, by, w, h);
        if (isSel) {
          ctx.fillStyle = "rgba(10,30,42,0.55)";
          ctx.fillRect(bx, by, w, h);
        } else {
          // compact: no box, just a thin dark outline under the text so it stays readable on the map
          ctx.lineWidth = 2.5; ctx.strokeStyle = "rgba(8,11,16,0.85)"; ctx.lineJoin = "round";
          ctx.font = BOLD; ctx.strokeText(cs, bx + 2, by + lh);
          ctx.font = REG; ctx.strokeText(typ, bx + 2 + wCs, by + lh);
          if (l2) ctx.strokeText(l2, bx + 2, by + lh * 2 + 1);
        }
        ctx.font = BOLD;
        ctx.fillStyle = p.cs === mineCs ? "#5dff9b" : (isSel ? "#4fd1ff" : "#ffffff");
        ctx.fillText(cs, bx + 2, by + lh);
        ctx.font = REG;
        ctx.fillStyle = "#c9d4e0";
        ctx.fillText(typ, bx + 2 + wCs, by + lh);
        if (fr) {
          ctx.fillStyle = "#7fe0a0";
          ctx.fillText(fr, bx + 2 + wCs + wTyp, by + lh);
        }
        ctx.fillStyle = "#a9b8c9";
        ctx.fillText(l2, bx + 2, by + lh * 2 + 1);
        break;
      }
    }
  }

  function drawMe(ws) {
    var x = sx(me.mx, ws), y = sy(me.my, ws), s = iconSize() * 1.5;
    var a = me.hdg * Math.PI / 180, c = Math.cos(a) * s, n = Math.sin(a) * s;
    ctx.beginPath();
    ctx.setTransform(DPR * c, DPR * n, -DPR * n, DPR * c, DPR * x, DPR * y);
    addShape(SHAPE_JET);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    // not on the network: hollow green outline (connected = solid green, drawn with the traffic)
    ctx.fillStyle = "rgba(93,255,155,0.12)"; ctx.fill();
    ctx.strokeStyle = "#5dff9b"; ctx.lineWidth = 1.4; ctx.stroke();
  }

  // ------------------------------------------------------------ info card
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function showCard() {
    var c = el("card"), h = "";
    if (!selected) { c.className = "hidden"; return; }
    if (selected.kind === "pilot") {
      var p = null;
      for (var i = 0; i < pilots.length; i++) if (pilots[i].cs === selected.key) { p = pilots[i]; break; }
      if (!p) { h = "<div class='cs'>" + esc(selected.key) + "</div><div class='sub'>disconnected</div>"; }
      else {
        h = "<div class='cs'>" + esc(p.cs) + "</div>" +
          "<div class='sub'>" + esc(p.type || "no flight plan") + (p.dep ? " | " + esc(p.dep) + " > " + esc(p.arr) : "") + "</div>" +
          "<div class='row'><span>Altitude</span><b>" + esc(altText(p)) + " (" + p.alt + " ft)</b></div>" +
          "<div class='row'><span>Ground speed</span><b>" + p.gs + " kt</b></div>" +
          "<div class='row'><span>Heading</span><b>" + ("00" + p.hdg).slice(-3) + "&deg;</b></div>" +
          "<div class='row'><span>Squawk</span><b>" + esc(p.sq) + "</b></div>" +
          "<div class='row'><span>Tuned</span><span class='freq'>" + esc(p.freq || "-") + "</span></div>";
      }
    } else if (selected.kind === "sector") {
      var s = findSector(selected.key);
      if (!s) { selected = null; c.className = "hidden"; return; }
      h = ctlHtml({ cs: s.cs, f: s.f, n: s.n, atis: s.atis }, s.name);
    } else if (selected.kind === "airport") {
      var a = opts.atc ? findAtcAirport(selected.key) : null, t = trafficAps[selected.key];
      if (!a && !t) { selected = null; c.className = "hidden"; return; }
      h = "<div class='cs'>" + esc(selected.key) + "</div>" + (t && t.name ? "<div class='sub'>" + esc(t.name) + "</div>" : "");
      if (t) {
        h += "<div class='lines'>" +
          "<span id='rd-tDep' class='lt dep" + (opts.depLines ? " on" : "") + "'>Departures " + t.nDep + "</span>" +
          "<span id='rd-tArr' class='lt arr" + (opts.arrLines ? " on" : "") + "'>Arrivals " + t.nArr + "</span></div>";
      }
      if (a) for (var j = 0; j < a.c.length; j++) h += ctlHtml(a.c[j]);
    }
    c.innerHTML = "<span class='x' id='rd-cardx'><i class='a'></i><i class='b'></i></span>" + h;
    c.className = "";
    el("cardx").onclick = function () { selected = null; showCard(); dirty = true; };
    if (el("tDep")) {
      el("tDep").onclick = function () { opts.depLines = !opts.depLines; save("radar.opts", opts); showCard(); dirty = true; };
      el("tArr").onclick = function () { opts.arrLines = !opts.arrLines; save("radar.opts", opts); showCard(); dirty = true; };
    }
  }
  function ctlHtml(k, voice) {
    var atis = k.atis && k.atis.length ? "<div class='atis'>" + esc(k.atis.join(" ")) + "</div>" : "";
    return "<div class='ctl'><div class='row'><b>" + esc(k.cs) + "</b><span class='freq'>" + esc(k.f) + "</span></div>" +
      (voice ? "<div class='sub'>" + esc(voice) + "</div>" : "") +
      (k.n ? "<div class='sub'>" + esc(k.n) + "</div>" : "") + atis + "</div>";
  }
  function findSector(k) { if (!atc) return null; for (var i = 0; i < atc.sectors.length; i++) if (atc.sectors[i].k === k) return atc.sectors[i]; return null; }
  function findAtcAirport(k) { if (!atc) return null; for (var i = 0; i < atc.airports.length; i++) if (atc.airports[i].icao === k) return atc.airports[i]; return null; }

  // ------------------------------------------------------------ hit testing
  function pickAt(x, y) {
    var best = null, bd = 144, i;
    for (i = 0; i < hits.length; i++) {
      var dx = hits[i].x - x, dy = hits[i].y - y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = hits[i]; }
    }
    // airports compete with planes: a click on an ATC badge or close to an airport dot picks the airport
    // unless a plane is right under the cursor
    var ab = null, ad = 81;
    if (opts.atc && atc) {
      for (i = 0; i < badgeHits.length; i++) {
        var b = badgeHits[i];
        if (x >= b[0] && x <= b[0] + b[2] && y >= b[1] && y <= b[1] + b[3]) { ab = b[4]; ad = 0; break; }
      }
    }
    if (!ab) for (i = 0; i < apHits.length; i++) {
      var ex = apHits[i].x - x, ey = apHits[i].y - y, e2 = ex * ex + ey * ey;
      if (e2 < ad) { ad = e2; ab = apHits[i]; }
    }
    if (best && (!ab || bd < Math.max(ad, 9))) return { kind: "pilot", key: best.cs };
    if (ab) return { kind: "airport", key: ab.icao };
    if (opts.atc && atc) {
      var ws = worldSize(), mx = view.x + (x - W / 2) / ws, my = view.y + (y - H / 2) / ws, found = null, fa = 1e9;
      for (i = 0; i < atc.sectors.length; i++) {
        var s = atc.sectors[i];
        for (var j = 0; j < s.polys.length; j++) {
          var p = s.polys[j];
          if (mx < p.bb[0] || mx > p.bb[2] || my < p.bb[1] || my > p.bb[3]) continue;
          if (inPoly(p.pts, mx, my)) {
            var area = (p.bb[2] - p.bb[0]) * (p.bb[3] - p.bb[1]);
            if (area < fa) { fa = area; found = s; }
          }
        }
      }
      if (found) return { kind: "sector", key: found.k };
    }
    return null;
  }
  function inPoly(pts, x, y) {
    var inside = false, n = pts.length, i, j;
    for (i = 0, j = n - 2; i < n; j = i, i += 2) {
      var xi = pts[i], yi = pts[i + 1], xj = pts[j], yj = pts[j + 1];
      if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) inside = !inside;
    }
    return inside;
  }

  // ------------------------------------------------------------ input
  // pointer position in map units (the sim panel is drawn at UI scale)
  function px(e) { var r = canvas.getBoundingClientRect(); return { x: (e.clientX - r.left) / UI, y: (e.clientY - r.top) / UI }; }
  var drag = null;
  // Clearway's panel only receives the mouse over its own boxes: while dragging, its full-screen capture
  // layer is switched on so the drag keeps going when the pointer leaves the radar
  function capture(on) { if (o.capture) o.capture.classList.toggle("on", on); }
  function endDrag() { drag = null; canvas.className = ""; capture(false); }
  canvas.addEventListener("mousedown", function (e) {
    if (e.button !== 0) return;
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
    capture(true);
  });
  // the mouse button released outside the panel sends no mouseup in the sim: end the drag then
  if (typeof Coherent !== "undefined" && Coherent.on) Coherent.on("mousePressOutsideView", function () { if (drag) endDrag(); });
  window.addEventListener("mousemove", function (e) {
    if (!drag) return;
    if (typeof e.buttons === "number" && e.buttons === 0 && drag.moved) { endDrag(); save("radar.view", view); return; }
    drag.lastMove = Date.now();
    var dx = (e.clientX - drag.x) / UI, dy = (e.clientY - drag.y) / UI;
    if (!drag.moved && dx * dx + dy * dy < 16) return;
    if (!drag.moved) { drag.moved = true; canvas.className = "drag"; if (follow) setFollow(false); }
    var ws = worldSize();
    view.x = drag.vx - dx / ws;
    view.y = Math.max(0, Math.min(1, drag.vy - dy / ws));
    if (view.x < 0) view.x += 1; else if (view.x > 1) view.x -= 1;
    dirty = true;
  });
  window.addEventListener("mouseup", function (e) {
    if (!drag) return;
    var d = drag; endDrag();
    if (d.moved) { save("radar.view", view); return; }
    var q = px(e);
    selected = pickAt(q.x, q.y);
    showCard();
    dirty = true;
  });
  canvas.addEventListener("wheel", function (e) {
    e.preventDefault();
    wheelAt = Date.now();
    var q = px(e);
    zoomAt((e.deltaY < 0 ? 0.5 : -0.5), q.x, q.y);
  });
  canvas.addEventListener("dblclick", function (e) {
    var q = px(e);
    zoomAt(1, q.x, q.y);
  });

  function zoomAt(dz, x, y) {
    if (follow) { x = W / 2; y = H / 2; }        // tracking: zoom around your aircraft
    var nz = Math.max(MIN_Z, Math.min(MAX_Z, view.z + dz));
    if (nz === view.z) return;
    var ws = worldSize(), mx = view.x + (x - W / 2) / ws, my = view.y + (y - H / 2) / ws;
    view.z = nz;
    var ws2 = worldSize();
    view.x = mx - (x - W / 2) / ws2;
    view.y = Math.max(0, Math.min(1, my - (y - H / 2) / ws2));
    save("radar.view", view);
    dirty = true;
  }

  el("zin").onclick = function () { zoomAt(1, W / 2, H / 2); };
  el("zout").onclick = function () { zoomAt(-1, W / 2, H / 2); };
  // Track button: keeps your aircraft in the centre until you turn it off or drag the map
  function myPos() {
    if (me) return me;
    for (var i = 0; mineCs && i < pilots.length; i++) if (pilots[i].cs === mineCs) return pilots[i];
    return null;
  }
  function setFollow(on) {
    follow = on;
    opts.track = on; save("radar.opts", opts);
    el("me").className = "btn tog" + (on ? " on" : "");
    if (on) trackNow();
  }
  function trackNow() {
    var p = myPos();
    if (!follow || !p) return;
    if (Math.abs(view.x - p.mx) > 1e-9 || Math.abs(view.y - p.my) > 1e-9) {
      view.x = p.mx; view.y = p.my; dirty = true;
    }
  }
  el("me").onclick = function () {
    setFollow(!follow);
    if (follow && !myPos()) el("status").textContent = "tracking: waiting for your aircraft...";
  };
  follow = !!opts.track;
  el("me").className = "btn tog" + (follow ? " on" : "");

  // Which network callsign is you: in the sim, the pilot in the feed closest to your sim position
  // (within ~4 nm and 1500 ft, since the feed is up to 15 s old). Once found it sticks while it stays near.
  function findMine() {
    var prev = mineCs, i, p;
    if (manualCs) mineCs = manualCs;
    else if (serverMe && serverMe.obs) mineCs = null;          // vPilot says: observer, so not in the pilot list
    else if (serverMe && serverMe.cs) mineCs = serverMe.cs;    // vPilot says exactly who you are
    else if (!me) mineCs = null;
    else {
      // Observer mode in vPilot (or not connected) means you are not in the pilot list, so nothing should
      // match. Strict limits keep a real pilot near you from being taken for you:
      //   on the ground: within ~0.3 nm and 200 ft;  flying: within ~4 nm, 1500 ft and 40 deg of heading.
      var ground = me.gs < 50;
      var lim = ground ? 0.005 : 0.07, altLim = ground ? 200 : 1500;
      var best = null, bd = lim * lim, cosl = Math.cos(me.lat * Math.PI / 180);
      for (i = 0; i < pilots.length; i++) {
        p = pilots[i];
        var dy = p.lat - me.lat, dx = (p.lon - me.lon) * cosl, d = dx * dx + dy * dy;
        var dh = Math.abs(((p.hdg - me.hdg) % 360 + 540) % 360 - 180);
        var fits = Math.abs(p.alt - me.alt) < altLim && (ground || dh < 40);
        if (p.cs === prev && fits && d < 4 * bd) { best = p; break; }      // keep the current match
        if (fits && d < bd) { bd = d; best = p; }
      }
      mineCs = best ? best.cs : null;
    }
    var found = false;
    for (i = 0; mineCs && i < pilots.length; i++) if (pilots[i].cs === mineCs) { found = true; break; }
    if (!found) mineCs = null;
    if (mineCs !== prev) dirty = true;
  }
  function bindToggle(id, key) {
    var b = el(id);
    b.className = "btn tog" + (opts[key] ? " on" : "");
    b.onclick = function () { opts[key] = !opts[key]; b.className = "btn tog" + (opts[key] ? " on" : ""); save("radar.opts", opts); dirty = true; };
  }
  bindToggle("tLabels", "labels");
  bindToggle("tAtc", "atc");
  bindToggle("tGround", "ground");
  function showSize() { el("tSize").textContent = SIZE_LABEL[opts.size] || "AUTO"; el("tSize").title = "Display size: " + opts.size + " (click to change)"; }
  if (el("tSize")) {
    showSize();
    el("tSize").onclick = function () {
      var i = SIZE_ORDER.indexOf(opts.size);
      opts.size = SIZE_ORDER[(i + 1) % SIZE_ORDER.length];
      save("radar.opts", opts); showSize(); resize();
    };
  }
  el("status").onclick = function () { perf.on = !perf.on; el("perf").className = perf.on ? "" : "hidden"; if (perf.on) showPerf(); };
  if (perf.on) el("perf").className = "";

  // benchmark: redraw n times while panning, return average ms per frame (used for the perf test)
  window.radarBench = function (n, z) {
    if (z) view.z = z;
    var t0 = performance.now(), x = view.x;
    for (var i = 0; i < n; i++) { view.x = x + i * 0.0005; draw(); }
    view.x = x; dirty = true;
    return { ms: +((performance.now() - t0) / n).toFixed(2), planes: perf.planes, sectorPts: perf.sectorPts };
  };

  // frame benchmark including the browser's own rendering: n full redraws, one per animation frame,
  // at zoom z centred on lat/lon; result (ms per frame) in window.radarBenchResult. View restored after.
  window.radarBenchFrames = function (n, z, lat, lon) {
    var saved = { x: view.x, y: view.y, z: view.z }, i = 0, t0 = 0;
    view.z = z; if (lat != null) { view.x = mercX(lon); view.y = mercY(lat); }
    window.radarBenchResult = null;
    function step(ts) {
      if (i === 0) t0 = ts;
      if (i < n) { view.x += 0.0002; draw(); i++; window.requestAnimationFrame(step); return; }
      window.radarBenchResult = { msPerFrame: +((ts - t0) / n).toFixed(1), planes: perf.planes, sectorPts: perf.sectorPts, lastDrawJs: +perf.last.toFixed(1) };
      view.x = saved.x; view.y = saved.y; view.z = saved.z; snap.ok = false; dirty = true;
    }
    window.requestAnimationFrame(step);
  };

  function showPerf() {
    var now = Date.now();
    while (perf.draws.length && perf.draws[0] < now - 10000) perf.draws.shift();
    var mem = (window.performance && performance.memory) ? Math.round(performance.memory.usedJSHeapSize / 1048576) + " MB" : "n/a";
    el("perf").textContent =
      "draw   " + perf.last.toFixed(1) + " ms (avg " + (perf.total / Math.max(1, perf.n)).toFixed(1) + ")\n" +
      "draws  " + perf.draws.length + " in last 10 s\n" +
      "planes " + perf.planes + " on screen / " + pilots.length + "\n" +
      "sector pts " + (perf.sectorPts || 0) + "\n" +
      "tiles  " + (perf.tiles || 0) + " cached\n" +
      "JS heap " + mem;
  }

  // ------------------------------------------------------------ own aircraft (in the sim)
  function readSim() {
    if (typeof SimVar === "undefined") return;
    try {
      var lat = SimVar.GetSimVarValue("PLANE LATITUDE", "degree latitude");
      var lon = SimVar.GetSimVarValue("PLANE LONGITUDE", "degree longitude");
      var hdg = SimVar.GetSimVarValue("PLANE HEADING DEGREES TRUE", "degree");
      var alt = SimVar.GetSimVarValue("PLANE ALTITUDE", "feet");
      var gs = SimVar.GetSimVarValue("GROUND VELOCITY", "knots");
      if (typeof lat !== "number" || (lat === 0 && lon === 0)) return;
      var n = { mx: mercX(lon), my: mercY(lat), hdg: hdg, lat: lat, lon: lon, alt: alt, gs: gs || 0 };
      var ws = worldSize();
      if (!me || Math.abs(n.mx - me.mx) * ws > 1 || Math.abs(n.my - me.my) * ws > 1 || Math.abs(n.hdg - me.hdg) > 2) {
        me = n;
        if (!mineCs && pilots.length) findMine();
        trackNow();
        dirty = true;
      }
    } catch (e) { /* not in the sim */ }
  }

  // ------------------------------------------------------------ loop
  // In the sim, everything is scaled with the screen height (1.0 at 1080p, 1.33 at 1440p) so text stays readable.
  function resize() {
    var r = canvas.getBoundingClientRect();
    var forced = parseFloat((/[?&]ui=([\d.]+)/.exec(qs) || [])[1]);           // ?ui=1.33 to test in a browser
    var auto = IN_SIM ? Math.max(1, (window.innerHeight || 1080) / 1080) : 1;
    UI = forced || (opts.size === "auto" ? auto : SIZES[opts.size]) || auto;
    DPR = (window.devicePixelRatio || 1) * UI;
    W = Math.max(1, Math.round(r.width / UI)); H = Math.max(1, Math.round(r.height / UI));
    canvas.width = Math.round(r.width * (window.devicePixelRatio || 1));
    canvas.height = Math.round(r.height * (window.devicePixelRatio || 1));
    sprites = {};
    snap.ok = false;                                   // the last frame no longer matches the canvas
    // all panel sizes are in em (radar.css); shrink them if the button column would not fit the window
    var font = 12 * UI;
    el("radar").style.fontSize = font + "px";
    var need = el("tools").offsetTop + el("tools").offsetHeight, avail = r.height - 4;
    if (need > avail && avail > 40) {
      font = Math.max(6, font * avail / need);
      el("radar").style.fontSize = font + "px";
    }
    lastSize = r.width + "x" + r.height;
    dirty = true;
  }
  var lastSize = "";
  window.addEventListener("resize", resize);
  var snap = { cv: null, x: 0, y: 0, z: 0, ok: false, fast: false };
  resize();
  // the sim does not always send a resize event when the panel window is resized: check the size ourselves
  setInterval(function () {
    if (paused) return;
    var r = canvas.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.width + "x" + r.height !== lastSize) resize();
  }, 300);

  // ------------------------------------------------------------ pause while closed / hidden
  // Nothing is polled, read or drawn while the panel is closed (MSFS panelInactive), the browser tab is
  // hidden, or the panel has no size. The companion stops downloading too once nobody asks for data.
  var paused = false, panelActive = true, rafOn = false;
  var ui = document.querySelector("ingame-ui");
  // Detach / dock button: Clearway moves the radar between its card and a separate window
  if (o.onDetach) {
    el("detach").className = "";
    el("detach").onclick = function () { o.onDetach(); };
  }
  if (ui) {
    ui.addEventListener("panelActive", function () { panelActive = true; checkVisible(); });
    ui.addEventListener("panelInactive", function () { panelActive = false; checkVisible(); });
  }
  document.addEventListener("visibilitychange", function () { checkVisible(); });
  function isVisible() {
    if (!panelActive || document.hidden) return false;
    var r = canvas.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function checkVisible() {
    var v = isVisible();
    if (v === !paused) return;
    paused = !v;
    if (paused) getJSON("/bye", function () {});     // tell the companion to stop downloading now
    if (!paused) {
      resize();
      pollTraffic(); pollAtc();
      setTimeout(pollTraffic, 3000);      // the companion may have been idle: fresh data follows shortly
      readSim();
      startFrames();
    }
  }
  function startFrames() { if (!rafOn) { rafOn = true; window.requestAnimationFrame(frame); } }
  function frame() {
    if (paused) { rafOn = false; return; }
    // schedule the next frame first: an error while drawing must never stop the loop
    // (that is what froze the map after a resize: the loop died and nothing redrew any more)
    window.requestAnimationFrame(frame);
    try {
      if (dirty) {
        if (interacting() && snap.ok) drawFast();
        else { draw(); takeSnapshot(); }
      } else if (snap.fast && !interacting()) {
        draw(); takeSnapshot();             // interaction over: one full redraw at the final position
      }
    } catch (e) {
      snap.ok = false; dirty = true;
      if (window.console) console.error("radar draw failed", e);
    }
  }

  // ------------------------------------------------------------ fast pan / zoom
  // While you drag or scroll, the last full frame is moved / scaled (one draw call) instead of
  // redrawing every sector, plane and label; the full redraw happens when you stop.
  var wheelAt = 0;
  // a drag counts as "in progress" only while the mouse keeps moving: a release the sim never reported
  // can no longer leave the map stuck in the fast mode
  function interacting() { return (drag && drag.moved && Date.now() - drag.lastMove < 300) || Date.now() - wheelAt < 180; }
  function takeSnapshot() {
    try {
      if (!canvas.width || !canvas.height) { snap.ok = false; return; }
      if (!snap.cv) snap.cv = document.createElement("canvas");
      if (snap.cv.width !== canvas.width || snap.cv.height !== canvas.height) {
        snap.cv.width = canvas.width; snap.cv.height = canvas.height;
      }
      var c2 = snap.cv.getContext("2d");
      c2.setTransform(1, 0, 0, 1, 0, 0);
      c2.drawImage(canvas, 0, 0);
      snap.x = view.x; snap.y = view.y; snap.z = view.z; snap.ok = true; snap.fast = false;
    } catch (e) { snap.ok = false; }
  }
  function drawFast() {
    dirty = false;
    var ws = worldSize(), s = Math.pow(2, view.z - snap.z);
    var dx = wrapDx(snap.x - view.x) * ws + W / 2 - (W / 2) * s;
    var dy = (snap.y - view.y) * ws + H / 2 - (H / 2) * s;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.fillStyle = "#0b0e13";
    ctx.fillRect(0, 0, W, H);
    ctx.drawImage(snap.cv, dx, dy, W * s, H * s);
    snap.fast = true;
  }

  paused = !isVisible();
  if (!paused) { pollTraffic(); pollAtc(); startFrames(); }
  setInterval(function () { if (!paused) { pollTraffic(); pollAtc(); } }, POLL_MS);
  setInterval(function () { if (!paused) updateStatus(); }, 5000);
  setInterval(function () { if (!paused) readSim(); }, 1000);
  setInterval(checkVisible, 1000);
  // heartbeat: the companion pauses its downloads 10 s after the last one (e.g. the sim closed the panel
  // without the panel getting a chance to say goodbye)
  setInterval(function () { if (!paused) getJSON("/ping", function () {}); }, 4000);
  }

  // The radar's markup (all ids rd-*). mount() builds it inside o.container; Clearway can later move the
  // #rd-radar element between its card and the detached window (listeners move with it).
  var MARKUP =
    '<canvas id="rd-map"></canvas>' +
    '<div id="rd-tools">' +
      '<div id="rd-zin" class="btn big" title="Zoom in">+</div>' +
      '<div id="rd-zout" class="btn big" title="Zoom out">-</div>' +
      '<div id="rd-me" class="btn tog" title="Track my aircraft">TRK</div>' +
      '<span class="sep"></span>' +
      '<div id="rd-tLabels" class="btn tog on" title="Aircraft labels">LBL</div>' +
      '<div id="rd-tAtc" class="btn tog on" title="Controllers and sectors">ATC</div>' +
      '<div id="rd-tGround" class="btn tog on" title="Aircraft on the ground">GND</div>' +
      '<span class="sep"></span>' +
      '<div id="rd-tSize" class="btn tog on" title="Display size">AUTO</div>' +
    '</div>' +
    '<div id="rd-topright">' +
      '<div id="rd-status">connecting...</div>' +
      '<div id="rd-detach" class="hidden" title="Open the radar in its own window"><i class="box"></i><i class="out"></i></div>' +
    '</div>' +
    '<div id="rd-card" class="hidden"></div>' +
    '<div id="rd-perf" class="hidden"></div>' +
    '<div id="rd-credit">Map (c) Esri, HERE, Garmin, (c) OpenStreetMap contributors | VATGlasses CC BY-NC-SA | VATSpy CC BY-SA</div>';

  // Clearway mounts the radar once its panel is ready; the browser test page calls mount() itself.
  var started = false;
  window.ClearwayRadar = {
    mount: function (o) {
      if (started) return;
      started = true;
      o = o || {};
      var root = document.createElement("div");
      root.id = "rd-radar";
      root.innerHTML = MARKUP;
      (o.container || document.body).appendChild(root);
      start(o);
    }
  };
})();
