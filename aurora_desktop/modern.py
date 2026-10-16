"""AURORA IPTV 0.2 desktop UI: groups, scrollable covers and XMLTV football."""
from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QSize, QTimer, QUrl, Signal, QObject, QThread
from PySide6.QtGui import QBrush, QColor, QFont, QGradient, QIcon, QLinearGradient, QPainter, QPixmap, QKeySequence, QShortcut
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget, QMenu,
)

from . import app as legacy
from .catalog import LibraryV2

# The original Qt player keeps the same settings, DB path, resuming and playlist management.
legacy.Library = LibraryV2


def asset(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return root / "assets" / name


class AuroraBanner(QFrame):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.setMaximumHeight(126)
        self._image = QPixmap(str(asset("aurora_banner.jpg")))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 14, 20, 14)
        title = QLabel("AURORA  /  IPTV")
        title.setStyleSheet("font-size:24px;font-weight:800;color:white;background:transparent;")
        subtitle = QLabel("SEU UNIVERSO DE ENTRETENIMENTO  ·  DESKTOP")
        subtitle.setStyleSheet("font-size:11px;letter-spacing:2px;color:#b5ffef;background:transparent;")
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self._image.isNull():
            scaled = self._image.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            p.drawPixmap(self.rect(), scaled, scaled.rect().adjusted(x,y,-x,-y))
        else:
            grad = QLinearGradient(0,0,self.width(),self.height())
            for pos,color in [(0,"#072537"),(.45,"#104c68"),(.78,"#32528a"),(1,"#21154b")]:
                grad.setColorAt(pos,QColor(color))
            p.fillRect(self.rect(),grad)
        overlay = QLinearGradient(0,0,self.width(),0)
        overlay.setColorAt(0,QColor(2,9,20,215))
        overlay.setColorAt(0.8,QColor(4,14,27,65))
        overlay.setColorAt(1,QColor(4,14,27,160))
        p.fillRect(self.rect(),overlay)


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
        self.blank = self.placeholder()

    def placeholder(self):
        p = QPixmap(72,86)
        p.fill(QColor("#18394b"))
        painter = QPainter(p)
        gradient = QLinearGradient(0,0,72,86)
        gradient.setColorAt(0,QColor("#134a65"))
        gradient.setColorAt(.55,QColor("#2a4172"))
        gradient.setColorAt(1,QColor("#1b1c45"))
        painter.fillRect(p.rect(),gradient)
        painter.setPen(QColor("#7dffde"))
        painter.setFont(QFont("Sans Serif",25,QFont.Weight.Bold))
        painter.drawText(p.rect(),Qt.AlignmentFlag.AlignCenter,"✦")
        painter.end()
        return QIcon(p)

    def reset(self):
        self.generation += 1
        self.queue.clear()

    def enqueue(self, item, url):
        item.setIcon(self.blank)
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


class MainWindow(legacy.MainWindow):
    """Reuses the tested player and incremental importer from 0.1.0."""

    def _build(self):
        root = QWidget(self)
        self.setCentralWidget(root)
        base = QHBoxLayout(root)
        base.setSpacing(0)
        base.setContentsMargins(0,0,0,0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(206)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(13,18,13,18)
        side.setSpacing(9)
        logo = QLabel()
        icon = QPixmap(str(asset("aurora_icon.png")))
        if not icon.isNull():
            logo.setPixmap(icon.scaled(84,84,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("✦")
            logo.setStyleSheet("font-size:40px;color:#77f4d6;")
        logo.setAlignment(Qt.AlignmentFlag.AlignLeft)
        side.addWidget(logo)
        brand = QLabel("AURORA IPTV")
        brand.setObjectName("brand")
        side.addWidget(brand)
        side.addWidget(QLabel("DESKTOP  ·  v0.2.0"))
        side.addSpacing(18)
        self.nav = {}
        for mode,title in [
            ("home","⌂  Início"),("live","▣  Ao vivo"),("movie","▤  Filmes"),
            ("series","▥  Séries"),("football","⚽  Futebol"),
            ("favorites","☆  Favoritos"),("settings","⚙  Configurações")
        ]:
            button = QPushButton(title)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False,m=mode:self.navigate(m))
            self.nav[mode] = button
            side.addWidget(button)
        side.addStretch()
        side.addWidget(QLabel("✧ Luzes da aurora, o seu conteúdo."))
        base.addWidget(sidebar)

        shell = QWidget()
        outer = QVBoxLayout(shell)
        outer.setContentsMargins(13,13,13,13)
        outer.setSpacing(12)
        upper = QHBoxLayout()
        upper.addWidget(AuroraBanner(),1)
        tool = QVBoxLayout()
        tool.addWidget(QLabel("LISTA ATIVA"))
        self.playlists = QComboBox()
        self.playlists.setMinimumWidth(210)
        self.playlists.currentIndexChanged.connect(self._on_playlist)
        tool.addWidget(self.playlists)
        tool.addStretch()
        upper.addLayout(tool)
        outer.addLayout(upper)

        panels = QSplitter(Qt.Orientation.Horizontal)
        panels.setChildrenCollapsible(False)
        outer.addWidget(panels,1)

        categories_panel = QFrame()
        categories_panel.setObjectName("panel")
        group_layout = QVBoxLayout(categories_panel)
        self.groups_title = QLabel("CLASSIFICAÇÃO")
        self.groups_title.setObjectName("heading")
        group_layout.addWidget(self.groups_title)
        self.groups_hint = QLabel("Categorias da lista")
        self.groups_hint.setObjectName("muted")
        self.groups_hint.setWordWrap(True)
        group_layout.addWidget(self.groups_hint)
        self.groups = QListWidget()
        self.groups.setObjectName("groups")
        self.groups.currentItemChanged.connect(self._change_category)
        group_layout.addWidget(self.groups,1)
        panels.addWidget(categories_panel)

        contents_panel = QFrame()
        contents_panel.setObjectName("panel")
        content_layout = QVBoxLayout(contents_panel)
        self.heading = QLabel("Explorar")
        self.heading.setObjectName("heading")
        content_layout.addWidget(self.heading)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        self.subtitle.setWordWrap(True)
        content_layout.addWidget(self.subtitle)
        self.search = QLineEdit()
        self.search.setPlaceholderText("⌕  Buscar em todo o conteúdo...")
        self.search.textChanged.connect(self._search)
        content_layout.addWidget(self.search)
        self.results = QListWidget()
        self.results.setIconSize(QSize(72,86))
        self.results.setUniformItemSizes(True)
        self.results.setSpacing(5)
        self.results.setWordWrap(True)
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
        play_layout = QVBoxLayout(player_panel)
        self.now = QLabel("AURORA  ·  PRONTO PARA ASSISTIR")
        self.now.setObjectName("muted")
        play_layout.addWidget(self.now)
        self.video_title = QLabel("Escolha um conteúdo")
        self.video_title.setWordWrap(True)
        self.video_title.setObjectName("heading")
        play_layout.addWidget(self.video_title)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(200)
        self.video.setStyleSheet("background:#030b13;")
        play_layout.addWidget(self.video,1)
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
        controls.addWidget(self.time)
        play_layout.addLayout(controls)
        actions = QHBoxLayout()
        self.favorite = QPushButton("☆ Favoritar")
        self.favorite.clicked.connect(self._favorite)
        actions.addWidget(self.favorite)
        fullscreen = QPushButton("⛶ Tela cheia")
        fullscreen.clicked.connect(lambda:self.video.setFullScreen(not self.video.isFullScreen()))
        actions.addWidget(fullscreen)
        actions.addWidget(QLabel("Volume"))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0,100)
        volume.setValue(75)
        volume.setMaximumWidth(110)
        volume.valueChanged.connect(lambda v:self.audio.setVolume(v/100))
        actions.addWidget(volume)
        play_layout.addLayout(actions)
        self.status = QLabel("Selecione sua playlist para começar.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        play_layout.addWidget(self.status)
        panels.addWidget(player_panel)
        panels.setSizes([225,420,680])
        base.addWidget(shell,1)

        QShortcut(QKeySequence("Space"),self,self._toggle_play)
        QShortcut(QKeySequence("Escape"),self,lambda:self.video.setFullScreen(False))
        self.selected_category = None
        self._loading_items = False
        self._exhausted = False
        self._indexed = set()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(240)
        self._search_timer.timeout.connect(self._refresh)
        self.guide_thread = None
        self.setMinimumSize(1070,620)
        self.resize(1550,860)

    def _theme_apply(self):
        super()._theme_apply()
        dark = self.settings.value("theme","system") == "dark"
        if self.settings.value("theme","system") == "system":
            dark = QApplication.instance().styleHints().colorScheme() != Qt.ColorScheme.Light
        extra = """
            QFrame#panel { border-radius:14px; }
            QLabel#heading { font-size:17px; font-weight:800; }
            QListWidget#groups::item {padding:13px 8px;}
            QListWidget#groups::item:selected {border-left:3px solid #58e4cc;}
            QLineEdit {min-height:18px;}
        """
        QApplication.instance().setStyleSheet(QApplication.instance().styleSheet() + extra)

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
            "favorites":"Favoritos", "settings":"Minhas playlists",
            "football":"Agenda de futebol",
        }
        self.heading.setText(titles.get(self.mode,"AURORA IPTV"))
        self.groups_title.setText("CLASSIFICAÇÃO" if self.mode != "football" else "CAMPEONATOS")
        self.groups_hint.setText("Selecione um grupo para filtrar" if self.mode not in ("home","settings") else "Navegue pela sua biblioteca")
        self.search.setVisible(self.mode not in ("settings","episodes"))
        self.previous.setVisible(self.mode == "episodes")
        self.theme_select.setVisible(self.mode == "settings")
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
            self.subtitle.setText("Clique com o botão direito para editar ou excluir listas. A atualização preserva seus dados.")
        elif self.mode == "football":
            self.subtitle.setText("Partidas e horários do guia XMLTV da playlist. Sem partidas fictícias.")
        elif self.mode == "series":
            self.subtitle.setText("Grupos e plataformas identificados na própria lista M3U.")
        else:
            self.subtitle.setText("Escolha uma categoria; a lista carrega conforme você rola.")
        if self.playlist_id is not None and self.mode in ("live","movie","series") and self.playlist_id not in self._indexed:
            # First start after update indexes old catalog in place without erasing favorites.
            self.status.setText("Organizando categorias da playlist existente...")
            QApplication.processEvents()
            self.library.ensure_categories(self.playlist_id)
            self._indexed.add(self.playlist_id)
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
            self.groups.addItem(item)
        self.groups.setCurrentRow(0)
        self.groups.blockSignals(False)
        self._load_items(reset=True)

    def _add_result(self,label,record):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole,record)
        item.setSizeHint(QSize(0,104))
        self.results.addItem(item)
        self.covers.enqueue(item,record.get("logo",""))
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
                    rows = self.library.football(self.playlist_id,self.selected_category,query,limit=61,offset=self.offset)
                else:
                    rows = self.library.browse(self.playlist_id,self.mode,self.selected_category,query,limit=61,offset=self.offset)
                self._exhausted = len(rows) <= 60
                self._add_many(rows[:60])
                self.offset += min(len(rows),60)
                self.page.setText(f"{self.offset:,} itens carregados · role para ver mais".replace(",","." ))
            if not self.results.count():
                self.page.setText("Nenhum conteúdo nesta categoria.")
        finally:
            self._loading_items = False

    def _add_many(self,rows):
        for r in rows:
            title = r.get("title","")
            if self.mode == "football":
                try:
                    dt = datetime.fromisoformat(r["start"]).strftime("%d/%m · %H:%M")
                except (KeyError,ValueError):
                    dt = "Horário indisponível"
                title = f"{dt}\n{title}\n{r.get('channel_title') or 'Canal sem correspondência'}"
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
            self.favorite.setText("★ Remover favorito" if self.library.is_favorite(self.playlist_id,k) else "☆ Favoritar")

    def _open(self,widget):
        row = widget.data(Qt.ItemDataRole.UserRole)
        if row.get("kind") in ("empty","playlist"):
            return
        if row.get("kind") == "football":
            if row.get("url"):
                self._start({**row,"kind":"live"})
            else:
                self.status.setText("O EPG não identificou um canal desta lista para o jogo selecionado.")
            return
        if row.get("kind") == "series" and self.mode != "episodes":
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

    def _import_ok(self,count):
        super()._import_ok(count)
        if self.playlist_id is not None:
            self._indexed.add(self.playlist_id)
        self._refresh()

    def closeEvent(self,event):
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
    app.styleHints().colorSchemeChanged.connect(lambda _:window._theme_apply())
    appearance = window.menuBar().addMenu("Aparência")
    for label,value in [("Escuro","dark"),("Claro","light"),("Conforme sistema","system")]:
        action = appearance.addAction(label)
        action.triggered.connect(lambda checked=False,k=value:(window.settings.setValue("theme",k),window._theme_apply()))
    playlist_menu = window.menuBar().addMenu("Playlists")
    playlist_menu.addAction("Adicionar M3U",window._add_url)
    playlist_menu.addAction("Atualizar lista",window._import_active)
    playlist_menu.addAction("Configurações",lambda:window.navigate("settings"))
    window.show()
    return app.exec()
