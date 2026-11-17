"""Render the flightsim.to / README screenshots (tools/screenshots/fs-*.html) to dist/screenshots/*.png (1920x1080).

Needs the test Clearway and fake vPilot running and filled (see prepare_shots.py). Serves the panel files on
8791 itself. Uses headless Edge + build\\venv (websocket-client).

    build\\venv\\Scripts\\python tools/screenshots/capture.py            -> all fs-*.html
    build\\venv\\Scripts\\python tools/screenshots/capture.py --measure  -> card sizes per tab (for layout)
"""
import base64
import functools
import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websocket

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = ROOT / "dist" / "screenshots"
CDP_PORT = 9344
# panel settings stored per origin (localhost:8791): icon position, radar view over central Europe
PANEL_STORAGE = {
    "CLEARWAY_POS": {"x": 0.03, "y": 0.25},
    "CLEARWAY_LOCK": None,
    "CLEARWAY_PAUSED": False,
    "CLEARWAY_SC_SAVED": True,
    "radar.view": {"x": 0.5194, "y": 0.3413, "z": 5.6},
    "radar.opts": {"labels": True, "atc": True, "ground": True, "depLines": True, "arrLines": True, "track": False, "size": "auto"},
}


def serve_panel():
    # The screenshot pages are served from the same origin as the panel (/shots/...): a panel iframe inside a
    # file:// page gets its own, empty storage, so the icon position and radar view set here wouldn't apply.
    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def translate_path(self, path):
            p = path.split("?")[0]
            if p.startswith("/shots/"):
                return str(HERE / p[len("/shots/"):])
            return super().translate_path(path)
    h = functools.partial(Quiet, directory=str(ROOT / "msfs-panel"))
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", 8791), h)
    except OSError:
        return None                      # already served
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


class Cdp:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True)
        self.n = 0

    def __call__(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{method}: {m['error']}")
                return m.get("result", {})

    def js(self, expr):
        return self("Runtime.evaluate", expression=expr, returnByValue=True).get("result", {}).get("value")


def edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        p = Path(base or "") / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if p.exists():
            return str(p)
    sys.exit("Edge not found")


def set_panel_storage(cdp, values):
    cdp("Page.navigate", url="http://localhost:8791/html_ui/InGamePanels/ClearwayPanel/radar.css")
    time.sleep(0.8)
    cdp.js("".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v))});" for k, v in values.items()))


def radar_close_up(cdp):
    """fs-radar: zoomed in on the busiest airborne traffic right now, labels on, one plane's full tag open.
    The view is centred on that plane, and fs-radar.html puts the radar map's centre at page (479.5, 317.7)."""
    traffic = json.loads(urllib.request.urlopen("http://127.0.0.1:8797/api/radar/traffic", timeout=30).read())["pilots"]
    best, plane = -1, None                  # [cs, lat, lon, alt, gs, hdg, type, freq, dep, arr, sq]
    for p in traffic:
        if 4000 <= p[3] <= 24000 and p[4] > 150:
            n = sum(1 for q in traffic if abs(q[1] - p[1]) < 0.9 and abs(q[2] - p[2]) < 1.4)
            if n > best:
                best, plane = n, p
    s = math.sin(math.radians(plane[1]))
    view = {"x": (plane[2] + 180) / 360, "y": 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi), "z": 8.3}
    set_panel_storage(cdp, {"radar.view": view})
    cdp("Page.navigate", url="http://localhost:8791/shots/fs-radar.html")
    time.sleep(8)
    for t in ("mousePressed", "mouseReleased"):
        cdp("Input.dispatchMouseEvent", type=t, x=479.5, y=317.7, button="left", clickCount=1)
    time.sleep(2.5)
    shot = cdp("Page.captureScreenshot", format="png")
    (OUT / "fs-radar.png").write_bytes(base64.b64decode(shot["data"]))
    print("saved", OUT / "fs-radar.png", "- centred on", plane[0], f"({best} planes nearby)")
    set_panel_storage(cdp, {"radar.view": PANEL_STORAGE["radar.view"]})


def main():
    serve_panel()
    profile = tempfile.mkdtemp(prefix="cw-shots-")
    proc = subprocess.Popen([edge(), "--headless=new", "--hide-scrollbars", "--no-first-run", f"--user-data-dir={profile}",
                             f"--remote-debugging-port={CDP_PORT}", "--allow-file-access-from-files", "about:blank"])
    try:
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2).read())
                page = next(t for t in tabs if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp("Page.enable")
        cdp("Page.navigate", url="http://localhost:8791/html_ui/InGamePanels/ClearwayPanel/radar.css")
        time.sleep(1)
        cdp.js("localStorage.clear();" + "".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v))});"
                                                for k, v in PANEL_STORAGE.items()))
        if "--measure" in sys.argv:
            cdp("Emulation.setDeviceMetricsOverride", width=1000, height=1080, deviceScaleFactor=1, mobile=False)
            for tab in ("cpdlc", "vpilot", "selcal", "radar"):
                cdp("Page.navigate", url=f"http://localhost:8791/html_ui/InGamePanels/ClearwayPanel/ClearwayPanel.html?api=http://localhost:8797&open={tab}")
                time.sleep(6 if tab == "radar" else 3)
                print(tab, cdp.js("(function(){var r=document.getElementById('cw-card').getBoundingClientRect();"
                                  "var b=document.getElementById('cw-bubble').getBoundingClientRect();"
                                  "return {card:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)],"
                                  "bubble:[Math.round(b.left),Math.round(b.top)]}})()"))
            return
        OUT.mkdir(parents=True, exist_ok=True)
        cdp("Emulation.setDeviceMetricsOverride", width=960, height=540, deviceScaleFactor=2, mobile=False)
        names = [a for a in sys.argv[1:] if not a.startswith("--")] or sorted(p.stem for p in HERE.glob("fs-*.html"))
        for name in names:
            if name == "fs-radar":
                radar_close_up(cdp)
                continue
            cdp("Page.navigate", url=f"http://localhost:8791/shots/{name}.html")
            time.sleep(9)                      # panels, phones and the radar (tiles, sectors) settle
            shot = cdp("Page.captureScreenshot", format="png")
            (OUT / f"{name}.png").write_bytes(base64.b64decode(shot["data"]))
            print("saved", OUT / f"{name}.png")
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
