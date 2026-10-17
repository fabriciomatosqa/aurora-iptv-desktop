"""AURORA IPTV Desktop: responsive aurora-themed player and library."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import os
import time
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QSize, QRectF, QPoint, QEvent, QTimer, QUrl, Signal, QObject, QThread, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QBrush, QColor, QFont, QGradient, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QDialog, QTextBrowser,
    QPushButton, QProgressBar, QSlider, QSplitter, QStackedWidget, QVBoxLayout, QWidget, QMenu, QGraphicsOpacityEffect, QStyleOptionSlider, QStyle, QStyledItemDelegate,
)

from . import app as legacy
from .catalog import LibraryV2, guess_xtream_epg
from .svg_icons import svg_icon_for
from .sports_data import fetch_score_updates, fixture_key, national_artwork
from .football_widgets import BadgeLoader, FootballCardWidget

# The original Qt player keeps the same settings, DB path, resuming and playlist management.
legacy.Library = LibraryV2


def asset(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "assets" / name


class AuroraGradientTitle(QLabel):
    """Crisp custom gradient lettering inspired by AURORA Utils."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setObjectName("heroTitle")
        self.setMinimumHeight(55)
        self.setMinimumWidth(310)

    def paintEvent(self, event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font=QFont("Segoe UI", 30, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.2)
        painter.setFont(font)
        rect=QRectF(2,0,self.width()-3,self.height())
        painter.setPen(QColor(5,15,29,155))
        painter.drawText(rect.translated(1.8,2), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())
        gradient=QLinearGradient(0,0,max(350,self.width()*.8),0)
        gradient.setColorAt(0,QColor("#ffffff"))
        gradient.setColorAt(.28,QColor("#e7fbff"))
        gradient.setColorAt(.58,QColor("#60ebdf"))
        gradient.setColorAt(.82,QColor("#8e9fff"))
        gradient.setColorAt(1,QColor("#d38bf1"))
        painter.setPen(QPen(QBrush(gradient),1))
        painter.drawText(rect,Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,self.text())
        painter.end()


class AuroraSeekSlider(QSlider):
    """Use the small four-point aurora star as playback-position thumb."""
    def __init__(self,orientation,parent=None):
        super().__init__(orientation,parent)
        self.setObjectName("auroraSeek")
        self.setMinimumHeight(26)

    def paintEvent(self,event):
        super().paintEvent(event)
        style=QStyleOptionSlider()
        self.initStyleOption(style)
        region=self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider,style,
            QStyle.SubControl.SC_SliderHandle,self)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        spark=svg_icon_for("sparkle",21).pixmap(QSize(21,21))
        painter.drawPixmap(region.center()-QPoint(10,10),spark)
        painter.end()


class AuroraBanner(QFrame):
    """A full-width, image-backed hero instead of an isolated picture tile.

    The source image is always center-cropped (never stretched), clipped to a
    rounded outline, then blended into the dark AURORA shell. Text stays part
    of the layout so it remains accessible and responsive.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("auroraHero")
        self.setMinimumHeight(198)
        self.setMaximumHeight(240)
        self._image = QPixmap(str(asset("aurora_banner.jpg")))
        layout=QVBoxLayout(self)
        layout.setContentsMargins(45,17,42,20)
        layout.setSpacing(7)
        layout.addStretch(1)

        brand=QHBoxLayout()
        brand.setSpacing(22)
        brand_logo=QLabel()
        brand_logo.setObjectName("heroLogo")
        logo=QPixmap(str(asset("aurora_icon.png")))
        if not logo.isNull():
            brand_logo.setPixmap(logo.scaled(
                106,106,Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        brand_logo.setFixedSize(110,110)
        brand.addWidget(brand_logo)
        text_column=QVBoxLayout()
        text_column.setSpacing(0)
        self.gradient_title=AuroraGradientTitle("AURORA IPTV")
        text_column.addWidget(self.gradient_title)
        subtitle=QLabel("SEU UNIVERSO DE ENTRETENIMENTO")
        subtitle.setObjectName("heroSubtitle")
        text_column.addWidget(subtitle)
        footnote=QLabel("CANAIS AO VIVO   ·   FILMES   ·   SÉRIES   ·   FUTEBOL")
        footnote.setObjectName("heroFootnote")
        text_column.addWidget(footnote)
        brand.addLayout(text_column,1)
        layout.addLayout(brand)
        layout.addStretch(1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        if w <= 1 or h <= 1:
            p.end()
            return
        frame = QRectF(0.5, 0.5, w-1, h-1)
        clip = QPainterPath()
        clip.addRoundedRect(frame, 16, 16)
        p.setClipPath(clip)
        p.fillRect(self.rect(), QColor("#09253a"))
        if not self._image.isNull():
            # Fit the *whole* source vertically. Widening a window must never
            # crop the sky/mountains or zoom the source simply to fill its width.
            img_w, img_h = self._image.width(), self._image.height()
            fitted_w = img_w * h / img_h
            left = (w - fitted_w) / 2
            source = QRectF(0, 0, img_w, img_h)
            if fitted_w >= w:
                # Narrower windows can still display the whole image with
                # slight empty margins filled by the existing aurora backdrop.
                target_w = w
                target_h = img_h * w / img_w
                top = (h - target_h) / 2
                p.drawPixmap(QRectF(0, top, target_w, target_h), self._image, source)
            else:
                # Mirror each end of the *same* image at the same scale.
                # Reflection avoids seams and panoramic zoom on 21:9/32:9.
                p.drawPixmap(QRectF(left, 0, fitted_w, h), self._image, source)
                edge_left = left
                edge_right = left + fitted_w
                for index in range(1, 9):
                    if edge_left <= 0 and edge_right >= w:
                        break
                    left_tile = QRectF(edge_left - fitted_w, 0, fitted_w, h)
                    right_tile = QRectF(edge_right, 0, fitted_w, h)
                    if index % 2:
                        p.save()
                        p.translate(edge_left, 0)
                        p.scale(-1, 1)
                        p.drawPixmap(QRectF(0, 0, fitted_w, h), self._image, source)
                        p.restore()
                        p.save()
                        p.translate(edge_right, 0)
                        p.scale(-1, 1)
                        p.drawPixmap(QRectF(-fitted_w, 0, fitted_w, h), self._image, source)
                        p.restore()
                    else:
                        p.drawPixmap(left_tile, self._image, source)
                        p.drawPixmap(right_tile, self._image, source)
                    edge_left -= fitted_w
                    edge_right += fitted_w
        else:
            backdrop = QLinearGradient(0, 0, w, h)
            backdrop.setColorAt(0, QColor("#0b293e"))
            backdrop.setColorAt(.42, QColor("#13677b"))
            backdrop.setColorAt(.74, QColor("#364f8b"))
            backdrop.setColorAt(1, QColor("#251a50"))
            p.fillRect(self.rect(), backdrop)
        # Blend the photograph into the dark shell around the text. The
        # transparent right side preserves the full northern-lights artwork.
        overlay = QLinearGradient(0, 0, w, 0)
        overlay.setColorAt(0, QColor(4, 16, 32, 197))
        overlay.setColorAt(.27, QColor(5, 22, 40, 125))
        overlay.setColorAt(.55, QColor(6, 24, 42, 18))
        overlay.setColorAt(1, QColor(6, 22, 39, 32))
        p.fillRect(self.rect(), overlay)
        lower = QLinearGradient(0, 0, 0, h)
        lower.setColorAt(0, QColor(5, 19, 34, 55))
        lower.setColorAt(.67, QColor(5, 19, 34, 0))
        lower.setColorAt(1, QColor(7, 22, 36, 100))
        p.fillRect(self.rect(), lower)
        # A restrained aurora accent along the bottom ties into the panels.
        streak = QLinearGradient(0, 0, w, 0)
        streak.setColorAt(0, QColor("#5fefcb"))
        streak.setColorAt(.45, QColor("#55c9d6"))
        streak.setColorAt(.76, QColor("#746ccf"))
        streak.setColorAt(1, QColor(99, 83, 155, 50))
        p.fillRect(QRectF(0, h-3, w, 3), streak)
        p.setClipping(False)
        p.setPen(QPen(QColor(102, 203, 213, 90), 1.1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(frame, 16, 16)
        p.end()


class PlayerSplash(QFrame):
    """Keep the screen useful and branded before a playable item is selected."""
    def __init__(self):
        super().__init__()
        self.setObjectName("playerSplash")
        # Colors are supplied by the global theme, including light mode.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26,24,26,24)
        layout.setSpacing(13)
        layout.addStretch(2)
        emblem = QLabel("✦")
        emblem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        emblem.setObjectName("splashEmblem")
        layout.addWidget(emblem)
        heading = QLabel("AURORA IPTV")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setObjectName("splashHeading")
        layout.addWidget(heading)
        description = QLabel("Escolha um canal, filme ou episódio para começar")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        description.setObjectName("splashDescription")
        layout.addWidget(description)
        layout.addStretch(2)


class ScoreWorker(QObject):
    completed = Signal(int, object)

    def __init__(self, playlist_id: int, records: list[dict]):
        super().__init__()
        self.playlist_id = playlist_id
        self.records = [dict(item) for item in records]

    def run(self):
        # Network lookup is isolated from Qt GUI and never sees credentials.
        try:
            updates = fetch_score_updates(self.records)
        except Exception:
            updates = {}
        self.completed.emit(self.playlist_id, updates)


class FootballLiveDelegate(QStyledItemDelegate):
    """Pulse only on an XMLTV-confirmed scheduled live broadcast.

    This badge is a display hint from the EPG, not proof of the video
    stream or a substitute for an independently verified live score.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pulse_on = True

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        record = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(record, dict) or record.get("kind") != "football":
            return
        if record.get("broadcast") != "live" or not self.pulse_on:
            return
        try:
            now = datetime.now().astimezone()
            start = datetime.fromisoformat(record["start"]).astimezone()
            end = datetime.fromisoformat(record["end"]).astimezone()
            if not (start <= now < end):
                return
        except (KeyError, TypeError, ValueError):
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#45d9a0"))
        box = option.rect
        painter.drawEllipse(QRectF(box.right() - 22, box.top() + 16, 10, 10))
        painter.restore()


class Covers(QObject):
    """Small bounded asynchronous cover cache; Qt requests never block the GUI."""
    def __init__(self, list_widget: QListWidget):
        super().__init__(list_widget)
        self.widget = list_widget
        self.network = QNetworkAccessManager(self)
        self.queue = deque()
        self.active = 0
        self.cache = {}
        self.failed = set()
        self.generation = 0
        self.max_items = 250
        self.blanks = {kind:self.placeholder(kind) for kind in
                       ("movie","series","live","football")}

    def placeholder(self, kind: str = "movie"):
        """A designed artwork tile rather than a generic diamond glyph."""
        kind = {
            "live": "live", "football_channel": "live", "football": "football",
            "series": "series", "movie": "movie",
        }.get(kind, "movie")
        pixmap = QPixmap(84, 104)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 84, 104)
        gradient.setColorAt(0, QColor("#1a4a66"))
        gradient.setColorAt(.52, QColor("#234167"))
        gradient.setColorAt(1, QColor("#302354"))
        painter.setPen(QColor("#386c7c"))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(1, 1, 82, 102, 11, 11)
        symbol = svg_icon_for(kind, 45).pixmap(QSize(45, 45))
        painter.drawPixmap((84-symbol.width())//2, (104-symbol.height())//2, symbol)
        painter.end()
        return QIcon(pixmap)

    def reset(self):
        self.generation += 1
        self.queue.clear()

    def enqueue(self, item, url, kind: str = "movie"):
        category = "live" if kind == "football_channel" else kind
        item.setIcon(self.blanks.get(category, self.blanks["movie"]))
        if not url or not url.startswith(("https://","http://")):
            return
        if url in self.cache:
            item.setIcon(self.cache[url])
        elif url not in self.failed and len(self.queue) < 500:
            self.queue.append((item,url,self.generation))
            self._dispatch()

    def _dispatch(self):
        while self.active < 5 and self.queue:
            item,url,generation = self.queue.popleft()
            if generation != self.generation:
                continue
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(9_000)
            self.active += 1
            reply = self.network.get(req)
            reply.finished.connect(lambda r=reply,it=item,u=url,g=generation:self._done(r,it,u,g))

    def _done(self, reply, item, url, generation):
        self.active -= 1
        try:
            data = bytes(reply.readAll())
            if reply.error() or len(data) > 2_000_000:
                self.failed.add(url)
            else:
                pixmap = QPixmap()
                if pixmap.loadFromData(data) and not pixmap.isNull():
                    scaled = pixmap.scaled(QSize(72,86),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
                    icon = QIcon(scaled)
                    self.cache[url] = icon
                    if len(self.cache) > self.max_items:
                        self.cache.pop(next(iter(self.cache)))
                    if generation == self.generation:
                        try:
                            if item.listWidget() is self.widget:
                                item.setIcon(icon)
                        except RuntimeError:
                            pass
                else:
                    self.failed.add(url)
        finally:
            reply.deleteLater()
            self._dispatch()


class GuideWorker(QObject):
    completed = Signal(int)
    failed = Signal(str)

    def __init__(self, database, playlist_id):
        super().__init__()
        self.database = database
        self.playlist_id = playlist_id

    def run(self):
        try:
            count = LibraryV2(self.database).import_football(self.playlist_id)
            self.completed.emit(count)
        except Exception as exc:
            message = str(exc)
            # A server exception may echo credentials embedded in the guide URL.
            if "http:" in message or "https:" in message:
                message = "Falha na atualização do EPG. Confira a URL e o servidor."
            self.failed.emit(message)


class IndexWorker(QObject):
    finished = Signal(int)
    failed = Signal(int)

    def __init__(self, database, playlist_id):
        super().__init__()
        self.database = database
        self.playlist_id = playlist_id

    def run(self):
        try:
            LibraryV2(self.database).ensure_categories(self.playlist_id)
            self.finished.emit(self.playlist_id)
        except Exception:
            self.failed.emit(self.playlist_id)


class MainWindow(legacy.MainWindow):
    """Reuses the tested player and incremental importer from 0.1.0."""

    def _build(self):
        root = QWidget(self)
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        # Preferences are fully accessible via Configurações; no redundant top menus.
        self.menuBar().hide()
        self.page_layout = QVBoxLayout(root)
        self.page_layout.setSpacing(0)
        self.page_layout.setContentsMargins(0,0,0,0)
        self.header_widget = QWidget(root)
        self.header_widget.setObjectName("mainHeader")
        upper = QHBoxLayout(self.header_widget)
        upper.setContentsMargins(0,0,0,0)
        upper.setSpacing(0)
        self.banner = AuroraBanner(self.header_widget)
        upper.addWidget(self.banner,1)
        self.page_layout.addWidget(self.header_widget)
        content_row = QWidget(root)
        base = QHBoxLayout(content_row)
        base.setSpacing(0)
        base.setContentsMargins(0,0,0,0)
        self.page_layout.addWidget(content_row,1)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(226)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18,19,18,12)
        side.setSpacing(11)
        side.addSpacing(4)
        self.nav = {}
        for mode,title in [
            ("home","Início"),("live","Ao vivo"),("movie","Filmes"),
            ("series","Séries"),("football","Futebol"),
            ("favorites","Favoritos"),("settings","Configurações")
        ]:
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setIcon(svg_icon_for(mode,30))
            button.setIconSize(QSize(30,30))
            button.setMinimumHeight(57)
            button.setCheckable(True)
            button.setToolTip(title)
            button.clicked.connect(lambda checked=False,m=mode:self.navigate(m))
            self.nav[mode] = button
            side.addWidget(button)
        side.addStretch()
        from . import __version__
        footer = QLabel(f"DESKTOP  /  v{__version__}")
        footer.setObjectName("versionFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        side.addWidget(footer)
        base.addWidget(sidebar)
        self.sidebar = sidebar

        shell = QWidget()
        shell.setObjectName("contentShell")
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(16,15,16,15)
        outer.setSpacing(14)
        self.outer_layout = outer
        panels = QSplitter(Qt.Orientation.Horizontal)
        self.panels = panels
        panels.setChildrenCollapsible(False)
        outer.addWidget(panels,1)

        categories_panel = QFrame()
        categories_panel.setObjectName("panel")
        categories_panel.setMinimumWidth(230)
        self.categories_panel = categories_panel
        group_layout = QVBoxLayout(categories_panel)
        group_layout.setContentsMargins(16,17,16,14)
        group_layout.setSpacing(9)
        self.groups_title = QLabel("CLASSIFICAÇÃO")
        self.groups_title.setObjectName("heading")
        group_layout.addWidget(self.groups_title)
        self.groups_hint = QLabel("Categorias da lista")
        self.groups_hint.setObjectName("muted")
        self.groups_hint.setWordWrap(True)
        group_layout.addWidget(self.groups_hint)
        self.groups = QListWidget()
        self.groups.setSpacing(4)
        self.groups.setWordWrap(False)
        self.groups.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.groups.setObjectName("groups")
        self.groups.currentItemChanged.connect(self._change_category)
        group_layout.addWidget(self.groups,1)
        panels.addWidget(categories_panel)

        contents_panel = QFrame()
        contents_panel.setObjectName("panel")
        contents_panel.setMinimumWidth(340)
        self.contents_panel = contents_panel
        content_layout = QVBoxLayout(contents_panel)
        content_layout.setContentsMargins(16,17,16,14)
        content_layout.setSpacing(10)
        heading_row = QHBoxLayout()
        heading_row.setSpacing(8)
        self.heading = QLabel("Explorar")
        self.heading.setObjectName("heading")
        heading_row.addWidget(self.heading, 1)
        # Native indeterminate progress bar, not a fake percent or timer.
        self.guide_busy = QProgressBar(contents_panel)
        self.guide_busy.setObjectName("guideBusy")
        self.guide_busy.setRange(0, 0)
        self.guide_busy.setTextVisible(False)
        self.guide_busy.setFixedSize(64, 12)
        self.guide_busy.setAccessibleName("Atualizando agenda de futebol")
        self.guide_busy.hide()
        heading_row.addWidget(self.guide_busy, 0)
        self.football_refresh = QPushButton("Atualizar")
        self.football_refresh.setObjectName("footballRefresh")
        self.football_refresh.setIcon(svg_icon_for("refresh", 22))
        self.football_refresh.setIconSize(QSize(20, 20))
        self.football_refresh.setToolTip("Atualizar agenda de partidas via XMLTV")
        self.football_refresh.clicked.connect(self._update_guide)
        self.football_refresh.setFixedHeight(36)
        heading_row.addWidget(self.football_refresh, 0)
        content_layout.addLayout(heading_row)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        content_layout.addWidget(self.subtitle)

        # The one and only playlist selector lives under Configurações.
        # Keeping self.playlists connected to legacy._reload_playlists() and
        # legacy._on_playlist() preserves import/switch/favorites behavior.
        self.playlist_settings = QFrame(contents_panel)
        self.playlist_settings.setObjectName("playlistSettings")
        playlist_layout = QVBoxLayout(self.playlist_settings)
        playlist_layout.setContentsMargins(16, 15, 16, 16)
        playlist_layout.setSpacing(8)
        section_title = QLabel("PLAYLIST ATIVA")
        section_title.setObjectName("settingsTitle")
        playlist_layout.addWidget(section_title)
        description = QLabel("Escolha qual biblioteca será usada para assistir.")
        description.setWordWrap(True)
        description.setObjectName("muted")
        playlist_layout.addWidget(description)
        self.playlists = QComboBox()
        self.playlists.setObjectName("activePlaylistSelector")
        self.playlists.setAccessibleName("Playlist ativa")
        self.playlists.setToolTip("Alternar a playlist ativa do AURORA")
        self.playlists.currentIndexChanged.connect(self._on_playlist)
        playlist_layout.addWidget(self.playlists)
        self.playlist_settings.hide()
        manage_buttons = QVBoxLayout()
        add_button = QPushButton("Adicionar playlist por URL")
        add_button.setObjectName("settingsAction")
        add_button.setIcon(svg_icon_for("add"))
        add_button.clicked.connect(self._add_url)
        manage_buttons.addWidget(add_button)
        file_button = QPushButton("Importar arquivo M3U")
        file_button.setObjectName("settingsAction")
        file_button.setIcon(svg_icon_for("upload"))
        file_button.clicked.connect(self._import_playlist_file)
        manage_buttons.addWidget(file_button)
        refresh_button = QPushButton("Atualizar playlist ativa")
        refresh_button.setObjectName("settingsAction")
        refresh_button.setIcon(svg_icon_for("refresh"))
        refresh_button.clicked.connect(self._import_active)
        manage_buttons.addWidget(refresh_button)
        playlist_layout.addLayout(manage_buttons)
        content_layout.addWidget(self.playlist_settings)

        self.appearance_settings = QFrame(contents_panel)
        self.appearance_settings.setObjectName("configCard")
        appearance_layout = QVBoxLayout(self.appearance_settings)
        appearance_layout.setContentsMargins(16,15,16,16)
        appearance_layout.setSpacing(10)
        appearance_title=QLabel("APARÊNCIA")
        appearance_title.setObjectName("settingsTitle")
        appearance_layout.addWidget(appearance_title)
        description=QLabel("Escolha o visual do AURORA IPTV para todas as telas.")
        description.setObjectName("muted")
        description.setWordWrap(True)
        appearance_layout.addWidget(description)
        self.theme_select = QComboBox()
        self.theme_select.setObjectName("themeSelector")
        for label,value in [
            ("Conforme o sistema","system"),
            ("Modo escuro","dark"),
            ("Modo claro","light")
        ]:
            self.theme_select.addItem(label,value)
        self.theme_select.currentIndexChanged.connect(self._theme_changed)
        appearance_layout.addWidget(self.theme_select)
        self.appearance_settings.hide()
        content_layout.addWidget(self.appearance_settings)

        self.updates_settings = QFrame(contents_panel)
        self.updates_settings.setObjectName("configCard")
        updates_layout = QVBoxLayout(self.updates_settings)
        updates_layout.setContentsMargins(16,15,16,16)
        updates_layout.setSpacing(10)
        updates_title=QLabel("ATUALIZAÇÕES")
        updates_title.setObjectName("settingsTitle")
        updates_layout.addWidget(updates_title)
        from . import __version__
        self.updates_version = QLabel(f"Versão instalada: {__version__}")
        self.updates_version.setObjectName("muted")
        updates_layout.addWidget(self.updates_version)
        updates_layout.addWidget(QLabel("Canal de atualizações"))
        self.update_channel = QComboBox()
        self.update_channel.setObjectName("updateChannel")
        self.update_channel.addItem("Estável", "stable")
        self.update_channel.addItem("Beta e estável", "beta")
        channel=self.settings.value("updates/channel","beta")
        self.update_channel.setCurrentIndex(max(0,self.update_channel.findData(channel)))
        self.update_channel.currentIndexChanged.connect(self._set_update_channel)
        updates_layout.addWidget(self.update_channel)
        self.check_updates_button=QPushButton("Verificar atualizações agora")
        self.check_updates_button.setObjectName("primary")
        self.check_updates_button.setIcon(svg_icon_for("update"))
        self.check_updates_button.clicked.connect(self._check_updates_now)
        updates_layout.addWidget(self.check_updates_button)
        note=QLabel("Novas versões continuam sendo verificadas automaticamente. "
                    "No Windows, a instalação é silenciosa; no Debian pode exigir autorização.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        updates_layout.addWidget(note)
        self.updates_settings.hide()
        content_layout.addWidget(self.updates_settings)

        self.epg_settings = QFrame(contents_panel)
        self.epg_settings.setObjectName("configCard")
        epg_layout = QVBoxLayout(self.epg_settings)
        epg_layout.setContentsMargins(16,15,16,16)
        epg_layout.setSpacing(10)
        epg_title=QLabel("GUIA DE FUTEBOL / EPG")
        epg_title.setObjectName("settingsTitle")
        epg_layout.addWidget(epg_title)
        epg_text=QLabel("Configure o guia XMLTV ou atualize os próximos jogos.")
        epg_text.setObjectName("muted")
        epg_text.setWordWrap(True)
        epg_layout.addWidget(epg_text)
        self.config_epg_button=QPushButton("Configurar fonte EPG")
        self.config_epg_button.setIcon(svg_icon_for("settings"))
        self.config_epg_button.clicked.connect(self._configure_guide)
        epg_layout.addWidget(self.config_epg_button)
        self.update_epg_button=QPushButton("Atualizar agenda de futebol")
        self.update_epg_button.setIcon(svg_icon_for("refresh"))
        self.update_epg_button.clicked.connect(self._update_guide)
        epg_layout.addWidget(self.update_epg_button)
        self.sports_online_checkbox = QCheckBox("Consultar resultados e escudos online (ESPN e fontes associadas)")
        self.sports_online_checkbox.setToolTip(
            "Os provedores e os titulares dos escudos estabelecem suas próprias condições de uso. "
            "Desative para não realizar consultas esportivas externas.")
        self.sports_online_checkbox.setChecked(self.settings.value(
            "football/online_data", True, type=bool))
        self.sports_online_checkbox.toggled.connect(self._sports_online_changed)
        epg_layout.addWidget(self.sports_online_checkbox)
        self.sports_attribution = QLabel(
            "Fontes: ESPN (resultados e escudos) e TheSportsDB (algumas federações). "
            "Imagens e dados sujeitos aos direitos e condições de seus titulares.")
        self.sports_attribution.setObjectName("muted")
        self.sports_attribution.setWordWrap(True)
        epg_layout.addWidget(self.sports_attribution)
        self.epg_settings.hide()
        content_layout.addWidget(self.epg_settings)
        self.settings_sections = {
            "playlists": self.playlist_settings,
            "appearance": self.appearance_settings,
            "updates": self.updates_settings,
            "guide": self.epg_settings,
        }

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar canais, filmes, séries...")
        self.search.textChanged.connect(self._search)
        content_layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setObjectName("results")
        self.results.setIconSize(QSize(70,88))
        self.badge_loader = BadgeLoader(self.results)
        self._football_card_widgets = {}
        self._football_updates = {}
        self._football_live_delegate = FootballLiveDelegate(self.results)
        self.results.setItemDelegate(self._football_live_delegate)
        self.results.setUniformItemSizes(True)
        self.results.setSpacing(7)
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.results.currentItemChanged.connect(self._selected)
        self.results.itemDoubleClicked.connect(self._open)
        self.results.verticalScrollBar().valueChanged.connect(self._near_end)
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._context)
        content_layout.addWidget(self.results,1)
        self.covers = Covers(self.results)
        self.page = QLabel("")
        self.page.setObjectName("muted")
        content_layout.addWidget(self.page)
        self.previous = QPushButton("Voltar à categoria anterior")
        self.previous.setIcon(svg_icon_for("back"))
        self.previous.setIconSize(QSize(22,22))
        self.previous.clicked.connect(self._go_back)
        content_layout.addWidget(self.previous)
        self.next = QPushButton()
        self.next.hide()
        self.action = QPushButton("Atualizar lista")
        self.action.setIcon(svg_icon_for("refresh"))
        self.action.setIconSize(QSize(23,23))
        self.action.setObjectName("primary")
        self.action.clicked.connect(self._main_action)
        content_layout.addWidget(self.action)
        self.second_action = QPushButton("Configurações")
        self.second_action.setIcon(svg_icon_for("settings"))
        self.second_action.setIconSize(QSize(23,23))
        self.second_action.clicked.connect(self._second_action)
        content_layout.addWidget(self.second_action)
        panels.addWidget(contents_panel)

        player_panel = QFrame()
        player_panel.setObjectName("panel")
        player_panel.setMinimumWidth(440)
        self.player_panel = player_panel
        play_layout = QVBoxLayout(player_panel)
        play_layout.setContentsMargins(17,17,17,14)
        play_layout.setSpacing(10)
        self.now = QLabel("AURORA  ·  PRONTO PARA ASSISTIR")
        self.now.setObjectName("playerEyebrow")
        play_layout.addWidget(self.now)
        self.video_title = QLabel("Escolha um conteúdo")
        self.video_title.setWordWrap(True)
        self.video_title.setObjectName("heading")
        play_layout.addWidget(self.video_title)
        self.player_more = QHBoxLayout()
        self.player_back = QPushButton("Voltar")
        self.player_back.setIcon(svg_icon_for("back",20))
        self.player_back.setToolTip("Retornar à categoria de origem")
        self.player_back.clicked.connect(self._go_back)
        self.player_more.addWidget(self.player_back)
        self.synopsis_button = QPushButton("Sinopse")
        self.synopsis_button.setIcon(svg_icon_for("series",20))
        self.synopsis_button.setToolTip("Ler sinopse ou descrição dos metadados, se disponível")
        self.synopsis_button.clicked.connect(self._show_synopsis)
        self.player_more.addWidget(self.synopsis_button)
        self.player_more.addStretch()
        play_layout.addLayout(self.player_more)
        self.synopsis_button.setVisible(False)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(200)
        self.video.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.video.setStyleSheet("background:#091b2a;")
        self.player_splash = PlayerSplash()
        self.video_stage = QStackedWidget()
        self.video_stage.setObjectName("videoStage")
        self.video_stage.addWidget(self.player_splash)
        self.video_stage.addWidget(self.video)
        self.video_stage.setCurrentWidget(self.player_splash)
        play_layout.addWidget(self.video_stage,1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.75)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(self._player_error)
        self.player.durationChanged.connect(self._duration)
        self.player.positionChanged.connect(self._position)
        self.player.mediaStatusChanged.connect(self._media_status)
        # Compact inline controls remain available in normal (non-fullscreen)
        # mode; fullscreen uses a separate floating overlay on the video.
        self.player_controls=QWidget(player_panel)
        controls=QHBoxLayout(self.player_controls)
        controls.setContentsMargins(0,0,0,0)
        controls.setSpacing(10)
        self.play=QPushButton("Reproduzir")
        self.play.setObjectName("playButton")
        self.play.setIcon(svg_icon_for("play",22))
        self.play.setIconSize(QSize(22,22))
        self.play.clicked.connect(self._toggle_play)
        controls.addWidget(self.play)
        self.seek=AuroraSeekSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.seek.setRange(0,0)
        controls.addWidget(self.seek,1)
        self.time=QLabel("00:00 / 00:00")
        self.time.setObjectName("playerTime")
        controls.addWidget(self.time)
        play_layout.addWidget(self.player_controls)

        self.player_actions=QWidget(player_panel)
        actions=QHBoxLayout(self.player_actions)
        actions.setContentsMargins(0,0,0,0)
        actions.setSpacing(10)
        self.favorite=QPushButton("Favoritar")
        self.favorite.setIcon(svg_icon_for("favorites"))
        self.favorite.setIconSize(QSize(22,22))
        self.favorite.clicked.connect(self._favorite)
        actions.addWidget(self.favorite)
        self.fullscreen_button=QPushButton("Tela cheia")
        self.fullscreen_button.setIcon(svg_icon_for("fullscreen"))
        self.fullscreen_button.setIconSize(QSize(20,20))
        self.fullscreen_button.clicked.connect(self._toggle_video_fullscreen)
        self.fullscreen_button.setToolTip("Tela cheia (F11) · sair com Esc")
        actions.addWidget(self.fullscreen_button)
        self.volume_button=QPushButton()
        self.volume_button.setObjectName("volumeButton")
        self.volume_button.setIcon(svg_icon_for("volume",22))
        self.volume_button.setIconSize(QSize(22,22))
        self.volume_button.setToolTip("Ativar/desativar som")
        self.volume_button.clicked.connect(self._toggle_mute)
        actions.addWidget(self.volume_button)
        self.volume_slider=AuroraSeekSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0,100)
        self.volume_slider.setValue(75)
        self.volume_slider.setMaximumWidth(125)
        self.volume_slider.valueChanged.connect(lambda v:self.audio.setVolume(v/100))
        actions.addWidget(self.volume_slider)
        play_layout.addWidget(self.player_actions)

        # Floating player HUD: it is a CHILD of the video stage, not a new
        # QVideoWidget/fullscreen output. The same decoder and rendering sink
        # remain connected throughout the transition.
        self.fs_overlay=QFrame(self.video_stage)
        self.fs_overlay.setObjectName("fullscreenOverlay")
        self.fs_overlay.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.fs_overlay.setMouseTracking(True)
        hud=QVBoxLayout(self.fs_overlay)
        hud.setContentsMargins(28,22,28,22)
        hud.setSpacing(12)
        top_row=QHBoxLayout()
        self.fs_content_label=QLabel("AURORA IPTV")
        self.fs_content_label.setObjectName("fsTitle")
        top_row.addWidget(self.fs_content_label,1)
        self.fs_top_exit=QPushButton("Sair da tela cheia")
        self.fs_top_exit.setIcon(svg_icon_for("exit-fullscreen",20))
        self.fs_top_exit.clicked.connect(self._leave_video_fullscreen)
        top_row.addWidget(self.fs_top_exit)
        hud.addLayout(top_row)
        hud.addStretch(1)

        self.fs_bottom=QFrame(self.fs_overlay)
        self.fs_bottom.setObjectName("fullscreenBottom")
        fs_box=QVBoxLayout(self.fs_bottom)
        fs_box.setContentsMargins(20,18,20,17)
        fs_box.setSpacing(9)
        seek_row=QHBoxLayout()
        self.fs_seek=AuroraSeekSlider(Qt.Orientation.Horizontal)
        self.fs_seek.setRange(0,0)
        self.fs_seek.sliderMoved.connect(self.player.setPosition)
        seek_row.addWidget(self.fs_seek,1)
        self.fs_time=QLabel("00:00 / 00:00")
        self.fs_time.setObjectName("playerTime")
        seek_row.addWidget(self.fs_time)
        fs_box.addLayout(seek_row)
        buttons=QHBoxLayout()
        buttons.setSpacing(12)
        self.fs_play=QPushButton("Reproduzir")
        self.fs_play.setIcon(svg_icon_for("play",24))
        self.fs_play.setIconSize(QSize(24,24))
        self.fs_play.setObjectName("playButton")
        self.fs_play.clicked.connect(self._toggle_play)
        buttons.addWidget(self.fs_play)
        self.fs_favorite=QPushButton("Favoritar")
        self.fs_favorite.setIcon(svg_icon_for("favorites",21))
        self.fs_favorite.setIconSize(QSize(21,21))
        self.fs_favorite.clicked.connect(self._favorite)
        buttons.addWidget(self.fs_favorite)
        buttons.addStretch(1)
        self.fs_volume_icon=QPushButton()
        self.fs_volume_icon.setIcon(svg_icon_for("volume",22))
        self.fs_volume_icon.setIconSize(QSize(22,22))
        self.fs_volume_icon.setToolTip("Ativar/desativar som")
        self.fs_volume_icon.clicked.connect(self._toggle_mute)
        buttons.addWidget(self.fs_volume_icon)
        self.fs_volume=AuroraSeekSlider(Qt.Orientation.Horizontal)
        self.fs_volume.setRange(0,100)
        self.fs_volume.setValue(75)
        self.fs_volume.setMaximumWidth(140)
        self.fs_volume.valueChanged.connect(self.volume_slider.setValue)
        self.volume_slider.valueChanged.connect(self.fs_volume.setValue)
        buttons.addWidget(self.fs_volume)
        self.fs_exit=QPushButton("Sair da tela cheia")
        self.fs_exit.setIcon(svg_icon_for("exit-fullscreen",20))
        self.fs_exit.clicked.connect(self._leave_video_fullscreen)
        buttons.addWidget(self.fs_exit)
        fs_box.addLayout(buttons)
        hud.addWidget(self.fs_bottom)
        self.fs_overlay.hide()

        self._fs_opacity=QGraphicsOpacityEffect(self.fs_overlay)
        self.fs_overlay.setGraphicsEffect(self._fs_opacity)
        self._fs_fade=QPropertyAnimation(self._fs_opacity,b"opacity",self)
        self._fs_fade.setDuration(2000)
        self._fs_fade.setStartValue(1.0)
        self._fs_fade.setEndValue(0.0)
        self._fs_fade.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._fs_fade.finished.connect(self._hide_fullscreen_overlay)
        self._fs_idle=QTimer(self)
        self._fs_idle.setSingleShot(True)
        self._fs_idle.setInterval(3000)
        self._fs_idle.timeout.connect(self._begin_fullscreen_fade)
        self.video_stage.installEventFilter(self)
        self.video.setMouseTracking(True)
        self.video_stage.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)
        self.player.positionChanged.connect(self._sync_fullscreen_position)
        self.player.durationChanged.connect(self._sync_fullscreen_duration)
        self.player.playbackStateChanged.connect(self._sync_play_icons)
        self.status = QLabel("Selecione sua playlist para começar.")
        self.status.setObjectName("statusInfo")
        self.status.setWordWrap(True)
        play_layout.addWidget(self.status)
        panels.addWidget(player_panel)
        panels.setStretchFactor(0,1)
        panels.setStretchFactor(1,2)
        panels.setStretchFactor(2,3)
        panels.setSizes([260,455,725])
        base.addWidget(shell,1)

        QShortcut(QKeySequence("Space"),self.video,self._toggle_play)
        self.exit_fullscreen_shortcut = QShortcut(QKeySequence("Escape"),self,self._leave_video_fullscreen)
        self.exit_fullscreen_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.enter_fullscreen_shortcut = QShortcut(QKeySequence("F11"),self,self._toggle_video_fullscreen)
        self.enter_fullscreen_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self._video_fullscreen = False
        self._fullscreen_was_maximized = False
        self._saved_panel_sizes = None
        self._saved_minimum_size = None
        self._saved_panel_margin = None
        self._saved_player_margin = None
        self._saved_player_spacing = None
        self._saved_player_min_width = None
        self._saved_video_mode = None
        self.selected_category = None
        self._browse_history = []
        self._loading_items = False
        self._exhausted = False
        self._indexed = set()
        self._auto_guide_attempted = set()
        self.index_thread = None
        self.index_worker = None
        self._index_error = set()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(240)
        self._search_timer.timeout.connect(self._refresh)
        self.guide_thread = None
        self.score_thread = None
        self.score_worker = None
        self._score_request_playlist = None
        self._score_last_started = 0.0
        self._score_timer = QTimer(self)
        self._score_timer.setInterval(60_000)
        self._score_timer.timeout.connect(self._start_score_updates)
        self._score_timer.start()
        self._live_badge_timer = QTimer(self)
        self._live_badge_timer.setInterval(700)
        self._live_badge_timer.timeout.connect(self._pulse_football_badge)
        self._live_badge_timer.start()
        self.setMinimumSize(1150,680)
        self.resize(1580,900)

    def eventFilter(self, obj, event):
        if getattr(self, "_video_fullscreen", False):
            kind=event.type()
            if obj is self.video_stage and kind == QEvent.Type.Resize:
                self._position_fullscreen_overlay()
            if kind == QEvent.Type.MouseMove and isinstance(obj, QWidget):
                if obj is self or self.isAncestorOf(obj):
                    self._show_fullscreen_overlay()
        return super().eventFilter(obj,event)

    def _position_fullscreen_overlay(self):
        if not hasattr(self,"fs_overlay"):
            return
        self.fs_overlay.setGeometry(self.video_stage.rect())
        if self._video_fullscreen:
            self.fs_overlay.raise_()

    def _show_fullscreen_overlay(self):
        if not self._video_fullscreen:
            return
        self._fs_fade.stop()
        self._fs_opacity.setOpacity(1.0)
        self._position_fullscreen_overlay()
        self.fs_overlay.show()
        self.fs_overlay.raise_()
        self._fs_idle.start(3000)

    def _begin_fullscreen_fade(self):
        if not self._video_fullscreen:
            return
        if self.fs_seek.isSliderDown() or self.fs_volume.isSliderDown():
            self._fs_idle.start(3000)
            return
        self._fs_fade.stop()
        self._fs_fade.setStartValue(1.0)
        self._fs_fade.setEndValue(0.0)
        self._fs_fade.start()

    def _hide_fullscreen_overlay(self):
        if self._video_fullscreen and self._fs_opacity.opacity() < .05:
            self.fs_overlay.hide()

    def _sync_play_icons(self, *args):
        playing=(self.player.playbackState()
                 == QMediaPlayer.PlaybackState.PlayingState)
        caption="Pausar" if playing else "Reproduzir"
        icon="pause" if playing else "play"
        self.play.setText(caption)
        self.play.setIcon(svg_icon_for(icon,22,light=not getattr(self,"_theme_dark",True)))
        self.fs_play.setText(caption)
        self.fs_play.setIcon(svg_icon_for(icon,24,light=not getattr(self,"_theme_dark",True)))

    def _sync_fullscreen_duration(self,duration):
        self.fs_seek.setRange(0,max(0,duration))
        self._sync_fullscreen_position(self.player.position())

    def _sync_fullscreen_position(self,position):
        if not self.fs_seek.isSliderDown():
            self.fs_seek.setValue(position)
        self.fs_time.setText(legacy.clock(position)+" / "+legacy.clock(self.player.duration()))

    def _toggle_mute(self):
        self.audio.setMuted(not self.audio.isMuted())
        self._sync_volume_icon()

    def _sync_volume_icon(self):
        icon="mute" if self.audio.isMuted() else "volume"
        self.volume_button.setIcon(svg_icon_for(icon,22,light=not getattr(self,"_theme_dark",True)))
        self.fs_volume_icon.setIcon(svg_icon_for(icon,22,light=not getattr(self,"_theme_dark",True)))

    def _sync_favorite_controls(self):
        enabled=self.favorite.isEnabled()
        self.fs_favorite.setEnabled(enabled)
        self.fs_favorite.setText(self.favorite.text() if enabled else "Favoritar")

    def _toggle_video_fullscreen(self):
        """Fullscreen the SAME media surface, with floating controls over it.

        Never reparent QVideoWidget, call its own setFullScreen(), or create a
        second video sink: those operations froze video on some Qt backends.
        """
        if self._video_fullscreen:
            self._leave_video_fullscreen()
            return
        self._video_fullscreen=True
        self._fullscreen_was_maximized=self.isMaximized()
        self._saved_panel_sizes=self.panels.sizes()
        self._saved_minimum_size=self.minimumSize()
        self._saved_player_min_width=self.player_panel.minimumWidth()
        layout=self.player_panel.layout()
        self._saved_player_margin=layout.contentsMargins()
        self._saved_player_spacing=layout.spacing()
        self._saved_video_mode=self.video.aspectRatioMode()
        self.setMinimumSize(0,0)
        self.player_panel.setMinimumWidth(0)
        self.player_panel.setStyleSheet(
            "QFrame#panel {background:#000000;border:0;border-radius:0;}")
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(0)
        self.sidebar.hide()
        self.header_widget.hide()
        self.categories_panel.hide()
        self.contents_panel.hide()
        self.now.hide()
        self.video_title.hide()
        self.status.hide()
        self.player_controls.hide()
        self.player_actions.hide()
        self.player_back.hide()
        self.synopsis_button.hide()
        self.menuBar().hide()
        self.outer_layout.setContentsMargins(0,0,0,0)
        self.outer_layout.setSpacing(0)
        # Fill the display, including ultrawide screens. This crops the edges
        # of 16:9 content on 21:9 monitors instead of drawing black pillarboxes.
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        self.fs_content_label.setText(
            self.playing.get("title","AURORA IPTV") if self.playing else "AURORA IPTV")
        self._sync_play_icons()
        self._sync_favorite_controls()
        self._sync_volume_icon()
        self.showFullScreen()
        self._show_fullscreen_overlay()
        self.video.setFocus(Qt.FocusReason.OtherFocusReason)

    def _leave_video_fullscreen(self):
        if not self._video_fullscreen:
            return
        self._video_fullscreen=False
        self._fs_idle.stop()
        self._fs_fade.stop()
        self._fs_opacity.setOpacity(1.0)
        self.fs_overlay.hide()
        if self._saved_video_mode is not None:
            self.video.setAspectRatioMode(self._saved_video_mode)
        if self._saved_player_min_width is not None:
            self.player_panel.setMinimumWidth(self._saved_player_min_width)
        self.player_panel.setStyleSheet("")
        layout=self.player_panel.layout()
        if self._saved_player_margin is not None:
            layout.setContentsMargins(self._saved_player_margin)
        if self._saved_player_spacing is not None:
            layout.setSpacing(self._saved_player_spacing)
        self.outer_layout.setContentsMargins(16,15,16,15)
        self.outer_layout.setSpacing(14)
        self.sidebar.show()
        self.header_widget.show()
        self.categories_panel.show()
        self.contents_panel.show()
        self.now.show()
        self.video_title.show()
        self.status.show()
        self.player_controls.show()
        self.player_actions.show()
        self.player_back.setVisible(bool(self.playing) and not self._video_fullscreen)
        self.synopsis_button.setVisible(
            bool((self.selected or self.playing) and
                 (self.selected or self.playing).get("kind") in ("movie","series")))
        # Keep the old top menu permanently hidden; settings own its actions.
        if self._saved_minimum_size is not None:
            self.setMinimumSize(self._saved_minimum_size)
        self.showNormal()
        if self._fullscreen_was_maximized:
            self.showMaximized()
        if self._saved_panel_sizes:
            self.panels.setSizes(self._saved_panel_sizes)
        self.video.setFocus(Qt.FocusReason.OtherFocusReason)

    def _start(self, item):
        if item.get("url"):
            self.video_stage.setCurrentWidget(self.video)
        super()._start(item)
        self._sync_play_icons()
        self._sync_favorite_controls()
        if item.get("url"):
            self.fs_content_label.setText(item.get("title","AURORA IPTV"))
            self.player_back.setVisible(True)
            self.synopsis_button.setVisible(item.get("kind") in ("movie","series"))
            self.video.setFocus()

    def _toggle_play(self):
        if self.playing:
            self.video_stage.setCurrentWidget(self.video)
        super()._toggle_play()
        self._sync_play_icons()

    def _favorite(self):
        super()._favorite()
        self._sync_favorite_controls()

    def _player_error(self, error, error_string):
        super()._player_error(error,error_string)
        if error != QMediaPlayer.Error.NoError:
            self.video_stage.setCurrentWidget(self.player_splash)

    def _theme_apply(self):
        # Replace, NEVER concatenate, stylesheets: the previous implementation
        # appended styles on each theme switch and introduced black QLabel bars.
        choice = self.settings.value("theme", "system")
        dark = choice == "dark" or (
            choice == "system" and
            QApplication.instance().styleHints().colorScheme() != Qt.ColorScheme.Light
        )
        self._theme_dark = dark
        bg = "#071624" if dark else "#edf5f8"
        side = "#091f31" if dark else "#e2f0f4"
        panel = "#102b40" if dark else "#ffffff"
        panel_end = "#0e2438" if dark else "#f8fbfd"
        inner = "#152f45" if dark else "#f1f8fa"
        row = "#17364b" if dark else "#e9f4f5"
        border = "#295069" if dark else "#bed7e0"
        muted = "#aac6d6" if dark else "#577487"
        text = "#f1fbff" if dark else "#173448"
        accent = "#6cebd6" if dark else "#127f82"
        accent_text = "#06242b" if dark else "#ffffff"
        selected = "#244c5c" if dark else "#ccefe9"
        hover = "#215069" if dark else "#d9f1ed"
        blue = "#82bbff" if dark else "#2377b1"
        track = "#24465c" if dark else "#ccdee4"
        gold = "#ffdc69" if dark else "#be8b1c"
        menu = "#112a3e" if dark else "#fbfeff"
        self.setAutoFillBackground(True)
        QApplication.instance().setStyleSheet(f"""
            QWidget {{
                color:{text};
                font-family:'Segoe UI','Inter','Noto Sans',sans-serif;
                font-size:14px;
            }}
            QMainWindow, QWidget#appRoot, QWidget#contentShell {{
                background:{bg};
            }}
            QLabel {{
                background:transparent;
                border:none;
                padding:0;
            }}
            QFrame#sidebar {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {side},stop:1 {bg});
                border:none;
                border-right:1px solid {border};
            }}
            QFrame#panel {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 {panel},stop:1 {panel_end});
                border:1px solid {border};
                border-radius:16px;
            }}
            QFrame#playerSplash {{
                background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {'#133e56' if dark else '#d8f4f0'},
                    stop:0.45 {'#1a4d67' if dark else '#d4e8f9'},
                    stop:0.78 {'#273960' if dark else '#e6ddfa'},
                    stop:1 {'#271d4e' if dark else '#f6ecfc'});
                border:1px solid {border};
                border-radius:14px;
            }}
            QLabel#splashEmblem {{
                color:{accent};font-size:64px;
            }}
            QLabel#splashHeading {{
                color:{text};font-size:29px;font-weight:850;
            }}
            QLabel#splashDescription {{
                color:{muted};font-size:14px;
            }}
            QLabel#heroBadge {{
                color:#aaf9ec;
                background:rgba(7,40,55,0.64);
                border:1px solid rgba(102,238,213,0.45);
                border-radius:9px;
                font-size:10px;
                font-weight:750;
                letter-spacing:1px;
                padding:5px 10px;
            }}
            QLabel#heroVersion {{
                color:#d7e9f5;
                background:rgba(6,20,38,0.62);
                border-radius:8px;
                font-size:11px;
                font-weight:650;
                padding:6px 11px;
            }}
            QLabel#heroTitle {{
                color:#ffffff;
                font-size:32px;
                font-weight:850;
                letter-spacing:1px;
                background:transparent;
            }}
            QLabel#heroSubtitle {{
                color:#9df7e1;
                font-size:11px;
                font-weight:750;
                letter-spacing:2px;
                background:transparent;
            }}
            QLabel#heroFootnote {{
                color:#c2d9e4;
                font-size:10px;
                letter-spacing:1px;
                background:transparent;
            }}
            QFrame#playlistSettings {{
                background:{inner};
                border:1px solid {border};
                border-radius:13px;
            }}
            QFrame#playlistSettings QLabel {{
                background:transparent;
                border:none;
            }}
            QLabel#settingsTitle {{
                color:{accent};
                font-size:12px;
                font-weight:800;
                letter-spacing:1px;
            }}
            QComboBox#activePlaylistSelector {{
                background:{panel};
                border:1px solid {border};
                border-radius:9px;
                min-height:24px;
                padding:10px 12px;
                font-weight:700;
            }}
            QComboBox#activePlaylistSelector:focus {{
                border:1px solid {accent};
            }}
            QLabel#brand {{
                font-size:19px;font-weight:800;color:{accent};
            }}
            QLabel#versionTag {{
                font-size:12px;color:{muted};padding:4px 0;
            }}
            QLabel#versionFooter {{
                font-size:11px;color:{muted};font-weight:650;
                padding:12px 2px 3px 0;
                border-top:1px solid {border};
            }}
            QFrame#configCard {{
                background:{inner};border:1px solid {border};
                border-radius:13px;
            }}
            QFrame#configCard QLabel {{
                background:transparent;border:none;
            }}
            QPushButton#settingsAction {{
                text-align:left;
                background:{row};padding:11px 12px;
            }}
            QPushButton#settingsAction:hover {{
                background:{hover};border-color:{accent};
            }}
            QLabel#heading {{
                font-size:19px;font-weight:750;color:{text};
                padding:3px 0 2px 0;
            }}
            QLabel#muted {{
                font-size:12px;color:{muted};padding:2px 0;
            }}
            QLabel#playerEyebrow {{
                font-size:11px;color:{accent};font-weight:650;
                padding:5px 8px;border-radius:6px;
                background:{inner};
            }}
            QLabel#playerTime {{
                color:{muted};font-size:12px;
                padding:5px 8px;border-radius:7px;
                background:{inner};
            }}
            QLabel#statusInfo {{
                color:{muted};font-size:12px;
                padding:8px 10px;border-radius:9px;
                background:{inner};border:1px solid {border};
            }}
            QMenuBar {{
                background:{bg};color:{text};
                padding:5px 10px;border:0;
            }}
            QMenuBar::item {{
                padding:8px 12px;border-radius:7px;
            }}
            QMenuBar::item:selected {{
                background:{hover};
            }}
            QMenu {{
                background:{menu};color:{text};
                border:1px solid {border};padding:6px;
            }}
            QMenu::item {{padding:8px 25px;border-radius:5px;}}
            QMenu::item:selected {{background:{hover};}}
            QPushButton {{
                color:{text};background:{row};
                border:1px solid {border};border-radius:11px;
                padding:11px 13px;font-size:13px;font-weight:650;
                min-height:17px;
            }}
            QPushButton:hover {{
                background:{hover};border-color:{accent};
            }}
            QPushButton:pressed {{background:{selected};}}
            QPushButton:disabled {{
                color:{muted};border-color:{border};
            }}
            QPushButton#navButton {{
                text-align:left;
                padding:12px 13px 12px 16px;
                min-height:35px;
                background:{inner};
                border:1px solid transparent;
                border-radius:11px;
                font-size:14px;font-weight:650;
            }}
            QPushButton#footballRefresh {{
                padding:5px 12px;
                min-height:24px;
                border-radius:9px;
                background:{inner};
                border:1px solid {border};
                font-size:12px;
            }}
            QPushButton#footballRefresh:hover {{
                background:{hover};border:1px solid {accent};
            }}
            QPushButton#navButton:hover {{
                background:{hover};
                border-color:{border};
            }}
            QPushButton#navButton:checked {{
                background:{selected};
                border:1px solid {accent};
                border-left:3px solid {accent};
                color:{text};
            }}
            QPushButton#primary {{
                background:{accent};color:{accent_text};
                border:1px solid {accent};
                font-weight:800;
            }}
            QPushButton#primary:hover {{
                background:{blue};border-color:{blue};
                color:{accent_text};
            }}
            QLineEdit,QComboBox {{
                background:{inner};color:{text};
                border:1px solid {border};border-radius:10px;
                padding:10px 12px;selection-background-color:{selected};
                min-height:19px;
            }}
            QLineEdit:focus,QComboBox:focus {{
                border:1px solid {accent};
            }}
            QLineEdit::placeholder {{color:{muted};}}
            QComboBox QAbstractItemView {{
                background:{menu};color:{text};
                selection-background-color:{selected};
                border:1px solid {border};
            }}
            QListWidget {{
                background:transparent;color:{text};
                border:0;outline:0;
                font-size:13px;
            }}
            QListWidget::item {{
                background:transparent;
                border:1px solid transparent;
                border-radius:11px;
                padding:10px 10px;
            }}
            QListWidget::item:hover {{
                background:{hover};
            }}
            QListWidget::item:selected {{
                background:{selected};
                border:1px solid {accent};
                color:{text};
            }}
            QListWidget#groups::item {{
                background:{inner};
                border:1px solid transparent;
                border-radius:10px;
                padding:12px 12px;
                margin:2px 1px;
            }}
            QListWidget#groups::item:hover {{
                background:{hover};
            }}
            QListWidget#groups::item:selected {{
                background:{selected};border:1px solid {accent};
                border-left:3px solid {accent};
                color:{text};
            }}
            QListWidget#results::item {{
                background:{row};
                padding:9px 9px;
                margin:3px 1px;
            }}
            QListWidget#results::item:selected {{
                background:{selected};
                border:1px solid {accent};
            }}
            QSplitter::handle {{
                background:{bg};
                width:7px;
            }}
            QScrollBar:vertical {{
                background:transparent;
                width:10px;margin:2px 0;
            }}
            QScrollBar::handle:vertical {{
                background:{track};border-radius:5px;min-height:45px;
            }}
            QScrollBar::handle:vertical:hover {{background:{accent};}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{
                height:0px;border:none;
            }}
            QScrollBar:horizontal {{
                background:transparent;height:8px;
            }}
            QScrollBar::handle:horizontal {{
                background:{track};border-radius:4px;min-width:24px;
            }}
            QSlider::groove:horizontal {{
                height:5px;background:{track};border-radius:3px;
            }}
            QSlider::sub-page:horizontal {{
                background:{accent};border-radius:3px;
            }}
            QSlider::handle:horizontal {{
                width:14px;height:14px;margin:-5px 0;
                background:{accent};border:2px solid {panel};
                border-radius:8px;
            }}
            QSlider#auroraSeek::handle:horizontal {{
                width:20px;height:20px;margin:-8px 0;
                background:transparent;border:0;border-radius:10px;
            }}
            QFrame#fullscreenOverlay {{
                background:transparent;border:0;
            }}
            QFrame#fullscreenBottom {{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                   stop:0 rgba(5,21,38,115),stop:.4 rgba(5,21,38,205),
                   stop:1 rgba(4,15,31,235));
                border:1px solid rgba(103,220,221,85);
                border-radius:14px;
            }}
            QLabel#fsTitle {{
                color:#ffffff;font-size:20px;font-weight:800;
                background:rgba(5,19,34,130);border-radius:9px;
                padding:10px 14px;
            }}
            QFrame#fullscreenOverlay QPushButton {{
                background:rgba(18,45,65,195);
                color:#f3fbff;border:1px solid rgba(123,225,226,120);
                border-radius:11px;padding:10px 14px;
            }}
            QFrame#fullscreenOverlay QPushButton:hover {{
                background:rgba(29,83,102,235);
                border:1px solid #72eddb;
            }}
            QFrame#fullscreenOverlay QSlider::groove:horizontal {{
                background:rgba(211,232,235,80);height:6px;
            }}
            QFrame#fullscreenOverlay QSlider::sub-page:horizontal {{
                background:#6cebd6;height:6px;
            }}
            QFrame#fullscreenOverlay QLabel#playerTime {{
                color:#d9fbf8;background:rgba(10,37,54,155);
            }}
            QToolTip {{
                color:{text};background:{menu};
                border:1px solid {accent};padding:5px;
            }}
        """)
        # Icons are drawn at 3x resolution; gold is reserved for favorites.
        for name, button in self.nav.items():
            button.setIcon(svg_icon_for(name, 30, light=not dark))
        self.previous.setIcon(svg_icon_for("back",24,light=not dark))
        self.action.setIcon(svg_icon_for("refresh",24,light=not dark))
        self.second_action.setIcon(svg_icon_for("manage",24,light=not dark))
        self.favorite.setIcon(svg_icon_for("favorites", 22, light=not dark))
        self.fullscreen_button.setIcon(svg_icon_for("fullscreen",20,light=not dark))
        self.fs_top_exit.setIcon(svg_icon_for("exit-fullscreen",20,light=not dark))
        self.fs_exit.setIcon(svg_icon_for("exit-fullscreen",20,light=not dark))
        self.fs_favorite.setIcon(svg_icon_for("favorites",21,light=not dark))
        self.config_epg_button.setIcon(svg_icon_for("settings",24,light=not dark))
        self.update_epg_button.setIcon(svg_icon_for("refresh",24,light=not dark))
        self.player_back.setIcon(svg_icon_for("back",20,light=not dark))
        self.synopsis_button.setIcon(svg_icon_for("series",20,light=not dark))
        self._sync_play_icons()
        self._sync_volume_icon()
        for card in self._football_card_widgets.values():
            card.apply_theme(dark)

    def _sports_online_changed(self, enabled: bool):
        self.settings.setValue("football/online_data", enabled)
        self._football_updates.clear()
        self._score_last_started = 0.0

    def _sports_online_enabled(self) -> bool:
        return self.settings.value("football/online_data", True, type=bool)

    def _on_playlist(self):
        # Selecting a playlist in Configurações should not unexpectedly
        # throw the user out of the page. Keep the prior import/progress
        # behavior and update the visible library in place.
        self._save_progress()
        self.playlist_id = self.playlists.currentData()
        if self.mode == "settings":
            selected = self.playlists.currentText()
            self.status.setText(
                f"Playlist ativa: {selected}" if selected else
                "Nenhuma playlist ativa. Adicione uma lista para começar.")
            self._refresh()
        else:
            self.navigate("home")

    def navigate(self, mode):
        self.mode = mode
        if mode != "episodes":
            self.series_name = ""
        self.selected_category = None
        self.offset = 0
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        for k,b in self.nav.items():
            b.setChecked(k == mode)
        self._refresh()
        if mode == "football" and self.playlist_id is not None:
            self._maybe_load_guide()
            QTimer.singleShot(800, self._start_score_updates)

    def _set_update_channel(self, index):
        channel = self.update_channel.itemData(index)
        if not channel:
            return
        controller = getattr(self, "update_controller", None)
        if controller is not None:
            controller.set_channel(channel)
        else:
            self.settings.setValue("updates/channel", channel)
            self.settings.remove("updates/last_check")

    def _check_updates_now(self):
        controller = getattr(self, "update_controller", None)
        if controller is not None:
            controller.check(manual=True)
        else:
            self.status.setText("O verificador de atualizações ainda não está disponível.")

    def _import_playlist_file(self):
        # Use the proven local M3U import path in the legacy interface.
        self._second_action()

    def _show_settings_section(self):
        active = self.mode == "settings"
        section = self.selected_category or "playlists"
        for name, widget in self.settings_sections.items():
            widget.setVisible(active and name == section)
        show_list = not active or section == "playlists"
        self.results.setVisible(show_list)
        self.page.setVisible(show_list)
        # Futebol uses a compact refresh next to the heading; setup EPG
        # is located under Configurações and must not occupy list height.
        self.action.setVisible(not active and self.mode != "football")
        self.second_action.setVisible(not active and self.mode != "football")
        if active:
            self.theme_select.blockSignals(True)
            self.theme_select.setCurrentIndex(
                max(0,self.theme_select.findData(self.settings.value("theme","system"))))
            self.theme_select.blockSignals(False)
            self.update_channel.blockSignals(True)
            self.update_channel.setCurrentIndex(
                max(0,self.update_channel.findData(self.settings.value("updates/channel","beta"))))
            self.update_channel.blockSignals(False)

    def _search(self):
        self._search_timer.start()

    def _change_category(self, current, previous):
        if not current:
            return
        self.selected_category = current.data(Qt.ItemDataRole.UserRole)
        self.offset = 0
        self._show_settings_section()
        self._load_items(reset=True)

    def _refresh(self):
        titles = {
            "home":"Continuar assistindo", "live":"Canais disponíveis",
            "movie":"Filmes", "series":"Séries", "episodes":self.series_name,
            "favorites":"Favoritos", "settings":"Playlists e preferências",
            "football":"Agenda de futebol",
        }
        self.heading.setText(titles.get(self.mode,"AURORA IPTV"))
        self.groups_title.setText("CLASSIFICAÇÃO" if self.mode != "football" else "CAMPEONATOS")
        self.groups_hint.setText("Escolha uma categoria" if self.mode not in ("home","settings") else "Sua biblioteca")
        self.search.setVisible(self.mode not in ("settings","episodes"))
        self.search.setPlaceholderText(
            "Buscar partidas por nome do time..." if self.mode == "football"
            else "Buscar canais, filmes, séries...")
        self.previous.setVisible(self.mode == "episodes")
        self.player_back.setVisible(bool(self.playing))
        self._show_settings_section()
        self.covers.reset()
        self.groups.blockSignals(True)
        self.groups.clear()
        self.groups.blockSignals(False)
        self.selected_category = None
        self.offset = 0
        self._football_card_widgets.clear()
        self.football_refresh.setVisible(self.mode == "football")
        self.guide_busy.setVisible(self.mode == "football" and bool(
            getattr(self, "guide_thread", None) and self.guide_thread.isRunning()))
        self.action.setVisible(self.mode not in ("settings", "football"))
        self.second_action.setVisible(self.mode not in ("settings", "football"))
        self.action.setText("Adicionar URL M3U" if self.mode == "settings" or self.playlist_id is None
                            else "Atualizar EPG Futebol" if self.mode == "football"
                            else "Atualizar playlist")
        self.action.setIcon(svg_icon_for("add" if self.mode == "settings" or self.playlist_id is None
                                         else "refresh",light=not getattr(self,"_theme_dark",True)))
        self.second_action.setText("Importar arquivo local" if self.mode == "settings"
                                   else "Configurar EPG" if self.mode == "football"
                                   else "Gerenciar playlists")
        self.second_action.setIcon(svg_icon_for("upload" if self.mode == "settings" else
                                                "settings" if self.mode == "football" else "manage",
                                                light=not getattr(self,"_theme_dark",True)))
        self.football_refresh.setIcon(svg_icon_for("refresh",20,
                                  light=not getattr(self,"_theme_dark",True)))
        if self.mode == "settings":
            self.subtitle.setText("Selecione a biblioteca ativa, adicione listas ou gerencie as existentes. Seus favoritos e progresso são preservados.")
        elif self.mode == "football":
            self.subtitle.setText("Agenda do EPG e canais esportivos disponíveis.")
        elif self.mode == "series":
            self.subtitle.setText("Gêneros de séries, plataformas e categorias da playlist.")
        else:
            self.subtitle.setText("Escolha uma categoria; a lista carrega conforme você rola.")
        if self.playlist_id is not None and self.mode in ("live","movie","series") and self.playlist_id not in self._indexed:
            self.results.clear()
            self.groups.clear()
            self.page.setText("Organizando as categorias em segundo plano...")
            if self.playlist_id not in self._index_error:
                self._start_index(self.playlist_id)
            return
        if self.mode in ("live","movie","series") and self.playlist_id is not None:
            categories = self.library.categories(self.playlist_id,self.mode)
            choices = [(f"Todos ({sum(g['total'] for g in categories):,})",None)]
            choices += [(f"{g['title']}  ·  {g['total']:,}",g["title"]) for g in categories]
        elif self.mode == "football" and self.playlist_id is not None:
            cats = self.library.football_categories(self.playlist_id)
            choices = [("Todos os jogos",None)] + [(r["title"],r["title"]) for r in cats]
        elif self.mode == "home":
            choices = [("Assistidos recentemente",None)]
        elif self.mode == "favorites":
            choices = [("Todos os favoritos",None)]
        elif self.mode == "settings":
            choices = [("Playlists", "playlists"), ("Aparência", "appearance"),
                       ("Atualizações", "updates"), ("Guia de futebol", "guide")]
        else:
            choices = [("Nenhuma playlist",None)]
        self.groups.blockSignals(True)
        for label,value in choices:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole,value)
            item.setToolTip(label)
            self.groups.addItem(item)
        self.groups.setCurrentRow(0)
        self.groups.blockSignals(False)
        if self.mode == "settings":
            self.selected_category = "playlists"
        self._show_settings_section()
        self._load_items(reset=True)

    def _add_result(self,label,record):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole,record)
        item.setSizeHint(QSize(0,170 if record.get("kind") == "football" else 106))
        item.setToolTip(label.replace("\n", " — "))
        self.results.addItem(item)
        if record.get("kind") != "football":
            self.covers.enqueue(item,record.get("logo",""),record.get("kind","movie"))
        return item

    def _load_items(self,reset=False):
        if self._loading_items or (self._exhausted and not reset):
            return
        self._loading_items = True
        try:
            if reset:
                self.covers.reset()
                self.results.clear()
                self.offset = 0
                self._exhausted = False
            if self.playlist_id is None and self.mode != "settings":
                self.page.setText("Adicione uma playlist em Configurações.")
                self._exhausted = True
                return
            query = self.search.text().strip()
            if self.mode == "settings":
                if self.selected_category in (None, "playlists"):
                    for r in self.library.playlists():
                        self._add_result(r["name"] + ("  ✓" if r["id"] == self.playlist_id else ""),{"kind":"playlist",**r})
                    self.page.setText("Clique com o botão direito em uma lista para editar ou remover.")
                self._exhausted = True
            elif self.mode == "home":
                rows = self.library.recent(self.playlist_id,limit=100)
                self._add_many(rows)
                self._exhausted = True
            elif self.mode == "favorites":
                rows = self.library.favorite_entries(self.playlist_id,query)
                self._add_many(rows)
                self._exhausted = True
            elif self.mode == "episodes":
                rows = self.library.episodes(self.playlist_id,self.series_name)
                # Series with thousands of episodes remain scrollable.
                self._add_many(rows)
                self._exhausted = True
            else:
                if self.mode == "football":
                    rows = self.library.football(self.playlist_id,self.selected_category,query,limit=61,offset=self.offset)
                    # An empty EPG is not a list of fixtures. Sports channels
                    # remain accessible under Ao vivo; never label channels as matches.
                    self._exhausted = len(rows) <= 60
                    if not rows and self.offset == 0:
                        self.page.setText(
                            "Nenhuma partida identificada. Os canais continuam disponíveis em Ao vivo.")
                else:
                    rows = self.library.browse(self.playlist_id,self.mode,self.selected_category,query,limit=61,offset=self.offset)
                    self._exhausted = len(rows) <= 60
                self._add_many(rows[:60] if not self._exhausted else rows)
                self.offset += min(len(rows),60)
                if rows:
                    noun = "partidas" if self.mode == "football" else "conteúdos"
                    self.page.setText(f"{self.offset:,} {noun} · role para explorar".replace(",", "."))
            if not self.results.count() and self.mode != "football":
                self.page.setText("Nenhum conteúdo nesta categoria.")
        finally:
            self._loading_items = False

    @staticmethod
    def _football_label(record):
        """Friendly but honest fixture card: no fabricated scores or badges."""
        stamp = record.get("start","")
        try:
            dt = datetime.fromisoformat(stamp).astimezone()
            weekdays = ("Segunda-Feira","Terça-Feira","Quarta-Feira",
                        "Quinta-Feira","Sexta-Feira","Sábado","Domingo")
            months = ("Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                      "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro")
            date = f"{weekdays[dt.weekday()]} - {dt.day} de {months[dt.month-1]}"
            time = dt.strftime("%H:%M")
        except (TypeError, ValueError):
            dt = None
            date = "Data indisponível"
            time = "--:--"
        league = record.get("competition") or "Competição não informada"
        home = record.get("home_team") or ""
        away = record.get("away_team") or ""
        if not home or not away:
            from .android_rules import football_details
            match = football_details(record.get("title",""),league)
            if match:
                home, away = match.home,match.away
        opponents = f"{home}  X  {away}" if home and away else record.get("title","")
        hscore, ascore = record.get("home_score"), record.get("away_score")
        if home and away and hscore is not None and ascore is not None:
            opponents = f"{home}  {hscore} X {ascore}  {away}"
        channel = record.get("channel_title") or "Canal indisponível"
        broadcast = record.get("broadcast")
        if broadcast == "replay":
            signal = "REPRISE"
        elif broadcast == "live" and dt is not None:
            try:
                until = datetime.fromisoformat(record.get("end",""))
                signal = "AO VIVO · conforme EPG" if dt <= datetime.now().astimezone() < until else ""
            except (TypeError,ValueError):
                signal = ""
        else:
            signal = ""
        lines = [league.upper(),opponents,"Transmissão: "+(signal or date),
                 "Horário: "+time + "    ·    Canal: "+channel]
        if signal == "REPRISE":
            lines[2] = "REPRISE  ·  Transmissão: " + date
        return "\n".join(lines)

    def _add_many(self,rows):
        for r in rows:
            title = r.get("title","")
            if self.mode == "football" and r.get("kind") == "football":
                match_key = fixture_key(r)
                if self._sports_online_enabled():
                    r = {**r, **national_artwork(r), **self._football_updates.get(match_key, {})}
                item = self._add_result(self._football_label(r), r)
                card = FootballCardWidget(r, self.badge_loader,
                                          dark=getattr(self, "_theme_dark", True))
                self.results.setItemWidget(item, card)
                self._football_card_widgets[match_key] = card
                continue
            elif r.get("kind") == "football_channel":
                title = "CANAL ESPORTIVO  ·  " + title
            elif r.get("kind") == "series" and self.mode != "episodes":
                title += f"\n{r.get('episodes',0)} episódios" if r.get("episodes") else ""
            elif self.mode == "episodes" and r.get("season") is not None:
                title += f"\nT{r['season']:02d}  E{r['episode']:02d}"
            self._add_result(title,r)

    def _pulse_football_badge(self):
        if self.mode == "football":
            self._football_live_delegate.pulse_on = not self._football_live_delegate.pulse_on
            for card in self._football_card_widgets.values():
                card.set_pulse(self._football_live_delegate.pulse_on)
            self.results.viewport().update()

    def _start_score_updates(self):
        if (self.mode != "football" or self.playlist_id is None
                or not self.isVisible()
                or os.environ.get("QT_QPA_PLATFORM") == "offscreen"
                or os.environ.get("AURORA_SCORE_OFFLINE") == "1"
                or not self._sports_online_enabled()):
            return
        if self.score_thread is not None and self.score_thread.isRunning():
            return
        if time.monotonic() - self._score_last_started < 54:
            return
        records = [self.results.item(n).data(Qt.ItemDataRole.UserRole)
                   for n in range(min(self.results.count(),70))]
        records = [row for row in records if isinstance(row,dict)
                   and row.get("kind") == "football"]
        if not records:
            return
        self._score_last_started = time.monotonic()
        # Mark ageing scores as stale even if the refresh provider is offline.
        for card in self._football_card_widgets.values():
            card.update_record(card.row)
        thread = QThread(self)
        worker = ScoreWorker(self.playlist_id, records)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._scores_ready)
        worker.completed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._scores_done)
        self.score_thread, self.score_worker = thread, worker
        self._score_request_playlist = self.playlist_id
        thread.start()

    def _scores_ready(self, playlist_id, updates):
        if playlist_id != self.playlist_id:
            return  # Playlist changed while network requests were in flight.
        if not self._sports_online_enabled():
            return
        self._football_updates.update(updates)
        if self.mode != "football":
            return
        selected = self.results.currentRow()
        scroll = self.results.verticalScrollBar().value()
        for n in range(self.results.count()):
            item = self.results.item(n)
            row = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(row,dict) or row.get("kind") != "football":
                continue
            key = fixture_key(row)
            if key not in updates:
                continue
            row = {**row, **updates[key]}
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setText(self._football_label(row))
            card = self._football_card_widgets.get(key)
            if card is not None:
                card.update_record(row)
        self.results.setCurrentRow(selected)
        self.results.verticalScrollBar().setValue(scroll)

    def _scores_done(self):
        self.score_thread = None
        self.score_worker = None

    def _near_end(self,value):
        scrollbar = self.results.verticalScrollBar()
        if scrollbar.maximum() - value < 420 and self.mode in ("live","movie","series","football"):
            self._load_items()

    def _selected(self,current,previous=None):
        self.selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        row = self.selected
        usable = bool(row and row.get("kind") not in ("empty","playlist","football") and self.playlist_id is not None)
        self.favorite.setEnabled(usable)
        if usable:
            k,_,_ = self._favorite_key(row)
            self.favorite.setText("Remover favorito" if self.library.is_favorite(self.playlist_id,k) else "Favoritar")
        self._sync_favorite_controls()
        self.synopsis_button.setVisible(bool(row and row.get("kind") in ("movie","series")))

    def _remember_browse(self):
        if self.mode not in ("home","favorites","series","movie","football","live","episodes"):
            return
        self._browse_history.append({
            "mode":self.mode,
            "series_name":self.series_name,
            "category":self.selected_category,
            "search":self.search.text(),
            "scroll":self.results.verticalScrollBar().value(),
        })
        self._browse_history = self._browse_history[-20:]

    def _go_back(self):
        if self._video_fullscreen:
            self._leave_video_fullscreen()
        if not self._browse_history:
            # Playback stays in the same section: returning simply focuses
            # the browse list, preserving category, query and scroll.
            if self._video_fullscreen:
                self._leave_video_fullscreen()
            self.results.setFocus()
            return
        history=self._browse_history.pop()
        self.series_name=history["series_name"]
        self.navigate(history["mode"])
        if history["search"]:
            self.search.blockSignals(True)
            self.search.setText(history["search"])
            self.search.blockSignals(False)
        if history["category"] is not None:
            for n in range(self.groups.count()):
                item=self.groups.item(n)
                if item.data(Qt.ItemDataRole.UserRole)==history["category"]:
                    self.groups.setCurrentRow(n)
                    break
        else:
            self._load_items(reset=True)
        self._restore_result_scroll(history["scroll"])
        self.status.setText("Retornou à categoria anterior.")

    def _restore_result_scroll(self, position):
        # Incremental catalogs may need more results before restoring scroll.
        for _ in range(10):
            bar=self.results.verticalScrollBar()
            if bar.maximum() >= position or self._exhausted:
                break
            old=self.offset
            self._load_items()
            if self.offset == old:
                break
        self.results.verticalScrollBar().setValue(
            min(position,self.results.verticalScrollBar().maximum()))

    def _show_synopsis(self):
        row=(self.selected if self.selected and self.selected.get("kind") in ("movie","series")
             else self.playing if self.playing and self.playing.get("kind") in ("movie","series")
             else {})
        if row.get("kind") not in ("movie","series"):
            return
        text=(row.get("synopsis") or "").strip() or "Sinopse não disponível."
        dialog=QDialog(self)
        dialog.setWindowTitle("AURORA IPTV · Sinopse")
        dialog.resize(600,420)
        layout=QVBoxLayout(dialog)
        heading=QLabel(row.get("series_name") or row.get("title") or "Conteúdo")
        heading.setObjectName("heading")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        browser=QTextBrowser()
        browser.setPlainText(text)
        browser.setReadOnly(True)
        layout.addWidget(browser,1)
        close=QPushButton("Fechar")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def _open(self,widget):
        row = widget.data(Qt.ItemDataRole.UserRole)
        if row.get("kind") in ("empty","playlist"):
            return
        if row.get("kind") == "football_channel":
            self._start({**row,"kind":"live"})
            return
        if row.get("kind") == "football":
            if row.get("url"):
                self._start({**row,"kind":"live"})
            else:
                self.status.setText("O EPG não identificou um canal desta lista para o jogo selecionado.")
            return
        if row.get("kind") == "series" and self.mode not in ("episodes", "home"):
            self._remember_browse()
            self.series_name = row.get("series_name") or row["title"]
            self.mode = "episodes"
            self._refresh()
            return
        if self.mode == "favorites":
            item = self.library.item(self.playlist_id,row["key"][5:]) if row.get("key","").startswith("item:") else None
            if item:
                self._start(item)
            return
        self._start(row)

    def _main_action(self):
        if self.mode == "football":
            self._update_guide()
        else:
            super()._main_action()

    def _second_action(self):
        if self.mode == "football":
            self._configure_guide()
        else:
            super()._second_action()

    def _maybe_load_guide(self):
        pid = self.playlist_id
        if not pid or pid in self._auto_guide_attempted:
            return
        self._auto_guide_attempted.add(pid)
        epg = self.library.get_epg_url(pid)
        if not epg:
            source = next((p["source"] for p in self.library.playlists() if p["id"] == pid), "")
            epg = guess_xtream_epg(source)
            if epg:
                self.library.set_epg_url(pid, epg)
        if epg and not self.library.football_categories(pid):
            QTimer.singleShot(50, self._update_guide)

    def _start_index(self, playlist_id):
        if self.index_thread is not None:
            return
        thread = QThread(self)
        worker = IndexWorker(self.library.path, playlist_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._index_ok)
        worker.failed.connect(self._index_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._index_done)
        self.index_thread = thread
        self.index_worker = worker
        thread.start()

    def _index_ok(self, playlist_id):
        self._indexed.add(playlist_id)
        if self.playlist_id == playlist_id:
            self.status.setText("Catálogo organizado.")
            self._refresh()

    def _index_failed(self, playlist_id):
        self._index_error.add(playlist_id)
        self.status.setText("Não foi possível reorganizar o catálogo. Atualize a playlist.")

    def _index_done(self):
        self.index_thread = None
        self.index_worker = None
        if (self.playlist_id is not None and self.mode in ("live","movie","series")
                and self.playlist_id not in self._indexed
                and self.playlist_id not in self._index_error):
            self._refresh()

    def _configure_guide(self):
        if self.playlist_id is None:
            QMessageBox.information(self,"AURORA IPTV","Adicione uma playlist primeiro.")
            return
        current = self.library.get_epg_url(self.playlist_id)
        url,ok = QInputDialog.getText(self,"Guia Futebol","URL XMLTV (XML ou XML.GZ):",text=current)
        if ok:
            try:
                self.library.set_epg_url(self.playlist_id,url)
            except ValueError as exc:
                QMessageBox.warning(self,"EPG inválido",str(exc))
            else:
                self.status.setText("Guia configurado. Clique em Atualizar EPG Futebol.")

    def _update_guide(self):
        if self.playlist_id is None:
            return
        if self.guide_thread and self.guide_thread.isRunning():
            self.status.setText("O guia já está sendo atualizado.")
            return
        if not self.library.get_epg_url(self.playlist_id):
            self._configure_guide()
            if not self.library.get_epg_url(self.playlist_id):
                return
        thread = QThread(self)
        worker = GuideWorker(self.library.path,self.playlist_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._guide_ok)
        worker.failed.connect(self._guide_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._guide_done)
        self.guide_thread,self.guide_worker = thread,worker
        self.football_refresh.setEnabled(False)
        self.update_epg_button.setEnabled(False)
        self.football_refresh.setText("Atualizando...")
        self.update_epg_button.setText("Atualizando...")
        self.guide_busy.setVisible(self.mode == "football")
        self.status.setText("Lendo programação do guia XMLTV...")
        thread.start()

    def _guide_ok(self,count):
        self.status.setText(f"Guia atualizado: {count} partidas encontradas.")
        if self.mode == "football":
            category = self.selected_category
            search = self.search.text()
            position = self.results.verticalScrollBar().value()
            self._refresh()
            if search:
                self.search.blockSignals(True)
                self.search.setText(search)
                self.search.blockSignals(False)
            if category:
                for n in range(self.groups.count()):
                    if self.groups.item(n).data(Qt.ItemDataRole.UserRole) == category:
                        self.groups.setCurrentRow(n)
                        break
            self._load_items(reset=True)
            self._restore_result_scroll(position)
            QTimer.singleShot(800, self._start_score_updates)

    def _guide_failed(self,error):
        self.status.setText("Não foi possível atualizar a programação.")
        QMessageBox.warning(self,"Guia de futebol",error)

    def _guide_done(self):
        self.guide_thread = None
        self.guide_worker = None
        self.football_refresh.setEnabled(True)
        self.update_epg_button.setEnabled(True)
        self.guide_busy.hide()
        self.football_refresh.setText("Atualizar")
        self.update_epg_button.setText("Atualizar agenda de futebol")

    def _import_active(self):
        if self.thread is None or not self.thread.isRunning():
            self._import_target = self.playlist_id
        super()._import_active()

    def _import_ok(self,count):
        target = getattr(self, "_import_target", None)
        self._import_target = None
        if target is not None:
            self._indexed.add(target)
        super()._import_ok(count)

    def _import_failed(self,message):
        self._import_target = None
        super()._import_failed(message)

    def closeEvent(self,event):
        controller = getattr(self, "update_controller", None)
        if controller is not None:
            if controller.downloader is not None and controller.downloader.isRunning():
                controller.shutdown()
                self.status.setText("Cancelando download de atualização antes de sair...")
                event.ignore()
                return
            if controller.checker is not None and controller.checker.isRunning():
                self.status.setText("Aguarde a verificação de atualizações terminar.")
                event.ignore()
                return
        if self.index_thread and self.index_thread.isRunning():
            QMessageBox.information(self,"Catálogo","Aguarde a organização dos conteúdos.")
            event.ignore()
            return
        if self.guide_thread and self.guide_thread.isRunning():
            QMessageBox.information(self,"EPG em andamento","Aguarde a conclusão da atualização do guia.")
            event.ignore()
            return
        if self.score_thread is not None and self.score_thread.isRunning():
            self.status.setText("Consultando resultados esportivos; encerramento após a consulta.")
            event.ignore()
            return
        self._live_badge_timer.stop()
        self._score_timer.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AURORA IPTV")
    app.setOrganizationName("Aurora")
    icon = asset("aurora_icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow()
    from . import __version__
    from .update_ui import UpdateController
    window.setWindowTitle(f"AURORA IPTV | Desktop v{__version__}")
    window.update_controller = UpdateController(window)
    app.styleHints().colorSchemeChanged.connect(lambda _:window._theme_apply())
    # Version, update channel, manual check, theme and playlist operations
    # live in the Settings page. Automatic checks still run on startup.
    window.menuBar().hide()
    window.show()
    QTimer.singleShot(350, window.update_controller.show_previous_result)
    QTimer.singleShot(6000, lambda: window.update_controller.check(manual=False))
    return app.exec()
