"""Make text from the networks display correctly (accents such as é, è, à, ç, ü).

Hoppie and VATSIM date from before UTF-8 was common: some clients send UTF-8, others the
old Western-European encoding (Windows-1252). Mixed up, "é" arrives as "Ã©" or "�".
"""
from __future__ import annotations

import re

# "Ã©", "Ã¨", "Ã§", "â€™" ... : UTF-8 bytes that were read as Windows-1252
_MOJIBAKE = re.compile("[ÂÃâ][\u0080-¿‘-›ŒœŠšŸŽžƒˆ˜€™]")


def decode_bytes(raw: bytes) -> str:
    """Decode a network reply: UTF-8 if it is valid UTF-8, otherwise Windows-1252."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def repair(text: str) -> str:
    """Undo the classic "Ã©" mix-up; leave anything else untouched."""
    if not text or not _MOJIBAKE.search(text):
        return text
    try:
        fixed = text.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    return fixed
