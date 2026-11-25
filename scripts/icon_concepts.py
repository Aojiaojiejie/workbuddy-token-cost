#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 6 版应用图标候选效果图，供定稿前比较。

输出：assets/design/concepts/ 下每版 512px 透明 PNG + 一张编号对照图 icon_concepts_sheet.png。
选定编号后，再由 make_icon.py 生成正式 ICO 并打包进 exe。
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "design"
CONCEPT_DIR = OUT / "concepts"
S = 1024
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def grad_round(canvas: Image.Image, s: int, top, bottom, radius=0.225) -> None:
    bg = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(bg)
    for y in range(s):
        t = y / max(1, s - 1)
        c = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,)
        d.line([(0, y), (s, y)], fill=c)
    m = Image.new("L", (s, s), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, s - 1, s - 1), radius=round(radius * s), fill=255)
    canvas.paste(bg, (0, 0), m)


def geom_yen(d: ImageDraw.ImageDraw, s: int, cx: float, cy: float,
             color, w: float, scale: float = 1.0) -> None:
    """用几何线条画 ¥，避免字体的小尺寸糊边。"""
    u = 0.30 * s * scale
    v_top = cy - 0.20 * s * scale
    v_mid = cy + 0.02 * s * scale
    v_bot = cy + 0.24 * s * scale
    d.line([(cx - u, v_top), (cx, v_mid), (cx + u, v_top)],
           fill=color, width=round(w), joint="curve")
    d.line([(cx, v_mid), (cx, v_bot)], fill=color, width=round(w))
    for dy in (0.065, 0.155):
        d.line([(cx - u * 0.82, cy + dy * s * scale),
                (cx + u * 0.82, cy + dy * s * scale)],
               fill=color, width=round(w * 0.82))
    r = w / 2
    for x, y in ((cx - u, v_top), (cx + u, v_top), (cx, v_bot)):
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def cap_line(d: ImageDraw.ImageDraw, pts, fill, width: float) -> None:
    d.line(pts, fill=fill, width=round(width), joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


# ---------- 方案 1：极简柱状仪表 ----------
def c1(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (28, 44, 82), (12, 20, 42))
    d = ImageDraw.Draw(canvas)
    base = 0.735 * s
    d.rounded_rectangle((0.20 * s, base - 0.006 * s, 0.80 * s, base + 0.006 * s),
                        radius=0.006 * s, fill=(255, 255, 255, 55))
    w = 0.135 * s
    for x, h, col in ((0.265, 0.18, (73, 110, 174)),
                      (0.435, 0.285, (96, 150, 226)),
                      (0.605, 0.405, (78, 226, 182))):
        d.rounded_rectangle((x * s, base - h * s, x * s + w, base),
                            radius=0.028 * s, fill=col + (255,))
    # 最高柱顶部一道同色系高光，避免悬空装饰
    d.rounded_rectangle((0.605 * s, base - 0.405 * s,
                         0.605 * s + w, base - 0.405 * s + 0.024 * s),
                        radius=0.012 * s, fill=(150, 245, 216, 255))


# ---------- 方案 2：玻璃紫字标 ----------
def c2(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (79, 70, 229), (124, 58, 237))
    glass = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glass).polygon(
        [(0, 0), (0.60 * s, 0), (0.20 * s, s), (0, s)], fill=(255, 255, 255, 34)
    )
    canvas.alpha_composite(glass)
    d = ImageDraw.Draw(canvas)
    geom_yen(d, s, 0.50 * s, 0.50 * s, (255, 255, 255, 255), 0.052 * s)


# ---------- 方案 3：Token 卡片 ----------
def c3(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (18, 48, 60), (8, 26, 38))
    d = ImageDraw.Draw(canvas)
    # 后层卡片，轻微错位
    d.rounded_rectangle((0.245 * s, 0.245 * s, 0.735 * s, 0.755 * s),
                        radius=0.115 * s, fill=(17, 116, 132, 255))
    # 主卡片
    card = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0.275 * s, 0.275 * s, 0.765 * s, 0.785 * s),
                         radius=0.115 * s, fill=(255, 255, 255, 255))
    grad = Image.new("RGBA", (s, s))
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / max(1, s - 1)
        c = (round(64 * (1 - t) + 20 * t), round(214 * (1 - t) + 184 * t),
             round(186 * (1 - t) + 166 * t), 255)
        gd.line([(0, y), (s, y)], fill=c)
    grad.putalpha(card.getchannel("A"))
    canvas.alpha_composite(grad)
    d = ImageDraw.Draw(canvas)
    for i, length in enumerate((0.30, 0.225, 0.15)):
        y = 0.415 * s + i * 0.105 * s
        d.rounded_rectangle((0.375 * s, y, (0.375 + length) * s, y + 0.045 * s),
                            radius=0.022 * s, fill=(255, 255, 255, 245))
    d.ellipse((0.665 * s, 0.665 * s, 0.705 * s, 0.705 * s), fill=(255, 255, 255, 235))


# ---------- 方案 4：浅底线性 ----------
def c4(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (252, 253, 255), (236, 242, 251))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((0.022 * s, 0.022 * s, 0.978 * s, 0.978 * s),
                        radius=0.215 * s, outline=(208, 219, 237, 255), width=round(0.012 * s))
    cx = cy = 0.50 * s
    r = 0.29 * s
    d.ellipse((cx - r, cy - r, cx + r, cy + r),
              outline=(29, 58, 110, 255), width=round(0.030 * s))
    geom_yen(d, s, cx, cy, (29, 58, 110, 255), 0.038 * s, 0.52)
    d.arc((cx - r, cy - r, cx + r, cy + r), 305, 55,
          fill=(22, 163, 110, 255), width=round(0.046 * s))


# ---------- 方案 5：缓存命中率环 ----------
def c5(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (22, 36, 68), (10, 17, 36))
    d = ImageDraw.Draw(canvas)
    cx = cy = 0.50 * s
    r, w = 0.305 * s, 0.085 * s
    box = (cx - r, cy - r, cx + r, cy + r)
    d.ellipse(box, outline=(43, 60, 99, 255), width=round(w))
    start, sweep, segs = -90, 330, 96
    for i in range(segs):
        a0 = start + sweep * i / segs
        a1 = start + sweep * (i + 1) / segs + 0.8
        t = i / segs
        col = (round(52 + (34 - 52) * t), 211, round(153 + (238 - 153) * t), 255)
        d.arc(box, a0, a1, fill=col, width=round(w))
    geom_yen(d, s, cx, cy + 0.005 * s, (240, 246, 255, 255), 0.038 * s, 0.52)


# ---------- 方案 6：趋势折线 ----------
def c6(canvas: Image.Image, s: int) -> None:
    grad_round(canvas, s, (32, 66, 178), (12, 116, 140))
    d = ImageDraw.Draw(canvas)
    pts = [(0.22, 0.66), (0.37, 0.55), (0.51, 0.61), (0.66, 0.36), (0.79, 0.29)]
    cap_line(d, [(x * s, y * s) for x, y in pts],
             (255, 255, 255, 255), 0.050 * s)
    ex, ey = pts[-1]
    R = 0.073 * s
    d.ellipse((ex * s - R, ey * s - R, ex * s + R, ey * s + R),
              fill=(255, 203, 87, 255), outline=(255, 255, 255, 255), width=round(0.012 * s))
    for i, length in enumerate((0.30, 0.21)):
        y = 0.775 * s + i * 0.048 * s
        d.rounded_rectangle((0.22 * s, y, (0.22 + length) * s, y + 0.016 * s),
                            radius=0.008 * s, fill=(255, 255, 255, 95))


CONCEPTS = [
    (1, "极简仪表", "深蓝底 · 递增柱 · 无文字", c1),
    (2, "玻璃字标", "蓝紫渐变 · 几何 ¥ 线稿", c2),
    (3, "Token 卡片", "深青底 · 青绿卡片 · 数据行", c3),
    (4, "线性浅底", "白底 · 深蓝细线 · 青绿弧", c4),
    (5, "命中率环", "渐变圆环 · 呼应缓存命中率", c5),
    (6, "趋势折线", "蓝青渐变 · 上升折线 · 金点", c6),
]


def make_sheet(images: dict[int, Image.Image], path: Path) -> None:
    w, h = 1160, 860
    sheet = Image.new("RGB", (w, h), (242, 245, 250))
    d = ImageDraw.Draw(sheet)
    f_head = load_font(30)
    f_name = load_font(22)
    f_desc = load_font(16)
    d.text((34, 18), "WorkBuddy Token Cost  ·  应用图标候选", font=f_head, fill=(24, 36, 62))

    cw, ch, gap, x0, y0 = 350, 380, 25, 30, 72
    for idx, (num, name, desc, _) in enumerate(CONCEPTS):
        col, row = idx % 3, idx // 3
        x, y = x0 + col * (cw + gap), y0 + row * (ch + gap)
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=20, fill=(255, 255, 255, 255))
        icon = images[num].resize((260, 260), Image.LANCZOS)
        sheet.paste(icon, (x + (cw - 260) // 2, y + 32), icon)
        d.text((x + 24, y + 310), f"{num}. {name}", font=f_name, fill=(26, 40, 70))
        d.text((x + 24, y + 344), desc, font=f_desc, fill=(108, 122, 148))
    sheet.save(path, format="PNG")


def main() -> None:
    CONCEPT_DIR.mkdir(exist_ok=True)
    images: dict[int, Image.Image] = {}
    for num, _, _, fn in CONCEPTS:
        canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        fn(canvas, S)
        img = canvas.resize((512, 512), Image.LANCZOS)
        images[num] = img
        p = CONCEPT_DIR / f"concept_{num}.png"
        img.save(p, format="PNG")
        print(f"  {p.name}: {p.stat().st_size:,} bytes")
    sheet = OUT / "icon_concepts_sheet.png"
    make_sheet(images, sheet)
    print(f"  {sheet.name}: {sheet.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
