"""VATSIM live data lookups (callsign, flight plan, position)."""
from __future__ import annotations

import gzip
import json
import urllib.request

FEED_URL = "https://data.vatsim.net/v3/vatsim-data.json"


def fetch_pilot(cid: str) -> dict | None:
    """Return the pilot entry for a VATSIM CID, or None if not connected."""
    req = urllib.request.Request(FEED_URL, headers={
        "User-Agent": "Clearway-CPDLC/1.0",
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
    data = json.loads(raw)
    try:
        cid_int = int(str(cid).strip())
    except ValueError:
        return None
    for pilot in data.get("pilots", []):
        if pilot.get("cid") == cid_int:
            return pilot
    return None


def summarize(pilot: dict) -> dict:
    fp = pilot.get("flight_plan") or {}
    return {
        "callsign": pilot.get("callsign", ""),
        "departure": fp.get("departure", ""),
        "arrival": fp.get("arrival", ""),
        "aircraft": fp.get("aircraft_short") or fp.get("aircraft", ""),
        "cruise": fp.get("altitude", ""),
        "lat": pilot.get("latitude"),
        "lon": pilot.get("longitude"),
        "alt": pilot.get("altitude"),
    }
