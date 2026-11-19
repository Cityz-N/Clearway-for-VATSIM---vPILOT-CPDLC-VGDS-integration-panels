"""TSAT start-up window from the vIFF / CDM network (the data behind vats.im/vdgs).

You submit your TOBT on the VDGS website; Clearway then reads your own flight's TOBT / TSAT / CTOT from
the public vIFF API so the panel clock can count down to the start-up window. Read only, no login.

Kept light on the community server:
- only while vPilot is connected (not as an observer), your flight is in the VATSIM data with a departure
  airport, and you're on the ground;
- one request for your departure airport every 3 minutes until a TSAT appears;
- then nothing more, unless the flight has a CTOT (checked once a minute, CTOTs move);
- it stops after take-off. Only your own flight is kept; everyone else's data is dropped at once.
It needs your VATSIM CID (Settings): the User-Agent is just that CID, so the vIFF operators can see who asks.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import threading
import time
import urllib.parse
import urllib.request

log = logging.getLogger("clearway.tsat")

VIFF_URL = os.environ.get("CLEARWAY_VIFF_URL", "https://api.viffsys.com").rstrip("/")
WAIT_FOR_TSAT = 180        # seconds between checks until a TSAT is set
WITH_CTOT = 60             # seconds between checks while the flight has a CTOT
AIRBORNE_GS = 50           # kt: above this you've left the ground
LOOP = 10                  # seconds between looks at the conditions (no request)


def _hhmm_to_ms(hhmm: str, now: float) -> int | None:
    """'1412' (UTC) -> epoch ms of the nearest such time to now (handles midnight)."""
    s = str(hhmm or "").strip().replace(":", "")
    if len(s) != 4 or not s.isdigit() or int(s[:2]) > 23 or int(s[2:]) > 59:
        return None
    today = dt.datetime.fromtimestamp(now, dt.timezone.utc).replace(hour=int(s[:2]), minute=int(s[2:]), second=0, microsecond=0)
    best = min((today + dt.timedelta(days=d) for d in (-1, 0, 1)), key=lambda t: abs(t.timestamp() - now))
    return int(best.timestamp() * 1000)


class TsatMixin:
    def _tsat_init(self) -> None:
        self.tsat: dict | None = None          # what the panel shows (None = no TSAT clock)
        self.tsat_error = ""
        self._tsat_key: tuple | None = None    # (callsign, departure) being followed
        self._tsat_next = 0.0                  # when the next request may go out (0 = now)
        self._tsat_done = False                # TSAT found without a CTOT: no more requests for this flight
        threading.Thread(target=self._tsat_loop, daemon=True, name="tsat").start()

    def _tsat_clear(self) -> None:
        if self.tsat is not None or self._tsat_key is not None:
            with self.lock:
                self.tsat = None
                self._tsat_key = None
                self._tsat_done = False
                self._tsat_next = 0.0
                self._bump()

    def _tsat_loop(self) -> None:
        while True:
            time.sleep(LOOP)
            try:
                self._tsat_tick()
            except Exception:                  # never let the thread die
                log.exception("TSAT check failed")

    def _tsat_tick(self) -> None:
        if not self.cfg.get("vdgs_tsat"):
            return self._tsat_clear()
        connected = self.vpilot_connected and self.vpilot_active() and not self.vpilot_observer
        cs = str(self.vpilot_callsign or "").upper()
        cid = str(self.cfg.get("vatsim_cid") or "").strip()
        if not connected or not cs or not cid.isdigit():
            return self._tsat_clear()          # needs VATSIM (vPilot) and your VATSIM CID in Settings
        feed = self._feed if self._feed and time.time() - self._feed["ts"] < 120 else self._vatsim_feed(max_age=60)
        me = (feed or {}).get("moving", {}).get(cs)
        if not me or not me["dep"]:
            return                             # not in the VATSIM data yet, or no flight plan: wait
        if (me["gs"] or 0) > AIRBORNE_GS:
            return self._tsat_clear()          # airborne: the start-up window is over
        key = (cs, me["dep"])
        if key != self._tsat_key:              # new flight (or new departure airport): start again
            with self.lock:
                self._tsat_key = key
                self.tsat = None
                self._tsat_done = False
                self._tsat_next = 0.0
                self._bump()
        if self._tsat_done or time.time() < self._tsat_next:
            return
        self._tsat_fetch(cs, me["dep"])

    def _tsat_fetch(self, cs: str, dep: str) -> None:
        cid = str(self.cfg.get("vatsim_cid") or "").strip()
        if not cid.isdigit():
            return
        ua = cid                               # the User-Agent is your VATSIM CID, nothing else
        url = f"{VIFF_URL}/ifps/depAirport?airport={urllib.parse.quote(dep)}"
        self._tsat_next = time.time() + WAIT_FOR_TSAT
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception as exc:
            log.info("vIFF not reachable: %s", exc)
            with self.lock:
                self.tsat_error = "CDM data not reachable"
            return
        mine = next((f for f in data if isinstance(f, dict) and str(f.get("callsign", "")).upper() == cs), None) \
            if isinstance(data, list) else None
        del data                               # other pilots' data isn't kept
        info = None
        if mine:
            cdm = mine.get("cdmData") or {}
            now = time.time()
            tsat = str(cdm.get("tsat") or "")
            ctot = str(mine.get("ctot") or cdm.get("ctot") or "")
            tsat_ms = _hhmm_to_ms(tsat, now)
            if mine.get("atot"):
                return self._tsat_clear()      # already took off
            if tsat_ms:
                info = {
                    "callsign": cs, "airport": dep,
                    "tobt": str(cdm.get("tobt") or mine.get("tobt") or ""), "tsat": tsat,
                    "ttot": str(cdm.get("ttot") or ""), "ctot": ctot,
                    "status": str(mine.get("cdmSts") or ""),
                    "tsat_ms": tsat_ms, "fetched": int(now * 1000),
                }
                if ctot:
                    self._tsat_next = now + WITH_CTOT
                else:
                    self._tsat_done = True     # one TSAT is enough without a CTOT
        with self.lock:
            self.tsat_error = ""
            if info != self.tsat:
                self.tsat = info
                self._bump()
