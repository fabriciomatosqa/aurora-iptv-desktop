"""AURORA IPTV Desktop: responsive aurora-themed player and library."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QSize, QRectF, QTimer, QUrl, Signal, QObject, QThread
from PySide6.QtGui import QBrush, QColor, QFont, QGradient, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QKeySequence, QShortcut
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSlider, QSplitter, QStackedWidget, QVBoxLayout, QWidget, QMenu,
)

from . import app as legacy
from .catalog import LibraryV2, guess_xtream_epg
from .ui_icons import icon_for

# The original Qt player keeps the same settings, DB path, resuming and playlist management.
legacy.Library = LibraryV2


def asset(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "assets" / name


class AuroraBanner(QFrame):
    """A full-width, image-backed hero instead of an isolated picture tile.

    The source image is always center-cropped (never stretched), clipped to a
    rounded outline, then blended into the dark AURORA shell. Text stays part
    of the layout so it remains accessible and responsive.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("auroraHero")
        self.setMinimumHeight(156)
        self.setMaximumHeight(182)
        self._image = QPixmap(str(asset("aurora_banner.jpg")))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(29, 17, 26, 18)
        layout.setSpacing(5)

        overline = QHBoxLayout()
        overline.setSpacing(9)
        badge = QLabel("✦  AURORA EXPERIENCE")
        badge.setObjectName("heroBadge")
        overline.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)
        overline.addStretch(1)
        from . import __version__
        version = QLabel(f"DESKTOP  /  v{__version__}")
        version.setObjectName("heroVersion")
        overline.addWidget(version, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(overline)
        layout.addStretch(1)

        title = QLabel("AURORA  /  IPTV")
        title.setObjectName("heroTitle")
        layout.addWidget(title)
        subtitle = QLabel("SEU UNIVERSO DE ENTRETENIMENTO")
        subtitle.setObjectName("heroSubtitle")
        layout.addWidget(subtitle)
        footnote = QLabel("CANAIS AO VIVO    ·    FILMES    ·    SÉRIES    ·    FUTEBOL")
        footnote.setObjectName("heroFootnote")
        layout.addWidget(footnote)
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
            # KeepAspectRatioByExpanding, but crop from the source directly:
            # this avoids the old distorted drawPixmap source rectangle.
            img_w, img_h = self._image.width(), self._image.height()
            source_aspect = img_w / img_h
            target_aspect = w / h
            if source_aspect > target_aspect:
                crop_width = img_h * target_aspect
                left = (img_w - crop_width) / 2
                source = QRectF(left, 0, crop_width, img_h)
            else:
                crop_height = img_w / target_aspect
                top = (img_h - crop_height) * 0.48
                source = QRectF(0, top, img_w, crop_height)
            p.drawPixmap(frame, self._image, source)
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
        overlay.setColorAt(0, QColor(4, 16, 32, 242))
        overlay.setColorAt(.30, QColor(5, 22, 40, 193))
        overlay.setColorAt(.62, QColor(6, 24, 42, 32))
        overlay.setColorAt(1, QColor(6, 22, 39, 100))
        p.fillRect(self.rect(), overlay)
        lower = QLinearGradient(0, 0, 0, h)
        lower.setColorAt(0, QColor(5, 19, 34, 55))
        lower.setColorAt(.67, QColor(5, 19, 34, 0))
        lower.setColorAt(1, QColor(7, 22, 36, 180))
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
        symbol = icon_for(kind, 45).pixmap(QSize(45, 45))
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
        base = QHBoxLayout(root)
        base.setSpacing(0)
        base.setContentsMargins(0,0,0,0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(226)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18,22,18,20)
        side.setSpacing(10)
        logo = QLabel()
        icon = QPixmap(str(asset("aurora_icon.png")))
        if not icon.isNull():
            logo.setPixmap(icon.scaled(78,78,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("✦")
            logo.setStyleSheet("font-size:40px;color:#77f4d6;")
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft)
        side.addWidget(logo)
        brand = QLabel("AURORA IPTV")
        brand.setObjectName("brand")
        side.addWidget(brand)
        from . import __version__
        version = QLabel(f"DESKTOP  ·  v{__version__}")
        version.setObjectName("versionTag")
        side.addWidget(version)
        side.addSpacing(18)
        self.nav = {}
        for mode,title in [
            ("home","Início"),("live","Ao vivo"),("movie","Filmes"),
            ("series","Séries"),("football","Futebol"),
            ("favorites","Favoritos"),("settings","Configurações")
        ]:
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setIcon(icon_for(mode))
            button.setIconSize(QSize(24,24))
            button.setMinimumHeight(48)
            button.setCheckable(True)
            button.setToolTip(title)
            button.clicked.connect(lambda checked=False,m=mode:self.navigate(m))
            self.nav[mode] = button
            side.addWidget(button)
        side.addStretch()
        footer = QLabel("✦  Luzes da aurora, seu universo.")
        footer.setObjectName("sidebarFooter")
        footer.setWordWrap(True)
        side.addWidget(footer)
        base.addWidget(sidebar)
        self.sidebar = sidebar

        shell = QWidget()
        shell.setObjectName("contentShell")
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(16,15,16,15)
        outer.setSpacing(14)
        self.outer_layout = outer
        self.header_widget = QWidget(shell)
        self.header_widget.setObjectName("mainHeader")
        upper = QHBoxLayout(self.header_widget)
        upper.setContentsMargins(0,0,0,0)
        upper.setSpacing(0)
        self.banner = AuroraBanner(self.header_widget)
        upper.addWidget(self.banner, 1)
        outer.addWidget(self.header_widget)

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
        self.heading = QLabel("Explorar")
        self.heading.setObjectName("heading")
        content_layout.addWidget(self.heading)
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
        content_layout.addWidget(self.playlist_settings)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar canais, filmes, séries...")
        self.search.textChanged.connect(self._search)
        content_layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setObjectName("results")
        self.results.setIconSize(QSize(70,88))
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
        self.previous = QPushButton("← Voltar às séries")
        self.previous.clicked.connect(lambda:self.navigate("series"))
        content_layout.addWidget(self.previous)
        self.next = QPushButton()
        self.next.hide()
        self.action = QPushButton("↻ Atualizar lista")
        self.action.setObjectName("primary")
        self.action.clicked.connect(self._main_action)
        content_layout.addWidget(self.action)
        self.second_action = QPushButton("⚙ Configurações")
        self.second_action.clicked.connect(self._second_action)
        content_layout.addWidget(self.second_action)
        self.theme_select = QComboBox()
        for label,value in [
            ("Aparência: Conforme o sistema","system"),
            ("Aparência: Escuro","dark"),
            ("Aparência: Claro","light")
        ]:
            self.theme_select.addItem(label,value)
        self.theme_select.currentIndexChanged.connect(self._theme_changed)
        content_layout.addWidget(self.theme_select)
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
        controls = QHBoxLayout()
        self.play = QPushButton("▶ Reproduzir")
        self.play.clicked.connect(self._toggle_play)
        controls.addWidget(self.play)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.seek.setRange(0,0)
        controls.addWidget(self.seek,1)
        self.time = QLabel("00:00 / 00:00")
        self.time.setObjectName("playerTime")
        controls.addWidget(self.time)
        play_layout.addLayout(controls)
        actions = QHBoxLayout()
        self.favorite = QPushButton("Favoritar")
        self.favorite.setIcon(icon_for("favorites"))
        self.favorite.setIconSize(QSize(21,21))
        self.favorite.clicked.connect(self._favorite)
        actions.addWidget(self.favorite)
        self.fullscreen_button = QPushButton("⛶ Tela cheia")
        self.fullscreen_button.clicked.connect(self._toggle_video_fullscreen)
        self.fullscreen_button.setToolTip("Tela cheia (F11) · sair com Esc")
        actions.addWidget(self.fullscreen_button)
        actions.addWidget(QLabel("Volume"))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0,100)
        volume.setValue(75)
        volume.setMaximumWidth(110)
        volume.valueChanged.connect(lambda v:self.audio.setVolume(v/100))
        actions.addWidget(volume)
        play_layout.addLayout(actions)
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
        self.selected_category = None
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
        self.setMinimumSize(1150,680)
        self.resize(1580,900)

    def _toggle_video_fullscreen(self):
        """Enlarge the existing video SURFACE without QVideoWidget.setFullScreen().

        Qt's native video window may freeze on Windows and some Linux compositors
        when QVideoWidget is independently promoted to a fullscreen window. We
        fullscreen the MAIN window instead and never reparent/rebind the player.
        """
        if self._video_fullscreen:
            self._leave_video_fullscreen()
            return
        self._video_fullscreen = True
        self._fullscreen_was_maximized = self.isMaximized()
        self._saved_panel_sizes = self.panels.sizes()
        self._saved_minimum_size = self.minimumSize()
        self.setMinimumSize(0, 0)
        self.sidebar.hide()
        self.header_widget.hide()
        self.categories_panel.hide()
        self.contents_panel.hide()
        self.now.hide()
        self.video_title.hide()
        self.status.hide()
        self.menuBar().hide()
        self.outer_layout.setContentsMargins(0,0,0,0)
        self.fullscreen_button.setText("⤢ Sair da tela cheia")
        self.fullscreen_button.setToolTip("Voltar à janela (Esc ou F11)")
        self.showFullScreen()
        self.video.setFocus(Qt.FocusReason.OtherFocusReason)

    def _leave_video_fullscreen(self):
        if not self._video_fullscreen:
            return
        self._video_fullscreen = False
        self.showNormal()
        if self._fullscreen_was_maximized:
            self.showMaximized()
        if self._saved_minimum_size is not None:
            self.setMinimumSize(self._saved_minimum_size)
        self.sidebar.show()
        self.header_widget.show()
        self.categories_panel.show()
        self.contents_panel.show()
        self.now.show()
        self.video_title.show()
        self.status.show()
        self.menuBar().show()
        self.outer_layout.setContentsMargins(16,15,16,15)
        if self._saved_panel_sizes:
            self.panels.setSizes(self._saved_panel_sizes)
        self.fullscreen_button.setText("⛶ Tela cheia")
        self.fullscreen_button.setToolTip("Tela cheia (F11) · sair com Esc")
        self.video.setFocus(Qt.FocusReason.OtherFocusReason)

    def _start(self, item):
        if item.get("url"):
            self.video_stage.setCurrentWidget(self.video)
        super()._start(item)
        if item.get("url"):
            self.video.setFocus()

    def _toggle_play(self):
        if self.playing:
            self.video_stage.setCurrentWidget(self.video)
        super()._toggle_play()

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
            QLabel#sidebarFooter {{
                font-size:11px;color:{muted};padding:9px 3px;
                border-top:1px solid {border};
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
                padding:9px 13px 9px 16px;
                background:{inner};
                border:1px solid transparent;
                border-radius:11px;
                font-size:14px;font-weight:650;
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
            QToolTip {{
                color:{text};background:{menu};
                border:1px solid {accent};padding:5px;
            }}
        """)
        # Icons are drawn at 3x resolution; gold is reserved for favorites.
        for name, button in self.nav.items():
            button.setIcon(icon_for(name, 24, light=not dark))
        self.favorite.setIcon(icon_for("favorites", 22, light=not dark))

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

    def _search(self):
        self._search_timer.start()

    def _change_category(self, current, previous):
        if not current:
            return
        self.selected_category = current.data(Qt.ItemDataRole.UserRole)
        self.offset = 0
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
        self.previous.setVisible(self.mode == "episodes")
        self.theme_select.setVisible(self.mode == "settings")
        self.playlist_settings.setVisible(self.mode == "settings")
        self.theme_select.blockSignals(True)
        self.theme_select.setCurrentIndex(max(0,self.theme_select.findData(self.settings.value("theme","system"))))
        self.theme_select.blockSignals(False)
        self.covers.reset()
        self.groups.blockSignals(True)
        self.groups.clear()
        self.groups.blockSignals(False)
        self.selected_category = None
        self.offset = 0
        self.action.setText("＋ Adicionar URL M3U" if self.mode == "settings" or self.playlist_id is None
                            else "↻ Atualizar EPG Futebol" if self.mode == "football"
                            else "↻ Atualizar playlist")
        self.second_action.setText("＋ Importar arquivo local" if self.mode == "settings"
                                   else "⚙ Configurar EPG" if self.mode == "football"
                                   else "⚙ Gerenciar playlists")
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
            choices = [("Listas de reprodução",None),("Guia Futebol", "guide")]
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
        self._load_items(reset=True)

    def _add_result(self,label,record):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole,record)
        item.setSizeHint(QSize(0,106))
        item.setToolTip(label.replace("\n", " — "))
        self.results.addItem(item)
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
                if self.selected_category == "guide":
                    url = self.library.get_epg_url(self.playlist_id) if self.playlist_id else ""
                    self._add_result("Guia configurado" if url else "Guia XMLTV ainda não configurado",{"kind":"empty"})
                    self.page.setText("Use ⚙ Configurar EPG na guia Futebol.")
                else:
                    for r in self.library.playlists():
                        self._add_result(r["name"] + ("  ✓" if r["id"] == self.playlist_id else ""),{"kind":"playlist",**r})
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
                    rows = self.library.football(self.playlist_id,None if query else self.selected_category,query,limit=61,offset=self.offset)
                    # Fallback to real sports channels when XMLTV gives no events.
                    if not rows and not self.library.football_categories(self.playlist_id):
                        rows = self.library.sport_channels(self.playlist_id,query,limit=160)
                        self._exhausted = True
                        self.page.setText("Canais esportivos · configure o EPG para visualizar os jogos")
                    else:
                        self._exhausted = len(rows) <= 60
                else:
                    rows = self.library.browse(self.playlist_id,self.mode,None if query else self.selected_category,query,limit=61,offset=self.offset)
                    self._exhausted = len(rows) <= 60
                self._add_many(rows[:60] if not self._exhausted else rows)
                self.offset += min(len(rows),60)
                if self.mode != "football" or self.library.football_categories(self.playlist_id):
                    self.page.setText(f"{self.offset:,} conteúdos · role para explorar".replace(",", "."))
            if not self.results.count():
                self.page.setText("Nenhum conteúdo nesta categoria.")
        finally:
            self._loading_items = False

    def _add_many(self,rows):
        for r in rows:
            title = r.get("title","")
            if self.mode == "football" and r.get("kind") == "football":
                try:
                    dt = datetime.fromisoformat(r["start"]).strftime("%d/%m · %H:%M")
                except (KeyError,ValueError):
                    dt = "Horário indisponível"
                status = "  •  REPRISE" if r.get("broadcast") == "replay" else "  •  AO VIVO" if r.get("broadcast") == "live" else ""
                title = f"{dt}{status}\n{title}\n{r.get('competition','Jogos')} · {r.get('channel_title') or 'Canal sem correspondência'}"
            elif r.get("kind") == "football_channel":
                title = "CANAL ESPORTIVO  ·  " + title
            elif r.get("kind") == "series" and self.mode != "episodes":
                title += f"\n{r.get('episodes',0)} episódios" if r.get("episodes") else ""
            elif self.mode == "episodes" and r.get("season") is not None:
                title += f"\nT{r['season']:02d}  E{r['episode']:02d}"
            self._add_result(title,r)

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
        self.status.setText("Lendo programação do guia XMLTV...")
        thread.start()

    def _guide_ok(self,count):
        self.status.setText(f"Guia atualizado: {count} partidas encontradas.")
        if self.mode == "football":
            self._refresh()

    def _guide_failed(self,error):
        self.status.setText("Não foi possível atualizar a programação.")
        QMessageBox.warning(self,"Guia de futebol",error)

    def _guide_done(self):
        self.guide_thread = None
        self.guide_worker = None

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
    appearance = window.menuBar().addMenu("Aparência")
    for label,value in [("Escuro","dark"),("Claro","light"),("Conforme sistema","system")]:
        action = appearance.addAction(label)
        action.triggered.connect(lambda checked=False,k=value:(window.settings.setValue("theme",k),window._theme_apply()))
    playlist_menu = window.menuBar().addMenu("Playlists")
    playlist_menu.addAction("Adicionar M3U",window._add_url)
    playlist_menu.addAction("Atualizar lista",window._import_active)
    playlist_menu.addAction("Configurações",lambda:window.navigate("settings"))
    window.update_controller.attach_menu(window.menuBar())
    window.show()
    QTimer.singleShot(350, window.update_controller.show_previous_result)
    QTimer.singleShot(6000, lambda: window.update_controller.check(manual=False))
    return app.exec()
