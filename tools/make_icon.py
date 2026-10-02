# -*- coding: utf-8 -*-
"""生成应用图标 icon.ico（纯标准库：手写 PNG + ICO 封装）

用法：python build_tools/make_icon.py [输出路径]
"""
import struct
import sys
import zlib
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else
           Path(__file__).resolve().parents[1] / "src" / "icon.ico")

SIZE = 256


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def sdf_round_box(px, py, cx, cy, hw, hh, r):
    qx = abs(px - cx) - (hw - r)
    qy = abs(py - cy) - (hh - r)
    ox, oy = max(qx, 0.0), max(qy, 0.0)
    outside = (ox * ox + oy * oy) ** 0.5
    inside = min(max(qx, qy), 0.0)
    return outside + inside - r


def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    c1 = vx * wx + vy * wy
    c2 = vx * vx + vy * vy
    t = c1 / c2 if c2 > 0 else 0.0
    t = _clamp(t, 0.0, 1.0)
    dx, dy = px - (ax + t * vx), py - (ay + t * vy)
    return (dx * dx + dy * dy) ** 0.5


def tri_sdf(px, py, a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = min(seg_dist(px, py, ax, ay, bx, by),
            seg_dist(px, py, bx, by, cx, cy),
            seg_dist(px, py, cx, cy, ax, ay))
    s1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    s2 = (cx - bx) * (py - by) - (cy - by) * (px - bx)
    s3 = (ax - cx) * (py - cy) - (ay - cy) * (px - cx)
    neg = (s1 < 0) or (s2 < 0) or (s3 < 0)
    pos = (s1 > 0) or (s2 > 0) or (s3 > 0)
    return d if (neg and pos) else (-d if not neg else d)


def cover(d, aa=1.0):
    """SDF 距离 -> alpha 覆盖率"""
    return _clamp(0.5 - d / aa, 0.0, 1.0)


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


PINK = (240, 145, 153)
BLUE = (122, 162, 247)
WHITE = (255, 255, 255)
ACCENT = (226, 122, 134)


def render():
    rows = []
    for y in range(SIZE):
        row = bytearray([0])  # filter type 0
        for x in range(SIZE):
            px, py = x + 0.5, y + 0.5
            # 1. 圆角渐变底
            d_bg = sdf_round_box(px, py, SIZE / 2, SIZE / 2, SIZE / 2 - 2, SIZE / 2 - 2, 62)
            a_bg = cover(d_bg)
            if a_bg <= 0:
                row += b"\x00\x00\x00\x00"
                continue
            t = (x + y) / (2 * (SIZE - 1))
            bg = lerp(PINK, BLUE, t)
            r, g, b = bg[0], bg[1], bg[2]
            a = a_bg
            # 2. 白色电视框
            d_tv = sdf_round_box(px, py, SIZE / 2, SIZE / 2, 78, 46, 18)
            a_tv = cover(d_tv)
            if a_tv > 0:
                r = r * (1 - a_tv) + WHITE[0] * a_tv
                g = g * (1 - a_tv) + WHITE[1] * a_tv
                b = b * (1 - a_tv) + WHITE[2] * a_tv
            # 3. 粉色播放三角
            d_tri = tri_sdf(px, py, (104, 100), (104, 156), (166, 128))
            a_tri = cover(d_tri)
            if a_tri > 0:
                r = r * (1 - a_tri) + ACCENT[0] * a_tri
                g = g * (1 - a_tri) + ACCENT[1] * a_tri
                b = b * (1 - a_tri) + ACCENT[2] * a_tri
            row += bytes((int(r), int(g), int(b), int(a * 255)))
        rows.append(bytes(row))
    return b"".join(rows)


def png_chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def make_png(raw):
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" +
            png_chunk(b"IHDR", ihdr) +
            png_chunk(b"IDAT", zlib.compress(raw, 9)) +
            png_chunk(b"IEND", b""))


def main():
    png = make_png(render())
    ico = (struct.pack("<HHH", 0, 1, 1) +
           struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) +
           png)
    OUT.write_bytes(ico)
    print(f"图标已生成: {OUT}（{len(ico)} 字节）")


if __name__ == "__main__":
    main()
