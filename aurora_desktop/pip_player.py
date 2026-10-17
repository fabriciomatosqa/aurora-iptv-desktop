"""AURORA Picture-in-Picture: one QMediaPlayer, one active video output.

The PiP is an independent, resizable OS window. We switch QMediaPlayer's
video output, never open the stream a second time. Some Qt backends can take
a short moment to rebind their rendering surface.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QSize, QEvent, QTimer, Signal
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QCheckBox, QSlider, QApplication)
from PySide6.QtGui import QShortcut, QKeySequence

from .svg_icons import svg_icon_for


class PiPWindow(QWidget):
    restore_requested = Signal()

    def __init__(self, player, audio, toggle_play, toggle_mute, parent=None):
        # Parentless tool window can move to a second monitor independently.
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("auroraPiP")
        self.setWindowTitle("AURORA IPTV · Picture-in-Picture")
        self.setMinimumSize(256, 170)
        self.resize(480, 300)
        self._player = player
        self._audio = audio
        self._controls_open = True
        self._closing_for_app = False
        self.setStyleSheet("""
            QWidget#auroraPiP {background:#091b2a;color:#e5faff;}
            QLabel {color:#e5faff;}
            QPushButton {color:#e5faff;background:#174057;border:1px solid #2c7687;
                         padding:6px 9px;border-radius:7px;}
            QCheckBox {color:#e5faff;}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)
        header = QHBoxLayout()
        self.title = QLabel("AURORA IPTV")
        self.title.setWordWrap(False)
        header.addWidget(self.title, 1)
        self.top_switch = QCheckBox("Sempre no topo")
        self.top_switch.setChecked(True)
        self.top_switch.toggled.connect(self._set_always_on_top)
        header.addWidget(self.top_switch)
        root.addLayout(header)
        self.video = QVideoWidget(self)
        self.video.setObjectName("pipVideo")
        self.video.setMinimumHeight(100)
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setMouseTracking(True)
        self.video.installEventFilter(self)
        root.addWidget(self.video, 1)
        self.controls = QWidget(self)
        controls = QHBoxLayout(self.controls)
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(5)
        self.play = QPushButton("Pausar")
        self.play.setIcon(svg_icon_for("pause", 20))
        self.play.clicked.connect(toggle_play)
        controls.addWidget(self.play)
        self.mute = QPushButton()
        self.mute.setIcon(svg_icon_for("volume", 20))
        self.mute.setToolTip("Ativar/desativar som")
        self.mute.clicked.connect(toggle_mute)
        controls.addWidget(self.mute)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setObjectName("pipVolume")
        self.volume.setRange(0, 100)
        self.volume.setValue(round(audio.volume() * 100))
        self.volume.valueChanged.connect(lambda v: audio.setVolume(v / 100))
        controls.addWidget(self.volume, 1)
        self.restore = QPushButton("Voltar ao Aurora")
        self.restore.setIcon(svg_icon_for("back", 20))
        self.restore.clicked.connect(self.restore_requested.emit)
        controls.addWidget(self.restore)
        root.addWidget(self.controls)
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(3300)
        self._idle.timeout.connect(self._hide_controls)
        self.setMouseTracking(True)
        self._player.playbackStateChanged.connect(self.sync_icons)
        self._audio.mutedChanged.connect(self.sync_icons)
        self._audio.volumeChanged.connect(self._sync_volume)
        QShortcut(QKeySequence("Escape"), self, self.restore_requested.emit)
        self.sync_icons()

    def set_title(self, value):
        self.title.setText(value or "AURORA IPTV")

    def eventFilter(self, watched, event):
        if watched is self.video and event.type() in (
                QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress):
            self.show_controls()
        return super().eventFilter(watched, event)

    def mouseMoveEvent(self, event):
        self.show_controls()
        super().mouseMoveEvent(event)

    def show_controls(self):
        self.controls.show()
        self._idle.start()

    def _hide_controls(self):
        if self.volume.isSliderDown() or self.top_switch.hasFocus():
            self._idle.start()
        else:
            self.controls.hide()

    def _sync_volume(self, value):
        self.volume.blockSignals(True)
        self.volume.setValue(round(value * 100))
        self.volume.blockSignals(False)

    def sync_icons(self, *_):
        playing = self._player.playbackState() == self._player.PlaybackState.PlayingState
        name = "pause" if playing else "play"
        self.play.setIcon(svg_icon_for(name, 20))
        self.play.setText("Pausar" if playing else "Reproduzir")
        self.mute.setIcon(svg_icon_for("mute" if self._audio.isMuted() else "volume", 20))

    def _set_always_on_top(self, enabled):
        # Changing flags can hide a Qt top-level window; restore it immediately.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        self.show()

    def closeEvent(self, event):
        if not self._closing_for_app:
            self.restore_requested.emit()
        event.accept()

    def prepare_for_app_exit(self):
        self._closing_for_app = True
        self._idle.stop()
        self.hide()
