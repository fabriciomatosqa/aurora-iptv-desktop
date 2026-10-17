"""Single-player Picture-in-Picture window for Windows and Linux.

QMediaPlayer is owned by MainWindow. The PiP owns only a SECOND VIDEO OUTPUT
widget, never a second decoder/player/audio output. Qt Multimedia attaches
the existing player to exactly one output at a time.

Some Wayland compositors cannot guarantee WindowStaysOnTopHint. The toggle is
best-effort and the OS remains responsible for window stacking.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)
from .svg_icons import svg_icon_for


class PiPWindow(QWidget):
    returnRequested = Signal()

    def __init__(self, parent=None):
        # Do not use a QWidget child of the main window: PiP must remain
        # visible when AURORA is minimized or behind another application.
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("AURORA IPTV · Picture-in-Picture")
        self.setObjectName("auroraPipWindow")
        self.setMinimumSize(280, 180)
        self.resize(480, 302)
        self.setStyleSheet("""
            QWidget#auroraPipWindow {background:#091725;color:#e9fbff;}
            QLabel {color:#e9fbff;}
            QFrame#pipControls {background:#102e42;border-top:1px solid #396173;}
            QPushButton {color:#e9fbff;background:#184457;border-radius:6px;
                         min-height:29px;padding:4px 6px;}
            QPushButton:hover {background:#286576;}
            QCheckBox {color:#c8edee;}
        """)
        self._restoring = False
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(3000)
        self._idle.timeout.connect(self._hide_controls)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.video = QVideoWidget(self)
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video.setMouseTracking(True)
        self.video.installEventFilter(self)
        layout.addWidget(self.video,1)
        self.controls = QFrame(self)
        self.controls.setObjectName("pipControls")
        toolbar = QHBoxLayout(self.controls)
        toolbar.setContentsMargins(8,5,8,5)
        toolbar.setSpacing(7)
        self.play = QPushButton("Pausar")
        self.play.setIcon(svg_icon_for("pause",20))
        toolbar.addWidget(self.play)
        self.volume = QPushButton()
        self.volume.setIcon(svg_icon_for("volume",20))
        self.volume.setToolTip("Ativar/desativar som")
        toolbar.addWidget(self.volume)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0,100)
        self.volume_slider.setFixedWidth(72)
        toolbar.addWidget(self.volume_slider)
        self.pin = QCheckBox("No topo")
        self.pin.setChecked(True)
        self.pin.setToolTip("Permanecer acima de outras janelas, se o sistema permitir")
        self.pin.toggled.connect(self._set_always_on_top)
        toolbar.addWidget(self.pin)
        toolbar.addStretch(1)
        self.restore_button = QPushButton("Voltar")
        self.restore_button.setIcon(svg_icon_for("back",20))
        self.restore_button.clicked.connect(self.returnRequested.emit)
        toolbar.addWidget(self.restore_button)
        self.close_button = QPushButton()
        self.close_button.setIcon(svg_icon_for("exit-fullscreen",20))
        self.close_button.setToolTip("Fechar janela PiP e retornar ao player")
        self.close_button.clicked.connect(self.returnRequested.emit)
        toolbar.addWidget(self.close_button)
        layout.addWidget(self.controls)
        self._show_controls()

    def showEvent(self, event):
        super().showEvent(event)
        # Windows, X11 and multi-monitor setups can otherwise restore a
        # remembered window location entirely outside the visible work area.
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            new_width = min(self.width(),max(280,available.width()))
            new_height = min(self.height(),max(180,available.height()))
            self.resize(new_width,new_height)
            x = max(available.left(),min(self.x(),available.right()-new_width+1))
            y = max(available.top(),min(self.y(),available.bottom()-new_height+1))
            self.move(x,y)
        self._show_controls()

    def eventFilter(self,obj,event):
        if obj is self.video and event.type() in (
            QEvent.Type.MouseMove,QEvent.Type.MouseButtonPress,QEvent.Type.Enter):
            self._show_controls()
        return super().eventFilter(obj,event)

    def mouseMoveEvent(self, event):
        self._show_controls()
        super().mouseMoveEvent(event)

    def _show_controls(self):
        self.controls.show()
        self._idle.start()

    def _hide_controls(self):
        # A user holding a slider or using a toggle must never lose controls.
        if (self.controls.underMouse() or self.volume_slider.isSliderDown()
                or self.pin.hasFocus()):
            self._idle.start()
        else:
            self.controls.hide()

    def _set_always_on_top(self, enabled: bool):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if self.isVisible():
            self.show()

    def closeEvent(self, event):
        if not self._restoring:
            event.ignore()
            self.returnRequested.emit()
            return
        self._idle.stop()
        super().closeEvent(event)
