"""Run Clearway against the mock Hoppie server, with a throwaway config in .dev-data/.

Usage: python tools/dev_run.py   then open http://localhost:8787/
Your real settings in %APPDATA%\\Clearway are not touched.
"""
import json
import os
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / ".dev-data"
DATA.mkdir(exist_ok=True)
os.environ["CLEARWAY_DATA_DIR"] = str(DATA)
# The test Clearway never holds the real keyboard (a panel field focused in a browser would otherwise make it
# swallow keys typed into a running MSFS). Set CLEARWAY_KEY_TARGETS yourself to test the keyboard hook.
os.environ.setdefault("CLEARWAY_KEY_TARGETS", "no-such-program-dev-run.exe")

cfg_file = DATA / "config.json"
cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}
cfg.update({
    "hoppie_logon": cfg.get("hoppie_logon") or "TESTLOGON123",
    "callsign_override": cfg.get("callsign_override") or "BAW117",
    "hoppie_url": "http://127.0.0.1:8790/connect.html",
    "ntfy_enabled": False,
    # a separate port, so a real vPilot/Clearway plugin on 8787 never talks to the test server
    "port": 8797,
    "open_browser_on_start": False,
})
cfg_file.write_text(json.dumps(cfg, indent=2))

sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "companion"))
import mock_hoppie  # noqa: E402
import clearway_app  # noqa: E402

threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8790), mock_hoppie.H).serve_forever, daemon=True).start()
if "--tray" not in sys.argv:
    sys.argv.append("--console")
clearway_app.main()
