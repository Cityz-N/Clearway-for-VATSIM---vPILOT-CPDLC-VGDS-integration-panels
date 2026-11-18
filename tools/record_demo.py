"""Record the animated WebP of the MSFS panel in use (tools/demo_anim/flight.html).

Needs the test Clearway and the fake vPilot running first (never the real Clearway on 8787):
    set CLEARWAY_FAKE_FP=1 & python tools/dev_run.py      (fake SimBrief + flight plan status from the mock server)
    set CLEARWAY_PORT=8797 & tools\\fake-vpilot\\bin\\Release\\net472\\FakeVpilot.exe vpilot-plugin\\compiled\\Clearway.vPilot.dll 1800
Start both fresh (dev_run first, then the fake vPilot, which announces the nearby controllers when it
starts), and keep the phone page closed: it marks the chat on screen as read.
Needs Pillow + websocket-client (build\\venv\\Scripts\\pip install pillow websocket-client). Then:
    build\\venv\\Scripts\\python tools/record_demo.py          -> dist/screenshots/clearway-demo.webp
"""
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websocket
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8797/api/"
PORT = 8792
CDP_PORT = 9333
FRAMES = ROOT / "build" / "demo_frames"
OUT = ROOT / "dist" / "screenshots" / "clearway-demo.webp"
MAX_BYTES = 9_500_000
CLIP = {"x": 0, "y": 150, "width": 1024, "height": 576, "scale": 1}   # x1.5625 device scale -> 1600x900


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def translate_path(self, path):
        path = path.split("?")[0]
        if path in ("/", "/index.html"):
            return str(ROOT / "tools" / "demo_anim" / "flight.html")
        if path.startswith("/html_ui/"):
            return str(ROOT / "msfs-panel" / path.lstrip("/"))
        return str(ROOT / "missing")


def call(path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


def prepare():
    """Radios set, a bit of frequency history, nothing unread.
    Start from a freshly started tools/dev_run.py: deleting old messages here would show a
    "deleted / Show" line in the card (deleted vPilot messages are not shown, so those go)."""
    vp_kinds = {"pm", "radio", "broadcast", "selcal", "vinfo", "vsys"}
    msgs = call("state?since=0")["messages"]
    if any(m["kind"] not in vp_kinds and m["dir"] != "sys" for m in msgs):
        sys.exit("The test Clearway already has CPDLC messages: restart tools/dev_run.py, then the fake vPilot.")
    for m in msgs:
        if m["kind"] in vp_kinds:
            call("delete", {"id": m["id"]})
    call("connect", {})
    call("com", {"com1": "118.500", "com1_stby": "121.975", "com1_tx": True,
                 "com2": "121.500", "com2_stby": "122.800", "com2_tx": False})
    for frm, msg in [("EGLL_TWR", "AFR1681 line up and wait runway 27R"),
                     ("EGLL_TWR", "AFR1681 wind 250 degrees 8 knots, runway 27R cleared for take-off"),
                     ("EGLL_TWR", "SHT8K contact Heathrow Departure 120.525, goodbye")]:
        call("vpilot/event", {"type": "radio", "from": frm, "message": msg, "frequencies": "118.500"})
        time.sleep(0.15)
    time.sleep(1)
    call("ack", {})
    # vPilot part of the demo: SimBrief name set (the mock serves the plan), no flight plan filed yet, and the
    # fake vPilot disconnected so the connect form can be shown
    call("settings", {"simbrief_user": "demo"})
    urllib.request.urlopen("http://127.0.0.1:8790/fp?set=none", timeout=5).read()
    call("vp/disconnect", {})
    for _ in range(20):
        if not call("state?since=0")["vpilot"]["connected"]:
            break
        time.sleep(0.3)


def radar_view():
    """Load the radar data, then centre the view on the busiest airborne traffic (labels readable after one
    zoom-in in the demo). Returns "x,y,z" for flight.html's ?rv= parameter."""
    for _ in range(90):
        t = call("radar/traffic")
        if t.get("pilots"):
            break
        time.sleep(1)
    else:
        sys.exit("Radar data didn't load")
    call("radar/atc")
    pilots, best, plane = t["pilots"], -1, None      # [cs, lat, lon, alt, gs, ...]
    for p in pilots:
        if 4000 <= p[3] <= 24000 and p[4] > 150:
            n = sum(1 for q in pilots if abs(q[1] - p[1]) < 0.9 and abs(q[2] - p[2]) < 1.4)
            if n > best:
                best, plane = n, p
    s = math.sin(math.radians(plane[1]))
    x, y = (plane[2] + 180) / 360, 0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)
    print(f"radar centred near {plane[0]} ({best} planes around)")
    # your aircraft (the demo's stand-in sim position) a little south-east of that plane, flying north-west
    me = f"{plane[1] - 0.25:.4f},{plane[2] + 0.35:.4f}"
    return f"{x:.6f},{y:.6f},7.0", me


class Cdp:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=30, suppress_origin=True)
        self.n = 0

    def __call__(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.n:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(self, expr):
        return self("Runtime.evaluate", expression=expr, returnByValue=True).get("result", {}).get("value")


def edge_path():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        p = Path(base or "") / "Microsoft" / "Edge" / "Application" / "msedge.exe"
        if p.exists():
            return str(p)
    sys.exit("Microsoft Edge not found")


def record(rv, me):
    shutil.rmtree(FRAMES, ignore_errors=True)
    FRAMES.mkdir(parents=True)
    profile = tempfile.mkdtemp(prefix="cw-demo-")
    edge = subprocess.Popen([edge_path(), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                             f"--user-data-dir={profile}", f"--remote-debugging-port={CDP_PORT}",
                             "--window-size=1920,1080", "about:blank"])
    try:
        for _ in range(50):
            try:
                targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2).read())
                page = next(t for t in targets if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        else:
            sys.exit("Edge did not start")
        cdp = Cdp(page["webSocketDebuggerUrl"])
        cdp("Emulation.setDeviceMetricsOverride", width=1920, height=1080, deviceScaleFactor=1.5625, mobile=False)
        cdp("Page.enable")
        cdp("Page.navigate", url=f"http://127.0.0.1:{PORT}/?rv={rv}&me={me}")
        for _ in range(200):
            if cdp.js("window.__ready === true"):
                break
            time.sleep(0.1)
        else:
            sys.exit("Demo page never got ready (is tools/dev_run.py running on 8797?)")
        cdp.js("window.__go()")
        frames, t0 = [], time.time()
        while True:
            shot = cdp("Page.captureScreenshot", format="png", clip=CLIP)
            t = time.time() - t0
            path = FRAMES / f"{len(frames):05d}.png"
            path.write_bytes(base64.b64decode(shot["data"]))
            frames.append((path, t))
            if len(frames) % 8 == 0 and cdp.js("window.__done === true"):
                break
            if t > 420:
                break
        err = cdp.js("window.__error || ''")
        if err:
            print("Script error:", err)
        print(f"{len(frames)} frames in {frames[-1][1]:.1f} s ({len(frames) / frames[-1][1]:.1f} fps)")
        return frames
    finally:
        edge.terminate()
        time.sleep(1)
        shutil.rmtree(profile, ignore_errors=True)


def encode(frames):
    images, durations, last = [], [], None
    for i, (path, t) in enumerate(frames):
        nxt = frames[i + 1][1] if i + 1 < len(frames) else t + 2.0     # hold the last frame 2 s
        data = path.read_bytes()
        if data == last:
            durations[-1] += (nxt - t) * 1000
            continue
        last = data
        images.append(Image.open(path).convert("RGB"))
        durations.append((nxt - t) * 1000)
    durations = [max(20, int(round(d))) for d in durations]
    print(f"{len(images)} distinct frames")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for quality in (92, 85, 78, 70, 60, 50):
        images[0].save(OUT, save_all=True, append_images=images[1:], duration=durations, loop=0,
                       quality=quality, method=5, minimize_size=True, allow_mixed=False)
        size = OUT.stat().st_size
        print(f"quality {quality}: {size / 1e6:.2f} MB")
        if size <= MAX_BYTES:
            break
    return OUT


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    prepare()
    frames = record(*radar_view())
    server.shutdown()
    if "--no-encode" not in sys.argv:
        print("Saved", encode(frames))


if __name__ == "__main__":
    main()
