"""Fake vIFF CDM server for testing Clearway's TSAT clock (tools/dev_run.py).

    python tools/mock_viff.py CALLSIGN [TSAT offset minutes, default 8] [--ctot] [--suggested]

Serves GET /ifps/depAirport?airport=XXXX on port 8792 with one flight: CALLSIGN with a TSAT that many
minutes from the moment the server starts (and a CTOT 20 minutes after it with --ctot). Every request is
printed with its User-Agent, so the polling rhythm can be checked. Start dev_run with
CLEARWAY_VIFF_URL=http://127.0.0.1:8792
"""
import datetime as dt
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CS = sys.argv[1].upper() if len(sys.argv) > 1 else "TEST123"
OFFSET = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 8
CTOT = "--ctot" in sys.argv
SUGGESTED = "--suggested" in sys.argv     # TOBT only, no TSAT (no CDM controller online)
T0 = time.time()


def hhmm(t: float) -> str:
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%H%M")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        tsat = T0 + OFFSET * 60
        flight = {"callsign": CS, "departure": "XXXX", "atot": "", "ctot": hhmm(tsat + 1200) if CTOT else "",
                  "cdmSts": "COMPLY", "cdmData": {"tobt": hhmm(tsat - 300) + "00", "tsat": hhmm(tsat) + "00",
                                                  "ttot": hhmm(tsat + 900) + "00",   # live cdmData: HHMMSS
                                                  "ctot": hhmm(tsat + 1200) if CTOT else ""}}
        if SUGGESTED:      # no CDM controller online: only the pilot's TOBT, no TSAT (like a real record)
            flight = {"callsign": CS, "departure": "XXXX", "atot": "", "ctot": "", "cdmSts": "", "tobt": hhmm(tsat),
                      "reqTobt": hhmm(tsat), "cdmData": {"tobt": "", "tsat": "", "ttot": "", "ctot": "",
                                                         "reqTobt": hhmm(tsat), "reqTobtType": "PILOT", "confirmed": True}}
        other = {"callsign": "OTHER1", "cid": "999", "cdmData": {"tsat": "0000"}}
        body = json.dumps([other, flight]).encode()
        print(time.strftime("%H:%M:%S"), self.path, "UA:", self.headers.get("User-Agent"), flush=True)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


print(f"mock vIFF on 8792: {CS} TSAT {hhmm(T0 + OFFSET * 60)}z{' with CTOT' if CTOT else ''}", flush=True)
ThreadingHTTPServer(("127.0.0.1", 8792), H).serve_forever()
