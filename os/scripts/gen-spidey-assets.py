#!/usr/bin/env python3
"""Generate Karen OS spidey assets (pure stdlib - no PIL):
  1. 1920x1080 desktop wallpaper      -> airootfs/opt/karen-linux/assets/wallpaper.png
  2. Plymouth theme: spider logo + 8 spinner frames -> airootfs/usr/share/plymouth/themes/karen-spidey/
Run from repo root: python os/scripts/gen-spidey-assets.py
"""

import math, os, struct, sys, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def png_write(path, w, h, pixels):
    rows = bytearray()
    for y in range(h):
        rows.append(0)
        rows.extend(pixels[y * w * 3:(y + 1) * w * 3])

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(rows), 9))
    out += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)
    print(f"  {path}  ({w}x{h}, {len(out)} bytes)")


def blend(c1, c2, a):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


NAVY_TOP = (0x0A, 0x0C, 0x18)
NAVY_BOT = (0x13, 0x1A, 0x33)
RED = (0xE3, 0x1C, 0x23)
DARK = (0xB1, 0x13, 0x13)
WEB_FAINT = (0x1B, 0x24, 0x47)


def wallpaper():
    w, h = 1920, 1080
    cx, cy = 960, 520
    px = bytearray(w * h * 3)
    i = 0
    for y in range(h):
        t = y / (h - 1)
        bg = tuple(int(NAVY_TOP[k] + (NAVY_BOT[k] - NAVY_TOP[k]) * t) for k in range(3))
        for x in range(w):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            col = bg
            if 0.5 < d <= 560:
                a = math.atan2(dy, dx)
                spoke = any(abs(((a + 2 * math.pi * k) - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi) < 0.0085
                            for k in range(12))
                if spoke and d > 90:
                    col = blend(col, WEB_FAINT, 0.9)
                if abs(d - 480) <= 4:
                    col = blend(col, RED, 1.0)
                elif abs(d - 340) <= 2.4 or abs(d - 250) <= 2.4:
                    col = blend(col, DARK, 0.9)
                elif d <= 13:
                    col = RED
            v = 1.0 - min(1.0, max(0.0, (d - 700) / 450)) * 0.55
            px[i] = int(col[0] * v)
            px[i + 1] = int(col[1] * v)
            px[i + 2] = int(col[2] * v)
            i += 3
    png_write(os.path.join(ROOT, "os", "profiles", "karenos", "airootfs", "opt", "karen-linux", "assets", "wallpaper.png"),
              w, h, px)


def plymouth_theme():
    d = os.path.join(ROOT, "os", "profiles", "karenos", "airootfs", "usr", "share", "plymouth", "themes", "karen-spidey")

    def frame(size, draw):
        px = bytearray(size * size * 4)
        i = 0
        for y in range(size):
            for x in range(size):
                r, g, b, a = draw(x, y)
                px[i], px[i + 1], px[i + 2], px[i + 3] = r, g, b, a
                i += 4
        rows = bytearray()
        for y in range(size):
            rows.append(0)
            rows.extend(px[y * size * 4:(y + 1) * size * 4])

        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

        out = b"\x89PNG\r\n\x1a\n"
        out += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        out += chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        out += chunk(b"IEND", b"")
        return out

    s = 128
    c = s // 2

    def logo(x, y):
        dx, dy = x - c, y - c
        d = math.hypot(dx, dy)
        if d <= 13:
            return (*RED, 255)
        if abs(d - 58) <= 5:
            return (*RED, 255)
        if abs(d - 38) <= 3 or abs(d - 26) <= 2:
            return (*DARK, 220)
        if 0.5 < d <= 70:
            a = math.atan2(dy, dx)
            if any(abs(((a + 2 * math.pi * k) - math.pi / 2 + math.pi) % (2 * math.pi) - math.pi) < 0.05 for k in range(12)):
                return (*DARK, 160)
        return (0, 0, 0, 0)

    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "spider.png"), "wb") as f:
        f.write(frame(s, logo))
    print(f"  {os.path.join(d, 'spider.png')} (logo)")

    def spinner(i):
        a0 = math.radians(i * 45 - 30)
        a1 = a0 + math.radians(70)

        def draw(x, y):
            dx, dy = x - c, y - c
            d = math.hypot(dx, dy)
            if 34 <= d <= 58:
                a = math.atan2(dy, dx)
                a = (a + 2 * math.pi) % (2 * math.pi)
                if a0 <= a <= a1 or a0 <= a + 2 * math.pi <= a1:
                    return (*RED, 255)
            if d <= 6:
                return (*RED, 255)
            return (0, 0, 0, 0)

        return frame(s, draw)

    for i in range(8):
        with open(os.path.join(d, f"frame{i}.png"), "wb") as f:
            f.write(spinner(i))
    print(f"  {d}/frame0..7.png (spinner)")


if __name__ == "__main__":
    wallpaper()
    plymouth_theme()
    print("done")