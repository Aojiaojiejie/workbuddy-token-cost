#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WorkBuddy Token 费用看板 —— 图形界面版（PySide6 / Qt6）。

深色数据看板：KPI 卡片 + 可切换指标的时间序列柱状图 + 任务明细表。
点击任意任务行，会打开该任务独立的图表窗口（今天按小时、历史按天）。
数据全部只读自 ~/.workbuddy，定价复用 token_cost.py。
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QDialog, QFileDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMenu, QMessageBox,
    QPushButton, QSizeGrip, QSizePolicy, QStyle, QStyledItemDelegate, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

import token_cost as core

VERSION = core.VERSION
FONT = "Microsoft YaHei UI"
NUM = "Segoe UI"

# ---------------------------------------------------------------- 配色
BG = "#0B0E13"
SURFACE = "#141920"
SURFACE_2 = "#1A212B"
SURFACE_3 = "#212A36"
BORDER = "#232B36"
BORDER_2 = "#2E3846"
TEXT = "#E9EFF8"
TEXT_2 = "#B7C2D3"
MUTED = "#78859A"
ORANGE = "#FF7A2F"
ORANGE_2 = "#FF9A5C"
BLUE = "#4C8DFF"
SKY = "#7CC7F5"
GREEN = "#3DDC97"
RED = "#FF6B6B"
GRID = "#1F2631"


def qss() -> str:
    return f"""
QWidget {{
    background: transparent;
    color: {TEXT};
    font-family: "{FONT}";
    font-size: 12px;
}}
QWidget#root {{ background: {BG}; }}

QFrame#titlebar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
QLabel#appname {{ color: {TEXT}; font-size: 14px; font-weight: 600; }}
QLabel#version {{
    color: {MUTED}; font-size: 10px; background: {SURFACE_2};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 1px 7px;
}}
QFrame#livePill {{
    background: rgba(61, 220, 151, 0.10);
    border: 1px solid rgba(61, 220, 151, 0.22);
    border-radius: 12px;
}}
QFrame#livePill[paused="true"] {{
    background: rgba(255, 176, 66, 0.10);
    border: 1px solid rgba(255, 176, 66, 0.26);
}}
QLabel#liveText {{ color: {GREEN}; font-size: 11px; font-weight: 600; }}
QLabel#liveText[paused="true"] {{ color: #FFB042; }}

QPushButton#winbtn {{
    background: transparent; border: none; border-radius: 7px;
    color: {MUTED}; font-size: 13px; min-width: 30px; max-width: 30px;
    min-height: 28px; max-height: 28px;
}}
QPushButton#winbtn:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#winclose:hover {{ background: #E5484D; color: #FFFFFF; }}

QFrame#card {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#cardflat {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
}}

QLabel#kpiLabel {{ color: {MUTED}; font-size: 11px; }}
QLabel#kpiSub {{ color: {MUTED}; font-size: 11px; }}
QLabel#cardTitle {{ color: {TEXT_2}; font-size: 12px; font-weight: 500; }}
QLabel#cardMeta {{ color: {MUTED}; font-size: 11px; }}
QLabel#hint {{ color: {MUTED}; font-size: 11px; }}
QLabel#status {{ color: {MUTED}; font-size: 11px; }}
QLabel#sectionTitle {{ color: {TEXT}; font-size: 13px; font-weight: 600; }}
QLabel#chip {{
    color: #8FB6FF; background: rgba(76, 141, 255, 0.14);
    border: 1px solid rgba(76, 141, 255, 0.24);
    border-radius: 6px; padding: 1px 8px; font-size: 10px;
}}

QLineEdit {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 6px 10px; color: {TEXT};
    selection-background-color: #2D4A7A; font-size: 12px;
}}
QLineEdit:focus {{ border: 1px solid #3A4A63; }}

QComboBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 5px 10px; color: {TEXT};
    font-size: 12px; min-height: 18px;
}}
QComboBox:hover {{ border: 1px solid {BORDER_2}; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER_2};
    border-radius: 8px; padding: 4px; outline: none;
    selection-background-color: {SURFACE_3};
}}
QComboBox QAbstractItemView::item {{ padding: 6px 10px; border-radius: 6px; }}

QWidget#segwrap {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px;
}}
QPushButton#seg {{
    background: transparent; border: none; border-radius: 6px;
    color: {MUTED}; font-size: 11px; padding: 4px 11px;
}}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{
    background: {SURFACE_3}; color: {TEXT}; font-weight: 600;
}}

QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
    color: {TEXT_2}; font-size: 12px; padding: 6px 14px;
}}
QPushButton:hover {{ background: {SURFACE_3}; color: {TEXT}; }}
QPushButton:pressed {{ background: #2B3646; }}
QPushButton#primary {{
    background: {ORANGE}; border: 1px solid {ORANGE}; color: #14181F;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {ORANGE_2}; border-color: {ORANGE_2}; }}
QPushButton#ghost {{
    background: transparent; border: 1px solid transparent; color: {MUTED};
    padding: 5px 9px;
}}
QPushButton#ghost:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#toggle {{
    background: transparent; border: 1px solid {BORDER}; color: {MUTED};
    border-radius: 8px; padding: 5px 11px; font-size: 11px;
}}
QPushButton#toggle:hover {{ color: {TEXT}; border-color: {BORDER_2}; }}
QPushButton#toggle:checked {{
    background: rgba(255, 122, 47, 0.14); border: 1px solid rgba(255, 122, 47, 0.38);
    color: {ORANGE_2};
}}

QTableWidget {{
    background: transparent; border: none; gridline-color: transparent;
    font-size: 12px; color: {TEXT_2};
}}
QTableWidget::item {{ padding: 0px 6px; border: none; }}
QTableWidget::item:hover {{ background: {SURFACE_2}; }}
QTableWidget::item:selected {{ background: #26313F; color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 0px 6px;
    font-size: 11px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px 0px;
}}
QScrollBar::handle:vertical {{
    background: #303948; border-radius: 4px; min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: #3C4757; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: #303948; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

QMenu {{
    background: {SURFACE_2}; border: 1px solid {BORDER_2};
    border-radius: 10px; padding: 6px;
}}
QMenu::item {{
    padding: 7px 22px 7px 14px; border-radius: 6px; color: {TEXT_2};
    font-size: 12px;
}}
QMenu::item:selected {{ background: {SURFACE_3}; color: {TEXT}; }}
QToolTip {{
    background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER_2};
    padding: 5px 8px; border-radius: 6px;
}}
"""


# ---------------------------------------------------------------- 小工具
def font(family: str = FONT, size: int = 12, weight=QFont.Normal) -> QFont:
    f = QFont(family)
    f.setPixelSize(size)
    f.setWeight(weight)
    return f


MODEL_SHORT = {"deepseek-v4.1-flash": "v4.1-flash",
               "deepseek-v4-flash": "v4-flash",
               "deepseek-flash": "flash",
               "deepseek-v4-pro": "v4-pro"}


def short_model(name: str) -> str:
    if not name:
        return "—"
    return MODEL_SHORT.get(name, name.replace("deepseek-", ""))


def fmt_int(n) -> str:
    return f"{int(n):,}"


def fmt_money(v: float, decimals: int = 2) -> str:
    return f"¥{v:,.{decimals}f}"


def fmt_tokens(n) -> str:
    n = int(n)
    if n >= 1_000_000_000:
        return f"{n / 1e9:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1e6:.2f}M"
    if n >= 1_000:
        return f"{n / 1e3:.1f}K"
    return str(n)


def axis_num(v: float) -> str:
    if v <= 0:
        return "0"
    if v >= 1e9:
        return f"{v / 1e9:.1f}B"
    if v >= 1e6:
        return f"{v / 1e6:.0f}M"
    if v >= 1e4:
        return f"{v / 1e3:.0f}K"
    if v >= 1:
        return f"{v:.0f}" if v >= 10 else f"{v:.1f}"
    return f"{v:.2f}"


def axis_scale(vmax: float, n: int = 2):
    """返回 (轴顶, 步长)，保证中间刻度也是整数好看的值。"""
    step = nice_ceil(max(vmax, 1e-9) / n)
    return step * n, step


def axis_fmt_for(top: float):
    """同一张图的所有 Y 轴刻度使用一致的小数位。"""
    if top >= 1000:
        return axis_num
    if top >= 10:
        return lambda v: "0" if v <= 0 else f"{v:.0f}"
    if top >= 1:
        return lambda v: "0" if v <= 0 else f"{v:.1f}"
    return lambda v: "0" if v <= 0 else f"{v:.2f}"


def nice_ceil(v: float) -> float:
    """把最大值抬到 1/1.5/2/2.5/3/4/5/6/8 ×10^n 的"好看"刻度。"""
    if v <= 0:
        return 1.0
    exp = math.floor(math.log10(v))
    base = 10.0 ** exp
    n = v / base
    for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10):
        if n <= step + 1e-9:
            return step * base
    return 10 * base


def sum_buckets(mapping: dict, keys) -> dict:
    out = {"requests": 0, "prompt": 0, "hit": 0, "miss": 0, "output": 0,
           "total": 0, "cost": 0.0, "peak": 0, "offpeak": 0}
    for k in keys:
        b = mapping.get(k)
        if not b:
            continue
        for key in out:
            out[key] += b.get(key, 0)
    return out


def resource(name: str) -> Path:
    """定位随包资源；PyInstaller 解包目录优先，源码运行时相对仓库根目录。"""
    base = getattr(sys, "_MEIPASS", None)
    return (Path(base) if base else Path(__file__).resolve().parent) / name


# ---------------------------------------------------------------- 基础控件
class ElidedLabel(QLabel):
    """自绘省略号标签，避免长标题把布局撑破。"""

    def __init__(self, text: str = "", color: str = TEXT, size: int = 13,
                 weight=QFont.DemiBold, parent=None):
        super().__init__(text, parent)
        self._full = text
        self._color = color
        self._size = size
        self._weight = weight
        self.setFont(font(FONT, size, weight))
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def setText(self, text: str):  # noqa: N802 (Qt 命名)
        self._full = text or ""
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font(FONT, self._size, self._weight))
        p.setPen(QColor(self._color))
        fm = QFontMetrics(font(FONT, self._size, self._weight))
        text = fm.elidedText(self._full, Qt.ElideRight, max(10, self.width()))
        p.drawText(self.rect(), int(self.alignment()), text)
        p.end()


class PulseDot(QWidget):
    """实时刷新的呼吸点。"""

    def __init__(self, color: str = GREEN, size: int = 14, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._phase = 0.0
        self._on = True
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(50)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def set_active(self, on: bool):
        self._on = on
        self.update()

    def _tick(self):
        if not self._on:
            return
        self._phase = (self._phase + 0.045) % 1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        if self._on:
            halo = QColor(self._color)
            halo.setAlphaF(max(0.0, 0.32 * (1 - self._phase)))
            p.setBrush(halo)
            p.setPen(Qt.NoPen)
            r = 2.6 + 3.4 * self._phase
            p.drawEllipse(QPointF(cx, cy), r, r)
        c = QColor(self._color) if self._on else QColor(MUTED)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), 2.8, 2.8)
        p.end()


class KpiCard(QFrame):
    """指标卡：标题 + 大数字（带单位）+ 说明行。"""

    def __init__(self, label: str, accent: str, compact: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._accent = accent
        self._compact = compact
        self.setFixedHeight(94 if compact else 112)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12 if compact else 14, 16, 11 if compact else 13)
        lay.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(7)
        dot = QWidget()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(f"background:{accent}; border-radius:3px;")
        top.addWidget(dot)
        lab = QLabel(label)
        lab.setObjectName("kpiLabel")
        top.addWidget(lab)
        top.addStretch(1)
        lay.addLayout(top)

        self.value = QLabel("--")
        self.value.setTextFormat(Qt.RichText)
        lay.addWidget(self.value)

        self.sub = QLabel("")
        self.sub.setObjectName("kpiSub")
        lay.addWidget(self.sub)
        lay.addStretch(1)

    def set_value(self, main: str, unit: str = "", sub: str = ""):
        size = 21 if self._compact else 27
        self.value.setText(
            f'<span style="font-family:\'{NUM}\'; font-size:{size}px;'
            f' font-weight:700; color:{TEXT};">{main}</span>'
            f'<span style="font-family:\'{FONT}\'; font-size:11px; color:{MUTED};">'
            f'&nbsp;&nbsp;{unit}</span>'
        )
        self.sub.setText(sub)


class Segmented(QWidget):
    """分段选择器（今天 / 近 7 天 / 近 30 天 / 全部）。"""

    changed = Signal(str)

    def __init__(self, options, current: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("segwrap")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._keys = []
        for key, label in options:
            btn = QPushButton(label)
            btn.setObjectName("seg")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(key == (current or options[0][0]))
            btn.clicked.connect(lambda _=False, k=key: self._on_click(k))
            self._group.addButton(btn)
            lay.addWidget(btn)
            self._keys.append(key)

    def _on_click(self, key: str):
        self.changed.emit(key)

    def set_value(self, key: str):
        for i, k in enumerate(self._keys):
            if k == key:
                self._group.buttons()[i].setChecked(True)


class ChevronCombo(QComboBox):
    """自绘箭头的下拉框，避免深色主题下箭头不可见。"""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.addItems(items)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(30)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(MUTED), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        cx = self.width() - 15
        cy = self.height() / 2 - 1
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2.5))
        p.drawLine(QPointF(cx, cy + 2.5), QPointF(cx + 4, cy - 2))
        p.end()


# ---------------------------------------------------------------- 图表
class TimeSeriesChart(QWidget):
    """时间序列图：柱状（bar）或面积（area），带悬停气泡。

    points: [{"label": 轴标签, "tip": 悬停标题, "value": 数值}]
    """

    def __init__(self, color: str = ORANGE, style: str = "bar", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._style = style
        self._points: list[dict] = []
        self._tip_fmt = lambda v: f"{v:,.2f}"          # noqa: E731
        self._empty = "暂无数据"
        self._hover = -1
        self._left = 40.0
        self._slot = 10.0
        self.setMouseTracking(True)
        self.setMinimumHeight(80)

    def set_data(self, points, tip_fmt=None, empty: str = "暂无数据"):
        self._points = points or []
        if tip_fmt:
            self._tip_fmt = tip_fmt
        self._empty = empty
        self._hover = -1
        self.update()

    # ---- 交互
    def mouseMoveEvent(self, event):
        if not self._points:
            return
        x = event.position().x()
        idx = int((x - self._left) // max(1.0, self._slot))
        idx = max(0, min(len(self._points) - 1, idx))
        if x < self._left - self._slot * 0.5 or x > self.width() + 2:
            idx = -1
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, event):
        if self._hover != -1:
            self._hover = -1
            self.update()

    # ---- 绘制
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        w, h = self.width(), self.height()
        if not self._points:
            p.setFont(font(FONT, 11))
            p.setPen(QColor(MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, self._empty)
            p.end()
            return

        values = [float(pt["value"]) for pt in self._points]
        top, step = axis_scale(max(values))

        f_axis = font(NUM, 10)
        fm_axis = QFontMetrics(f_axis)
        ticks = [top, step, 0.0]
        fmt_axis = axis_fmt_for(top)
        gutter = max(fm_axis.horizontalAdvance(fmt_axis(t)) for t in ticks) + 14
        left = min(gutter, w * 0.28)
        plot = QRectF(left, 10, max(12.0, w - left - 4), max(12.0, h - 10 - 24))
        n = len(self._points)
        slot = plot.width() / n
        self._left, self._slot = left, slot

        # 网格 + Y 轴刻度
        p.setFont(f_axis)
        for i, val in enumerate(ticks):
            y = plot.top() + plot.height() * i / 2
            p.setPen(QPen(QColor(GRID), 1))
            p.drawLine(QPointF(left, y), QPointF(plot.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 8, left - 10, 16),
                       int(Qt.AlignRight | Qt.AlignVCenter), fmt_axis(val))

        # 数据
        if self._style == "area":
            self._paint_area(p, plot, slot, values, top)
        else:
            self._paint_bars(p, plot, slot, values, top)

        # X 轴标签
        f_x = font(NUM, 10)
        fm_x = QFontMetrics(f_x)
        p.setFont(f_x)
        p.setPen(QColor(MUTED))
        sample = max(fm_x.horizontalAdvance(pt["label"]) for pt in self._points)
        need = sample + 16
        step = max(1, int(math.ceil(need / max(1.0, slot))), int(math.ceil(n / 8)))
        shown = set(range(0, n, step))
        if n - 1 not in shown and (n - 1) % step > step / 2:
            shown.add(n - 1)
        for i in sorted(shown):
            cx = plot.left() + slot * (i + 0.5)
            text = self._points[i]["label"]
            tw = fm_x.horizontalAdvance(text)
            x = min(max(cx - tw / 2, 0), w - tw)
            p.drawText(QPointF(x, h - 6), text)

        # 悬停气泡
        if 0 <= self._hover < n:
            self._paint_tip(p, plot, slot, top)

        p.end()

    def _paint_bars(self, p, plot, slot, values, top):
        bw = min(26.0, max(2.0, slot * 0.62))
        for i, v in enumerate(values):
            if v <= 0:
                continue
            hgt = plot.height() * v / top
            cx = plot.left() + slot * (i + 0.5)
            rect = QRectF(cx - bw / 2, plot.bottom() - hgt, bw, hgt)
            base = (QColor(self._color).lighter(126) if i == self._hover
                    else QColor(self._color))
            grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
            grad.setColorAt(0.0, base.lighter(114))
            grad.setColorAt(1.0, base)
            p.setPen(Qt.NoPen)
            p.setBrush(grad)
            radius = min(3.0, bw / 2)
            if hgt > radius * 2:
                path = QPainterPath()
                path.addRoundedRect(rect, radius, radius)
                p.fillPath(path, grad)
                p.fillRect(QRectF(rect.left(), rect.top() + radius,
                                  rect.width(), max(0.0, rect.height() - radius)), grad)
            else:
                p.drawRect(rect)

    def _paint_area(self, p, plot, slot, values, top):
        pts = [QPointF(plot.left() + slot * (i + 0.5),
                       plot.bottom() - plot.height() * v / top)
               for i, v in enumerate(values)]
        if len(pts) < 2:
            return
        line = QPainterPath(pts[0])
        for a, b in zip(pts, pts[1:]):
            cx = (a.x() + b.x()) / 2
            line.cubicTo(QPointF(cx, a.y()), QPointF(cx, b.y()), b)
        fill = QPainterPath(line)
        fill.lineTo(QPointF(pts[-1].x(), plot.bottom()))
        fill.lineTo(QPointF(pts[0].x(), plot.bottom()))
        fill.closeSubpath()
        grad = QLinearGradient(0, plot.top(), 0, plot.bottom())
        c1 = QColor(self._color)
        c1.setAlpha(150)
        c2 = QColor(self._color)
        c2.setAlpha(6)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawPath(fill)
        pen = QPen(QColor(self._color).lighter(112), 1.6)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(line)
        if 0 <= self._hover < len(pts):
            hp = pts[self._hover]
            p.setBrush(QColor(self._color).lighter(130))
            p.setPen(QPen(QColor(SURFACE), 2))
            p.drawEllipse(hp, 3.4, 3.4)

    def _paint_tip(self, p, plot, slot, top):
        pt = self._points[self._hover]
        f1, f2 = font(FONT, 10), font(NUM, 11, QFont.DemiBold)
        fm1, fm2 = QFontMetrics(f1), QFontMetrics(f2)
        t1, t2 = str(pt["tip"]), self._tip_fmt(pt["value"])
        w1, w2 = fm1.horizontalAdvance(t1), fm2.horizontalAdvance(t2)
        pad = 13
        tw = pad * 2 + w1 + 12 + w2
        th = 29.0
        cx = plot.left() + slot * (self._hover + 0.5)
        x = min(max(cx - tw / 2, 2.0), self.width() - tw - 2)
        v = float(pt["value"])
        bar_h = plot.height() * v / (top or 1.0)
        y = plot.bottom() - bar_h - th - 9
        y = max(2.0, y)
        rect = QRectF(x, y, tw, th)
        p.setPen(QPen(QColor(BORDER_2), 1))
        p.setBrush(QColor(SURFACE_3))
        p.drawRoundedRect(rect, th / 2, th / 2)
        p.setFont(f1)
        p.setPen(QColor(TEXT_2))
        p.drawText(QRectF(x + pad, y, w1 + 2, th), int(Qt.AlignLeft | Qt.AlignVCenter), t1)
        p.setFont(f2)
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(x + pad + w1 + 12, y, w2, th),
                   int(Qt.AlignLeft | Qt.AlignVCenter), t2)


class SparkDelegate(QStyledItemDelegate):
    """表格里的"近 7 日"迷你柱状图。"""

    def __init__(self, color: str = ORANGE, days: int = 7, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._days = days

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        r = option.rect
        if option.state & QStyle.State_Selected:
            bg = QColor("#26313F")
        elif index.row() % 2:
            bg = QColor("#12171E")
        else:
            bg = QColor(SURFACE)
        painter.fillRect(r, bg)

        vals = index.data(Qt.UserRole) or []
        vals = [float(v) for v in vals][-self._days:]
        vals = [0.0] * (self._days - len(vals)) + vals
        mx = max(vals) if vals and max(vals) > 0 else 1.0
        bar_w, gap = 5.0, 3.0
        total_w = self._days * bar_w + (self._days - 1) * gap
        x0 = r.left() + (r.width() - total_w) / 2
        base_y = r.top() + r.height() / 2 + 9
        for i, v in enumerate(vals):
            hgt = 0 if v <= 0 else max(2.0, 18.0 * v / mx)
            c = QColor(self._color)
            c.setAlpha(70 + int(160 * (v / mx)))
            painter.setPen(Qt.NoPen)
            painter.setBrush(c)
            x = x0 + i * (bar_w + gap)
            if hgt > 0:
                painter.drawRoundedRect(QRectF(x, base_y - hgt, bar_w, hgt), 1.5, 1.5)
            else:
                painter.setBrush(QColor(BORDER_2))
                painter.drawEllipse(QPointF(x + bar_w / 2, base_y - 1.0), 1.0, 1.0)
        painter.restore()


class SessionTable(QTableWidget):
    """带空状态文案的表格。"""

    def __init__(self, rows: int, cols: int, parent=None):
        super().__init__(rows, cols, parent)
        self.empty_text = "暂无数据"
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(36)
        self.horizontalHeader().setFixedHeight(32)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setFrameShape(QFrame.NoFrame)
        self.setAlternatingRowColors(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() == 0:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.TextAntialiasing)
            p.setFont(font(FONT, 11))
            p.setPen(QColor(MUTED))
            p.drawText(self.viewport().rect(), Qt.AlignCenter, self.empty_text)
            p.end()


# ---------------------------------------------------------------- 后台扫描
class Scanner(QThread):
    ready = Signal(object)
    failed = Signal(str)

    def __init__(self, ctx, interval: float):
        super().__init__()
        self.ctx = ctx
        self.interval = interval
        self.wake = threading.Event()
        self.stop_flag = False
        self.paused = False
        self.round_no = 0
        self.first = True

    def nudge(self):
        self.wake.set()

    def stop(self):
        self.stop_flag = True
        self.wake.set()

    def run(self):
        while not self.stop_flag:
            if not self.paused:
                try:
                    if (not self.ctx.args.offline and self.ctx.args.price_refresh > 0
                            and (self.first or time.time() - self.ctx.price_time
                                 >= self.ctx.args.price_refresh)):
                        try:
                            self.ctx.prices = core.fetch_prices()
                            self.ctx.price_source = "官网实时价格"
                            self.ctx.price_time = time.time()
                        except Exception as exc:
                            self.ctx.price_source = f"内置价格表（联网失败: {type(exc).__name__}）"
                        self.first = False
                    snap = core.collect(self.ctx)
                    self.round_no += 1
                    self.ready.emit((snap, self.round_no))
                except Exception as exc:
                    self.failed.emit(f"{type(exc).__name__}: {exc}")
            self.wake.wait(self.interval)
            self.wake.clear()


# ---------------------------------------------------------------- 主窗口
RANGES = [("today", "今天"), ("7d", "近 7 天"), ("30d", "近 30 天"), ("all", "全部")]
METRICS = [("cost", "消费"), ("requests", "请求"), ("tokens", "Tokens")]
# 指标 -> (颜色, 图表样式)；主图与详情窗口共用，避免两处映射漂移
METRIC_STYLE = {"cost": (ORANGE, "bar"), "requests": (BLUE, "area"), "tokens": (SKY, "bar")}


class MainWindow(QWidget):
    HEADS = ["#", "任务", "模型", "近 7 日", "请求", "输入", "命中率",
             "输出", "总 Token", "费用 (CNY)"]
    WIDTHS = [36, 0, 96, 84, 66, 84, 72, 82, 96, 96]
    SORTS = [None, "title", "model", None, "requests", "prompt", "hit",
             "output", "total", "cost"]

    def __init__(self, opts):
        super().__init__()
        self.opts = opts
        self.setObjectName("root")
        self.setWindowTitle(f"WorkBuddy Token 费用看板  v{VERSION}")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setMinimumSize(1120, 700)
        self.resize(1280, 900)

        self.last_snap = None
        self.prev_snap = None
        self.range_key = getattr(opts, "range", "today") or "today"
        self.metric_key = "cost"
        self.sort_key = "cost"
        self.sort_rev = True
        self.rows: list[dict] = []
        self.view_rows: list[dict] = []
        self.details: dict = {}
        self._base_status = "正在扫描…"
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self._restore_status)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.titlebar = self._build_titlebar()
        outer.addWidget(self.titlebar)

        content = QWidget()
        content.setObjectName("root")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(12)
        lay.addWidget(self._build_toolbar())
        lay.addLayout(self._build_kpi())
        lay.addWidget(self._build_chart_card(), 4)
        lay.addWidget(self._build_table_card(), 5)
        lay.addLayout(self._build_status())
        outer.addWidget(content, 1)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)
        self._grip.setStyleSheet("background: transparent;")

        self.ctx = self._make_ctx()
        self.scanner = Scanner(self.ctx, opts.interval)
        self.scanner.ready.connect(self.on_snapshot)
        self.scanner.failed.connect(lambda m: self.status.setText("扫描异常：" + m))
        self.scanner.start()
        self._restore_status()

    # ---------- 标题栏
    def _build_titlebar(self):
        bar = QFrame()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(56)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(10)

        icon = QLabel()
        pm = QPixmap(str(resource("assets/app_icon.ico")))
        if not pm.isNull():
            icon.setPixmap(pm.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setFixedSize(24, 24)
        lay.addWidget(icon)

        name = QLabel("WorkBuddy Token 费用看板")
        name.setObjectName("appname")
        lay.addWidget(name)
        ver = QLabel(f"v{VERSION}")
        ver.setObjectName("version")
        ver.setFixedHeight(20)
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver, 0, Qt.AlignVCenter)
        lay.addStretch(1)

        self.live_pill = QFrame()
        self.live_pill.setObjectName("livePill")
        pl = QHBoxLayout(self.live_pill)
        pl.setContentsMargins(9, 3, 11, 3)
        pl.setSpacing(4)
        self.dot = PulseDot(GREEN)
        pl.addWidget(self.dot)
        self.live_text = QLabel("实时刷新 · 3s")
        self.live_text.setObjectName("liveText")
        pl.addWidget(self.live_text)
        lay.addWidget(self.live_pill)
        lay.addSpacing(6)

        self.pin_btn = QPushButton("置顶")
        self.pin_btn.setObjectName("toggle")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setCursor(Qt.PointingHandCursor)
        self.pin_btn.setChecked(bool(getattr(self.opts, "topmost", False)))
        self.pin_btn.clicked.connect(lambda *_: self.toggle_topmost())
        lay.addWidget(self.pin_btn)

        for text, slot, name_ in (("—", self.showMinimized, "winbtn"),
                                  ("✕", self.close, "winclose")):
            b = QPushButton(text)
            b.setObjectName(name_)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda *_, s=slot: s())
            lay.addWidget(b)

        bar.mousePressEvent = self._bar_press
        bar.mouseMoveEvent = self._bar_move
        bar.mouseReleaseEvent = self._bar_release
        self._drag = None
        return bar

    def _bar_press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _bar_move(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def _bar_release(self, e):
        self._drag = None

    # ---------- 工具栏
    def _build_toolbar(self):
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(56)
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        lay.addWidget(self._muted("时间维度"))
        self.range_seg = Segmented(RANGES, self.range_key)
        self.range_seg.changed.connect(self.on_range_changed)
        lay.addWidget(self.range_seg)
        lay.addWidget(self._sep())

        self.scope = ChevronCombo(["仅 deepseek-flash", "含 v4-pro", "全部模型（估算）"])
        self.scope.setFixedWidth(158)
        self.scope.currentTextChanged.connect(lambda _: self.filters_changed())
        lay.addWidget(self.scope)

        self.peak = ChevronCombo(["按时间自动", "全部按高峰", "全部按闲时"])
        self.peak.setFixedWidth(118)
        self.peak.currentTextChanged.connect(lambda _: self.filters_changed())
        lay.addWidget(self.peak)
        lay.addWidget(self._sep())

        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索任务标题")
        self.search.setFixedWidth(150)
        self.search.setMinimumHeight(30)
        pal = self.search.palette()
        pal.setColor(QPalette.PlaceholderText, QColor(MUTED))
        self.search.setPalette(pal)
        self.search.textChanged.connect(lambda *_: self.redraw_table())
        lay.addWidget(self.search)

        self.exclude = QPushButton("排除本窗口")
        self.exclude.setObjectName("toggle")
        self.exclude.setCheckable(True)
        self.exclude.setCursor(Qt.PointingHandCursor)
        self.exclude.clicked.connect(lambda *_: self.filters_changed())
        lay.addWidget(self.exclude)
        lay.addStretch(1)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda *_: self.scanner.nudge())
        lay.addWidget(self.refresh_btn)

        self.interval_box = ChevronCombo(["1s", "2s", "3s", "5s", "10s"])
        self.interval_box.setFixedWidth(66)
        self.interval_box.setToolTip("自动刷新间隔")
        cur = f"{int(self.opts.interval)}s" if float(self.opts.interval).is_integer() else "3s"
        self.interval_box.setCurrentText(cur if cur in ("1s", "2s", "3s", "5s", "10s") else "3s")
        self.interval_box.currentTextChanged.connect(lambda *_: self.interval_changed())
        lay.addWidget(self.interval_box)

        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("toggle")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setCursor(Qt.PointingHandCursor)
        self.pause_btn.clicked.connect(lambda *_: self.toggle_pause())
        lay.addWidget(self.pause_btn)

        self.export_btn = QPushButton("导出")
        self.export_btn.setObjectName("primary")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        menu = QMenu(self.export_btn)
        menu.addAction("导出 CSV（逐会话）", lambda: self.export("csv"))
        menu.addAction("导出 JSON（含每日/分时）", lambda: self.export("json"))
        self.export_btn.setMenu(menu)
        lay.addWidget(self.export_btn)
        return card

    def _muted(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("hint")
        return lab

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setFixedSize(1, 18)
        line.setStyleSheet(f"background:{BORDER};")
        return line

    # ---------- KPI
    def _build_kpi(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        self.kpi_cost = KpiCard("消费金额", ORANGE)
        self.kpi_req = KpiCard("API 请求次数", BLUE)
        self.kpi_tokens = KpiCard("Tokens", SKY)
        self.kpi_hit = KpiCard("缓存命中率", GREEN)
        for c in (self.kpi_cost, self.kpi_req, self.kpi_tokens, self.kpi_hit):
            row.addWidget(c, 1)
        return row

    # ---------- 主图表
    def _build_chart_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(206)
        card.setMaximumHeight(340)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.chart_title = QLabel("消费金额（CNY）")
        self.chart_title.setObjectName("cardTitle")
        head.addWidget(self.chart_title)
        self.chart_total = QLabel("¥0.00")
        self.chart_total.setStyleSheet(
            f"color:{TEXT}; font-family:'{NUM}'; font-size:17px; font-weight:700;")
        head.addWidget(self.chart_total)
        self.chart_meta = QLabel("")
        self.chart_meta.setObjectName("cardMeta")
        head.addWidget(self.chart_meta)
        head.addStretch(1)
        self.metric_seg = Segmented(METRICS, self.metric_key)
        self.metric_seg.changed.connect(self.on_metric_changed)
        head.addWidget(self.metric_seg)
        lay.addLayout(head)

        self.chart = TimeSeriesChart(ORANGE, "bar")
        self.chart.setMinimumHeight(120)
        lay.addWidget(self.chart, 1)
        return card

    # ---------- 表格
    def _build_table_card(self):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(160)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 10, 8, 8)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setContentsMargins(8, 0, 8, 0)
        head.setSpacing(8)
        self.table_title = QLabel("任务明细")
        self.table_title.setObjectName("sectionTitle")
        head.addWidget(self.table_title)
        self.table_hint = QLabel("")
        self.table_hint.setObjectName("hint")
        head.addWidget(self.table_hint)
        head.addStretch(1)
        tip = QLabel("点击任意任务 → 查看该任务的图表")
        tip.setObjectName("hint")
        head.addWidget(tip)
        lay.addLayout(head)

        self.table = SessionTable(0, len(self.HEADS))
        self.table.setHorizontalHeaderLabels(self.HEADS)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for i, w in enumerate(self.WIDTHS):
            if w:
                self.table.setColumnWidth(i, w)
        hh.sectionClicked.connect(self.sort_by)
        self.table.cellClicked.connect(self._cell_clicked)
        self.table.setItemDelegateForColumn(3, SparkDelegate(ORANGE))
        self.table.empty_text = "当前时间范围内没有任务数据"
        lay.addWidget(self.table, 1)
        return card

    # ---------- 状态栏
    def _build_status(self):
        row = QHBoxLayout()
        row.setSpacing(10)
        self.status = QLabel("正在扫描…")
        self.status.setObjectName("status")
        row.addWidget(self.status)
        row.addStretch(1)
        ver = QLabel(f"v{VERSION}  ·  deepseek-flash 官网定价  ·  只读数据源")
        ver.setObjectName("status")
        row.addWidget(ver)
        return row

    # ---------- 上下文
    def _make_ctx(self):
        args = argparse.Namespace(
            root=str(self.opts.root), title=self.opts.title,
            all_models=False, include_pro=False, exclude_current=False,
            peak="auto", since="", until="", holidays="", offline=self.opts.offline,
            top=0, csv="", json="", list=False, pause=False, no_pause=True,
            watch=0.0, once=True, count=0, price_refresh=600.0,
        )
        root = Path(self.opts.root).expanduser().resolve()
        if self.opts.offline:
            prices, source = dict(core.FALLBACK_PRICES), "内置价格表（离线）"
        else:
            # 先用内置价表把界面点亮，官网价格交给后台线程首轮获取
            prices, source = dict(core.FALLBACK_PRICES), "内置价格表（正在获取官网价格…）"
        meta, note = core.load_session_meta(root / "workbuddy.db")
        active = core.load_active_ids(root / "sessions")
        return core.Context(
            args=args, root=root, prices=prices, price_source=source,
            price_time=time.time(), meta=meta, meta_note=note,
            active_ids=active, excluded_active=set(), since=None, until=None,
            holidays=set(),
        )

    # ---------- 交互
    def on_range_changed(self, key: str):
        self.range_key = key
        if self.last_snap:
            self.on_snapshot((self.last_snap, self.scanner.round_no), keep_prev=True)

    def on_metric_changed(self, key: str):
        self.metric_key = key
        color, style = METRIC_STYLE[key]
        self.chart._color = QColor(color)
        self.chart._style = style
        self.chart.update()
        if self.last_snap:
            self._refresh_chart(self.last_snap)

    def filters_changed(self):
        a = self.ctx.args
        a.peak = {"按时间自动": "auto", "全部按高峰": "all",
                  "全部按闲时": "off"}[self.peak.currentText()]
        m = self.scope.currentText()
        a.all_models = (m == "全部模型（估算）")
        a.include_pro = (m == "含 v4-pro")
        self.ctx.excluded_active = set(self.ctx.active_ids) if self.exclude.isChecked() else set()
        if hasattr(self, "scanner"):
            self.scanner.nudge()

    def toggle_topmost(self):
        on = self.pin_btn.isChecked()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)
        self.show()

    def interval_changed(self):
        if not hasattr(self, "scanner"):
            return
        try:
            self.scanner.interval = float(self.interval_box.currentText().rstrip("s"))
        except (ValueError, TypeError):
            self.scanner.interval = 3.0
        if not self.scanner.paused:
            self.live_text.setText(f"实时刷新 · {self.scanner.interval:g}s")
        self.scanner.nudge()

    def toggle_pause(self):
        self.scanner.paused = not self.scanner.paused
        paused = self.scanner.paused
        self.pause_btn.setText("继续" if paused else "暂停")
        self.pause_btn.setChecked(paused)
        self.live_pill.setProperty("paused", paused)
        self.live_text.setProperty("paused", paused)
        for w in (self.live_pill, self.live_text):
            w.style().unpolish(w)
            w.style().polish(w)
        self.live_text.setText("已暂停" if paused else f"实时刷新 · {self.scanner.interval:g}s")
        self.dot.set_color("#FFB042" if paused else GREEN)
        self.dot.set_active(not paused)
        self.scanner.nudge()

    # ---------- 数据
    def _day_keys(self, snap, rng: str) -> list[str]:
        today = date.fromisoformat(snap.today)
        if rng == "7d":
            start = today - timedelta(days=6)
        elif rng == "30d":
            start = today - timedelta(days=29)
        else:
            days = sorted(snap.daily_total)
            start = date.fromisoformat(days[0]) if days else today
        return [(start + timedelta(days=i)).isoformat()
                for i in range((today - start).days + 1)]

    def _range_source(self, snap):
        """返回 (总桶映射, 会话桶映射, keys, 是否按小时)。"""
        if self.range_key == "today":
            return snap.hourly_total, snap.hourly_by_session, list(range(24)), True
        keys = self._day_keys(snap, self.range_key)
        return snap.daily_total, snap.daily_by_session, keys, False

    def _range_rows(self, snap) -> list[dict]:
        if self.range_key == "all":
            return [dict(s) for s in snap.rows]
        _, by_sid, keys, _ = self._range_source(snap)
        out = []
        for s in snap.rows:
            b = sum_buckets(by_sid.get(s["sid"], {}), keys)
            if not b["requests"]:
                continue
            row = dict(s)
            row.update(b)
            row["peak_requests"] = b["peak"]
            row["offpeak_requests"] = b["offpeak"]
            out.append(row)
        return out

    def on_snapshot(self, payload, keep_prev: bool = False):
        snap, round_no = payload
        if not keep_prev:
            self.prev_snap = self.last_snap
        self.last_snap = snap
        self._refresh_all()
        for dlg in list(self.details.values()):
            try:
                dlg.set_snapshot(snap)
            except Exception:
                pass
        if not keep_prev:
            now = datetime.fromtimestamp(snap.scanned_at, core.CN_TZ).strftime("%H:%M:%S")
            extra = " · 含非 Flash 估算" if self.ctx.args.all_models else ""
            self.status.setText(
                f"第 {round_no} 次刷新 · {now} · 扫描 {snap.elapsed:.2f}s · "
                f"{snap.files} 个文件 / {snap.usage_records:,} 条用量记录 · "
                f"{self.ctx.price_source}{extra}"
            )
            self._base_status = self.status.text()

    def _refresh_all(self):
        snap = self.last_snap
        if not snap:
            return
        total_map, _, keys, hourly = self._range_source(snap)
        agg = sum_buckets(total_map, keys)
        self._refresh_kpi(agg)
        self._refresh_chart(snap)
        self.rows = self._range_rows(snap)
        self.redraw_table()

    def _range_label(self) -> str:
        return {"today": "今天", "7d": "近 7 天", "30d": "近 30 天",
                "all": "全部"}[self.range_key]

    def _refresh_kpi(self, agg: dict):
        cost = agg["cost"]
        req = agg["requests"]
        tokens = agg["total"]
        hit_rate = 100 * agg["hit"] / agg["prompt"] if agg["prompt"] else 0.0
        self.kpi_cost.set_value(fmt_money(cost), "CNY",
                                f"{self._range_label()}累计 · 峰谷计价")
        self.kpi_req.set_value(fmt_int(req), "次",
                               f"峰 {fmt_int(agg['peak'])} · 闲 {fmt_int(agg['offpeak'])}")
        self.kpi_tokens.set_value(fmt_tokens(tokens), "",
                                  f"输入 {fmt_tokens(agg['prompt'])} · 输出 {fmt_tokens(agg['output'])}")
        self.kpi_hit.set_value(f"{hit_rate:.2f}%", "命中率",
                               f"命中 {fmt_tokens(agg['hit'])} · 未命中 {fmt_tokens(agg['miss'])}")

    def _metric_meta(self):
        """(图表标题, 标题区数值格式, 悬停数值格式)"""
        return {
            "cost": ("消费金额（CNY）", lambda v: f"¥{v:,.2f}", lambda v: f"¥{v:,.2f}"),
            "requests": ("API 请求次数", lambda v: f"{v:,.0f}", lambda v: f"{v:,.0f} 次"),
            "tokens": ("Tokens", lambda v: fmt_tokens(v),
                       lambda v: f"{fmt_tokens(v)} tokens"),
        }[self.metric_key]

    def _refresh_chart(self, snap):
        total_map, _, keys, hourly = self._range_source(snap)
        title, head_fmt, tip_fmt = self._metric_meta()
        self.chart_title.setText(title)
        pts = self._points(total_map, keys, hourly, snap.today if hourly else "")
        agg = sum_buckets(total_map, keys)
        value = {"cost": agg["cost"], "requests": agg["requests"],
                 "tokens": agg["total"]}[self.metric_key]
        self.chart_total.setText(head_fmt(value))
        self.chart_meta.setText(
            f"· 按小时（{snap.today[5:]}）" if hourly
            else f"· 按天 · {len(keys)} 天")
        color, _ = METRIC_STYLE[self.metric_key]
        self.chart._color = QColor(color)
        self.chart.set_data(pts, tip_fmt=tip_fmt,
                            empty="当前时间范围内暂无数据")

    def _points(self, buckets: dict, keys, hourly: bool, day_iso: str = ""):
        metric = self.metric_key
        out = []
        for k in keys:
            b = buckets.get(k)
            if not b:
                v = 0.0
            elif metric == "cost":
                v = float(b["cost"])
            elif metric == "requests":
                v = float(b["requests"])
            else:
                v = float(b["total"])
            if hourly:
                out.append({"label": f"{k:02d}:00",
                            "tip": f"{day_iso} {k:02d}:00", "value": v})
            else:
                out.append({"label": f"{k[5:7]}/{k[8:10]}", "tip": k, "value": v})
        return out

    # ---------- 表格
    def sort_by(self, col: int):
        key = self.SORTS[col] if col < len(self.SORTS) else None
        if key is None:
            return
        if self.sort_key == key:
            self.sort_rev = not self.sort_rev
        else:
            self.sort_key, self.sort_rev = key, key not in ("title", "model")
        self.redraw_table()

    def _sync_headers(self):
        labels = []
        for head, key in zip(self.HEADS, self.SORTS):
            if key is not None and key == self.sort_key:
                head = head + (" ↓" if self.sort_rev else " ↑")
            labels.append(head)
        self.table.setHorizontalHeaderLabels(labels)
        for i in range(len(labels)):
            item = self.table.horizontalHeaderItem(i)
            if item is None:
                continue
            if i in (0, 1, 2):
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            elif i == 3:
                item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            else:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def redraw_table(self):
        if not self.last_snap:
            return
        kw = self.search.text().strip().lower()
        rows = [s for s in self.rows if not kw or kw in s["title"].lower()]
        k = self.sort_key
        if k == "hit":
            rows.sort(key=lambda s: s["hit"] / s["prompt"] if s["prompt"] else 0,
                      reverse=self.sort_rev)
        elif k == "model":
            rows.sort(key=lambda s: (s["models"].most_common(1)[0][0] if s["models"] else ""),
                      reverse=self.sort_rev)
        elif k == "title":
            rows.sort(key=lambda s: s["title"], reverse=self.sort_rev)
        else:
            rows.sort(key=lambda s: s.get(k, 0), reverse=self.sort_rev)

        spark_days = self._spark_days()
        self.table.setUpdatesEnabled(False)
        self.table.setRowCount(len(rows))
        for i, s in enumerate(rows):
            rate = 100 * s["hit"] / s["prompt"] if s["prompt"] else 0.0
            model = s["models"].most_common(1)[0][0] if s["models"] else ""
            vals = [str(i + 1), s["title"], short_model(model), "",
                    fmt_int(s["requests"]), fmt_tokens(s["prompt"]), f"{rate:.2f}%",
                    fmt_tokens(s["output"]), fmt_tokens(s["total"]),
                    f"{s['cost']:.4f}"]
            for j, v in enumerate(vals):
                item = self.table.item(i, j)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(i, j, item)
                item.setText(v)
                item.setData(Qt.UserRole, s["sid"] if j == 0 else None)
                if j == 1:
                    item.setForeground(QColor(TEXT))
                    item.setToolTip(s["title"])
                elif j == 2:
                    item.setForeground(QColor(MUTED))
                    item.setToolTip(model or "未知模型")
                elif j == 9:
                    item.setForeground(QColor(ORANGE_2))
                else:
                    item.setForeground(QColor(TEXT_2))
                if j >= 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif j == 2:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            spark = self.table.item(i, 3)
            if spark is None:
                spark = QTableWidgetItem()
                self.table.setItem(i, 3, spark)
            spark.setData(Qt.UserRole, [d[1] for d in spark_days.get(s["sid"], [])])
        self.table.setUpdatesEnabled(True)
        self.view_rows = rows
        self._sync_headers()
        self.table_hint.setText(f"{len(rows)} 个任务 · {self._range_label()}")

    def _spark_days(self) -> dict:
        """每个任务最近 7 个自然日的消费，用于表格迷你柱。"""
        snap = self.last_snap
        if not snap:
            return {}
        today = date.fromisoformat(snap.today)
        keys = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
        out = {}
        for s in self.rows:
            buckets = snap.daily_by_session.get(s["sid"], {})
            out[s["sid"]] = [(k, buckets.get(k, {}).get("cost", 0.0)) for k in keys]
        return out

    def _cell_clicked(self, row: int, col: int):
        if row < 0 or row >= len(self.view_rows):
            return
        self.open_detail(self.view_rows[row])

    def open_detail(self, s):
        sid = s["sid"]
        dlg = self.details.get(sid)
        if dlg is None:
            dlg = DetailWindow(self, sid, s["title"])
            dlg.closed.connect(lambda k=sid: self.details.pop(k, None))
            offset = 40 + 26 * len(self.details)
            scr = QApplication.primaryScreen().availableGeometry()
            x = min(self.x() + offset, scr.right() - dlg.width() - 12)
            y = min(self.y() + offset, scr.bottom() - dlg.height() - 12)
            dlg.move(max(scr.left() + 8, x), max(scr.top() + 8, y))
            self.details[sid] = dlg
        dlg.set_snapshot(self.last_snap)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def open_detail_by_title(self, keyword: str) -> bool:
        if not self.last_snap or not keyword:
            return False
        row = next((x for x in self.last_snap.rows if keyword in x["title"]), None)
        if row:
            self.open_detail(row)
            return True
        return False

    # ---------- 导出
    def export(self, kind: str):
        if not self.last_snap:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出数据",
            f"token_cost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{kind}",
            f"{kind.upper()} 文件 (*.{kind})",
        )
        if not path:
            return
        a = copy.copy(self.ctx.args)
        a.csv = path if kind == "csv" else ""
        a.json = path if kind == "json" else ""
        msgs = core.export_files(replace(self.ctx, args=a), self.last_snap, quiet=True)
        if any(m.startswith("[错误]") for m in msgs):
            QMessageBox.critical(self, "导出失败", "\n".join(msgs))
        else:
            self.toast(f"已导出 → {path}")

    def toast(self, text: str, ms: int = 6000):
        self.status.setText(text)
        self._toast_timer.start(ms)

    def _restore_status(self):
        if hasattr(self, "_base_status"):
            self.status.setText(self._base_status)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._grip.move(self.width() - 16, self.height() - 16)
        self._grip.raise_()

    def closeEvent(self, event):
        try:
            for d in list(self.details.values()):
                d.close()
            self.scanner.stop()
            self.scanner.wait(1500)
        except Exception:
            pass
        event.accept()


# ---------------------------------------------------------------- 任务详情窗口
class DetailWindow(QDialog):
    closed = Signal(str)

    def __init__(self, parent, sid: str, title: str):
        super().__init__(parent, Qt.Window | Qt.FramelessWindowHint)
        self.sid = sid
        self.title_text = title
        self.snap = None
        self.range_key = getattr(parent, "range_key", "today")
        self.metric_key = "cost"
        self._drag = None
        self._init_done = False
        self.setObjectName("root")
        self.setWindowTitle(f"任务图表 · {title}")
        scr = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1040, scr.width() - 60), min(880, scr.height() - 60))
        self.setMinimumSize(860, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        body = QWidget()
        body.setObjectName("root")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(18, 14, 18, 12)
        lay.setSpacing(12)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.range_seg = Segmented(RANGES, self.range_key)
        self.range_seg.changed.connect(self._on_range)
        row.addWidget(self.range_seg)
        self.range_meta = QLabel("")
        self.range_meta.setObjectName("hint")
        row.addWidget(self.range_meta)
        row.addStretch(1)
        self.session_label = QLabel(f"会话 ID · {sid[:8]}…{sid[-4:]}")
        self.session_label.setObjectName("hint")
        row.addWidget(self.session_label)
        lay.addLayout(row)

        krow = QHBoxLayout()
        krow.setSpacing(10)
        self.k_cost = KpiCard("消费金额", ORANGE, compact=True)
        self.k_req = KpiCard("API 请求次数", BLUE, compact=True)
        self.k_tokens = KpiCard("Tokens", SKY, compact=True)
        self.k_hit = KpiCard("缓存命中率", GREEN, compact=True)
        for c in (self.k_cost, self.k_req, self.k_tokens, self.k_hit):
            krow.addWidget(c, 1)
        lay.addLayout(krow)
        lay.addWidget(self._build_main_chart(), 5)
        lay.addLayout(self._build_sub_charts())
        lay.addWidget(self._build_table(), 4)

        foot = QHBoxLayout()
        note = QLabel("数据随主界面实时刷新 · 与主看板同源（北京时间）")
        note.setObjectName("hint")
        foot.addWidget(note)
        foot.addStretch(1)
        lay.addLayout(foot)
        outer.addWidget(body, 1)

        grip = QSizeGrip(self)
        grip.setFixedSize(16, 16)
        grip.setStyleSheet("background: transparent;")
        self._grip = grip

    # ---- 头
    def _build_header(self):
        bar = QFrame()
        bar.setObjectName("titlebar")
        bar.setFixedHeight(54)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(18, 0, 12, 0)
        lay.setSpacing(10)
        self.title_label = ElidedLabel(self.title_text, TEXT, 13, QFont.DemiBold)
        lay.addWidget(self.title_label, 1)
        self.model_chip = QLabel("—")
        self.model_chip.setObjectName("chip")
        self.model_chip.setFixedHeight(20)
        self.model_chip.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.model_chip, 0, Qt.AlignVCenter)
        close = QPushButton("✕")
        close.setObjectName("winbtn")
        close.clicked.connect(lambda *_: self.close())
        lay.addWidget(close)
        bar.mousePressEvent = self._press
        bar.mouseMoveEvent = self._move
        bar.mouseReleaseEvent = self._release
        return bar

    def _press(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _move(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def _release(self, e):
        self._drag = None

    # ---- 图表卡片
    def _build_main_chart(self):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(160)
        card.setMaximumHeight(400)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(8)
        lab = QLabel("消费金额（CNY）")
        lab.setObjectName("cardTitle")
        head.addWidget(lab)
        self.main_total = QLabel("¥0.00")
        self.main_total.setStyleSheet(
            f"color:{TEXT}; font-family:'{NUM}'; font-size:17px; font-weight:700;")
        head.addWidget(self.main_total)
        head.addStretch(1)
        lay.addLayout(head)
        self.main_chart = TimeSeriesChart(ORANGE, "bar")
        self.main_chart.setMinimumHeight(96)
        lay.addWidget(self.main_chart, 1)
        return card

    def _sub_card(self, title: str, color: str, style: str):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(130)
        card.setMaximumHeight(210)
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 10)
        lay.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        lab = QLabel(title)
        lab.setObjectName("cardTitle")
        head.addWidget(lab)
        val = QLabel("0")
        val.setStyleSheet(
            f"color:{TEXT}; font-family:'{NUM}'; font-size:14px; font-weight:700;")
        head.addWidget(val)
        head.addStretch(1)
        lay.addLayout(head)
        chart = TimeSeriesChart(color, style)
        chart.setMinimumHeight(110)
        lay.addWidget(chart, 1)
        return card, val, chart

    def _build_sub_charts(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        c1, self.req_val, self.req_chart = self._sub_card("API 请求次数", BLUE, "area")
        c2, self.tok_val, self.tok_chart = self._sub_card("Tokens", SKY, "bar")
        row.addWidget(c1, 1)
        row.addWidget(c2, 1)
        return row

    def _build_table(self):
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumHeight(110)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 10, 8, 8)
        lay.setSpacing(6)
        head = QHBoxLayout()
        head.setContentsMargins(8, 0, 8, 0)
        self.detail_table_title = QLabel("分时明细")
        self.detail_table_title.setObjectName("sectionTitle")
        head.addWidget(self.detail_table_title)
        head.addStretch(1)
        lay.addLayout(head)

        self.tbl = SessionTable(0, 6)
        self.tbl.setHorizontalHeaderLabels(
            ["时间", "请求", "输入", "输出", "总 Token", "费用 (CNY)"])
        for i in range(6):
            item = self.tbl.horizontalHeaderItem(i)
            if item is not None:
                item.setTextAlignment((Qt.AlignLeft if i == 0 else Qt.AlignRight)
                                      | Qt.AlignVCenter)
        hh = self.tbl.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.Stretch)
        self.tbl.verticalHeader().setDefaultSectionSize(28)
        lay.addWidget(self.tbl, 1)
        return card

    # ---- 数据
    def _on_range(self, key: str):
        self.range_key = key
        if self.snap:
            self._refresh()

    def set_snapshot(self, snap):
        self.snap = snap
        if not self._init_done:
            self._init_done = True
            self._pick_default_range(snap)
        row = next((x for x in snap.rows if x["sid"] == self.sid), None)
        if row:
            if row["title"] != self.title_text:
                self.title_text = row["title"]
                self.title_label.setText(row["title"])
            model = row["models"].most_common(1)[0][0] if row["models"] else "—"
            self.model_chip.setText(model)
        self._refresh()

    def _pick_default_range(self, snap):
        """打开时若当前范围内没有这个任务的数据，自动退到有数据的范围。"""
        if snap.hourly_by_session.get(self.sid):
            return
        days = sorted(snap.daily_by_session.get(self.sid, {}))
        if not days:
            return
        today = date.fromisoformat(snap.today)
        recent = [d for d in days if (today - date.fromisoformat(d)).days < 30]
        key = "30d" if recent else "all"
        self.range_key = key
        self.range_seg.set_value(key)

    def _source(self):
        snap = self.snap
        if self.range_key == "today":
            return (snap.hourly_by_session.get(self.sid, {}),
                    list(range(24)), True, snap.today)
        today = date.fromisoformat(snap.today)
        if self.range_key == "7d":
            start = today - timedelta(days=6)
        elif self.range_key == "30d":
            start = today - timedelta(days=29)
        else:
            days = sorted(snap.daily_by_session.get(self.sid, {})) or [snap.today]
            start = date.fromisoformat(days[0])
        keys = [(start + timedelta(days=i)).isoformat()
                for i in range((today - start).days + 1)]
        return snap.daily_by_session.get(self.sid, {}), keys, False, ""

    def _points(self, buckets, keys, hourly, day_iso, metric):
        out = []
        for k in keys:
            b = buckets.get(k)
            if not b:
                v = 0.0
            elif metric == "cost":
                v = float(b["cost"])
            elif metric == "requests":
                v = float(b["requests"])
            else:
                v = float(b["total"])
            out.append({"label": f"{k:02d}:00" if hourly else f"{k[5:7]}/{k[8:10]}",
                        "tip": f"{day_iso} {k:02d}:00" if hourly else k,
                        "value": v})
        return out

    def _refresh(self):
        if not self.snap:
            return
        buckets, keys, hourly, day_iso = self._source()
        agg = sum_buckets(buckets, keys)
        hit = 100 * agg["hit"] / agg["prompt"] if agg["prompt"] else 0.0
        self.k_cost.set_value(fmt_money(agg["cost"]), "CNY",
                              f"{self._range_label()} · 峰 {fmt_int(agg['peak'])} / 闲 {fmt_int(agg['offpeak'])}")
        self.k_req.set_value(fmt_int(agg["requests"]), "次",
                             f"平均 {agg['requests'] / max(1, len(keys)):.1f} / {'小时' if hourly else '天'}")
        self.k_tokens.set_value(fmt_tokens(agg["total"]), "tokens",
                                f"输入 {fmt_tokens(agg['prompt'])} · 输出 {fmt_tokens(agg['output'])}")
        self.k_hit.set_value(f"{hit:.2f}%", "命中率",
                             f"命中 {fmt_tokens(agg['hit'])} · 未命中 {fmt_tokens(agg['miss'])}")

        self.range_meta.setText(f"· 按小时（{day_iso[5:]}）" if hourly else f"· 按天 · {len(keys)} 天")
        cost_pts = self._points(buckets, keys, hourly, day_iso, "cost")
        req_pts = self._points(buckets, keys, hourly, day_iso, "requests")
        tok_pts = self._points(buckets, keys, hourly, day_iso, "tokens")
        empty = "该时间范围内没有这个任务的用量"
        self.main_chart.set_data(cost_pts, tip_fmt=lambda v: f"¥{v:,.2f}", empty=empty)
        self.req_chart.set_data(req_pts, tip_fmt=lambda v: f"{v:,.0f} 次", empty=empty)
        self.tok_chart.set_data(tok_pts, tip_fmt=lambda v: f"{fmt_tokens(v)} tokens", empty=empty)
        self.main_total.setText(fmt_money(agg["cost"]))
        self.req_val.setText(f"{agg['requests']:,}")
        self.tok_val.setText(fmt_tokens(agg["total"]))

        rows = sorted(buckets.items(), reverse=True)
        rows = [(k, v) for k, v in rows if v.get("requests")]
        self.tbl.setRowCount(len(rows))
        self.detail_table_title.setText("分时明细" if hourly else "逐日明细")
        for i, (k, v) in enumerate(rows):
            label = f"{day_iso} {k:02d}:00" if hourly else str(k)
            vals = [label, fmt_int(v["requests"]), fmt_tokens(v["prompt"]),
                    fmt_tokens(v["output"]), fmt_tokens(v["total"]), f"{v['cost']:.4f}"]
            for j, val in enumerate(vals):
                item = self.tbl.item(i, j)
                if item is None:
                    item = QTableWidgetItem()
                    self.tbl.setItem(i, j, item)
                item.setText(val)
                item.setForeground(QColor(TEXT if j == 0 else
                                          (ORANGE_2 if j == 5 else TEXT_2)))
                if j:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.tbl.empty_text = "该时间范围内没有明细"

    def _range_label(self):
        return {"today": "今天", "7d": "近 7 天", "30d": "近 30 天",
                "all": "全部"}[self.range_key]

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._grip.move(self.width() - 16, self.height() - 16)
        self._grip.raise_()

    def closeEvent(self, event):
        self.closed.emit(self.sid)
        super().closeEvent(event)


# ---------------------------------------------------------------- 入口
def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--root", default=str(Path.home() / ".workbuddy"))
    ap.add_argument("--title", default="")
    ap.add_argument("--interval", type=float, default=3.0)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--topmost", action="store_true")
    ap.add_argument("--detail", default="", help="启动后打开标题含该关键词的任务图表")
    ap.add_argument("--range", default="today", choices=[k for k, _ in RANGES])
    ap.add_argument("--metric", default="cost", choices=[k for k, _ in METRICS])
    ap.add_argument("--shot", default="", help="调试：延时截图主窗口后退出")
    ap.add_argument("--shot-detail", default="", help="调试：截图详情窗口后退出")
    opts, _ = ap.parse_known_args()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(qss())
    app.setFont(font(FONT, 12))
    try:
        app.setWindowIcon(QIcon(str(resource("assets/app_icon.ico"))))
    except Exception:
        pass

    win = MainWindow(opts)
    if opts.topmost:
        win.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    scr = app.primaryScreen().availableGeometry()
    w = min(1280, int(scr.width() * 0.94))
    h = min(920, int(scr.height() * 0.94))
    win.resize(w, h)
    win.move(scr.x() + (scr.width() - w) // 2, scr.y() + max(0, (scr.height() - h) // 3))
    win.metric_seg.set_value(opts.metric)
    win.on_metric_changed(opts.metric)
    win.show()

    if opts.detail:
        QTimer.singleShot(2200, lambda: win.open_detail_by_title(opts.detail))
    if opts.shot:
        def shot():
            win.grab().save(opts.shot)
            if not opts.shot_detail:
                app.quit()
        QTimer.singleShot(3200, shot)
    if opts.shot_detail:
        def shot_detail():
            dlg = next(iter(win.details.values()), None)
            if dlg is not None:
                dlg.grab().save(opts.shot_detail)
            app.quit()
        QTimer.singleShot(4200, shot_detail)
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log = Path(tempfile.gettempdir()) / "WorkBuddyTokenCost_gui_error.log"
        try:
            with log.open("w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        sys.exit(1)
