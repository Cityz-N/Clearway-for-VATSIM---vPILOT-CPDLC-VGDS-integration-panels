"""Purpose labels for CPDLC/telex messages (DCL, CLEARANCE, OCEANIC, LOGON, REQUEST, METAR...).

The label is only for display; message handling still uses the message "kind".
"""
from __future__ import annotations

import re

# "CLR TO LFML...", "CLEARED BAW117 AS FILED...", "PDC ...", "DEPARTURE CLEARANCE ..."
_CLEARANCE = re.compile(r"\b(CLR|CLRD|CLEARED|CLEARANCE|PDC|DCL)\b")


def classify(msg: dict, parent: dict | None = None) -> str:
    kind, direction = msg.get("kind"), msg.get("dir")
    text = str(msg.get("text", "")).upper().replace("@", "")
    if kind in ("cpdlc", "telex"):
        if direction == "out":
            if text.startswith("REQUEST PREDEP CLEARANCE"):
                return "DCL"
            if text.startswith("OCEANIC CLEARANCE REQUEST"):
                return "OCEANIC"
            if text.startswith("REQUEST LOGON") or text == "LOGOFF":
                return "LOGON"
            if text.startswith("REQUEST") or text.startswith("WHEN CAN WE EXPECT"):
                return "REQUEST"
            if parent is not None and parent.get("tag"):
                return parent["tag"]          # a reply carries the label of what it answers
        else:
            if text.startswith(("LOGON", "LOGOFF", "HANDOVER", "CURRENT ATC UNIT", "CURRENT ATS UNIT")):
                return "LOGON"
            if "OCEANIC" in text and ("CLEARED" in text or "CLRD" in text or "CLEARANCE" in text):
                return "OCEANIC"
            if _CLEARANCE.search(text):
                return "CLEARANCE"
            if parent is not None and parent.get("tag") == "REQUEST":
                return "REQUEST"              # ATC's answer to one of your requests
        return "CPDLC" if kind == "cpdlc" else "TELEX"
    if kind == "info":
        for word in ("METAR", "TAF", "ATIS"):
            if text.startswith(word):
                return word
        if parent is not None and parent.get("tag") in ("METAR", "TAF", "ATIS"):
            return parent["tag"]
        if "ATIS" in text or "INFORMATION" in text:
            return "ATIS"
        if re.match(r"^[A-Z]{4} \d{6}Z", text):
            return "METAR"
        return "INFO"
    return ""
