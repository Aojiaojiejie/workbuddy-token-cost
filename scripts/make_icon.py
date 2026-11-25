#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成应用图标：三根递增圆角柱 + 上升折线 + 金色终点，蓝青渐变底。

柱作为半透明背景层，折线走柱顶上方，两组图形不互相穿插。
输出（assets/）：app_icon.ico（7 种尺寸，传统 BMP/DIB 条目）、512px 预览、多尺寸对照图。
注意：PNG 压缩的 ICO 条目经 PyInstaller 写入 exe 后，Windows 仍会读出默认图标，
      因此必须使用传统 DIB 格式。
"""

from __future__ import annotations

import io
import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
S = 1024  # 超采样画布，保证缩小后边缘干净
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """按平台取一款中文字体；都缺失时退回 Pillow 内置字体，保证脚本可跨平台跑。"""
    for path in FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)

BG_TOP = (32, 66, 178)       # 方案 6 渐变上
BG_BOTTOM = (12, 116, 140)   # 方案 6 渐变下
GOLD = (255, 203, 87)        # 折线终点
MINT = (140, 243, 212)       # 最高柱
WHITE = (255, 255, 255)


def linear_gradient(size: int, top, bottom) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / max(1, size - 1)
        c = tuple(round(top[i] * (1 - t) + bottom[i] * t) for i in range(3)) + (255,)
        d.line([(0, y), (size, y)], fill=c)
    return img


def soft_light(size: int, strength: float = 0.12) -> Image.Image:
    """左上柔光，低分辨率生成后放大以保持平滑。"""
    n = 256
    light = Image.new("L", (n, n), 0)
    px = light.load()
    cx, cy, radius = 0.30 * n, 0.20 * n, 0.75 * n
    for y in range(n):
        for x in range(n):
            v = max(0.0, 1.0 - math.hypot(x - cx, y - cy) / radius) ** 2
            px[x, y] = round(255 * strength * v)
    return light.resize((size, size), Image.LANCZOS)


def rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def cap_line(d: ImageDraw.ImageDraw, pts, fill, width: float) -> None:
    """带圆头端点的折线。"""
    d.line(pts, fill=fill, width=round(width), joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def render(size: int, simple: bool = False) -> Image.Image:
    """渲染单个尺寸；simple=True 用于 32px 及以下，减少会糊成噪点的细节。"""
    s = S
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # 背景：蓝青渐变 + 左上柔光，裁成圆角方
    bg = linear_gradient(s, BG_TOP, BG_BOTTOM)
    bg.paste(WHITE + (255,), (0, 0), soft_light(s))
    canvas.paste(bg, (0, 0), rounded_mask(s, round(0.225 * s)))
    d = ImageDraw.Draw(canvas)

    base = 0.735 * s
    bar_w = 0.135 * s
    # 底部基线（方案 1）
    d.rounded_rectangle((0.20 * s, base - 0.006 * s, 0.80 * s, base + 0.006 * s),
                        radius=0.006 * s, fill=WHITE + (70,))

    # 三根递增柱：半透明白 -> 亮青绿；小尺寸提高不透明度避免发灰
    if simple:
        bar_colors = [WHITE + (165,), WHITE + (215,), MINT + (255,)]
    else:
        bar_colors = [WHITE + (70,), WHITE + (125,), MINT + (255,)]
    for x, h, col in zip((0.265, 0.435, 0.605), (0.18, 0.285, 0.405), bar_colors):
        d.rounded_rectangle((x * s, base - h * s, x * s + bar_w, base),
                            radius=0.028 * s, fill=col)

    # 波动上升折线（方案 6），始终位于柱顶上方，不与柱体交叉
    if simple:
        pts = [(0.25, 0.465), (0.50, 0.355), (0.755, 0.225)]
        line_w, gold_r, outline = 0.065 * s, 0.078 * s, 0.014 * s
    else:
        pts = [(0.22, 0.470), (0.365, 0.365), (0.495, 0.405),
               (0.635, 0.255), (0.765, 0.210)]
        line_w, gold_r, outline = 0.048 * s, 0.060 * s, 0.012 * s
    cap_line(d, [(x * s, y * s) for x, y in pts], WHITE + (255,), line_w)

    # 金色终点
    ex, ey = pts[-1][0] * s, pts[-1][1] * s
    d.ellipse((ex - gold_r, ey - gold_r, ex + gold_r, ey + gold_r),
              fill=GOLD + (255,), outline=WHITE + (255,), width=round(outline))

    return canvas.resize((size, size), Image.LANCZOS)


def single_dib(img: Image.Image, size: int):
    """借 Pillow 生成单尺寸标准 ICO，取出其中的传统 BMP/DIB 图标数据。"""
    buf = io.BytesIO()
    img.save(buf, format="ICO", sizes=[(size, size)], bitmap_format="bmp")
    data = buf.getvalue()
    w, h, colors, reserved, planes, bpp, nbytes, offset = struct.unpack_from(
        "<BBBBHHII", data, 6
    )
    return (w, h, colors, reserved, planes, bpp, data[offset:offset + nbytes])


def build_ico_bmp(images: dict[int, Image.Image], path: Path) -> None:
    """合并为多尺寸 ICO；DIB 条目可被 PyInstaller 与 Windows 图标加载器可靠读取。"""
    entries = [single_dib(img, size) for size, img in images.items()]
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, payload = b"", b""
    for w, h, colors, reserved, _planes, _bpp, blob in entries:
        # ICONDIRENTRY 的 planes/bitCount 必须与 DIB 头一致（传统 ICO 要求 planes=1）
        dib_planes, dib_bpp = struct.unpack_from("<HH", blob, 12)
        directory += struct.pack("<BBBBHHII", w, h, colors, reserved,
                                 dib_planes, dib_bpp, len(blob), offset)
        payload += blob
        offset += len(blob)
    path.write_bytes(header + directory + payload)


def make_size_sheet(images: dict[int, Image.Image], path: Path) -> None:
    """浅色背景上的真实像素尺寸对照图。"""
    w, h = 1000, 430
    sheet = Image.new("RGB", (w, h), (242, 245, 250))
    d = ImageDraw.Draw(sheet)
    d.rounded_rectangle((20, 20, w - 20, h - 20), radius=24, fill=(255, 255, 255))
    title = load_font(26)
    label = load_font(19)
    d.text((52, 40), "WorkBuddy Token Cost  /  应用图标（定稿）",
           font=title, fill=(28, 40, 70))
    for size, x, y in ((256, 70, 92), (64, 400, 188), (32, 600, 204), (16, 770, 212)):
        img = images[size]
        sheet.paste(img, (x, y), img)
        text = f"{size} px"
        bbox = d.textbbox((0, 0), text, font=label)
        d.text((x + size / 2 - (bbox[2] - bbox[0]) / 2, 370), text,
               font=label, fill=(95, 108, 135))
    sheet.save(path, format="PNG")


def main() -> None:
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {s: render(s, simple=(s <= 32)) for s in sizes}
    build_ico_bmp(images, OUT / "app_icon.ico")
    render(512).save(OUT / "app_icon_preview.png", format="PNG")
    make_size_sheet(images, OUT / "icon_preview_sizes.png")
    print("已生成:")
    for name in ("app_icon.ico", "app_icon_preview.png", "icon_preview_sizes.png"):
        print(f"  {name}: {(OUT / name).stat().st_size:,} bytes")
    print("  ICO 尺寸:", ", ".join(f"{s}x{s}" for s in sizes))


if __name__ == "__main__":
    main()
