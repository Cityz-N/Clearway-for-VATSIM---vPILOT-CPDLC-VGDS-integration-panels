"""Render the Clearway app icon to PNG (no third-party packages needed).

Usage: python tools/make_icons.py
Writes companion/web/icon-180.png and icon-512.png. iOS needs a PNG home-screen icon.
"""
import math
import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "companion" / "web"


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def bubble(x, y):
    # Ellipse centred (32,30.5) radii 19 x 16.5, plus a tail towards (18,51). Units: 64-grid.
    if ((x - 32) / 19) ** 2 + ((y - 30.5) / 16.5) ** 2 <= 1:
        return True
    # tail triangle
    ax, ay, bx, by, cx, cy = 19, 40, 18, 51, 28, 46
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / d
    l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / d
    return l1 >= 0 and l2 >= 0 and 1 - l1 - l2 >= 0


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def check(x, y):
    return min(seg_dist(x, y, 24, 31.5, 29.5, 37), seg_dist(x, y, 29.5, 37, 41, 25.5)) <= 2


def inside_rounded(x, y, r=16):
    cx = min(max(x, r), 64 - r)
    cy = min(max(y, r), 64 - r)
    return math.hypot(x - cx, y - cy) <= r


def render(size, rounded):
    ss = 3
    rows = []
    c1, c2 = (238, 242, 255), (223, 231, 255)
    accent, white = (91, 124, 250), (255, 255, 255)
    for py in range(size):
        row = bytearray([0])
        for px in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    x = (px + (sx + .5) / ss) * 64 / size
                    y = (py + (sy + .5) / ss) * 64 / size
                    if rounded and not inside_rounded(x, y):
                        continue
                    col = lerp(c1, c2, (x + y) / 128)
                    if bubble(x, y):
                        col = white if check(x, y) else accent
                    acc[0] += col[0]; acc[1] += col[1]; acc[2] += col[2]; acc[3] += 255
            n = ss * ss
            a = acc[3] / n
            if a:
                row += bytes([int(acc[0] / (acc[3] / 255)), int(acc[1] / (acc[3] / 255)), int(acc[2] / (acc[3] / 255)), int(a)])
            else:
                row += bytes([0, 0, 0, 0])
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    # iOS applies its own rounded mask, so the PNGs are full squares.
    (OUT / "icon-180.png").write_bytes(render(180, rounded=False))
    (OUT / "icon-512.png").write_bytes(render(512, rounded=False))
    # Windows .ico for Clearway.exe (a single 256 px PNG entry, supported since Vista)
    png = render(256, rounded=True)
    ico = struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png
    (OUT / "clearway.ico").write_bytes(ico)   # used for Clearway.exe and the tray icon
    print("icons written to", OUT)
