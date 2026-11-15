"""
Prism Player — a native desktop media player.
Run:  python main.py        (needs:  pip install -r requirements.txt)
"""
import sys
import os
import time

from PySide6.QtCore import (Qt, QTimer, QUrl, QPropertyAnimation, QEasingCurve,
                             QSize, QRectF, QPointF, QPoint, Signal, Property, QSettings, QEvent)
from PySide6.QtGui import (QIcon, QPixmap, QPainter, QColor, QLinearGradient,
                            QPolygonF, QPen, QBrush, QImage)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedLayout,
    QPushButton, QSlider, QLabel, QFileDialog, QListWidget, QListWidgetItem,
    QComboBox, QDockWidget, QGraphicsOpacityEffect, QFrame
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

APP_NAME = "Prism Player"
APP_VERSION = "1.1.0"
VIOLET = "#7C5CFC"
TEAL = "#34E8C0"
BG = "#0A0B0E"
SURFACE = "#15171D"
SURFACE2 = "#1D2028"
TEXT = "#ECEDF2"
MUTED = "#878B98"
LINE = "#262A33"

VIDEO_EXT = (".mp4", ".webm", ".ogg", ".mov", ".mkv", ".avi", ".m4v", ".wmv", ".flv")


def fmt_ms(ms):
    if ms <= 0 or ms != ms:
        return "0:00"
    s = int(ms / 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def lerp_color(c1, c2, t):
    return QColor(
        int(c1.red() + (c2.red() - c1.red()) * t),
        int(c1.green() + (c2.green() - c1.green()) * t),
        int(c1.blue() + (c2.blue() - c1.blue()) * t),
    )


def make_logo_pixmap(size=64):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(VIOLET))
    grad.setColorAt(1, QColor(TEAL))

    outer = QPolygonF([QPointF(size * 0.5, size * 0.08),
                        QPointF(size * 0.92, size * 0.85),
                        QPointF(size * 0.08, size * 0.85)])
    pen = QPen(QBrush(grad), size * 0.07)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPolygon(outer)

    inner = QPolygonF([QPointF(size * 0.5, size * 0.34),
                        QPointF(size * 0.68, size * 0.68),
                        QPointF(size * 0.32, size * 0.68)])
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawPolygon(inner)
    p.end()
    return pm


class IconButton(QPushButton):
    def __init__(self, glyph, tooltip="", big=False):
        super().__init__(glyph)
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        d = 44 if big else 36
        self.setFixedSize(d, d)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT}; border: none;
                border-radius: {d // 2}px; font-size: {18 if big else 15}px;
            }}
            QPushButton:hover {{ background: rgba(255,255,255,0.10); }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.18); }}
            QPushButton:disabled {{ color: {MUTED}; }}
        """)


class ToggleSwitch(QWidget):
    """An animated on/off pill switch, violet->teal when on."""
    toggled = Signal(bool)

    def __init__(self, checked=False):
        super().__init__()
        self._checked = checked
        self._t = 1.0 if checked else 0.0
        self.setFixedSize(42, 24)
        self.setCursor(Qt.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"t")
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def getT(self):
        return self._t

    def setT(self, v):
        self._t = v
        self.update()

    t = Property(float, getT, setT)

    def isChecked(self):
        return self._checked

    def setChecked(self, val, animate=True):
        self._checked = val
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._t)
            self._anim.setEndValue(1.0 if val else 0.0)
            self._anim.start()
        else:
            self._t = 1.0 if val else 0.0
            self.update()

    def mousePressEvent(self, e):
        if self.isEnabled():
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = lerp_color(QColor(LINE), QColor(TEAL), self._t)
        if not self.isEnabled():
            track = QColor(LINE)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, 0, self.width(), self.height(), self.height() / 2, self.height() / 2)
        d = self.height() - 6
        x = 3 + self._t * (self.width() - d - 6)
        p.setBrush(QColor("#FFFFFF") if self.isEnabled() else QColor(MUTED))
        p.drawEllipse(QRectF(x, 3, d, d))


class SettingRow(QWidget):
    def __init__(self, title, subtitle, checked, enabled=True):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 10, 0, 10)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet(f"color:{TEXT}; font-size:13.5px; font-weight:600; background:transparent;")
        text_box.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(f"color:{MUTED}; font-size:11.5px; background:transparent;")
            text_box.addWidget(s)
        lay.addLayout(text_box, 1)
        self.switch = ToggleSwitch(checked)
        self.switch.setEnabled(enabled)
        lay.addWidget(self.switch)


class SettingsOverlay(QWidget):
    """A centred modal settings card over a dim backdrop."""
    def __init__(self, window):
        super().__init__(window)
        self.window_ref = window
        self.setStyleSheet("background: rgba(0,0,0,150);")
        self.hide()

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet(f"""
            QFrame {{ background:{SURFACE}; border:1px solid {LINE}; border-radius:16px; }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 20, 22, 18)
        cl.setSpacing(2)

        head = QHBoxLayout()
        title = QLabel("Settings")
        title.setStyleSheet(f"color:{TEXT}; font-size:16px; font-weight:700; background:transparent;")
        head.addWidget(title)
        head.addStretch(1)
        close_btn = IconButton("✕", "Close")
        close_btn.clicked.connect(self.hide_animated)
        head.addWidget(close_btn)
        cl.addLayout(head)
        cl.addSpacing(6)

        s = window.settings
        self.row_anim = SettingRow("Smooth UI animations", "Fades for the control bar and panels", s["anim_enabled"])
        self.row_loop = SettingRow("Loop playlist", "Jump back to the first video at the end", s["loop_playlist"])
        self.row_autoplay = SettingRow("Autoplay next", "Keep playing through the playlist", s["autoplay_next"])
        peek_sub = "Thumbnail preview while you drag the seek bar" if HAS_CV2 else "Needs: pip install opencv-python"
        self.row_peek = SettingRow("Scrubber video peek", peek_sub, s["peek_enabled"] and HAS_CV2, enabled=HAS_CV2)
        self.row_remember = SettingRow("Remember volume", "Keep your volume level next time you open Prism", s["remember_volume"])

        for row in (self.row_anim, self.row_loop, self.row_autoplay, self.row_peek, self.row_remember):
            cl.addWidget(row)
            line = QFrame()
            line.setFixedHeight(1)
            line.setStyleSheet(f"background:{LINE}; border:none;")
            cl.addWidget(line)

        self.row_anim.switch.toggled.connect(lambda v: window.update_setting("anim_enabled", v))
        self.row_loop.switch.toggled.connect(lambda v: window.update_setting("loop_playlist", v))
        self.row_autoplay.switch.toggled.connect(lambda v: window.update_setting("autoplay_next", v))
        self.row_peek.switch.toggled.connect(lambda v: window.update_setting("peek_enabled", v))
        self.row_remember.switch.toggled.connect(lambda v: window.update_setting("remember_volume", v))

        version_lbl = QLabel(f"{APP_NAME} v{APP_VERSION}")
        version_lbl.setStyleSheet(f"color:{MUTED}; font-size:10.5px; background:transparent;")
        version_lbl.setAlignment(Qt.AlignRight)
        cl.addSpacing(4)
        cl.addWidget(version_lbl)

        outer.addWidget(card, alignment=Qt.AlignCenter)

        self.opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_fx)
        self.anim = QPropertyAnimation(self.opacity_fx, b"opacity")
        self.anim.setDuration(180)
        # connected once — avoids stacking duplicate slots if toggled rapidly
        self.anim.finished.connect(self._on_anim_finished)

    def mousePressEvent(self, e):
        # click on the dim backdrop (outside the card) closes it
        self.hide_animated()

    def show_animated(self):
        self.setGeometry(self.window_ref.rect())
        self.raise_()
        self.show()
        self.opacity_fx.setOpacity(0.0)
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def hide_animated(self):
        self.anim.stop()
        self.anim.setStartValue(self.opacity_fx.opacity())
        self.anim.setEndValue(0.0)
        self.anim.start()

    def _on_anim_finished(self):
        if self.anim.endValue() == 0.0:
            self.hide()


class PeekPreview(QLabel):
    """Floating thumbnail shown above the scrubber on hover."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedSize(160, 90)
        self.setStyleSheet(f"""
            background:{SURFACE2}; border:1px solid {LINE}; border-radius:8px;
        """)
        self.setAlignment(Qt.AlignCenter)
        self.hide()


class VideoStage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ref = window
        self.setAcceptDrops(True)
        self.setStyleSheet(f"background:{BG};")

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background:black;")
        self.video_widget.mousePressEvent = self._on_video_click

        self.empty = QWidget()
        elay = QVBoxLayout(self.empty)
        elay.setAlignment(Qt.AlignCenter)
        elay.setSpacing(14)
        ring = QLabel("▶")
        ring.setAlignment(Qt.AlignCenter)
        ring.setFixedSize(84, 84)
        ring.setStyleSheet(f"border:1.5px dashed {LINE}; border-radius:42px; color:{MUTED}; font-size:22px;")
        title = QLabel("Nothing playing")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"color:{TEXT}; font-size:17px; font-weight:600;")
        sub = QLabel("Drag a video file here, or choose one from your PC.\nPlayback runs locally — nothing leaves your machine.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{MUTED}; font-size:12.5px;")
        choose = QPushButton("Choose video")
        choose.setCursor(Qt.PointingHandCursor)
        choose.setFixedWidth(160)
        choose.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {VIOLET}, stop:1 {TEAL});
                color:#0A0B0E; font-weight:700; font-size:13px; border:none; border-radius:18px; padding:10px;
            }}
        """)
        choose.clicked.connect(lambda: window.open_files())
        elay.addWidget(ring, alignment=Qt.AlignCenter)
        elay.addWidget(title)
        elay.addWidget(sub)
        elay.addWidget(choose, alignment=Qt.AlignCenter)

        self.stack = QStackedLayout(self)
        self.stack.setStackingMode(QStackedLayout.StackAll)
        self.stack.addWidget(self.video_widget)
        self.stack.addWidget(self.empty)
        self.show_empty(True)
        self.setMouseTracking(True)

    def show_empty(self, show):
        self.empty.setVisible(show)
        self.video_widget.setVisible(True)

    def _on_video_click(self, event):
        self.window_ref.toggle_play()

    def mouseMoveEvent(self, e):
        self.window_ref.notice_activity()
        super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e):
        self.window_ref.toggle_fullscreen()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        self.window_ref.add_files(paths)


class PrismPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1040, 640)
        self.setMinimumSize(560, 360)
        self.logo_pm = make_logo_pixmap(128)
        self.setWindowIcon(QIcon(self.logo_pm))
        self.setStyleSheet(f"QMainWindow {{ background:{BG}; }}")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)

        self.playlist = []
        self.cur_index = -1
        self._was_playing_before_scrub = False
        self._cv2_cap = None
        self._cv2_cap_path = None
        self._last_peek_grab = 0.0

        self.qsettings = QSettings("Prism", "PrismPlayer")
        self.settings = {
            "anim_enabled": self.qsettings.value("anim_enabled", True, type=bool),
            "loop_playlist": self.qsettings.value("loop_playlist", False, type=bool),
            "autoplay_next": self.qsettings.value("autoplay_next", True, type=bool),
            "peek_enabled": self.qsettings.value("peek_enabled", True, type=bool),
            "remember_volume": self.qsettings.value("remember_volume", True, type=bool),
        }
        start_volume = self.qsettings.value("volume", 100, type=int) if self.settings["remember_volume"] else 100

        self._build_ui()
        self._build_player()
        self.vol_slider.setValue(start_volume)

        self.settings_overlay = SettingsOverlay(self)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self._fade_controls_out)
        self.notice_activity()
        self.setFocus()

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background:{SURFACE}; border-bottom:1px solid {LINE};")
        header.setFixedHeight(54)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 14, 0)
        hl.setSpacing(10)

        logo_lbl = QLabel()
        logo_lbl.setPixmap(self.logo_pm.scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand = QLabel(f'<b>Prism</b> <span style="color:{TEAL}">Player</span>')
        brand.setStyleSheet(f"color:{TEXT}; font-size:16px;")
        hl.addWidget(logo_lbl)
        hl.addWidget(brand)
        hl.addStretch(1)

        open_btn = QPushButton("Open files")
        playlist_btn = QPushButton("Playlist")
        for b in (open_btn, playlist_btn):
            b.setCursor(Qt.PointingHandCursor)
            b.setFocusPolicy(Qt.NoFocus)
            b.setStyleSheet(f"""
                QPushButton {{
                    background:{SURFACE2}; color:{TEXT}; border:1px solid {LINE};
                    padding:7px 14px; border-radius:14px; font-size:12.5px;
                }}
                QPushButton:hover {{ border-color:{VIOLET}; }}
                QPushButton:pressed {{ background:{LINE}; }}
            """)
        open_btn.clicked.connect(self.open_files)
        playlist_btn.clicked.connect(self.toggle_playlist)
        hl.addWidget(open_btn)
        hl.addWidget(playlist_btn)

        self.settings_btn = IconButton("⚙", "Settings")
        self.settings_btn.clicked.connect(self.toggle_settings)
        hl.addWidget(self.settings_btn)

        root.addWidget(header)

        self.stage = VideoStage(self)
        root.addWidget(self.stage, 1)

        self.controls = self._build_controls()
        self.controls.setParent(self.stage)
        self.opacity_fx = QGraphicsOpacityEffect(self.controls)
        self.controls.setGraphicsEffect(self.opacity_fx)
        self.fade_anim = QPropertyAnimation(self.opacity_fx, b"opacity")
        self.fade_anim.setDuration(220)

        self.peek = PeekPreview(self.stage)

        self.setCentralWidget(central)

        self.dock = QDockWidget("Playlist", self)
        self.dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.dock.setStyleSheet(f"""
            QDockWidget {{ color:{MUTED}; background:{SURFACE}; }}
            QDockWidget::title {{ padding:10px; background:{SURFACE}; }}
        """)
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ background:{SURFACE}; color:{TEXT}; border:none; font-size:12.5px; }}
            QListWidget::item {{ padding:9px 10px; border-radius:8px; }}
            QListWidget::item:selected {{ background:{SURFACE2}; color:{TEAL}; }}
            QListWidget::item:hover {{ background:{SURFACE2}; }}
        """)
        self.list_widget.itemDoubleClicked.connect(self._on_playlist_pick)
        self.dock.setWidget(self.list_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.hide()

    def _build_controls(self):
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        v = QVBoxLayout(box)
        v.setContentsMargins(20, 0, 20, 16)
        v.setSpacing(10)

        # thin translucent scrub bar, full width
        scrub_wrap = QFrame()
        scrub_wrap.setStyleSheet("background: rgba(10,11,14,150); border-radius:10px;")
        sw = QHBoxLayout(scrub_wrap)
        sw.setContentsMargins(14, 9, 14, 9)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.setFocusPolicy(Qt.NoFocus)
        self.scrub.setMouseTracking(True)
        self.scrub.installEventFilter(self)
        self.scrub.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height:4px; background:rgba(255,255,255,40); border-radius:2px; }}
            QSlider::sub-page:horizontal {{
                height:4px; border-radius:2px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {VIOLET}, stop:1 {TEAL});
            }}
            QSlider::handle:horizontal {{ width:12px; height:12px; margin:-5px 0; border-radius:6px; background:white; }}
        """)
        self.scrub.sliderPressed.connect(self._scrub_pressed)
        self.scrub.sliderReleased.connect(self._scrub_released)
        self.scrub.sliderMoved.connect(self._scrub_moved)
        sw.addWidget(self.scrub)
        v.addWidget(scrub_wrap)

        # floating pill button bar, centred, sized to its content
        pill_row = QHBoxLayout()
        pill_row.addStretch(1)

        pill = QFrame()
        pill.setStyleSheet("background: rgba(21,23,29,235); border-radius:24px;")
        row = QHBoxLayout(pill)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(2)

        self.prev_btn = IconButton("⏮", "Previous")
        self.prev_btn.clicked.connect(self.play_prev)
        row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(42, 42)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setFocusPolicy(Qt.NoFocus)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {VIOLET}, stop:1 {TEAL});
                color:#0A0B0E; border:none; border-radius:21px; font-size:16px;
            }}
            QPushButton:hover {{ padding-left:2px; }}
            QPushButton:pressed {{ background: {VIOLET}; }}
        """)
        self.play_btn.clicked.connect(self.toggle_play)
        row.addWidget(self.play_btn)

        self.next_btn = IconButton("⏭", "Next")
        self.next_btn.clicked.connect(self.play_next)
        row.addWidget(self.next_btn)

        vol_wrap = QWidget()
        vol_lay = QHBoxLayout(vol_wrap)
        vol_lay.setContentsMargins(0, 0, 0, 0)
        vol_lay.setSpacing(2)
        vol_wrap.setMouseTracking(True)
        vol_wrap.installEventFilter(self)

        self.mute_btn = IconButton("🔊", "Mute")
        self.mute_btn.clicked.connect(self.toggle_mute)
        vol_lay.addWidget(self.mute_btn)

        self.vol_slider = QSlider(Qt.Horizontal)
        self.vol_slider.setMaximumWidth(0)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFocusPolicy(Qt.NoFocus)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height:4px; background:rgba(255,255,255,40); border-radius:2px; }}
            QSlider::sub-page:horizontal {{ height:4px; border-radius:2px; background:{TEAL}; }}
            QSlider::handle:horizontal {{ width:11px; height:11px; margin:-4px 0; border-radius:5px; background:white; }}
        """)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        self._vol_anim = QPropertyAnimation(self.vol_slider, b"maximumWidth")
        self._vol_anim.setDuration(160)
        self._vol_anim.setEasingCurve(QEasingCurve.OutCubic)
        vol_lay.addWidget(self.vol_slider)
        self._vol_wrap = vol_wrap
        row.addWidget(vol_wrap)

        self.speed_box = QComboBox()
        self.speed_box.addItems(["0.5x", "0.75x", "1x", "1.25x", "1.5x", "2x"])
        self.speed_box.setCurrentIndex(2)
        self.speed_box.setFocusPolicy(Qt.NoFocus)
        self.speed_box.setFixedWidth(56)
        self.speed_box.setStyleSheet(f"""
            QComboBox {{ background:transparent; color:{TEXT}; border:none;
                         border-radius:16px; padding:6px 8px; font-size:12px; }}
            QComboBox:hover {{ background: rgba(255,255,255,0.08); }}
        """)
        self.speed_box.currentTextChanged.connect(self._on_speed_changed)
        row.addWidget(self.speed_box)

        self.time_lbl = QLabel("0:00 / 0:00")
        self.time_lbl.setStyleSheet(f"color:{MUTED}; font-size:12px; padding:0 10px;")
        row.addWidget(self.time_lbl)

        self.pill_playlist_btn = QPushButton("Playlist  ›")
        self.pill_playlist_btn.setCursor(Qt.PointingHandCursor)
        self.pill_playlist_btn.setFocusPolicy(Qt.NoFocus)
        self.pill_playlist_btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{MUTED}; border:none;
                           border-radius:14px; padding:6px 12px; font-size:12px; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.08); color:{TEXT}; }}
        """)
        self.pill_playlist_btn.clicked.connect(self.toggle_playlist)
        row.addWidget(self.pill_playlist_btn)

        self.fs_btn = IconButton("⛶", "Fullscreen")
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        row.addWidget(self.fs_btn)

        self.pill_settings_btn = IconButton("⚙", "Settings")
        self.pill_settings_btn.setStyleSheet(self.pill_settings_btn.styleSheet() + f"""
            QPushButton {{ border:1.5px solid {VIOLET}; }}
        """)
        self.pill_settings_btn.clicked.connect(self.toggle_settings)
        row.addWidget(self.pill_settings_btn)

        pill_row.addWidget(pill)
        pill_row.addStretch(1)
        v.addLayout(pill_row)
        return box

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, "controls"):
            h = 112
            self.controls.setGeometry(0, self.stage.height() - h, self.stage.width(), h)
        if hasattr(self, "settings_overlay") and self.settings_overlay.isVisible():
            self.settings_overlay.setGeometry(self.rect())

    # ---------- player backend ----------
    def _build_player(self):
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.stage.video_widget)
        self.audio.setVolume(1.0)

        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.mediaStatusChanged.connect(self._on_media_status)

    # ---------- settings ----------
    def update_setting(self, key, value):
        self.settings[key] = value
        self.qsettings.setValue(key, value)

    def toggle_settings(self):
        if self.settings_overlay.isVisible():
            self.settings_overlay.hide_animated()
        else:
            self.settings_overlay.show_animated()

    # ---------- file handling ----------
    def open_files(self):
        filt = "Video files (*.mp4 *.webm *.ogg *.mov *.mkv *.avi *.m4v *.wmv *.flv);;All files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Open video files", "", filt)
        self.add_files(paths)

    def add_files(self, paths):
        valid = [p for p in paths if os.path.splitext(p)[1].lower() in VIDEO_EXT]
        if not valid:
            return
        start_new = self.cur_index == -1
        for p in valid:
            self.playlist.append(p)
            self.list_widget.addItem(QListWidgetItem(os.path.basename(p)))
        if start_new:
            self.load_index(len(self.playlist) - len(valid))

    def load_index(self, i):
        if not (0 <= i < len(self.playlist)):
            return
        self.cur_index = i
        self.list_widget.setCurrentRow(i)
        self.stage.show_empty(False)
        self.player.setSource(QUrl.fromLocalFile(self.playlist[i]))
        self.player.play()
        self._close_cv2_cap()
        self.peek.hide()

    def _on_playlist_pick(self, item):
        self.load_index(self.list_widget.row(item))

    def play_next(self):
        if self.playlist:
            self.load_index((self.cur_index + 1) % len(self.playlist))

    def play_prev(self):
        if self.playlist:
            self.load_index((self.cur_index - 1) % len(self.playlist))

    def toggle_playlist(self):
        self.dock.setVisible(not self.dock.isVisible())

    # ---------- playback controls ----------
    def toggle_play(self):
        if self.cur_index == -1:
            self.open_files()
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        self.mute_btn.setText("🔇" if self.audio.isMuted() else "🔊")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
            self.fs_btn.setText("⛶")
        else:
            self.showFullScreen()
            self.fs_btn.setText("⤢")

    def _on_volume_changed(self, val):
        self.audio.setVolume(val / 100)
        self.audio.setMuted(False)
        self.mute_btn.setText("🔊" if val > 0 else "🔇")
        if self.settings["remember_volume"]:
            self.qsettings.setValue("volume", val)

    def _on_speed_changed(self, text):
        self.player.setPlaybackRate(float(text.replace("x", "")))

    def _scrub_pressed(self):
        self._was_playing_before_scrub = self.player.playbackState() == QMediaPlayer.PlayingState
        self.player.pause()

    def _scrub_moved(self, val):
        if self.player.duration() > 0:
            ms = val / 1000 * self.player.duration()
            self.time_lbl.setText(f"{fmt_ms(ms)} / {fmt_ms(self.player.duration())}")
            x = int(val / 1000.0 * self.scrub.width())
            global_pt = self.scrub.mapToGlobal(QPoint(x, 0))
            self._update_peek(val / 1000.0, global_pt)

    def _scrub_released(self):
        if self.player.duration() > 0:
            self.player.setPosition(int(self.scrub.value() / 1000 * self.player.duration()))
        if self._was_playing_before_scrub:
            self.player.play()
        self.peek.hide()

    def _on_position_changed(self, pos):
        if not self.scrub.isSliderDown() and self.player.duration() > 0:
            self.scrub.setValue(int(pos / self.player.duration() * 1000))
        self.time_lbl.setText(f"{fmt_ms(pos)} / {fmt_ms(self.player.duration())}")

    def _on_duration_changed(self, dur):
        self.time_lbl.setText(f"{fmt_ms(self.player.position())} / {fmt_ms(dur)}")

    def _on_state_changed(self, state):
        self.play_btn.setText("⏸" if state == QMediaPlayer.PlayingState else "▶")
        self.notice_activity()

    def _on_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            at_last = self.cur_index == len(self.playlist) - 1
            if at_last:
                if self.settings["loop_playlist"]:
                    self.load_index(0)
                # else: stay stopped on the last frame
            elif self.settings["autoplay_next"]:
                self.play_next()

    # ---------- scrubber video peek ----------
    def eventFilter(self, obj, event):
        if obj is self.scrub and self.settings["peek_enabled"] and HAS_CV2 and self.cur_index != -1:
            if event.type() == QEvent.MouseMove and not self.scrub.isSliderDown():
                frac = max(0.0, min(1.0, event.position().x() / max(1, self.scrub.width())))
                dur = self.player.duration()
                if dur > 0:
                    self._update_peek(frac, self.scrub.mapToGlobal(event.position().toPoint()))
            elif event.type() == QEvent.Leave:
                self.peek.hide()
        elif obj is getattr(self, "_vol_wrap", None):
            if event.type() == QEvent.Enter:
                self._animate_vol(72)
            elif event.type() == QEvent.Leave:
                self._animate_vol(0)
        return super().eventFilter(obj, event)

    def _animate_vol(self, target):
        self._vol_anim.stop()
        self._vol_anim.setStartValue(self.vol_slider.maximumWidth())
        self._vol_anim.setEndValue(target)
        self._vol_anim.start()

    def _update_peek(self, frac, global_point):
        dur = self.player.duration()
        if dur <= 0 or not (0 <= self.cur_index < len(self.playlist)):
            return
        now = time.monotonic()
        if now - self._last_peek_grab < 0.08:
            return
        self._last_peek_grab = now
        frame = self._grab_frame(self.playlist[self.cur_index], frac * dur)
        if frame is not None:
            self.peek.setPixmap(frame.scaled(self.peek.width(), self.peek.height(),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation))
            local = self.stage.mapFromGlobal(global_point)
            x = max(4, min(self.stage.width() - self.peek.width() - 4, local.x() - self.peek.width() // 2))
            y = self.controls.y() - self.peek.height() - 10
            self.peek.move(x, y)
            self.peek.raise_()
            self.peek.show()

    def _grab_frame(self, path, ms):
        if not HAS_CV2:
            return None
        try:
            if self._cv2_cap is None or self._cv2_cap_path != path:
                self._close_cv2_cap()
                self._cv2_cap = cv2.VideoCapture(path)
                self._cv2_cap_path = path
            cap = self._cv2_cap
            if not cap or not cap.isOpened():
                return None
            cap.set(cv2.CAP_PROP_POS_MSEC, max(0, ms))
            ok, frame = cap.read()
            if not ok:
                return None
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
            return QPixmap.fromImage(img.copy())
        except Exception:
            return None

    def _close_cv2_cap(self):
        if self._cv2_cap is not None:
            try:
                self._cv2_cap.release()
            except Exception:
                pass
        self._cv2_cap = None
        self._cv2_cap_path = None

    def closeEvent(self, e):
        self._close_cv2_cap()
        super().closeEvent(e)

    # ---------- auto-hide controls ----------
    def notice_activity(self):
        if self.settings["anim_enabled"]:
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.opacity_fx.opacity())
            self.fade_anim.setEndValue(1.0)
            self.fade_anim.start()
        else:
            self.opacity_fx.setOpacity(1.0)
        self.controls.raise_()
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.hide_timer.start(2800)
        else:
            self.hide_timer.stop()

    def _fade_controls_out(self):
        if self.settings["anim_enabled"]:
            self.fade_anim.stop()
            self.fade_anim.setStartValue(self.opacity_fx.opacity())
            self.fade_anim.setEndValue(0.0)
            self.fade_anim.start()
        else:
            self.opacity_fx.setOpacity(0.0)

    # ---------- keyboard ----------
    def keyPressEvent(self, e):
        key = e.key()
        if key == Qt.Key_Space:
            self.toggle_play()
        elif key == Qt.Key_F:
            self.toggle_fullscreen()
        elif key == Qt.Key_M:
            self.toggle_mute()
        elif key == Qt.Key_Right:
            self.player.setPosition(min(self.player.duration(), self.player.position() + 5000))
        elif key == Qt.Key_Left:
            self.player.setPosition(max(0, self.player.position() - 5000))
        elif key == Qt.Key_Up:
            self.vol_slider.setValue(min(100, self.vol_slider.value() + 5))
        elif key == Qt.Key_Down:
            self.vol_slider.setValue(max(0, self.vol_slider.value() - 5))
        elif key == Qt.Key_Escape:
            if self.settings_overlay.isVisible():
                self.settings_overlay.hide_animated()
            elif self.isFullScreen():
                self.toggle_fullscreen()
        else:
            super().keyPressEvent(e)
        self.notice_activity()

    def mouseMoveEvent(self, e):
        self.notice_activity()
        super().mouseMoveEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.toLocalFile()]
        self.add_files(paths)


def main():
    # Silences Qt's FFmpeg-backend encoder-capability probe log (the
    # "could not find any MFT" lines) — it's informational noise about
    # hardware ENCODERS, unrelated to Prism, which only ever decodes/plays.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.multimedia.ffmpeg.*=false")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    win = PrismPlayer()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
