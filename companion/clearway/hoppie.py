"""Minimal client for the Hoppie ACARS network (https://www.hoppie.nl/acars/).

Only the HTTP transport and response parsing live here; CPDLC logic is in session.py.
"""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .textfix import decode_bytes, repair

USER_AGENT = "Clearway-CPDLC/1.0"
TIMEOUT = 15  # seconds, as requested by the Hoppie documentation


class HoppieError(Exception):
    pass


@dataclass
class Incoming:
    sender: str
    kind: str      # lower case: cpdlc, telex, ads-c, inforeq, ...
    packet: str


def _top_level_groups(text: str) -> list[str]:
    """Return the contents of each top-level {...} group, honouring nesting."""
    groups, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0:
                groups.append(text[start:i])
    return groups


def parse_response(text: str) -> list[Incoming]:
    """Parse a connect.html reply.

    Replies look like ``ok`` or ``ok {SENDER type {packet}} {SENDER type {packet}}``.
    Errors look like ``error {reason}``. Some replies (e.g. inforeq) can carry a plain
    ``{text}`` group, which is returned as a message from SERVER.
    """
    stripped = text.strip()
    if stripped.lower().startswith("error"):
        groups = _top_level_groups(stripped)
        raise HoppieError(groups[0] if groups else stripped)
    if not stripped.lower().startswith("ok"):
        raise HoppieError(stripped[:200] or "empty reply")

    messages: list[Incoming] = []
    for group in _top_level_groups(stripped[2:]):
        inner = _top_level_groups(group)
        if inner:
            head = group[: group.index("{")].split()
            sender = head[0] if head else "SERVER"
            kind = head[1].lower() if len(head) > 1 else "telex"
            messages.append(Incoming(sender.upper(), kind, inner[0].strip()))
        elif group.strip():
            messages.append(Incoming("SERVER", "telex", group.strip()))
    return messages


class HoppieClient:
    def __init__(self, url: str, logon: str):
        self.url = url
        self.logon = logon

    def send(self, sender: str, to: str, kind: str, packet: str = "") -> list[Incoming]:
        body = urllib.parse.urlencode({
            "logon": self.logon,
            "from": sender,
            "to": to,
            "type": kind,
            "packet": packet,
        }, encoding="cp1252", errors="replace").encode()   # Hoppie clients use Western-European text
        req = urllib.request.Request(self.url, data=body, headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                text = repair(decode_bytes(resp.read()))   # accents: UTF-8 or Windows-1252
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HoppieError(f"network error: {exc}") from exc
        return parse_response(text)


# ---------------------------------------------------------------- CPDLC packets

_CPDLC_RE = re.compile(r"^/data2/(\d*)/(\d*)/([A-Z]*)/(.*)$", re.IGNORECASE | re.DOTALL)


@dataclass
class CpdlcPacket:
    min: int | None      # message identification number
    mrn: int | None      # message reference number (the message this one answers)
    ra: str              # response attribute: WU, AN, R, Y, N, NE
    text: str


def parse_cpdlc(packet: str) -> CpdlcPacket | None:
    m = _CPDLC_RE.match(packet.strip())
    if not m:
        return None
    min_, mrn, ra, text = m.groups()
    return CpdlcPacket(int(min_) if min_ else None, int(mrn) if mrn else None, ra.upper(), text.strip())


def build_cpdlc(min_: int, mrn: int | None, ra: str, text: str) -> str:
    return f"/data2/{min_}/{'' if mrn is None else mrn}/{ra}/{text}"
