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
# TSAT clock: never ask the real vIFF server from the test Clearway; tools/mock_viff.py answers on 8792
os.environ.setdefault("CLEARWAY_VIFF_URL", "http://127.0.0.1:8792")
# "quit when vPilot closes" watches a process name nobody runs, so the test Clearway never follows the real vPilot
os.environ.setdefault("CLEARWAY_VPILOT_EXE", "no-such-vpilot-dev-run.exe")

cfg_file = DATA / "config.json"
cfg = json.loads(cfg_file.read_text()) if cfg_file.exists() else {}
cfg.update({
    "hoppie_logon": cfg.get("hoppie_logon") or "TESTLOGON123",
    "callsign_override": cfg.get("callsign_override") or "BAW117",
    "vatsim_cid": cfg.get("vatsim_cid") or "1000000",     # a made-up CID (TSAT User-Agent test)
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

# SimBrief comes from the mock server (no real account); the flight plan status too when CLEARWAY_FAKE_FP=1
# (switch it with http://127.0.0.1:8790/fp?set=filed / none), so the vPilot "FP status" warning can be shown.
import time  # noqa: E402
import urllib.request as _ur  # noqa: E402
from clearway import selcal as _selcal  # noqa: E402
_selcal.SIMBRIEF_URL = "http://127.0.0.1:8790/simbrief"
if os.environ.get("CLEARWAY_FAKE_FP") == "1":
    def _fake_fp_loop(self):
        while True:
            time.sleep(1)
            on = self.vpilot_connected and self.vpilot_active() and not self.vpilot_observer
            try:
                status = json.loads(_ur.urlopen("http://127.0.0.1:8790/fp", timeout=3).read())["status"] if on else None
            except Exception:
                continue
            if status != self.fp_status:
                with self.lock:
                    self.fp_status = status
                    self._bump()
    _selcal.SelcalMixin._fp_loop = _fake_fp_loop
if "--tray" not in sys.argv:
    sys.argv.append("--console")
clearway_app.main()
