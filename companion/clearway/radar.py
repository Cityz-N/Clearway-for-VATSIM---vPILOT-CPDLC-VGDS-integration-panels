"""Radar tab of the Clearway panel: live VATSIM traffic, controllers and VATGlasses sectors.

Downloads the VATSIM data feed and the voice transceiver list (the frequency each pilot is tuned to),
VATGlasses sector data and VATSpy airports, works out which online controller owns which sector, and
serves small JSON files plus cached dark map tiles to the panel under /api/radar/...

Nothing is loaded until the radar is first opened (the sector data takes ~120 MB of memory), and the
live downloads pause 10 s after the radar is hidden (the panel pings every 4 s while it shows it).
Data: VATSIM feed; VATGlasses (CC BY-NC-SA 4.0); VATSpy data project (CC BY-SA 4.0);
map tiles: Esri World Dark Gray Canvas (no key needed).
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import os
import re
import threading
import time
import traceback
import urllib.request
import zipfile

from .config import data_dir

_log = logging.getLogger("clearway.radar")
UA = "ClearwayRadar/1.0"
CACHE = str(data_dir() / "radar")
FEED_URL = "https://data.vatsim.net/v3/vatsim-data.json"
TX_URL = "https://data.vatsim.net/v3/transceivers-data.json"
VG_URL = "https://codeload.github.com/vatglasses-project/vatglasses-data/zip/refs/heads/main"
SPY_URL = "https://raw.githubusercontent.com/vatsimnetwork/vatspy-data-project/master/VATSpy.dat"
# Esri "Dark Gray Canvas" raster tiles: no API key or account needed (CARTO now requires a key).
TILE_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
FEED_EVERY = 15
IDLE_AFTER = 10      # seconds without a panel request before downloads pause (open panels ping every 4 s)
STATIC_MAX_AGE = 24 * 3600


def log(*a):
    _log.info(" ".join(str(x) for x in a))


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data


def cached_download(url, name):
    """Download a static file at most once a day; fall back to the old copy if offline."""
    path = os.path.join(CACHE, name)
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > STATIC_MAX_AGE:
        try:
            log("downloading", name)
            data = fetch(url, timeout=120)
            os.makedirs(CACHE, exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
        except Exception as e:
            if not os.path.exists(path):
                raise
            log("download failed, using cached", name, e)
    with open(path, "rb") as f:
        return f.read()


# Same fix as Clearway's textfix.py: some VATSIM clients send Windows-1252 text that ends up as
# UTF-8 read twice ("Ã©" instead of "é"). Undo that; leave anything else untouched.
_MOJIBAKE = re.compile("[ÂÃâ][\u0080-¿‘-›ŒœŠšŸŽžƒˆ˜€™]")


def fix_text(text):
    if not text or not isinstance(text, str) or not _MOJIBAKE.search(text):
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def freq_key(f):
    try:
        return int(round(float(f) * 1000))
    except (TypeError, ValueError):
        return None


def first_seg(s):
    for i, ch in enumerate(s):
        if ch in "_-":
            return s[:i]
    return s


def dms(v):
    """VATGlasses point: "-ddmmss" / "-dddmmss" strings, negative = S/W."""
    v = v.strip()
    neg = v.startswith("-")
    v = v.lstrip("+-")
    sec = int(v[-2:]); mn = int(v[-4:-2]); deg = int(v[:-4] or 0)
    d = deg + mn / 60.0 + sec / 3600.0
    return -d if neg else d


def ring_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def ring_centroid(pts):
    a = ring_area(pts)
    if abs(a) < 1e-12:
        return pts[0]
    cx = cy = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        c = x1 * y2 - x2 * y1
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    return (cx / (6 * a), cy / (6 * a))


# ---------------------------------------------------------------- static data
class Static:
    def __init__(self):
        self.airports = {}      # ICAO -> (lat, lon, name)
        self.airspaces = []     # dicts: set, id, group colour, owners [(set,pos)], polys [[(lat,lon)...]]
        self.positions = {}     # (set,pos) -> dict
        self.pos_index = {}     # (first segment of prefix, type) -> [(set,pos)]
        self.vg_airports = {}   # ICAO -> (lat, lon) from VATGlasses

    def load(self):
        self._load_vatspy()
        self._load_vatglasses()

    def _load_vatspy(self):
        text = cached_download(SPY_URL, "VATSpy.dat").decode("utf-8", "replace")
        section = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            if line.startswith("["):
                section = line
                continue
            if section == "[Airports]":
                p = line.split("|")
                if len(p) >= 4 and p[0] not in self.airports:
                    try:
                        self.airports[p[0]] = (float(p[2]), float(p[3]), fix_text(p[1]))
                    except ValueError:
                        pass
                    if len(p) > 4 and p[4] and p[4] not in self.airports:   # IATA/LID alias (e.g. US "LAX")
                        try:
                            self.airports[p[4]] = (float(p[2]), float(p[3]), p[1])
                        except ValueError:
                            pass
        log("VATSpy airports:", len(self.airports))

    def _load_vatglasses(self):
        raw = cached_download(VG_URL, "vatglasses.zip")
        zf = zipfile.ZipFile(io.BytesIO(raw))
        files = {}
        for n in zf.namelist():
            parts = n.split("/")
            if len(parts) >= 3 and parts[1] == "data" and n.endswith(".json"):
                files["/".join(parts[2:])] = n
        static_sets = [k for k in files if "/" not in k]
        dyn_sets = sorted({k.split("/")[0] for k in files if k.endswith("/airspace.json")})
        n_sec = 0
        for name in static_sets:
            sid = name[:-5]
            try:
                d = json.loads(zf.read(files[name]).decode("utf-8"))
            except Exception as e:
                log("skip", name, e)
                continue
            n_sec += self._add_set(sid, d.get("airspace", []), d.get("positions", {}), d.get("groups", {}), d.get("airports", {}))
        for sid in dyn_sets:
            try:
                a = json.loads(zf.read(files[sid + "/airspace.json"]).decode("utf-8"))
                p = json.loads(zf.read(files[sid + "/positions.json"]).decode("utf-8"))
                own_name = files.get(sid + "/ownership/default.json")
                own = json.loads(zf.read(own_name).decode("utf-8")).get("airspace", {}) if own_name else {}
            except Exception as e:
                log("skip dynamic", sid, e)
                continue
            lst = []
            for key, asp in (a.get("airspace") or {}).items():
                asp = dict(asp)
                asp["owner"] = own.get(key, asp.get("owner", []))
                lst.append(asp)
            n_sec += self._add_set(sid, lst, p.get("positions", {}), a.get("groups", {}) or p.get("groups", {}), a.get("airports", {}) or p.get("airports", {}))
        for (sid, pid), pos in self.positions.items():
            for pre in pos.get("pre", []):
                self.pos_index.setdefault((first_seg(pre), pos.get("type", "")), []).append((sid, pid))
        log("VATGlasses: %d sets, %d airspaces, %d sectors, %d positions" % (
            len(static_sets) + len(dyn_sets), len(self.airspaces), n_sec, len(self.positions)))

    def _add_set(self, sid, airspace, positions, groups, airports):
        for pid, pos in positions.items():
            self.positions[(sid, pid)] = pos
        for icao, ap in (airports or {}).items():
            c = ap.get("coord") if isinstance(ap, dict) else None
            if c and len(c) == 2:
                self.vg_airports[icao] = (float(c[0]), float(c[1]))
        # Without ATIS parsing we cannot know the runway in use: take the first runway each airport lists.
        default_rwy = {}
        for asp in airspace:
            for sec in asp.get("sectors", []):
                for cond in sec.get("runways", []) or []:
                    r = cond.get("runway")
                    r = r[0] if isinstance(r, list) and r else r
                    if r is not None:
                        default_rwy.setdefault(cond.get("icao"), str(r))
        n = 0
        for asp in airspace:
            owners = []
            for o in asp.get("owner", []) or []:
                owners.append(tuple(o.split("/", 1)) if "/" in o else (sid, o))
            polys = []
            for sec in asp.get("sectors", []) or []:
                ok = True
                for cond in sec.get("runways", []) or []:
                    r = cond.get("runway")
                    rl = [str(x) for x in r] if isinstance(r, list) else [str(r)]
                    if default_rwy.get(cond.get("icao")) not in rl:
                        ok = False
                if not ok:
                    continue
                pts = []
                for p in sec.get("points", []) or []:
                    try:
                        q = (round(dms(p[0]), 4), round(dms(p[1]), 4))
                    except Exception:
                        continue
                    if not pts or pts[-1] != q:
                        pts.append(q)
                if len(pts) > 1 and pts[0] == pts[-1]:
                    pts.pop()
                if len(pts) < 3:
                    continue
                # same winding everywhere so one canvas fill (non-zero rule) unions overlapping layers
                xy = [(lon, lat) for lat, lon in pts]
                if ring_area(xy) < 0:
                    pts.reverse()
                polys.append(pts)
                n += 1
            if polys and owners:
                g = (groups or {}).get(asp.get("group"), {})
                self.airspaces.append({"set": sid, "id": asp.get("id", ""), "gcol": g.get("colour"),
                                       "owners": owners, "polys": polys})
        return n

    def airport_coord(self, icao):
        if icao in self.airports:
            lat, lon, _ = self.airports[icao]
            return lat, lon
        return self.vg_airports.get(icao)


# ---------------------------------------------------------------- live state
class State:
    def __init__(self, static):
        self.st = static
        self.lock = threading.Lock()
        self.traffic = b"{}"
        self.traffic_ver = 0
        self.atc = b"{}"
        self.atc_ver = 0
        self.atc_key = None
        self.stats = {}
        self.last_request = 0.0
        self.last_update = time.time()

    def run(self):
        # Download only while a panel is asking for data; idle after IDLE_AFTER s without requests.
        idle = False
        while True:
            time.sleep(1)
            now = time.time()
            if now - self.last_request > IDLE_AFTER:
                if not idle:
                    idle = True
                    log("no panel open: downloads paused")
                continue
            if idle:
                idle = False
                log("panel open: downloads resumed")
            if now - self.last_update < FEED_EVERY:
                continue
            self.last_update = now
            try:
                self.update()
            except Exception:
                _log.exception("radar update failed")

    def update(self):
        t0 = time.time()
        feed = json.loads(fetch(FEED_URL))
        try:
            tx = json.loads(fetch(TX_URL))
        except Exception as e:
            log("transceivers failed", e)
            tx = []
        t1 = time.time()
        freqs = {}
        for e in tx:
            ts = e.get("transceivers") or []
            fl = []
            for t in ts:
                f = t.get("frequency")
                if f:
                    s = "%.3f" % (f / 1e6)
                    if s not in fl:
                        fl.append(s)
            if fl:
                freqs[e.get("callsign")] = fl
        # Observers (vPilot observer mode included) are listed as facility-0 "controllers" and are never drawn.
        # Belt and braces: drop a pilot entry if the same callsign is also logged in as an observer.
        observers = {c.get("callsign") for c in feed.get("controllers", []) if c.get("facility") == 0}
        pilots = []
        for p in feed.get("pilots", []):
            if p["callsign"] in observers:
                continue
            fp = p.get("flight_plan") or {}
            pilots.append([p["callsign"], round(p["latitude"], 4), round(p["longitude"], 4), p.get("altitude", 0),
                           p.get("groundspeed", 0), p.get("heading", 0), fp.get("aircraft_short") or "",
                           " ".join(freqs.get(p["callsign"], [])), fp.get("departure") or "", fp.get("arrival") or "",
                           p.get("transponder") or ""])
        # positions of every departure / destination airport in use (for faint airport dots and route lines)
        aps = {}
        for p in pilots:
            for icao in (p[8], p[9]):
                if icao and icao not in aps:
                    c = self.st.airport_coord(icao)
                    if c:
                        name = self.st.airports.get(icao, (0, 0, ""))[2]
                        aps[icao] = [round(c[0], 4), round(c[1], 4), name]
        traffic = {"t": feed.get("general", {}).get("update_timestamp"), "pilots": pilots, "aps": aps}
        atc = self.build_atc(feed, freqs)
        t2 = time.time()
        tb = json.dumps(traffic, separators=(",", ":")).encode()
        ab = json.dumps(atc, separators=(",", ":")).encode()
        with self.lock:
            self.traffic = tb
            self.traffic_ver += 1
            key = hash(ab)
            if key != self.atc_key:
                self.atc_key = key
                self.atc_ver += 1
                atc["v"] = self.atc_ver
                self.atc = json.dumps(atc, separators=(",", ":")).encode()
            self.stats = {"download_s": round(t1 - t0, 2), "process_s": round(t2 - t1, 3),
                          "pilots": len(pilots), "controllers": len(feed.get("controllers", [])),
                          "traffic_kb": len(tb) // 1024, "atc_kb": len(self.atc) // 1024}
        log("feed: %(pilots)d pilots, %(controllers)d ATC, download %(download_s)ss, process %(process_s)ss, "
            "traffic %(traffic_kb)d KB, atc %(atc_kb)d KB" % self.stats)

    def build_atc(self, feed, freqs):
        st = self.st
        online = {}           # (set,pos) -> controller info
        airports = {}         # ICAO -> list of controllers
        unplaced = []
        approach_circles = []
        names = {c["id"]: c["short"] for c in feed.get("facilities", [])}

        def ctl_info(c):
            return {"cs": c["callsign"], "f": c.get("frequency", ""), "n": fix_text(c.get("name", "")),
                    "atis": [fix_text(t) for t in (c.get("text_atis") or [])]}

        for c in feed.get("controllers", []) + feed.get("atis", []):
            cs = c.get("callsign", "")
            fac = c.get("facility", 0)
            if fac == 0 or c.get("frequency") == "199.998" or "_" not in cs:
                continue
            typ = cs.rsplit("_", 1)[-1]
            fk = freq_key(c.get("frequency"))
            matched = None
            if typ != "ATIS":
                for key in st.pos_index.get((first_seg(cs), typ), []):
                    pos = st.positions[key]
                    if not any(cs.startswith(p + "_") for p in pos.get("pre", [])):
                        continue
                    pf = pos.get("frequency")
                    if pf and freq_key(pf) != fk:
                        continue
                    if key not in online:
                        matched = key
                        break
                    matched = matched or key
                if matched and matched not in online:
                    info = ctl_info(c)
                    info["pos"] = matched
                    online[matched] = info
            prefix = cs.split("_")[0]
            if typ in ("DEL", "GND", "TWR", "ATIS", "APP", "DEP", "RMP"):
                coord = st.airport_coord(prefix) or (st.airport_coord("K" + prefix) if len(prefix) == 3 else None)
                if coord:
                    ap = airports.setdefault(prefix, {"icao": prefix, "lat": coord[0], "lon": coord[1], "c": []})
                    i = ctl_info(c); i["t"] = typ
                    ap["c"].append(i)
                    if typ in ("APP", "DEP") and not matched:
                        approach_circles.append([coord[0], coord[1], c["callsign"]])
                    continue
            if not matched:
                i = ctl_info(c); i["t"] = names.get(fac, typ)
                unplaced.append(i)

        # sector ownership: first online position in each airspace's owner list
        groups = {}           # owner key -> {"c": colour, "p": [polys], "lab": ...}
        for asp in st.airspaces:
            owner = next((o for o in asp["owners"] if o in online), None)
            if not owner:
                continue
            k = owner[0] + "/" + owner[1]
            g = groups.get(k)
            if g is None:
                pos = st.positions.get(owner, {})
                col = None
                for entry in pos.get("colours", []) or []:
                    req = entry.get("online") or []
                    if all((owner[0], r) in online for r in req):
                        col = entry.get("hex")
                        break
                g = groups[k] = {"k": k, "c": col or asp["gcol"] or "#5aa0ff", "p": [], "big": (0, None)}
                info = online[owner]
                g["cs"] = info["cs"]; g["f"] = info["f"]; g["n"] = info["n"]; g["name"] = pos.get("callsign", "")
                g["atis"] = info["atis"]
            for poly in asp["polys"]:
                g["p"].append([v for pt in poly for v in pt])
                a = abs(ring_area([(lon, lat) for lat, lon in poly]))
                if a > g["big"][0]:
                    g["big"] = (a, poly)
        sectors = []
        for g in groups.values():
            big = g.pop("big")[1]
            cx, cy = ring_centroid([(lon, lat) for lat, lon in big])
            g["lab"] = [round(cy, 3), round(cx, 3)]
            sectors.append(g)
        placed = {info["cs"] for info in online.values()}
        unplaced = [u for u in unplaced if u["cs"] not in placed]
        return {"sectors": sectors, "airports": list(airports.values()), "circles": approach_circles,
                "unplaced": unplaced}


# ---------------------------------------------------------------- tiles
tile_locks = {}
tile_lock_guard = threading.Lock()


def get_tile(z, x, y):
    path = os.path.join(CACHE, "tiles", str(z), str(x), "%d.png" % y)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    with tile_lock_guard:
        lk = tile_locks.setdefault(path, threading.Lock())
    try:
        with lk:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read()
            url = TILE_URL.format(z=z, x=x, y=y)
            data = fetch(url, timeout=15)
            if not data.startswith(b"\x89PNG") and not data.startswith(b"\xff\xd8"):
                raise ValueError("not an image")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path + ".tmp", "wb") as f:
                f.write(data)
            os.replace(path + ".tmp", path)
            return data
    finally:
        with tile_lock_guard:          # don't keep one lock per tile forever
            if tile_locks.get(path) is lk:
                tile_locks.pop(path, None)


# ---------------------------------------------------------------- Clearway glue
class Radar:
    """Owned by the HTTP server. Loads everything on first use, in the background."""

    def __init__(self, session):
        self.session = session
        self.state = None
        self.loading = False
        self.error = ""
        self.lock = threading.Lock()

    def _ensure_started(self):
        with self.lock:
            if self.state or self.loading:
                return
            self.loading = True
            self.error = ""
        threading.Thread(target=self._load, name="radar-load", daemon=True).start()

    def _load(self):
        try:
            os.makedirs(CACHE, exist_ok=True)
            static = Static()
            static.load()
            state = State(static)
            state.last_request = time.time()
            state.update()
            threading.Thread(target=state.run, name="radar", daemon=True).start()
            self.state = state
        except Exception as exc:
            _log.exception("radar data could not be loaded")
            self.error = str(exc)
        finally:
            self.loading = False

    def _me(self) -> dict:
        """Your callsign from the vPilot plugin (exact, better than guessing from the sim position)."""
        s = self.session
        try:
            if s.vpilot_connected and s.vpilot_active():
                return {"cs": s.vpilot_callsign or "", "obs": bool(s.vpilot_observer)}
        except AttributeError:
            pass
        return {}

    def handle(self, action: str, query: dict):
        """Returns (status, body bytes, content type, cache-control)."""
        if action in ("traffic", "atc", "ping") or action.startswith("tiles/"):
            if self.state:
                self.state.last_request = time.time()
        if action == "bye":                     # the radar was hidden: pause the downloads now
            if self.state:
                self.state.last_request = 0.0
            return 200, b'{"ok":1}', "application/json", "no-store"
        if action == "ping":
            self._ensure_started()
            return 200, b'{"ok":1}', "application/json", "no-store"
        if action.startswith("tiles/"):
            try:
                z, x, y = [int(v) for v in action[6:].replace(".png", "").split("/")]
            except ValueError:
                return 404, b"{}", "application/json", "no-store"
            if not (0 <= z <= 19 and 0 <= x < 2 ** z and 0 <= y < 2 ** z):
                return 404, b"{}", "application/json", "no-store"
            data = get_tile(z, x, y)
            return 200, data, ("image/jpeg" if data[:2] == b"\xff\xd8" else "image/png"), "max-age=604800"
        if action in ("traffic", "atc"):
            self._ensure_started()
            st = self.state
            if not st:
                msg = ("radar data failed: " + self.error) if self.error else "loading radar data..."
                return 200, json.dumps({"loading": msg}).encode(), "application/json", "no-store"
            if action == "atc":
                with st.lock:
                    if (query.get("v") or [""])[0] == str(st.atc_ver):
                        return 200, b'{"same":1}', "application/json", "no-store"
                    return 200, st.atc, "application/json", "no-store"
            with st.lock:
                body = st.traffic
            me = json.dumps(self._me(), separators=(",", ":")).encode()
            if body.endswith(b"}") and len(body) > 2:      # add "me" without re-encoding the whole feed
                body = body[:-1] + b',"me":' + me + b"}"
            return 200, body, "application/json", "no-store"
        return 404, b'{"error":"not found"}', "application/json", "no-store"
