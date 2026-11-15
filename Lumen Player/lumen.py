# -*- coding: utf-8 -*-
"""
Lumen - a premium video + music player.
PyQt6 + QtMultimedia (FFmpeg backend): MP4, MKV, AVI, MOV, WEBM, MP3, FLAC, WAV, OGG, AAC, M4A ...
Every file you open is saved to your Library automatically, and watched folders are scanned for all media.
"""
import os
import sys
import re
import json
import time
import random
import subprocess
import ctypes
from pathlib import Path

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PyQt6.QtCore import (Qt, QUrl, QTimer, QSize, QRectF, QPointF, QPoint, QEvent, QThread, pyqtSignal,
                          pyqtProperty, QPropertyAnimation, QEasingCurve, QVariantAnimation, QByteArray,
                          QLocale, QAbstractListModel, QModelIndex)
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient, QConicalGradient,
                         QPainterPath, QFont, QFontMetrics, QPixmap, QIcon, QImage, QCursor, QDesktopServices)
from PyQt6.QtWidgets import (QApplication, QWidget, QAbstractButton, QVBoxLayout, QHBoxLayout, QStackedWidget,
                             QLabel, QLineEdit, QFrame, QScrollArea, QListView, QListWidget, QListWidgetItem,
                             QStyledItemDelegate, QStyle, QFileDialog, QMenu, QMessageBox,
                             QGraphicsOpacityEffect, QToolTip)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaMetaData, QMediaFormat, QAudio
from PyQt6.QtMultimediaWidgets import QVideoWidget

APP = "Lumen"
VERSION = "1.0.0"

VIDEO_EXT = {".mp4", ".m4v", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".f4v", ".mpg", ".mpeg",
             ".m2ts", ".mts", ".ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx", ".asf", ".rm", ".rmvb"}
AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif",
             ".ape", ".mka", ".ac3", ".amr", ".wv"}
MEDIA_EXT = VIDEO_EXT | AUDIO_EXT
SCAN_EXT = MEDIA_EXT - {".ts"}          # .ts is also TypeScript - only play it when opened explicitly
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "$recycle.bin", "windows", "program files", "program files (x86)"}
SPEEDS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 3.0]
BAR_H = 104
DRAWER_W = 340

DATA = Path(os.environ.get("APPDATA", str(Path.home()))) / "Lumen"
DEFAULTS = {
    "dark": True, "accent": "#8B5CF6", "toasts": True,
    "resume": True, "autonext": True, "autosave": True, "autoscan": True, "autohide": True,
    "remember_vol": True, "volume": 0.8, "muted": False, "on_top": False, "seek_step": 10,
    "shuffle": False, "repeat": 0, "folders": [], "geometry": "", "sort": 0, "kind": 0,
    "last_dir": str(Path.home()),
}


# ----------------------------------------------------------------------------- helpers
def app_dir():
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def fmt_time(ms):
    s = max(0, int(ms // 1000))
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_size(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def fmt_rate(v):
    try:
        v = float(v)
    except Exception:
        return ""
    return f"{v / 1e6:.1f} Mbps" if v >= 1e6 else f"{v / 1000:.0f} kbps"


def nkey(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def norm(p):
    return os.path.normcase(os.path.abspath(p))


def lin_volume(v):
    try:
        return QAudio.convertVolume(v, QAudio.VolumeScale.LogarithmicVolumeScale, QAudio.VolumeScale.LinearVolumeScale)
    except Exception:
        return v * v


def as_text(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x)
    return str(v)


def meta(md, name):
    key = getattr(QMediaMetaData.Key, name, None)
    if key is None:
        return None
    try:
        return md.value(key)
    except Exception:
        return None


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def alpha(c, a):
    c = QColor(c)
    c.setAlpha(int(max(0, min(255, a))))
    return c


def rgba(c, a):
    c = QColor(c)
    return f"rgba({c.red()},{c.green()},{c.blue()},{a})"


AL = Qt.AlignmentFlag
A_C = AL.AlignCenter.value
A_L = (AL.AlignLeft | AL.AlignVCenter).value
A_R = (AL.AlignRight | AL.AlignVCenter).value


# ----------------------------------------------------------------------------- theme
class Theme:
    def __init__(self):
        self.dark = True
        self.accent = "#8B5CF6"
        self.refresh()

    def refresh(self):
        d = self.dark
        self.bg = "#0A0A12" if d else "#F3F3F9"
        self.side = "#0F0F19" if d else "#FFFFFF"
        self.surface = "#14141F" if d else "#FFFFFF"
        self.surface2 = "#1D1D2D" if d else "#EAEAF4"
        self.border = "#27273B" if d else "#DCDCEA"
        self.text = "#F4F4FB" if d else "#15152A"
        self.sub = "#A0A0BC" if d else "#5B5B78"
        self.mute = "#6C6C88" if d else "#9A9AB4"
        self.track = "#2B2B40" if d else "#D2D2E2"
        self.a1 = QColor(self.accent)
        h, s, l, _ = self.a1.getHsl()
        self.a2 = QColor.fromHsl(((h if h >= 0 else 0) + 38) % 360, s, min(255, l + 12))


T = Theme()
ACCENTS = ["#8B5CF6", "#3B82F6", "#06B6D4", "#22C55E", "#EC4899", "#F97316"]

QSS = """
QWidget { color: @text@; font-family: "Segoe UI Variable Text","Segoe UI","Inter",sans-serif; font-size: 13px; }
#root { background: @bg@; }
#side { background: @side@; border-right: 1px solid @border@; }
#bar { background: @side@; border-top: 1px solid @border@; }
#drawer { background: @side@; border-left: 1px solid @border@; }
#card { background: @surface@; border: 1px solid @border@; border-radius: 16px; }
#sep { background: @border@; min-height: 1px; max-height: 1px; border: none; }
QLabel { background: transparent; }
#pageTitle { font-size: 22px; font-weight: 700; }
#bigTitle { font-size: 30px; font-weight: 700; }
#h2 { font-size: 11px; font-weight: 700; color: @mute@; letter-spacing: 1px; }
#sub { color: @sub@; }
#cap { color: @mute@; font-size: 11px; font-weight: 600; }
#val { color: @text@; font-size: 13px; }
#time { color: @sub@; font-size: 12px; }
#npTitle { font-size: 14px; font-weight: 700; }
#rowTitle { font-size: 14px; font-weight: 600; }
#rowDesc { color: @sub@; font-size: 12px; }
#detTitle { font-size: 17px; font-weight: 700; }
#toast { background: @surface2@; border: 1px solid @border@; border-radius: 16px; padding: 7px 16px; font-weight: 600; }
QLineEdit#search { background: @surface2@; border: 1px solid @border@; border-radius: 19px; padding: 0 16px; selection-background-color: @accent@; }
QLineEdit#search:focus { border: 1px solid @accent@; }
QListView, QListWidget { background: transparent; border: none; outline: 0; }
QListWidget::item { padding: 9px 12px; border-radius: 10px; color: @sub@; }
QListWidget::item:hover { background: @surface2@; }
QListWidget::item:selected { background: @accent_b@; color: @text@; }
QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px 2px; }
QScrollBar::handle:vertical { background: @track@; border-radius: 4px; min-height: 40px; }
QScrollBar::handle:vertical:hover { background: @mute@; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal { height: 0; }
QMenu { background: @surface2@; border: 1px solid @border@; padding: 6px; }
QMenu::item { padding: 8px 26px 8px 14px; border-radius: 6px; }
QMenu::item:selected { background: @accent_b@; }
QMenu::separator { height: 1px; background: @border@; margin: 5px 8px; }
QToolTip { background: @surface2@; color: @text@; border: 1px solid @border@; padding: 5px 8px; }
QMessageBox, QDialog { background: @surface@; }
QPushButton { background: @surface2@; border: 1px solid @border@; border-radius: 8px; padding: 7px 18px; }
QPushButton:hover { background: @track@; }
"""


def build_qss():
    m = {"@bg@": T.bg, "@side@": T.side, "@surface@": T.surface, "@surface2@": T.surface2, "@border@": T.border,
         "@text@": T.text, "@sub@": T.sub, "@mute@": T.mute, "@track@": T.track, "@accent@": T.accent,
         "@accent_b@": rgba(T.accent, 70)}
    s = QSS
    for k, v in m.items():
        s = s.replace(k, v)
    return s


# ----------------------------------------------------------------------------- icons (drawn, no files)
ICONS = {
    "play": [("p", "M8 5.5 L19 12 L8 18.5 Z", "f")],
    "pause": [("p", "M7 5 H10 V19 H7 Z", "f"), ("p", "M14 5 H17 V19 H14 Z", "f")],
    "stop": [("p", "M6.5 6.5 H17.5 V17.5 H6.5 Z", "f")],
    "prev": [("p", "M6 5 H8.2 V19 H6 Z", "f"), ("p", "M19 5.5 L9.5 12 L19 18.5 Z", "f")],
    "next": [("p", "M18 5 H15.8 V19 H18 Z", "f"), ("p", "M5 5.5 L14.5 12 L5 18.5 Z", "f")],
    "shuffle": [("p", "M4 7 H7 C12 7 12 17 17 17 H20", "s"), ("p", "M4 17 H7 C8.5 17 9.6 16.2 10.5 15", "s"),
                ("p", "M13.5 9 C14.4 7.8 15.5 7 17 7 H20", "s"), ("p", "M18 5 L20.5 7 L18 9", "s"),
                ("p", "M18 15 L20.5 17 L18 19", "s")],
    "repeat": [("p", "M4 12 V10 Q4 7 7 7 H19", "s"), ("p", "M16.5 4.5 L19.5 7 L16.5 9.5", "s"),
               ("p", "M20 12 V14 Q20 17 17 17 H5", "s"), ("p", "M7.5 14.5 L4.5 17 L7.5 19.5", "s")],
    "repeat1": [("p", "M4 12 V10 Q4 7 7 7 H19", "s"), ("p", "M16.5 4.5 L19.5 7 L16.5 9.5", "s"),
                ("p", "M20 12 V14 Q20 17 17 17 H5", "s"), ("p", "M7.5 14.5 L4.5 17 L7.5 19.5", "s"),
                ("p", "M11 10.8 L12.6 9.6 V14.4", "s")],
    "volume": [("p", "M4 10 H7.5 L12.5 6 V18 L7.5 14 H4 Z", "f"), ("p", "M15.5 9.5 Q17.5 12 15.5 14.5", "s"),
               ("p", "M18 7 Q21.5 12 18 17", "s")],
    "volume_low": [("p", "M4 10 H7.5 L12.5 6 V18 L7.5 14 H4 Z", "f"), ("p", "M15.5 9.5 Q17.5 12 15.5 14.5", "s")],
    "mute": [("p", "M4 10 H7.5 L12.5 6 V18 L7.5 14 H4 Z", "f"), ("p", "M16 9.5 L21 14.5", "s"),
             ("p", "M21 9.5 L16 14.5", "s")],
    "fullscreen": [("p", "M4 9 V4 H9", "s"), ("p", "M15 4 H20 V9", "s"), ("p", "M20 15 V20 H15", "s"),
                   ("p", "M9 20 H4 V15", "s")],
    "fullscreen_exit": [("p", "M9 4 V9 H4", "s"), ("p", "M15 4 V9 H20", "s"), ("p", "M20 15 H15 V20", "s"),
                        ("p", "M4 15 H9 V20", "s")],
    "info": [("o", (12, 12, 9), "s"), ("p", "M12 11 V16.5", "s"), ("o", (12, 7.7, 1.1), "f")],
    "folder": [("p", "M3 7.5 Q3 5.5 5 5.5 H9.5 L12 8.5 H19 Q21 8.5 21 10.5 V17.5 Q21 19.5 19 19.5 H5 Q3 19.5 3 17.5 Z", "s")],
    "plus": [("p", "M12 5 V19", "s"), ("p", "M5 12 H19", "s")],
    "sliders": [("p", "M4 7 H20", "s"), ("p", "M4 12 H20", "s"), ("p", "M4 17 H20", "s"), ("o", (9, 7, 2.4), "f"),
                ("o", (15.5, 12, 2.4), "f"), ("o", (8, 17, 2.4), "f")],
    "grid": [("p", "M4.5 4.5 H10.5 V10.5 H4.5 Z", "s"), ("p", "M13.5 4.5 H19.5 V10.5 H13.5 Z", "s"),
             ("p", "M4.5 13.5 H10.5 V19.5 H4.5 Z", "s"), ("p", "M13.5 13.5 H19.5 V19.5 H13.5 Z", "s")],
    "music": [("p", "M9 17.5 V6 L19 4 V15.5", "s"), ("o", (6.8, 17.5, 2.4), "f"), ("o", (16.8, 15.5, 2.4), "f")],
    "video": [("p", "M3.5 6.5 H16 V17.5 H3.5 Z", "s"), ("p", "M16 10.5 L21 7.5 V16.5 L16 13.5 Z", "f")],
    "playcircle": [("o", (12, 12, 9), "s"), ("p", "M10 8.5 L15.5 12 L10 15.5 Z", "f")],
    "queue": [("p", "M4 7 H14", "s"), ("p", "M4 12 H14", "s"), ("p", "M4 17 H10", "s"),
              ("p", "M16.5 13 L21 16 L16.5 19 Z", "f")],
    "chevron": [("p", "M7 9.5 L12 14.5 L17 9.5", "s")],
    "audio": [("p", "M5 12 V10 Q5 5 12 5 Q19 5 19 10 V12", "s"), ("p", "M4 12 H7 V18 H4 Z", "f"),
              ("p", "M17 12 H20 V18 H17 Z", "f")],
    "subs": [("p", "M4 6 H20 V18 H4 Z", "s"), ("p", "M7 11 H11", "s"), ("p", "M13 11 H17", "s"), ("p", "M7 14.5 H12", "s")],
}


def svg(d):
    tok = re.findall(r"[MLHVCQZ]|-?\d*\.?\d+", d)
    path = QPainterPath()
    i, cmd, x, y = 0, "", 0.0, 0.0

    def num():
        nonlocal i
        v = float(tok[i])
        i += 1
        return v

    while i < len(tok):
        if tok[i].isalpha():
            cmd = tok[i]
            i += 1
        if cmd == "Z":
            path.closeSubpath()
            cmd = ""
            continue
        if cmd == "M":
            x, y = num(), num()
            path.moveTo(x, y)
            cmd = "L"
        elif cmd == "L":
            x, y = num(), num()
            path.lineTo(x, y)
        elif cmd == "H":
            x = num()
            path.lineTo(x, y)
        elif cmd == "V":
            y = num()
            path.lineTo(x, y)
        elif cmd == "Q":
            a, b, x, y = num(), num(), num(), num()
            path.quadTo(a, b, x, y)
        elif cmd == "C":
            a, b, c, d2, x, y = num(), num(), num(), num(), num(), num()
            path.cubicTo(a, b, c, d2, x, y)
        else:
            break
    return path


_ICON_CACHE = {}


def draw_icon(p, name, rect, color, width=2.0):
    items = _ICON_CACHE.get(name)
    if items is None:
        items = []
        for kind, data, mode in ICONS[name]:
            items.append((svg(data) if kind == "p" else data, kind, mode))
        _ICON_CACHE[name] = items
    p.save()
    p.translate(rect.center())
    s = min(rect.width(), rect.height()) / 24.0
    p.scale(s, s)
    p.translate(-12, -12)
    color = QColor(color)
    for geo, kind, mode in items:
        if mode == "f":
            p.setBrush(QBrush(color))
            p.setPen(QPen(color, 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        else:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if kind == "p":
            p.drawPath(geo)
        else:
            cx, cy, r = geo
            p.drawEllipse(QPointF(cx, cy), r, r)
    p.restore()


# ----------------------------------------------------------------------------- animated widgets
class Hoverable(QAbstractButton):
    """Button base with smooth hover + press animations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._h = 0.0
        self._p = 0.0
        self._ah = QPropertyAnimation(self, b"hv", self)
        self._ah.setDuration(170)
        self._ah.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._ap = QPropertyAnimation(self, b"pr", self)
        self._ap.setDuration(120)
        self._ap.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def _get_hv(self):
        return self._h

    def _set_hv(self, v):
        self._h = v
        self.update()

    hv = pyqtProperty(float, _get_hv, _set_hv)

    def _get_pr(self):
        return self._p

    def _set_pr(self, v):
        self._p = v
        self.update()

    pr = pyqtProperty(float, _get_pr, _set_pr)

    def _anim(self, a, cur, end):
        a.stop()
        a.setStartValue(cur)
        a.setEndValue(end)
        a.start()

    def enterEvent(self, e):
        self._anim(self._ah, self._h, 1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._anim(self._ah, self._h, 0.0)
        self._anim(self._ap, self._p, 0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._anim(self._ap, self._p, 1.0)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._anim(self._ap, self._p, 0.0)
        super().mouseReleaseEvent(e)

    def press_scale(self, p, r, amount=0.07):
        sc = 1 - amount * self._p
        p.translate(r.center())
        p.scale(sc, sc)
        p.translate(-r.center())


class IconButton(Hoverable):
    def __init__(self, icon, size=40, isize=20, primary=False, tip="", parent=None):
        super().__init__(parent)
        self.icon, self.isize, self.primary = icon, isize, primary
        self.setFixedSize(size, size)
        if tip:
            self.setToolTip(tip)

    def set_icon(self, name):
        if name != self.icon:
            self.icon = name
            self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.35)
        r = QRectF(self.rect())
        self.press_scale(p, r)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        if self.primary:
            inset = 2.0 - 1.6 * self._h
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, T.a1)
            g.setColorAt(1, T.a2)
            glow = alpha(T.a1, 70 * self._h)
            p.setBrush(glow)
            p.drawEllipse(r.adjusted(-1, -1, 1, 1))
            p.setBrush(QBrush(g))
            p.drawEllipse(r.adjusted(inset, inset, -inset, -inset))
            color = QColor("white")
        else:
            bg = QColor(T.text)
            bg.setAlpha(int(34 * self._h + (22 if on else 0)))
            p.setBrush(bg)
            p.drawEllipse(r.adjusted(1, 1, -1, -1))
            color = T.a1 if on else mix(T.sub, T.text, self._h)
        s = self.isize * (1 + 0.06 * self._h)
        draw_icon(p, self.icon, QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s), color)


class Pill(Hoverable):
    def __init__(self, text, icon=None, primary=False, height=36, parent=None):
        super().__init__(parent)
        self.icon, self.primary, self.hh = icon, primary, height
        f = QFont(self.font())
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        self.setFont(f)
        self.setText(text)
        self.setFixedHeight(height)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + 32 + (22 if self.icon else 0), self.hh)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        self.press_scale(p, r, 0.04)
        rad = r.height() / 2
        if self.primary:
            g = QLinearGradient(r.topLeft(), r.topRight())
            g.setColorAt(0, T.a1)
            g.setColorAt(1, T.a2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, rad, rad)
            p.setBrush(QColor(255, 255, 255, int(34 * self._h)))
            p.drawRoundedRect(r, rad, rad)
            fg = QColor("white")
        else:
            p.setPen(QPen(mix(T.border, T.a1, self._h * 0.7), 1))
            p.setBrush(mix(T.surface2, T.track, self._h))
            p.drawRoundedRect(r, rad, rad)
            fg = T.text
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(self.text())
        isz = 16
        total = tw + (isz + 7 if self.icon else 0)
        x = r.center().x() - total / 2
        p.setPen(fg)
        if self.icon:
            draw_icon(p, self.icon, QRectF(x, r.center().y() - isz / 2, isz, isz), fg, 2.2)
            x += isz + 7
        p.drawText(QRectF(x, r.top(), tw + 2, r.height()), A_L, self.text())


class NavButton(Hoverable):
    def __init__(self, icon, label, parent=None):
        super().__init__(parent)
        self.icon, self.label = icon, label
        self.setCheckable(True)
        self.setFixedSize(68, 62)
        self._s = 0.0
        self._as = QPropertyAnimation(self, b"sl", self)
        self._as.setDuration(240)
        self._as.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(lambda on: self._anim(self._as, self._s, 1.0 if on else 0.0))

    def _get_sl(self):
        return self._s

    def _set_sl(self, v):
        self._s = v
        self.update()

    sl = pyqtProperty(float, _get_sl, _set_sl)

    def nextCheckState(self):
        self.setChecked(True)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(4, 2, -4, -2)
        self.press_scale(p, r, 0.05)
        p.setPen(Qt.PenStyle.NoPen)
        bg = alpha(T.a1, 40 * self._s)
        if self._h > 0:
            hv = QColor(T.text)
            hv.setAlpha(int(16 * self._h * (1 - self._s)))
            p.setBrush(hv)
            p.drawRoundedRect(r, 14, 14)
        p.setBrush(bg)
        p.drawRoundedRect(r, 14, 14)
        col = mix(mix(T.sub, T.text, self._h), T.a1, self._s)
        draw_icon(p, self.icon, QRectF(r.center().x() - 11, r.top() + 8, 22, 22), col)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(col)
        p.drawText(QRectF(r.left(), r.top() + 33, r.width(), 18), A_C, self.label)
        p.setBrush(T.a1)
        p.setPen(Qt.PenStyle.NoPen)
        hh = 26 * self._s
        p.drawRoundedRect(QRectF(-2, self.height() / 2 - hh / 2, 5, hh), 2.5, 2.5)


class Swatch(Hoverable):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setCheckable(True)
        self.setFixedSize(32, 32)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        self.press_scale(p, r, 0.1)
        s = 20 + 3 * self._h
        c = r.center()
        if self.isChecked():
            p.setPen(QPen(self.color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 14, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(c, s / 2, s / 2)


class Toggle(QAbstractButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self._pos = 1.0 if checked else 0.0
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(48, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._a = QPropertyAnimation(self, b"tp", self)
        self._a.setDuration(220)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._go)

    def _get_tp(self):
        return self._pos

    def _set_tp(self, v):
        self._pos = v
        self.update()

    tp = pyqtProperty(float, _get_tp, _set_tp)

    def _go(self, on):
        self._a.stop()
        self._a.setStartValue(self._pos)
        self._a.setEndValue(1.0 if on else 0.0)
        self._a.start()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.topRight())
        g.setColorAt(0, mix(T.track, T.a1, self._pos))
        g.setColorAt(1, mix(T.track, T.a2, self._pos))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 8
        x = r.left() + 4 + (r.width() - d - 8) * self._pos
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawEllipse(QRectF(x, r.top() + 5, d, d))
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, r.top() + 4, d, d))


class Segmented(QWidget):
    changed = pyqtSignal(int)

    def __init__(self, labels, index=0, parent=None):
        super().__init__(parent)
        self.labels = labels
        self._i = index
        self._sel = float(index)
        self._sw = max(62, max(len(x) for x in labels) * 9 + 30)
        self.setFixedSize(self._sw * len(labels) + 8, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._a = QPropertyAnimation(self, b"sel", self)
        self._a.setDuration(260)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_sel(self):
        return self._sel

    def _set_sel(self, v):
        self._sel = v
        self.update()

    sel = pyqtProperty(float, _get_sel, _set_sel)

    def index(self):
        return self._i

    def setIndex(self, i, emit=True):
        if i == self._i:
            return
        self._i = i
        self._a.stop()
        self._a.setStartValue(self._sel)
        self._a.setEndValue(float(i))
        self._a.start()
        if emit:
            self.changed.emit(i)

    def mousePressEvent(self, e):
        i = int((e.position().x() - 4) // self._sw)
        self.setIndex(max(0, min(len(self.labels) - 1, i)))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(T.border), 1))
        p.setBrush(QColor(T.surface2))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        hl = QRectF(4 + self._sel * self._sw, 4, self._sw, self.height() - 8)
        g = QLinearGradient(hl.topLeft(), hl.topRight())
        g.setColorAt(0, T.a1)
        g.setColorAt(1, T.a2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(hl, hl.height() / 2, hl.height() / 2)
        f = QFont(self.font())
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        for i, lab in enumerate(self.labels):
            near = max(0.0, 1 - abs(self._sel - i))
            p.setPen(mix(T.sub, QColor("white"), near))
            p.drawText(QRectF(4 + i * self._sw, 0, self._sw, self.height()), A_C, lab)


class Slider(QWidget):
    moved = pyqtSignal(int)
    released = pyqtSignal(int)
    hovered = pyqtSignal(int, QPoint)
    wheel = pyqtSignal(int)

    def __init__(self, maximum=100, parent=None):
        super().__init__(parent)
        self._min, self._max, self._v = 0, maximum, 0
        self._drag = False
        self._h = 0.0
        self.setFixedHeight(24)
        self.setMinimumWidth(60)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._a = QPropertyAnimation(self, b"hv", self)
        self._a.setDuration(160)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_hv(self):
        return self._h

    def _set_hv(self, v):
        self._h = v
        self.update()

    hv = pyqtProperty(float, _get_hv, _set_hv)

    def _to(self, end):
        self._a.stop()
        self._a.setStartValue(self._h)
        self._a.setEndValue(end)
        self._a.start()

    def setRange(self, lo, hi):
        self._min, self._max = lo, max(hi, lo + 1)
        self.update()

    def setValue(self, v):
        if self._drag:
            return
        self._v = max(self._min, min(self._max, int(v)))
        self.update()

    def value(self):
        return self._v

    def _x2v(self, x):
        pad = 9
        w = max(1, self.width() - 2 * pad)
        f = min(1.0, max(0.0, (x - pad) / w))
        return int(self._min + f * (self._max - self._min))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pad = 9
        cy = self.height() / 2
        w = self.width() - 2 * pad
        th = 4 + 2.5 * self._h
        frac = (self._v - self._min) / (self._max - self._min)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(T.track))
        p.drawRoundedRect(QRectF(pad, cy - th / 2, w, th), th / 2, th / 2)
        fw = w * frac
        if fw > 0.5:
            g = QLinearGradient(pad, 0, pad + max(w, 1), 0)
            g.setColorAt(0, T.a1)
            g.setColorAt(1, T.a2)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(pad, cy - th / 2, fw, th), th / 2, th / 2)
        kr = 7.0 * max(self._h, 1.0 if self._drag else 0.0)
        if kr > 0.5:
            p.setBrush(QColor(0, 0, 0, 60))
            p.drawEllipse(QPointF(pad + fw, cy + 1), kr, kr)
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(pad + fw, cy), kr, kr)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._v = self._x2v(e.position().x())
            self.moved.emit(self._v)
            self.update()
            self._to(1.0)

    def mouseMoveEvent(self, e):
        v = self._x2v(e.position().x())
        if self._drag:
            self._v = v
            self.moved.emit(v)
            self.update()
        self.hovered.emit(v, e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.released.emit(self._v)
            self.update()
            if not self.underMouse():
                self._to(0.0)

    def enterEvent(self, e):
        self._to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self._drag:
            self._to(0.0)
        super().leaveEvent(e)

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if d:
            self.wheel.emit(1 if d > 0 else -1)


class Reveal(QWidget):
    """Clips a fixed-size inner widget; animate `amt` 0..1 to slide it open/closed."""

    def __init__(self, inner, size, horizontal, parent=None):
        super().__init__(parent)
        self.inner, self.size_, self.hz, self._a = inner, size, horizontal, 1.0
        inner.setParent(self)
        inner.show()
        self.set_amt(1.0)

    def get_amt(self):
        return self._a

    def set_amt(self, v):
        self._a = v
        n = int(round(self.size_ * v))
        if self.hz:
            self.setFixedWidth(n)
        else:
            self.setFixedHeight(n)
        self.setVisible(n > 0)

    amt = pyqtProperty(float, get_amt, set_amt)

    def resizeEvent(self, e):
        if self.hz:
            self.inner.setGeometry(0, 0, self.size_, self.height())
        else:
            self.inner.setGeometry(0, 0, self.width(), self.size_)
        super().resizeEvent(e)


# ----------------------------------------------------------------------------- views
def logo_pixmap(size):
    pm = QPixmap(os.path.join(app_dir(), "icon.png"))
    if not pm.isNull():
        return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, T.a1)
    g.setColorAt(1, T.a2)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    draw_icon(p, "play", QRectF(size * 0.25, size * 0.25, size * 0.5, size * 0.5), QColor("white"))
    p.end()
    return pm


class Video(QVideoWidget):
    clicked = pyqtSignal()
    dbl = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.dbl.emit()
        super().mouseDoubleClickEvent(e)


class AudioView(QWidget):
    """Cover art / artwork stage shown for music."""

    def __init__(self):
        super().__init__()
        self.pix = None
        self.title, self.sub = "", ""
        self.angle = 0.0
        self.playing = False
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)

    def _tick(self):
        self.angle = (self.angle + 1.6) % 360
        self.update()

    def set_info(self, title, sub):
        self.title, self.sub = title, sub
        self.update()

    def set_cover(self, pix):
        self.pix = pix
        self.update()

    def set_playing(self, on):
        self.playing = on
        self._sync()

    def _sync(self):
        if self.playing and self.isVisible():
            self.timer.start()
        else:
            self.timer.stop()

    def showEvent(self, e):
        self._sync()
        super().showEvent(e)

    def hideEvent(self, e):
        self._sync()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.43
        side = max(120.0, min(h * 0.5, w * 0.5, 360.0))
        gr = side * 1.15
        g = QRadialGradient(QPointF(cx, cy), gr)
        g.setColorAt(0, alpha(T.a1, 80))
        g.setColorAt(1, alpha(T.a1, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), gr, gr)
        r = QRectF(cx - side / 2, cy - side / 2, side, side)
        cg = QConicalGradient(QPointF(cx, cy), self.angle)
        cg.setColorAt(0, T.a1)
        cg.setColorAt(0.5, T.a2)
        cg.setColorAt(1, T.a1)
        p.setPen(QPen(QBrush(cg), 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r.adjusted(-11, -11, 11, 11), 32, 32)
        path = QPainterPath()
        path.addRoundedRect(r, 24, 24)
        p.save()
        p.setClipPath(path)
        if self.pix is not None and not self.pix.isNull():
            sc = self.pix.scaled(int(side), int(side), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                 Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(QPointF(r.left() - (sc.width() - side) / 2, r.top() - (sc.height() - side) / 2), sc)
        else:
            lg = QLinearGradient(r.topLeft(), r.bottomRight())
            lg.setColorAt(0, T.a1)
            lg.setColorAt(1, T.a2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(lg))
            p.drawRect(r)
            s = side * 0.4
            draw_icon(p, "music", QRectF(cx - s / 2, cy - s / 2, s, s), QColor(255, 255, 255, 230), 1.6)
        p.restore()
        f = QFont(self.font())
        f.setPixelSize(26)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(T.text))
        fm = QFontMetrics(f)
        ty = cy + side / 2 + 34
        p.drawText(QRectF(24, ty, w - 48, 38), A_C, fm.elidedText(self.title, Qt.TextElideMode.ElideRight, int(w - 48)))
        f2 = QFont(self.font())
        f2.setPixelSize(15)
        p.setFont(f2)
        p.setPen(QColor(T.sub))
        p.drawText(QRectF(24, ty + 40, w - 48, 24), A_C, self.sub)


class EmptyView(QWidget):
    def __init__(self, main):
        super().__init__()
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(116))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t = QLabel("Play anything")
        t.setObjectName("bigTitle")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s = QLabel("Drop a video or song anywhere in this window.\nMP4, MKV, AVI, MOV, WEBM, MP3, FLAC, WAV, OGG, M4A and more.")
        s.setObjectName("sub")
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b1 = Pill("Open files", "folder", primary=True, height=42)
        b2 = Pill("Open folder", "folder", height=42)
        b1.clicked.connect(main.open_dialog)
        b2.clicked.connect(main.open_folder_dialog)
        row.addWidget(b1)
        row.addWidget(b2)
        for w in (logo, t, s):
            v.addWidget(w)
        v.addSpacing(8)
        v.addLayout(row)

    def paintEvent(self, e):
        p = QPainter(self)
        g = QRadialGradient(QPointF(self.width() / 2, self.height() * 0.4), max(self.width(), self.height()) * 0.55)
        g.setColorAt(0, alpha(T.a1, 40))
        g.setColorAt(1, alpha(T.a1, 0))
        p.fillRect(self.rect(), QBrush(g))


# ----------------------------------------------------------------------------- library
class LibModel(QAbstractListModel):
    def __init__(self):
        super().__init__()
        self.rows = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, idx, role=Qt.ItemDataRole.DisplayRole):
        if idx.isValid() and role == Qt.ItemDataRole.DisplayRole:
            return self.rows[idx.row()]["title"]
        return None

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()


class LibDelegate(QStyledItemDelegate):
    H = 72

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def sizeHint(self, option, index):
        return QSize(0, self.H)

    def paint(self, p, o, idx):
        e = idx.model().rows[idx.row()]
        t = self.view.hover_t if idx.row() == self.view.hover_row else 0.0
        sel = bool(o.state & QStyle.StateFlag.State_Selected)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(o.rect()).adjusted(2, 3, -2, -3)
        bg = mix(T.surface, T.surface2, t)
        if sel:
            bg = mix(bg, T.a1, 0.2)
        p.setPen(QPen(mix(T.border, T.a1, 1.0 if sel else t * 0.5), 1))
        p.setBrush(bg)
        p.drawRoundedRect(r, 13, 13)
        # tile
        tile = QRectF(r.left() + 11, r.top() + (r.height() - 46) / 2, 46, 46)
        g = QLinearGradient(tile.topLeft(), tile.bottomRight())
        if e["kind"] == "audio":
            g.setColorAt(0, QColor("#F472B6"))
            g.setColorAt(1, QColor("#FB923C"))
        else:
            g.setColorAt(0, T.a1)
            g.setColorAt(1, T.a2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawRoundedRect(tile, 11, 11)
        ir = QRectF(tile.center().x() - 11, tile.center().y() - 11, 22, 22)
        p.setOpacity(1 - t)
        draw_icon(p, "music" if e["kind"] == "audio" else "video", ir, QColor("white"))
        p.setOpacity(t)
        draw_icon(p, "play", ir, QColor("white"))
        p.setOpacity(1.0)
        # text
        x0 = tile.right() + 14
        rx = r.right() - 14
        tw = max(40, rx - x0 - 120)
        f = QFont(o.font)
        f.setPixelSize(14)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor(T.text))
        p.drawText(QRectF(x0, r.top() + 9, tw, 20), A_L,
                   QFontMetrics(f).elidedText(e["title"], Qt.TextElideMode.ElideRight, int(tw)))
        f2 = QFont(o.font)
        f2.setPixelSize(12)
        p.setFont(f2)
        p.setPen(QColor(T.sub))
        sub = e.get("artist") or os.path.basename(os.path.dirname(e["path"])) or e["path"]
        p.drawText(QRectF(x0, r.top() + 30, tw, 18), A_L, QFontMetrics(f2).elidedText(sub, Qt.TextElideMode.ElideRight, int(tw)))
        if e.get("dur", 0) > 0 and e.get("pos", 0) > 0:
            frac = min(1.0, e["pos"] / e["dur"])
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(T.track))
            p.drawRoundedRect(QRectF(x0, r.bottom() - 11, tw, 3), 1.5, 1.5)
            pg = QLinearGradient(x0, 0, x0 + tw, 0)
            pg.setColorAt(0, T.a1)
            pg.setColorAt(1, T.a2)
            p.setBrush(QBrush(pg))
            p.drawRoundedRect(QRectF(x0, r.bottom() - 11, tw * frac, 3), 1.5, 1.5)
        # right column
        ext = os.path.splitext(e["path"])[1].lstrip(".").upper()[:5]
        f3 = QFont(o.font)
        f3.setPixelSize(10)
        f3.setBold(True)
        p.setFont(f3)
        bw = QFontMetrics(f3).horizontalAdvance(ext) + 14
        badge = QRectF(rx - bw, r.top() + 11, bw, 18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(alpha(T.a1, 46))
        p.drawRoundedRect(badge, 9, 9)
        p.setPen(mix(T.a1, T.text, 0.35))
        p.drawText(badge, A_C, ext)
        p.setFont(f2)
        p.setPen(QColor(T.sub))
        info = " · ".join(x for x in (fmt_time(e["dur"]) if e.get("dur") else "", e.get("res", ""), fmt_size(e["size"]) if e.get("size") else "") if x)
        p.drawText(QRectF(rx - 200, r.top() + 34, 200, 18), A_R, info)
        p.restore()


class LibView(QListView):
    def __init__(self, model):
        super().__init__()
        self.setModel(model)
        self.setItemDelegate(LibDelegate(self))
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.hover_row, self.hover_t = -1, 0.0
        self._a = QVariantAnimation(self)
        self._a.setDuration(170)
        self._a.setStartValue(0.0)
        self._a.setEndValue(1.0)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._a.valueChanged.connect(self._tick)

    def _tick(self, v):
        self.hover_t = float(v)
        self.viewport().update()

    def mouseMoveEvent(self, e):
        i = self.indexAt(e.position().toPoint())
        r = i.row() if i.isValid() else -1
        if r != self.hover_row:
            self.hover_row, self.hover_t = r, 0.0
            self._a.stop()
            if r >= 0:
                self._a.start()
            self.viewport().update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.hover_row = -1
        self.viewport().update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.model().rowCount() == 0:
            p = QPainter(self.viewport())
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = self.viewport().rect().center()
            draw_icon(p, "grid", QRectF(c.x() - 24, c.y() - 60, 48, 48), QColor(T.mute), 1.5)
            f = QFont(self.font())
            f.setPixelSize(16)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor(T.text))
            p.drawText(QRectF(0, c.y() - 4, self.viewport().width(), 28), A_C, "Nothing here yet")
            f.setBold(False)
            f.setPixelSize(13)
            p.setFont(f)
            p.setPen(QColor(T.sub))
            p.drawText(QRectF(0, c.y() + 24, self.viewport().width(), 24), A_C,
                       "Files you open are saved automatically. Add files or a folder to fill your library.")


class Scanner(QThread):
    found = pyqtSignal(list, bool)

    def __init__(self, folders, parent=None):
        super().__init__(parent)
        self.folders = folders
        self.all = []
        self.added = 0

    def run(self):
        buf = []
        for folder in self.folders:
            for root, dirs, files in os.walk(folder):
                dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith("$")]
                for f in files:
                    if os.path.splitext(f)[1].lower() in SCAN_EXT:
                        path = os.path.join(root, f)
                        buf.append(path)
                        self.all.append(path)
                        if len(buf) >= 250:
                            self.found.emit(buf, False)
                            buf = []
        self.found.emit(buf, True)


class Store:
    def __init__(self):
        DATA.mkdir(parents=True, exist_ok=True)
        self.sf, self.lf = DATA / "settings.json", DATA / "library.json"
        self.s = dict(DEFAULTS)
        self.s.update(self._read(self.sf, {}))
        self.lib = self._read(self.lf, [])

    @staticmethod
    def _read(f, default):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _write(f, obj):
        try:
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, f)
        except Exception:
            pass

    def save(self):
        self._write(self.sf, self.s)
        self._write(self.lf, self.lib)


def make_entry(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    return {"path": path, "title": Path(path).stem, "kind": "audio" if ext in AUDIO_EXT else "video", "size": size,
            "added": time.time(), "pos": 0, "dur": 0, "plays": 0, "last": 0}


def register_open_with(add=True):
    """Adds/removes Lumen in Explorer's 'Open with' list for every media type (per-user, no admin needed)."""
    import winreg
    if getattr(sys, "frozen", False):
        exe = sys.executable
        cmd = f'"{exe}" "%1"'
    else:
        exe = sys.executable
        pyw = exe.replace("python.exe", "pythonw.exe")
        cmd = f'"{pyw}" "{os.path.abspath(__file__)}" "%1"'
    base = r"Software\Classes\Lumen.Media"
    hk = winreg.HKEY_CURRENT_USER
    if add:
        winreg.SetValue(hk, base, winreg.REG_SZ, "Lumen media file")
        winreg.SetValue(hk, base + r"\DefaultIcon", winreg.REG_SZ, f"{exe},0")
        winreg.SetValue(hk, base + r"\shell\open\command", winreg.REG_SZ, cmd)
        for ext in MEDIA_EXT:
            k = winreg.CreateKey(hk, rf"Software\Classes\{ext}\OpenWithProgids")
            winreg.SetValueEx(k, "Lumen.Media", 0, winreg.REG_NONE, b"")
            winreg.CloseKey(k)
    else:
        for ext in MEDIA_EXT:
            try:
                k = winreg.OpenKey(hk, rf"Software\Classes\{ext}\OpenWithProgids", 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(k, "Lumen.Media")
                winreg.CloseKey(k)
            except OSError:
                pass
        for sub in (r"\shell\open\command", r"\shell\open", r"\shell", r"\DefaultIcon", ""):
            try:
                winreg.DeleteKey(hk, base + sub)
            except OSError:
                pass
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


# ----------------------------------------------------------------------------- main window
DETAIL_FIELDS = [("artist", "Artist"), ("album", "Album"), ("genre", "Genre"), ("year", "Year"),
                 ("dur", "Duration"), ("res", "Resolution"), ("fps", "Frame rate"), ("vcodec", "Video codec"),
                 ("acodec", "Audio codec"), ("vbr", "Video bitrate"), ("abr", "Audio bitrate"),
                 ("fmt", "Container"), ("size", "File size"), ("added", "Added to library"),
                 ("plays", "Times played"), ("path", "Location")]


class Main(QWidget):
    PLAYER, LIBRARY, SETTINGS = 0, 1, 2

    def __init__(self, store):
        super().__init__()
        self.store, self.s = store, store.s
        self.index = {norm(e["path"]): e for e in store.lib}
        self.queue, self.qi, self.history, self.current = [], -1, [], None
        self._pending, self._last_save, self.err_streak = 0, 0.0, 0
        self.shuffle, self.repeat, self.speed = bool(self.s["shuffle"]), int(self.s["repeat"]), 1.0
        self.drawer_open, self._scans = False, []
        self._cursor_hidden, self._last_pos, self.last_act = False, QCursor.pos(), time.monotonic()
        self._titlebar_done = False
        T.dark, T.accent = bool(self.s["dark"]), self.s["accent"]
        T.refresh()

        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowTitle(APP)
        self.setWindowIcon(QIcon(os.path.join(app_dir(), "icon.ico")))
        self.setMinimumSize(980, 640)
        self.resize(1220, 760)
        self.setAcceptDrops(True)
        if self.s["geometry"]:
            self.restoreGeometry(QByteArray.fromBase64(self.s["geometry"].encode()))
        if self.s["on_top"]:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.store.save)
        self.click_timer = QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.toggle_play)
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(150)
        self.idle_timer.timeout.connect(self.idle_tick)
        self._bar_target = 1.0

        self.build_ui()
        self.build_engine()
        QApplication.instance().setStyleSheet(build_qss())
        QApplication.instance().installEventFilter(self)
        self.idle_timer.start()

        self.go(self.PLAYER)
        self.refresh_library()
        if self.s["autoscan"] and self.s["folders"]:
            QTimer.singleShot(900, lambda: self.scan_folders(self.s["folders"], quiet=True))

    # ------------------------------------------------------------------ UI
    def build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.side = QWidget()
        self.side.setObjectName("side")
        self.side.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.side.setFixedWidth(84)
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(8, 18, 8, 16)
        sl.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(44))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(logo)
        sl.addSpacing(16)
        self.nav = [NavButton("playcircle", "Player"), NavButton("grid", "Library"), NavButton("sliders", "Settings")]
        for i, b in enumerate(self.nav):
            b.clicked.connect(lambda _=False, i=i: self.go(i))
        sl.addWidget(self.nav[0], 0, Qt.AlignmentFlag.AlignHCenter)
        sl.addWidget(self.nav[1], 0, Qt.AlignmentFlag.AlignHCenter)
        sl.addStretch(1)
        sl.addWidget(self.nav[2], 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.side)

        col = QVBoxLayout()
        col.setSpacing(0)
        root.addLayout(col, 1)

        self.header = QWidget()
        self.header.setFixedHeight(64)
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(28, 0, 28, 0)
        self.page_title = QLabel("Now Playing")
        self.page_title.setObjectName("pageTitle")
        self.toast = QLabel("")
        self.toast.setObjectName("toast")
        self._toast_fx = QGraphicsOpacityEffect(self.toast)
        self._toast_fx.setOpacity(0.0)
        self.toast.setGraphicsEffect(self._toast_fx)
        self._toast_a = QPropertyAnimation(self._toast_fx, b"opacity", self)
        self._toast_a.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._toast_t = QTimer(self)
        self._toast_t.setSingleShot(True)
        self._toast_t.timeout.connect(self._toast_hide)
        hl.addWidget(self.page_title)
        hl.addStretch(1)
        hl.addWidget(self.toast)
        col.addWidget(self.header)

        self.pages = QStackedWidget()
        col.addWidget(self.pages, 1)
        self.pages.addWidget(self.build_player_page())
        self.pages.addWidget(self.build_library_page())
        self.pages.addWidget(self.build_settings_page())

        self.bar_inner = self.build_controls()
        self.bar = Reveal(self.bar_inner, BAR_H, horizontal=False)
        col.addWidget(self.bar)
        self.bar_anim = QPropertyAnimation(self.bar, b"amt", self)
        self.bar_anim.setDuration(260)
        self.bar_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def build_player_page(self):
        page = QWidget()
        h = QHBoxLayout(page)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.views = QStackedWidget()
        self.empty = EmptyView(self)
        self.video = Video()
        self.audio_view = AudioView()
        vwrap = QWidget()
        vwrap.setStyleSheet("background:#000;")
        vl = QVBoxLayout(vwrap)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.addWidget(self.video)
        self.views.addWidget(self.empty)
        self.views.addWidget(vwrap)
        self.views.addWidget(self.audio_view)
        h.addWidget(self.views, 1)
        self.drawer_inner = self.build_drawer()
        self.drawer = Reveal(self.drawer_inner, DRAWER_W, horizontal=True)
        self.drawer.set_amt(0.0)
        self.drawer_anim = QPropertyAnimation(self.drawer, b"amt", self)
        self.drawer_anim.setDuration(300)
        self.drawer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        h.addWidget(self.drawer)
        self.video.clicked.connect(lambda: self.click_timer.start(230))
        self.video.dbl.connect(self._video_dbl)
        return page

    def _video_dbl(self):
        self.click_timer.stop()
        self.toggle_fullscreen()

    def build_drawer(self):
        w = QWidget()
        w.setObjectName("drawer")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.setContentsMargins(18, 16, 14, 16)
        v.setSpacing(12)
        self.drawer_tabs = Segmented(["Details", "Up Next"])
        v.addWidget(self.drawer_tabs, 0, Qt.AlignmentFlag.AlignLeft)
        self.drawer_stack = QStackedWidget()
        v.addWidget(self.drawer_stack, 1)

        sc = QScrollArea()
        sc.setWidgetResizable(True)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(0, 0, 8, 0)
        il.setSpacing(12)
        self.det_title = QLabel("Nothing playing")
        self.det_title.setObjectName("detTitle")
        self.det_title.setWordWrap(True)
        il.addWidget(self.det_title)
        self.det = {}
        for key, label in DETAIL_FIELDS:
            c = QWidget()
            cl = QVBoxLayout(c)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(1)
            cap = QLabel(label.upper())
            cap.setObjectName("cap")
            val = QLabel("")
            val.setObjectName("val")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cl.addWidget(cap)
            cl.addWidget(val)
            c.setVisible(False)
            il.addWidget(c)
            self.det[key] = (c, val)
        il.addStretch(1)
        sc.setWidget(inner)

        qw = QWidget()
        ql = QVBoxLayout(qw)
        ql.setContentsMargins(0, 0, 0, 0)
        ql.setSpacing(10)
        self.qlist = QListWidget()
        self.qlist.setUniformItemSizes(True)
        self.qlist.itemDoubleClicked.connect(lambda it: self.play_index(self.qlist.row(it)))
        ql.addWidget(self.qlist, 1)
        clr = Pill("Clear queue", height=34)
        clr.clicked.connect(self.clear_queue)
        ql.addWidget(clr, 0, Qt.AlignmentFlag.AlignLeft)

        self.drawer_stack.addWidget(sc)
        self.drawer_stack.addWidget(qw)
        self.drawer_tabs.changed.connect(self.drawer_stack.setCurrentIndex)
        return w

    def build_library_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 0, 28, 8)
        v.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search your library")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(38)
        self._search_t = QTimer(self)
        self._search_t.setSingleShot(True)
        self._search_t.timeout.connect(self.refresh_library)
        self.search.textChanged.connect(lambda _: self._search_t.start(140))
        self.kind_seg = Segmented(["All", "Video", "Music"], int(self.s["kind"]))
        self.kind_seg.changed.connect(self._kind_changed)
        self.SORTS = ["Recently added", "Name", "Recently played", "Size"]
        self.sort_btn = Pill(self.SORTS[int(self.s["sort"])], "chevron")
        self.sort_btn.clicked.connect(self.sort_menu)
        b_files = Pill("Add files", "plus")
        b_folder = Pill("Add folder", "folder")
        b_all = Pill("Play all", "play", primary=True)
        b_files.clicked.connect(self.add_files_dialog)
        b_folder.clicked.connect(self.add_folder_dialog)
        b_all.clicked.connect(self.play_all)
        top.addWidget(self.search, 1)
        top.addWidget(self.kind_seg)
        top.addWidget(self.sort_btn)
        top.addWidget(b_files)
        top.addWidget(b_folder)
        top.addWidget(b_all)
        v.addLayout(top)
        self.count_lbl = QLabel("")
        self.count_lbl.setObjectName("sub")
        v.addWidget(self.count_lbl)
        self.model = LibModel()
        self.view = LibView(self.model)
        self.view.doubleClicked.connect(self.lib_play)
        self.view.activated.connect(self.lib_play)
        self.view.customContextMenuRequested.connect(self.lib_menu)
        v.addWidget(self.view, 1)
        return page

    def build_settings_page(self):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        body = QWidget()
        col = QVBoxLayout(body)
        col.setContentsMargins(28, 0, 28, 28)
        col.setSpacing(10)

        def card(heading):
            col.addSpacing(8)
            lab = QLabel(heading.upper())
            lab.setObjectName("h2")
            col.addWidget(lab)
            fr = QFrame()
            fr.setObjectName("card")
            cl = QVBoxLayout(fr)
            cl.setContentsMargins(20, 4, 20, 4)
            cl.setSpacing(0)
            col.addWidget(fr)
            return cl

        def row(cl, title, desc, widget):
            if cl.count():
                sep = QFrame()
                sep.setObjectName("sep")
                cl.addWidget(sep)
            rw = QWidget()
            h = QHBoxLayout(rw)
            h.setContentsMargins(0, 14, 0, 14)
            h.setSpacing(16)
            left = QVBoxLayout()
            left.setSpacing(2)
            t = QLabel(title)
            t.setObjectName("rowTitle")
            left.addWidget(t)
            if desc:
                d = QLabel(desc)
                d.setObjectName("rowDesc")
                d.setWordWrap(True)
                left.addWidget(d)
            h.addLayout(left, 1)
            h.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
            cl.addWidget(rw)

        # appearance
        c = card("Appearance")
        row(c, "Dark mode", "Switch between the dark and light look.",
            self.bind_toggle("dark", "Dark mode on", "Light mode on", lambda v: self.apply_theme()))
        sw = QWidget()
        swl = QHBoxLayout(sw)
        swl.setContentsMargins(0, 0, 0, 0)
        swl.setSpacing(4)
        self.swatches = []
        for col_hex in ACCENTS:
            b = Swatch(col_hex)
            b.setChecked(col_hex.lower() == str(self.s["accent"]).lower())
            b.clicked.connect(lambda _=False, h=col_hex: self.set_accent(h))
            self.swatches.append(b)
            swl.addWidget(b)
        row(c, "Accent color", "Used for buttons, sliders and highlights.", sw)
        row(c, "Notifications", "Small messages when you toggle something or change speed and volume.",
            self.bind_toggle("toasts", "Notifications on", "Notifications off"))

        # playback
        c = card("Playback")
        row(c, "Resume where you left off", "Videos and songs continue from the last position.",
            self.bind_toggle("resume", "Resume on", "Resume off"))
        row(c, "Play next automatically", "Move on to the next item in the queue when one ends.",
            self.bind_toggle("autonext", "Auto-play next on", "Auto-play next off"))
        row(c, "Remember volume", "Start with the volume you used last time.",
            self.bind_toggle("remember_vol", "Volume is remembered", "Volume resets each launch"))
        steps = [5, 10, 15, 30]
        seg = Segmented([f"{x}s" for x in steps], steps.index(self.s["seek_step"]) if self.s["seek_step"] in steps else 1)
        seg.changed.connect(lambda i: self._set_step(steps[i]))
        row(c, "Skip step", "How far the left and right arrow keys jump.", seg)
        row(c, "Auto-hide controls in fullscreen", "Controls and cursor fade out while you watch.",
            self.bind_toggle("autohide", "Auto-hide on", "Auto-hide off"))
        row(c, "Always on top", "Keep the player above other windows.",
            self.bind_toggle("on_top", "Always on top", "Always on top off", self._set_on_top))

        # library
        c = card("Library")
        row(c, "Save opened files automatically",
            "Every video or song you open is added to your Library, in any format.",
            self.bind_toggle("autosave", "Auto-save on", "Auto-save off"))
        row(c, "Scan watched folders on startup", "New videos and music in your folders show up by themselves.",
            self.bind_toggle("autoscan", "Startup scan on", "Startup scan off"))
        fw = QWidget()
        fl = QHBoxLayout(fw)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(8)
        bf = Pill("Add folder", "plus", height=34)
        bs = Pill("Scan now", height=34)
        br = Pill("Remove selected", height=34)
        bf.clicked.connect(self.add_watch_folder)
        bs.clicked.connect(lambda: self.scan_folders(self.s["folders"]))
        br.clicked.connect(self.remove_watch_folder)
        for b in (bf, bs, br):
            fl.addWidget(b)
        row(c, "Watched folders", "Lumen saves every video and song it finds in these folders.", fw)
        self.folder_list = QListWidget()
        self.folder_list.setFixedHeight(104)
        c.addWidget(self.folder_list)
        c.addSpacing(10)
        self.refresh_folder_list()
        clr = Pill("Clear library", height=34)
        clr.clicked.connect(self.clear_library)
        row(c, "Clear library", "Removes the list only. Your files are never touched.", clr)

        # system
        if sys.platform == "win32":
            c = card("Windows")
            w = QWidget()
            wl = QHBoxLayout(w)
            wl.setContentsMargins(0, 0, 0, 0)
            wl.setSpacing(8)
            ba, bd = Pill("Add", height=34), Pill("Remove", height=34)
            ba.clicked.connect(lambda: self._open_with(True))
            bd.clicked.connect(lambda: self._open_with(False))
            wl.addWidget(ba)
            wl.addWidget(bd)
            row(c, "Show Lumen in 'Open with'", "Adds Lumen to the right-click menu of every video and music file.", w)

        c = card("Keyboard")
        k = QLabel("Space  play / pause      ← →  skip      ↑ ↓  volume      M  mute      F  fullscreen\n"
                   "N / P  next / previous      [ ]  speed      I  details      S  stop      Ctrl+O  open files")
        k.setObjectName("rowDesc")
        k.setContentsMargins(0, 14, 0, 14)
        c.addWidget(k)
        c = card("About")
        a = QLabel(f"{APP} {VERSION} - plays everything FFmpeg can decode.")
        a.setObjectName("rowDesc")
        a.setContentsMargins(0, 14, 0, 14)
        c.addWidget(a)
        col.addStretch(1)
        sc.setWidget(body)
        return sc

    def build_controls(self):
        w = QWidget()
        w.setObjectName("bar")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(w)
        v.setContentsMargins(24, 8, 24, 12)
        v.setSpacing(0)
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        self.t_cur = QLabel("0:00")
        self.t_cur.setObjectName("time")
        self.t_cur.setFixedWidth(58)
        self.t_cur.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.t_tot = QLabel("0:00")
        self.t_tot.setObjectName("time")
        self.t_tot.setFixedWidth(58)
        self.seek = Slider(1)
        self.seek.moved.connect(lambda v: self.t_cur.setText(fmt_time(v)))
        self.seek.released.connect(lambda v: self.player.setPosition(v))
        self.seek.hovered.connect(lambda val, pt: QToolTip.showText(pt + QPoint(-18, -38), fmt_time(val), self.seek))
        r1.addWidget(self.t_cur)
        r1.addWidget(self.seek, 1)
        r1.addWidget(self.t_tot)
        v.addLayout(r1)

        r2 = QHBoxLayout()
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(1)
        self.np_title = QLabel("Nothing playing")
        self.np_title.setObjectName("npTitle")
        self.np_sub = QLabel("Open a file or drop one here")
        self.np_sub.setObjectName("sub")
        ll.addStretch(1)
        ll.addWidget(self.np_title)
        ll.addWidget(self.np_sub)
        ll.addStretch(1)
        left.setMinimumWidth(180)

        center = QWidget()
        cl = QHBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        self.btn_shuffle = IconButton("shuffle", 40, 20, tip="Shuffle (queue order)")
        self.btn_shuffle.setCheckable(True)
        self.btn_shuffle.setChecked(self.shuffle)
        self.btn_prev = IconButton("prev", 42, 20, tip="Previous (P)")
        self.btn_play = IconButton("play", 54, 22, primary=True, tip="Play / Pause (Space)")
        self.btn_next = IconButton("next", 42, 20, tip="Next (N)")
        self.btn_repeat = IconButton("repeat1" if self.repeat == 2 else "repeat", 40, 20, tip="Repeat")
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.setChecked(self.repeat > 0)
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_prev.clicked.connect(lambda: self.prev_track())
        self.btn_play.clicked.connect(self.toggle_play)
        self.btn_next.clicked.connect(lambda: self.step(1))
        self.btn_repeat.clicked.connect(self.cycle_repeat)
        for b in (self.btn_shuffle, self.btn_prev, self.btn_play, self.btn_next, self.btn_repeat):
            cl.addWidget(b)

        right = QWidget()
        rl = QHBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addStretch(1)
        self.btn_audio = Pill("Audio", "audio", height=32)
        self.btn_subs = Pill("Subtitles", "subs", height=32)
        self.btn_audio.setVisible(False)
        self.btn_subs.setVisible(False)
        self.btn_audio.clicked.connect(self.audio_menu)
        self.btn_subs.clicked.connect(self.subs_menu)
        self.btn_speed = Pill("1×", height=32)
        self.btn_speed.clicked.connect(self.speed_menu)
        self.btn_open = IconButton("folder", 36, 19, tip="Open files (Ctrl+O)")
        self.btn_open.clicked.connect(self.open_dialog)
        self.btn_vol = IconButton("volume", 36, 20, tip="Mute (M)")
        self.btn_vol.clicked.connect(self.toggle_mute)
        self.vol = Slider(100)
        self.vol.setFixedWidth(104)
        self.vol.moved.connect(lambda v: self.set_volume(v, notify=False))
        self.vol.wheel.connect(lambda d: self.set_volume(self.vol.value() + 5 * d))
        self.btn_info = IconButton("info", 36, 20, tip="Details & queue (I)")
        self.btn_info.setCheckable(True)
        self.btn_info.clicked.connect(self.toggle_drawer)
        self.btn_fs = IconButton("fullscreen", 36, 20, tip="Fullscreen (F)")
        self.btn_fs.clicked.connect(self.toggle_fullscreen)
        for wdg in (self.btn_audio, self.btn_subs, self.btn_speed, self.btn_open, self.btn_vol, self.vol,
                    self.btn_info, self.btn_fs):
            rl.addWidget(wdg)

        r2.addWidget(left, 1)
        r2.addWidget(center)
        r2.addWidget(right, 1)
        v.addLayout(r2)
        return w

    # ------------------------------------------------------------------ engine
    def build_engine(self):
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        v = int(round(float(self.s["volume"]) * 100)) if self.s["remember_vol"] else 80
        self.set_volume(v, notify=False)
        if self.s["remember_vol"] and self.s["muted"]:
            self.audio.setMuted(True)
        self.refresh_vol_icon()
        self.player.positionChanged.connect(self.on_pos)
        self.player.durationChanged.connect(self.on_dur)
        self.player.playbackStateChanged.connect(self.on_state)
        self.player.mediaStatusChanged.connect(self.on_status)
        self.player.errorOccurred.connect(self.on_error)
        self.player.metaDataChanged.connect(self.on_meta)
        self.player.hasVideoChanged.connect(self.on_hasvideo)
        self.player.tracksChanged.connect(self.on_tracks)

    def entry(self, path):
        return self.index.get(norm(path)) if path else None

    def queue_save(self):
        self.save_timer.start(800)

    def add_paths(self, paths):
        n = 0
        for p in paths:
            k = norm(p)
            if k in self.index:
                continue
            e = make_entry(p)
            self.store.lib.append(e)
            self.index[k] = e
            n += 1
        if n:
            self.refresh_library()
            self.queue_save()
        return n

    # --- playing
    def open_paths(self, paths):
        files = [p for p in paths if os.path.isfile(p)]
        dirs = [p for p in paths if os.path.isdir(p)]
        if files:
            if self.s["autosave"]:
                self.add_paths(files)
            self.play_queue(files, 0)
        elif dirs:
            self.scan_folders(dirs, play=True, add=self.s["autosave"])

    def play_queue(self, paths, i=0, show=True):
        self.queue = list(paths)
        self.history = []
        self.qi = -1
        self.refresh_queue()
        self.play_index(i, show=show)

    def play_index(self, i, record=True, show=True):
        if not (0 <= i < len(self.queue)):
            return
        if record and self.qi >= 0 and self.shuffle:
            self.history = (self.history + [self.qi])[-100:]
        self.qi = i
        self.play_path(self.queue[i], show)
        self.mark_queue()

    def play_path(self, path, show=True):
        if not os.path.isfile(path):
            self.notify("File not found")
            return
        self.commit_position()
        self.current = path
        e = self.entry(path)
        if e is None and self.s["autosave"]:
            self.add_paths([path])
            e = self.entry(path)
        self._pending = 0
        if e and self.s["resume"]:
            pos, dur = e.get("pos", 0), e.get("dur", 0)
            if pos > 8000 and (dur == 0 or pos < dur - 8000):
                self._pending = pos
        if e:
            e["plays"] = e.get("plays", 0) + 1
            e["last"] = time.time()
            self.queue_save()
        ext = os.path.splitext(path)[1].lower()
        kind = e["kind"] if e else ("audio" if ext in AUDIO_EXT else "video")
        title = e["title"] if e else Path(path).stem
        sub = (e.get("artist") if e else "") or os.path.basename(os.path.dirname(path))
        self.views.setCurrentIndex(1 if kind == "video" else 2)
        self.audio_view.set_cover(None)
        self.audio_view.set_info(title, sub)
        self.set_now_playing(title, sub)
        self.seek.setRange(0, 1)
        self.seek.setValue(0)
        self.t_cur.setText("0:00")
        self.t_tot.setText("0:00")
        self.det_title.setText(title)
        for cont, _lab in self.det.values():
            cont.setVisible(False)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        if show and kind == "video":
            self.go(self.PLAYER)
        elif show and self.pages.currentIndex() != self.LIBRARY:
            self.go(self.PLAYER)

    def set_now_playing(self, title, sub):
        fm = QFontMetrics(self.np_title.font())
        self.np_title.setText(fm.elidedText(title, Qt.TextElideMode.ElideRight, 300))
        self.np_sub.setText(sub)

    def commit_position(self):
        e = self.entry(self.current)
        if e:
            pos, dur = self.player.position(), e.get("dur", 0) or self.player.duration()
            e["pos"] = pos if (dur <= 0 or pos < dur - 3000) else 0
            self.queue_save()

    def toggle_play(self):
        if self.current is None:
            if self.queue:
                self.play_index(max(0, self.qi))
            else:
                self.open_dialog()
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def stop(self):
        self.commit_position()
        self.player.stop()

    def seek_by(self, direction):
        step = int(self.s["seek_step"]) * 1000
        dur = max(self.player.duration(), 0)
        pos = max(0, self.player.position() + direction * step)
        if dur:
            pos = min(pos, dur - 100)
        self.player.setPosition(int(pos))
        self.notify(f"{'Forward' if direction > 0 else 'Back'} {self.s['seek_step']}s")

    def step(self, d, auto=False):
        n = len(self.queue)
        if not n:
            return
        if auto and self.repeat == 2:
            self.play_index(self.qi, record=False)
            return
        if self.shuffle and n > 1:
            if d < 0 and self.history:
                self.play_index(self.history.pop(), record=False)
                return
            self.play_index(random.choice([k for k in range(n) if k != self.qi]))
            return
        i = self.qi + d
        if i >= n or i < 0:
            if auto and self.repeat != 1:
                return
            i %= n
        self.play_index(i)

    def prev_track(self):
        if self.player.position() > 3000 or len(self.queue) < 2:
            self.player.setPosition(0)
        else:
            self.step(-1)

    def toggle_shuffle(self):
        self.shuffle = self.btn_shuffle.isChecked()
        self.s["shuffle"] = self.shuffle
        self.queue_save()
        self.notify("Shuffle on" if self.shuffle else "Shuffle off")

    def cycle_repeat(self):
        self.repeat = (self.repeat + 1) % 3
        self.s["repeat"] = self.repeat
        self.btn_repeat.set_icon("repeat1" if self.repeat == 2 else "repeat")
        self.btn_repeat.setChecked(self.repeat > 0)
        self.queue_save()
        self.notify(["Repeat off", "Repeat all", "Repeat one"][self.repeat])

    def set_volume(self, v, notify=True):
        v = int(max(0, min(100, v)))
        self.audio.setVolume(lin_volume(v / 100.0))
        self.s["volume"] = v / 100.0
        self.vol.setValue(v)
        self.refresh_vol_icon()
        self.queue_save()
        if notify:
            self.notify(f"Volume {v}%")

    def refresh_vol_icon(self):
        v = self.vol.value()
        if self.audio.isMuted() or v == 0:
            self.btn_vol.set_icon("mute")
        else:
            self.btn_vol.set_icon("volume_low" if v < 50 else "volume")

    def toggle_mute(self):
        m = not self.audio.isMuted()
        self.audio.setMuted(m)
        self.s["muted"] = m
        self.refresh_vol_icon()
        self.queue_save()
        self.notify("Muted" if m else "Sound on")

    def set_speed(self, r):
        self.speed = r
        self.player.setPlaybackRate(r)
        self.btn_speed.setText(f"{r:g}×")
        self.btn_speed.updateGeometry()
        self.notify(f"Speed {r:g}×")

    def nudge_speed(self, d):
        i = SPEEDS.index(self.speed) if self.speed in SPEEDS else SPEEDS.index(1.0)
        self.set_speed(SPEEDS[max(0, min(len(SPEEDS) - 1, i + d))])

    # --- player signals
    def on_pos(self, ms):
        if self._pending:
            return
        self.seek.setValue(ms)
        if not self.seek._drag:
            self.t_cur.setText(fmt_time(ms))
        now = time.monotonic()
        if now - self._last_save > 5:
            self._last_save = now
            self.commit_position()

    def on_dur(self, ms):
        self.seek.setRange(0, max(ms, 1))
        self.t_tot.setText(fmt_time(ms))
        e = self.entry(self.current)
        if e and ms > 0:
            e["dur"] = ms
            self.queue_save()

    def on_state(self, st):
        playing = st == QMediaPlayer.PlaybackState.PlayingState
        self.btn_play.set_icon("pause" if playing else "play")
        self.audio_view.set_playing(playing)

    def on_status(self, st):
        S = QMediaPlayer.MediaStatus
        if st in (S.LoadedMedia, S.BufferedMedia) and self._pending:
            pos, self._pending = self._pending, 0
            self.player.setPosition(int(pos))
        if st == S.LoadedMedia:
            self.err_streak = 0
            self.refresh_details()
        elif st == S.EndOfMedia:
            e = self.entry(self.current)
            if e:
                e["pos"] = 0
                self.queue_save()
            if self.s["autonext"]:
                self.step(1, auto=True)

    def on_error(self, err, msg):
        self.err_streak += 1
        name = Path(self.current).name if self.current else "file"
        self.notify(f"Can't play {name}")
        if self.s["autonext"] and len(self.queue) > 1 and self.err_streak < min(5, len(self.queue)):
            QTimer.singleShot(600, lambda: self.step(1, auto=True))

    def on_hasvideo(self, has):
        if self.current and self.views.currentIndex() != 0:
            self.views.setCurrentIndex(1 if has else 2)

    def on_tracks(self):
        try:
            self.btn_audio.setVisible(len(self.player.audioTracks()) > 1)
            self.btn_subs.setVisible(len(self.player.subtitleTracks()) > 0)
        except Exception:
            pass

    def on_meta(self):
        self.refresh_details()

    # --- details panel
    def refresh_details(self):
        path = self.current
        if not path:
            return
        md = self.player.metaData()
        e = self.entry(path)
        title = as_text(meta(md, "Title")) or (e["title"] if e else Path(path).stem)
        artist = as_text(meta(md, "ContributingArtist")) or as_text(meta(md, "Author")) or as_text(meta(md, "AlbumArtist")) or as_text(meta(md, "LeadPerformer"))
        album = as_text(meta(md, "AlbumTitle"))
        genre = as_text(meta(md, "Genre"))
        d = meta(md, "Date")
        year = ""
        if d is not None:
            try:
                year = str(d.date().year()) if hasattr(d, "date") else str(d.year())
            except Exception:
                year = str(d)[:4]
        res = meta(md, "Resolution")
        res_txt = ""
        if res is not None and hasattr(res, "width") and res.width() > 0:
            h = res.height()
            tag = "4K" if h >= 2000 else "2K" if h >= 1400 else "Full HD" if h >= 1000 else "HD" if h >= 700 else ""
            res_txt = f"{res.width()} × {h}" + (f"  ({tag})" if tag else "")
        fps = meta(md, "VideoFrameRate")
        fps_txt = f"{float(fps):.2f}".rstrip("0").rstrip(".") + " fps" if fps else ""

        def codec(kind, v):
            if v is None:
                return ""
            try:
                if kind == "v":
                    return QMediaFormat.videoCodecName(QMediaFormat.VideoCodec(v))
                return QMediaFormat.audioCodecName(QMediaFormat.AudioCodec(v))
            except Exception:
                return str(v)

        fmt = meta(md, "FileFormat")
        try:
            fmt_txt = QMediaFormat.fileFormatName(QMediaFormat.FileFormat(fmt)) if fmt is not None else ""
        except Exception:
            fmt_txt = ""
        ext = os.path.splitext(path)[1].lstrip(".").upper()
        fmt_txt = f"{fmt_txt} ({ext})" if fmt_txt and ext else (fmt_txt or ext)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = 0
        dur = self.player.duration()
        vals = {
            "artist": artist, "album": album, "genre": genre, "year": year,
            "dur": fmt_time(dur) if dur > 0 else "", "res": res_txt, "fps": fps_txt,
            "vcodec": codec("v", meta(md, "VideoCodec")), "acodec": codec("a", meta(md, "AudioCodec")),
            "vbr": fmt_rate(meta(md, "VideoBitRate")) if meta(md, "VideoBitRate") else "",
            "abr": fmt_rate(meta(md, "AudioBitRate")) if meta(md, "AudioBitRate") else "",
            "fmt": fmt_txt, "size": fmt_size(size) if size else "",
            "added": time.strftime("%d %b %Y", time.localtime(e["added"])) if e else "",
            "plays": str(e.get("plays", 0)) if e else "",
            "path": path.replace("\\", "\\\u200b").replace("/", "/\u200b"),
        }
        self.det_title.setText(title)
        for k, (cont, lab) in self.det.items():
            lab.setText(vals.get(k, ""))
            cont.setVisible(bool(vals.get(k)))
        # keep library + now-playing in sync with real tags
        if e:
            changed = False
            if e["kind"] == "audio" and title and e["title"] != title:
                e["title"], changed = title, True
            if artist and e.get("artist") != artist:
                e["artist"], changed = artist, True
            if res_txt and e.get("res") != res_txt.split("  ")[0]:
                e["res"], changed = res_txt.split("  ")[0], True
            if changed:
                self.queue_save()
        self.set_now_playing(e["title"] if e else title, artist or os.path.basename(os.path.dirname(path)))
        self.audio_view.set_info(e["title"] if e else title, " · ".join(x for x in (artist, album) if x))
        for name in ("ThumbnailImage", "CoverArtImage"):
            img = meta(md, name)
            if isinstance(img, QImage) and not img.isNull():
                self.audio_view.set_cover(QPixmap.fromImage(img))
                break

    # --- track menus
    @staticmethod
    def track_label(md, i):
        parts = []
        t = as_text(meta(md, "Title"))
        if t:
            parts.append(t)
        lang = meta(md, "Language")
        if lang is not None:
            try:
                name = QLocale.languageToString(QLocale.Language(lang))
                if name and name != "AnyLanguage":
                    parts.append(name)
            except Exception:
                pass
        return " · ".join(parts) or f"Track {i + 1}"

    def popup_above(self, menu, btn):
        menu.exec(btn.mapToGlobal(QPoint(0, -menu.sizeHint().height() - 6)))

    def audio_menu(self):
        m = QMenu(self)
        cur = self.player.activeAudioTrack()
        for i, md in enumerate(self.player.audioTracks()):
            a = m.addAction(self.track_label(md, i))
            a.setCheckable(True)
            a.setChecked(i == cur)
            a.triggered.connect(lambda _=False, i=i: (self.player.setActiveAudioTrack(i), self.notify("Audio track changed")))
        self.popup_above(m, self.btn_audio)

    def subs_menu(self):
        m = QMenu(self)
        cur = self.player.activeSubtitleTrack()
        off = m.addAction("Off")
        off.setCheckable(True)
        off.setChecked(cur < 0)
        off.triggered.connect(lambda: (self.player.setActiveSubtitleTrack(-1), self.notify("Subtitles off")))
        m.addSeparator()
        for i, md in enumerate(self.player.subtitleTracks()):
            a = m.addAction(self.track_label(md, i))
            a.setCheckable(True)
            a.setChecked(i == cur)
            a.triggered.connect(lambda _=False, i=i: (self.player.setActiveSubtitleTrack(i), self.notify("Subtitles on")))
        self.popup_above(m, self.btn_subs)

    def speed_menu(self):
        m = QMenu(self)
        for r in SPEEDS:
            a = m.addAction(f"{r:g}×" + ("  (normal)" if r == 1.0 else ""))
            a.setCheckable(True)
            a.setChecked(r == self.speed)
            a.triggered.connect(lambda _=False, r=r: self.set_speed(r))
        self.popup_above(m, self.btn_speed)

    # ------------------------------------------------------------------ queue
    def refresh_queue(self):
        self.qlist.clear()
        for k, p in enumerate(self.queue):
            e = self.entry(p)
            self.qlist.addItem(QListWidgetItem(f"{k + 1}.  {e['title'] if e else Path(p).stem}"))
        self.mark_queue()

    def mark_queue(self):
        for k in range(self.qlist.count()):
            it = self.qlist.item(k)
            f = it.font()
            f.setBold(k == self.qi)
            it.setFont(f)
            it.setForeground(QBrush(T.a1 if k == self.qi else QColor(T.sub)))

    def clear_queue(self):
        keep = [self.current] if self.current else []
        self.queue, self.qi, self.history = keep, (0 if keep else -1), []
        self.refresh_queue()
        self.notify("Queue cleared")

    # ------------------------------------------------------------------ library actions
    def _kind_changed(self, i):
        self.s["kind"] = i
        self.queue_save()
        self.refresh_library()

    def sort_menu(self):
        m = QMenu(self)
        for i, name in enumerate(self.SORTS):
            a = m.addAction(name)
            a.setCheckable(True)
            a.setChecked(i == self.s["sort"])
            a.triggered.connect(lambda _=False, i=i: self.set_sort(i))
        m.exec(self.sort_btn.mapToGlobal(QPoint(0, self.sort_btn.height() + 6)))

    def set_sort(self, i):
        self.s["sort"] = i
        self.sort_btn.setText(self.SORTS[i])
        self.sort_btn.updateGeometry()
        self.queue_save()
        self.refresh_library()

    def refresh_library(self):
        q = self.search.text().strip().lower()
        k = self.kind_seg.index()
        want = {1: "video", 2: "audio"}.get(k)
        rows = [e for e in self.store.lib
                if (want is None or e["kind"] == want)
                and (not q or q in e["title"].lower() or q in e["path"].lower() or q in e.get("artist", "").lower())]
        key = int(self.s["sort"])
        if key == 0:
            rows.sort(key=lambda e: -e["added"])
        elif key == 1:
            rows.sort(key=lambda e: nkey(e["title"]))
        elif key == 2:
            rows.sort(key=lambda e: -e.get("last", 0))
        else:
            rows.sort(key=lambda e: -e.get("size", 0))
        self.model.set_rows(rows)
        total = len(self.store.lib)
        self.count_lbl.setText(f"{len(rows)} shown · {total} saved in your library")

    def lib_play(self, idx):
        rows = self.model.rows
        if not (0 <= idx.row() < len(rows)):
            return
        e = rows[idx.row()]
        self.play_queue([r["path"] for r in rows], idx.row(), show=(e["kind"] == "video"))

    def play_all(self):
        rows = self.model.rows
        if rows:
            self.play_queue([r["path"] for r in rows], random.randrange(len(rows)) if self.shuffle else 0,
                            show=(rows[0]["kind"] == "video"))

    def lib_menu(self, pos):
        sel = sorted({i.row() for i in self.view.selectionModel().selectedIndexes()})
        if not sel:
            return
        rows = [self.model.rows[i] for i in sel]
        m = QMenu(self)
        a_play = m.addAction("Play")
        a_q = m.addAction("Add to queue")
        a_show = m.addAction("Show in folder") if len(rows) == 1 else None
        m.addSeparator()
        a_rm = m.addAction("Remove from library")
        act = m.exec(self.view.viewport().mapToGlobal(pos))
        if act is None:
            return
        if act == a_play:
            self.play_queue([r["path"] for r in rows], 0, show=(rows[0]["kind"] == "video"))
        elif act == a_q:
            self.queue += [r["path"] for r in rows]
            self.refresh_queue()
            self.notify(f"Added {len(rows)} to queue")
        elif a_show is not None and act == a_show:
            self.reveal(rows[0]["path"])
        elif act == a_rm:
            gone = {norm(r["path"]) for r in rows}
            self.store.lib[:] = [e for e in self.store.lib if norm(e["path"]) not in gone]
            for k in gone:
                self.index.pop(k, None)
            self.refresh_library()
            self.queue_save()
            self.notify(f"Removed {len(rows)} from library")

    @staticmethod
    def reveal(path):
        if sys.platform == "win32":
            subprocess.Popen(["explorer", f"/select,{os.path.normpath(path)}"])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def clear_library(self):
        if QMessageBox.question(self, APP, "Remove everything from your library?\nYour files stay where they are.") == QMessageBox.StandardButton.Yes:
            self.store.lib.clear()
            self.index.clear()
            self.refresh_library()
            self.queue_save()
            self.notify("Library cleared")

    # --- dialogs & scanning
    def open_dialog(self):
        allx = " ".join("*" + x for x in sorted(MEDIA_EXT))
        vx = " ".join("*" + x for x in sorted(VIDEO_EXT))
        ax = " ".join("*" + x for x in sorted(AUDIO_EXT))
        files, _ = QFileDialog.getOpenFileNames(self, "Open media", self.s["last_dir"],
                                                f"Media files ({allx});;Video ({vx});;Music ({ax});;All files (*.*)")
        if files:
            self.s["last_dir"] = os.path.dirname(files[0])
            self.open_paths(files)

    def open_folder_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Open a folder to play", self.s["last_dir"])
        if d:
            self.s["last_dir"] = d
            self.open_paths([d])

    def add_files_dialog(self):
        allx = " ".join("*" + x for x in sorted(MEDIA_EXT))
        files, _ = QFileDialog.getOpenFileNames(self, "Add to library", self.s["last_dir"], f"Media files ({allx});;All files (*.*)")
        if files:
            self.s["last_dir"] = os.path.dirname(files[0])
            n = self.add_paths(files)
            self.notify(f"Added {n} new file{'s' if n != 1 else ''}")

    def add_folder_dialog(self):
        d = QFileDialog.getExistingDirectory(self, "Add a folder to your library", self.s["last_dir"])
        if d:
            self.s["last_dir"] = d
            self.scan_folders([d])

    def scan_folders(self, folders, play=False, quiet=False, add=True):
        folders = [f for f in folders if os.path.isdir(f)]
        if not folders:
            return
        t = Scanner(folders, self)
        self._scans.append(t)
        t.found.connect(lambda paths, done, t=t: self._on_scan(t, paths, done, play, quiet, add))
        t.finished.connect(lambda t=t: self._scans.remove(t) if t in self._scans else None)
        if not quiet:
            self.notify("Scanning folder...")
        t.start()

    def _on_scan(self, t, paths, done, play, quiet, add):
        if add:
            t.added += self.add_paths(paths)
        if done:
            if play and t.all:
                self.play_queue(sorted(t.all, key=nkey), 0)
            elif not quiet or t.added:
                self.notify(f"Found {t.added} new file{'s' if t.added != 1 else ''}")

    def add_watch_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Watch a folder", self.s["last_dir"])
        if d and d not in self.s["folders"]:
            self.s["folders"].append(d)
            self.queue_save()
            self.refresh_folder_list()
            self.scan_folders([d])

    def remove_watch_folder(self):
        for it in self.folder_list.selectedItems():
            if it.text() in self.s["folders"]:
                self.s["folders"].remove(it.text())
        self.queue_save()
        self.refresh_folder_list()

    def refresh_folder_list(self):
        self.folder_list.clear()
        for f in self.s["folders"]:
            self.folder_list.addItem(f)

    def _open_with(self, add):
        try:
            register_open_with(add)
            self.notify("Added to 'Open with'" if add else "Removed from 'Open with'")
        except Exception:
            self.notify("Couldn't change Windows settings")

    # ------------------------------------------------------------------ settings helpers
    def bind_toggle(self, key, msg_on, msg_off, after=None):
        t = Toggle(bool(self.s[key]))

        def changed(v):
            self.s[key] = v
            self.queue_save()
            if after:
                after(v)
            self.notify(msg_on if v else msg_off)

        t.toggled.connect(changed)
        return t

    def _set_step(self, v):
        self.s["seek_step"] = v
        self.queue_save()
        self.notify(f"Skip step {v}s")

    def _set_on_top(self, v):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, v)
        self.show()
        self._titlebar_done = False
        self.apply_titlebar()

    def set_accent(self, hexcol):
        self.s["accent"] = hexcol
        for b in self.swatches:
            b.setChecked(b.color.name().lower() == hexcol.lower())
        self.queue_save()
        self.apply_theme()
        self.notify("Accent color changed")

    def apply_theme(self):
        T.dark, T.accent = bool(self.s["dark"]), self.s["accent"]
        T.refresh()
        QApplication.instance().setStyleSheet(build_qss())
        self.apply_titlebar()
        self.mark_queue()
        for w in QApplication.allWidgets():
            w.update()

    def apply_titlebar(self):
        if sys.platform != "win32":
            return
        try:
            hwnd = int(self.winId())
            dwm = ctypes.windll.dwmapi

            def setattr_(attr, val):
                v = ctypes.c_int(val)
                dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)

            def colorref(c):
                c = QColor(c)
                return c.red() | (c.green() << 8) | (c.blue() << 16)

            setattr_(20, 1 if T.dark else 0)
            setattr_(35, colorref(T.side))
            setattr_(36, colorref(T.text))
        except Exception:
            pass

    # ------------------------------------------------------------------ toasts / navigation
    def notify(self, text):
        if not self.s["toasts"]:
            return
        self.toast.setText(text)
        self.toast.adjustSize()
        a = self._toast_a
        a.stop()
        a.setDuration(150)
        a.setStartValue(self._toast_fx.opacity())
        a.setEndValue(1.0)
        a.start()
        self._toast_t.start(1900)

    def _toast_hide(self):
        a = self._toast_a
        a.stop()
        a.setDuration(420)
        a.setStartValue(self._toast_fx.opacity())
        a.setEndValue(0.0)
        a.start()

    def go(self, i):
        cur = self.pages.currentIndex()
        for k, b in enumerate(self.nav):
            b.setChecked(k == i)
        self.page_title.setText(["Now Playing", "Library", "Settings"][i])
        if i == cur:
            return
        self.pages.setCurrentIndex(i)
        if i != self.PLAYER:
            self.fade_in(self.pages.currentWidget())

    def fade_in(self, w):
        fx = QGraphicsOpacityEffect(w)
        fx.setOpacity(0.0)
        w.setGraphicsEffect(fx)
        a = QPropertyAnimation(fx, b"opacity", w)
        a.setDuration(240)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.finished.connect(lambda: QTimer.singleShot(0, lambda: w.setGraphicsEffect(None)))
        a.start()
        self._fade = a

    def toggle_drawer(self):
        if self.isFullScreen():
            self.btn_info.setChecked(False)
            return
        self.drawer_open = self.btn_info.isChecked()
        if self.drawer_open:
            self.go(self.PLAYER)
        self.drawer_anim.stop()
        self.drawer_anim.setStartValue(self.drawer.amt)
        self.drawer_anim.setEndValue(1.0 if self.drawer_open else 0.0)
        self.drawer_anim.start()

    # ------------------------------------------------------------------ fullscreen + auto-hide
    def toggle_fullscreen(self):
        if not self.isFullScreen():
            self._was_max = self.isMaximized()
            self.go(self.PLAYER)
            self.side.hide()
            self.header.hide()
            self.drawer.set_amt(0.0)
            self.btn_fs.set_icon("fullscreen_exit")
            self.showFullScreen()
            self.last_act = time.monotonic()
        else:
            self.wake()
            self.side.show()
            self.header.show()
            self.btn_fs.set_icon("fullscreen")
            if self.drawer_open:
                self.drawer.set_amt(1.0)
            self.showMaximized() if self._was_max else self.showNormal()

    def set_bar(self, show):
        target = 1.0 if show else 0.0
        if target == self._bar_target:
            return
        self._bar_target = target
        self.bar_anim.stop()
        self.bar_anim.setStartValue(self.bar.amt)
        self.bar_anim.setEndValue(target)
        self.bar_anim.start()

    def wake(self):
        self.set_bar(True)
        if self._cursor_hidden:
            QApplication.restoreOverrideCursor()
            self._cursor_hidden = False

    def idle_tick(self):
        pos = QCursor.pos()
        if pos != self._last_pos:
            self._last_pos = pos
            self.last_act = time.monotonic()
            if self.isFullScreen():
                self.wake()
        if (self.isFullScreen() and self.s["autohide"] and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
                and time.monotonic() - self.last_act > 2.6 and not self.bar.underMouse()):
            self.set_bar(False)
            if not self._cursor_hidden:
                QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
                self._cursor_hidden = True

    # ------------------------------------------------------------------ input
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.KeyPress and self.isActiveWindow() and QApplication.activePopupWidget() is None:
            fw = QApplication.focusWidget()
            if isinstance(fw, QLineEdit):
                if ev.key() == Qt.Key.Key_Escape:
                    fw.clearFocus()
                    return True
                return False
            if self.handle_key(ev):
                return True
        return False

    def handle_key(self, ev):
        k, auto = ev.key(), ev.isAutoRepeat()
        ctrl = bool(ev.modifiers() & Qt.KeyboardModifier.ControlModifier)
        K = Qt.Key
        if ctrl and k == K.Key_O:
            self.open_dialog()
        elif ctrl:
            return False
        elif k in (K.Key_Space, K.Key_K):
            if not auto:
                self.toggle_play()
        elif k in (K.Key_Right, K.Key_L):
            self.seek_by(1)
        elif k in (K.Key_Left, K.Key_J):
            self.seek_by(-1)
        elif k == K.Key_Up:
            self.set_volume(self.vol.value() + 5)
        elif k == K.Key_Down:
            self.set_volume(self.vol.value() - 5)
        elif k == K.Key_M and not auto:
            self.toggle_mute()
        elif k in (K.Key_F, K.Key_F11) and not auto:
            self.toggle_fullscreen()
        elif k == K.Key_Escape and self.isFullScreen():
            self.toggle_fullscreen()
        elif k in (K.Key_N, K.Key_PageDown) and not auto:
            self.step(1)
        elif k in (K.Key_P, K.Key_PageUp) and not auto:
            self.prev_track()
        elif k == K.Key_BracketLeft and not auto:
            self.nudge_speed(-1)
        elif k == K.Key_BracketRight and not auto:
            self.nudge_speed(1)
        elif k == K.Key_I and not auto:
            self.btn_info.click()
        elif k == K.Key_S and not auto:
            self.stop()
        else:
            return False
        return True

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.open_paths(paths)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._titlebar_done:
            self._titlebar_done = True
            QTimer.singleShot(0, self.apply_titlebar)

    def closeEvent(self, e):
        if self.isFullScreen():
            self.showNormal()
        if self._cursor_hidden:
            QApplication.restoreOverrideCursor()
        self.commit_position()
        self.s["geometry"] = self.saveGeometry().toBase64().data().decode()
        self.player.stop()
        self.store.save()
        super().closeEvent(e)


def main():
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lumen.MediaPlayer")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    w = Main(Store())
    w.show()
    args = [a for a in sys.argv[1:] if os.path.exists(a)]
    if args:
        QTimer.singleShot(300, lambda: w.open_paths(args))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
