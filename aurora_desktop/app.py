"""AURORA IPTV Desktop: Qt application for Windows and Linux."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, QSettings, QThread, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu,
    QMessageBox, QProgressDialog, QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget
)

from .core import Library

DARK = """
QWidget {background:#091522;color:#e8fbff;font:13px 'Segoe UI','Noto Sans',sans-serif;}
QMainWindow {background:#07111c;}
QFrame#sidebar {background:#0c2030;border-right:1px solid #245260;}
QFrame#panel {background:#0e2232;border:1px solid #204555;border-radius:14px;}
QLabel#brand {color:#74f4d8;font-size:23px;font-weight:800;}
QLabel#heading {font-size:21px;font-weight:700;}
QLabel#muted {color:#a2bcca;}
QPushButton {background:#193548;border:1px solid #2e5c66;border-radius:9px;padding:9px 12px;}
QPushButton:hover {background:#275a67;border-color:#68dfc5;}
QPushButton:checked,QPushButton#primary {color:#052a30;background:#6be8cb;font-weight:700;}
QComboBox,QLineEdit {background:#142d3e;border:1px solid #376272;border-radius:8px;padding:9px;}
QComboBox QAbstractItemView {background:#142d3e;color:white;}
QListWidget {background:#0e2232;border:1px solid #204555;border-radius:12px;padding:8px;}
QListWidget::item {padding:12px 10px;border-radius:8px;}
QListWidget::item:selected {background:#1f5b60;color:white;}
QListWidget::item:hover {background:#1a4654;}
QSlider::groove:horizontal {height:5px;background:#2d5060;}
QSlider::handle:horizontal {background:#70e8ce;width:13px;margin:-5px 0;border-radius:6px;}
"""
LIGHT = """
QWidget {background:#edf6f9;color:#102a3d;font:13px 'Segoe UI','Noto Sans',sans-serif;}
QMainWindow {background:#edf6f9;}
QFrame#sidebar {background:#d7ecee;border-right:1px solid #a3c7cb;}
QFrame#panel {background:white;border:1px solid #c6dfe3;border-radius:14px;}
QLabel#brand {color:#146a70;font-size:23px;font-weight:800;}
QLabel#heading {font-size:21px;font-weight:700;}
QLabel#muted {color:#55717e;}
QPushButton {background:#dcecef;border:1px solid #bfd7db;border-radius:9px;padding:9px 12px;}
QPushButton:hover {background:#bce7df;border-color:#469f99;}
QPushButton:checked,QPushButton#primary {color:white;background:#137777;font-weight:700;}
QComboBox,QLineEdit {background:white;border:1px solid #aacbd0;border-radius:8px;padding:9px;}
QComboBox QAbstractItemView {background:white;}
QListWidget {background:white;border:1px solid #c6dfe3;border-radius:12px;padding:8px;}
QListWidget::item {padding:12px 10px;border-radius:8px;}
QListWidget::item:selected {background:#c5ede8;color:#102a3d;}
QListWidget::item:hover {background:#e1f2ef;}
QSlider::groove:horizontal {height:5px;background:#c1d9db;}
QSlider::handle:horizontal {background:#137777;width:13px;margin:-5px 0;border-radius:6px;}
"""


def clock(milliseconds: int) -> str:
    seconds = max(0, int(milliseconds) // 1000)
    if seconds >= 3600:
        return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'
    return f'{seconds // 60:02d}:{seconds % 60:02d}'


class ImportWorker(QObject):
    finished = Signal(int)
    failed = Signal(str)

    def __init__(self, db_path: Path, playlist_id: int):
        super().__init__()
        self.db_path = db_path
        self.playlist_id = playlist_id

    @Slot()
    def run(self):
        try:
            total = Library(self.db_path).import_playlist(self.playlist_id)
        except Exception as exc:
            # Network errors may contain credentials in query strings. Never display them.
            message = str(exc)
            if 'http' in message.lower() or 'https' in message.lower():
                message = 'Falha na conexão ou autenticação da playlist.'
            self.failed.emit(message)
        else:
            self.finished.emit(total)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.library = Library()
        self.settings = QSettings('Aurora', 'AURORA IPTV Desktop')
        self.playlist_id = None
        self.playing_playlist = None
        self.playing = None
        self.selected = None
        self.mode = 'home'
        self.series_name = ''
        self.offset = 0
        self.pending_resume = 0
        self._completed_playback = False
        self.thread = None
        self.worker = None
        self.setWindowTitle('AURORA IPTV | Desktop')
        self.resize(1430, 840)
        self.setMinimumSize(920, 580)
        self._build()
        self._theme_apply()
        self._reload_playlists()
        self.navigate('home')
        self.autosave = QTimer(self)
        self.autosave.timeout.connect(self._save_progress)
        self.autosave.start(10_000)

    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(207)
        menu = QVBoxLayout(side)
        menu.setContentsMargins(15, 25, 15, 18)
        menu.setSpacing(10)
        brand = QLabel('✦ AURORA')
        brand.setObjectName('brand')
        menu.addWidget(brand)
        menu.addWidget(QLabel('IPTV · DESKTOP'))
        menu.addSpacing(22)
        self.nav = {}
        for key, name in [
            ('home', '⌂  Início'), ('live', '▣  Ao vivo'), ('movie', '▤  Filmes'),
            ('series', '▥  Séries'), ('favorites', '☆  Favoritos'),
            ('settings', '⚙  Configurações')
        ]:
            button = QPushButton(name)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, mode=key: self.navigate(mode))
            self.nav[key] = button
            menu.addWidget(button)
        menu.addStretch()
        muted = QLabel('AURORA IPTV · beta 0.1\nSem listas pré-instaladas')
        muted.setObjectName('muted')
        muted.setWordWrap(True)
        menu.addWidget(muted)
        layout.addWidget(side)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(14)
        top = QHBoxLayout()
        header = QLabel('Seu universo de entretenimento')
        header.setObjectName('heading')
        top.addWidget(header, 1)
        self.playlists = QComboBox()
        self.playlists.setMinimumWidth(200)
        self.playlists.currentIndexChanged.connect(self._on_playlist)
        top.addWidget(self.playlists)
        main.addLayout(top)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        main.addWidget(split, 1)
        catalog = QFrame()
        catalog.setObjectName('panel')
        c = QVBoxLayout(catalog)
        self.heading = QLabel('Início')
        self.heading.setObjectName('heading')
        c.addWidget(self.heading)
        self.subtitle = QLabel('')
        self.subtitle.setWordWrap(True)
        self.subtitle.setObjectName('muted')
        c.addWidget(self.subtitle)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Pesquisar no catálogo...')
        self.search.textChanged.connect(self._search)
        c.addWidget(self.search)
        self.results = QListWidget()
        self.results.currentItemChanged.connect(self._selected)
        self.results.itemDoubleClicked.connect(self._open)
        self.results.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.results.customContextMenuRequested.connect(self._context)
        c.addWidget(self.results, 1)
        row = QHBoxLayout()
        self.previous = QPushButton('← Voltar')
        self.previous.clicked.connect(self._prev)
        row.addWidget(self.previous)
        self.page = QLabel('')
        row.addWidget(self.page, 1, Qt.AlignmentFlag.AlignCenter)
        self.next = QPushButton('Próxima →')
        self.next.clicked.connect(self._next)
        row.addWidget(self.next)
        c.addLayout(row)
        self.action = QPushButton('Adicionar playlist')
        self.action.setObjectName('primary')
        self.action.clicked.connect(self._main_action)
        c.addWidget(self.action)
        self.second_action = QPushButton('Gerenciar playlists')
        self.second_action.clicked.connect(self._second_action)
        c.addWidget(self.second_action)
        self.theme_select = QComboBox()
        self.theme_select.addItem('Aparência: Conforme o sistema', 'system')
        self.theme_select.addItem('Aparência: Escuro', 'dark')
        self.theme_select.addItem('Aparência: Claro', 'light')
        self.theme_select.currentIndexChanged.connect(self._theme_changed)
        c.addWidget(self.theme_select)
        split.addWidget(catalog)

        pane = QFrame()
        pane.setObjectName('panel')
        p = QVBoxLayout(pane)
        self.now = QLabel('PRONTO PARA ASSISTIR')
        self.now.setObjectName('muted')
        p.addWidget(self.now)
        self.video_title = QLabel('AURORA IPTV')
        self.video_title.setObjectName('heading')
        self.video_title.setWordWrap(True)
        p.addWidget(self.video_title)
        self.video = QVideoWidget()
        self.video.setMinimumHeight(230)
        self.video.setStyleSheet('background:#020a11;')
        p.addWidget(self.video, 1)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(0.75)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.errorOccurred.connect(self._player_error)
        self.player.durationChanged.connect(self._duration)
        self.player.positionChanged.connect(self._position)
        self.player.mediaStatusChanged.connect(self._media_status)
        transport = QHBoxLayout()
        self.play = QPushButton('▶ Reproduzir')
        self.play.clicked.connect(self._toggle_play)
        transport.addWidget(self.play)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self.player.setPosition)
        transport.addWidget(self.seek, 1)
        self.time = QLabel('00:00 / 00:00')
        transport.addWidget(self.time)
        p.addLayout(transport)
        bottom = QHBoxLayout()
        self.favorite = QPushButton('☆ Favoritar')
        self.favorite.clicked.connect(self._favorite)
        bottom.addWidget(self.favorite)
        full = QPushButton('⛶ Tela cheia')
        full.clicked.connect(lambda: self.video.setFullScreen(not self.video.isFullScreen()))
        bottom.addWidget(full)
        bottom.addWidget(QLabel('Volume'))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setFixedWidth(94)
        volume.setRange(0, 100)
        volume.setValue(75)
        volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
        bottom.addWidget(volume)
        p.addLayout(bottom)
        self.status = QLabel('Cadastre uma playlist para começar.')
        self.status.setObjectName('muted')
        self.status.setWordWrap(True)
        p.addWidget(self.status)
        split.addWidget(pane)
        split.setSizes([440, 730])
        layout.addWidget(content, 1)
        QShortcut(QKeySequence('Space'), self, self._toggle_play)
        QShortcut(QKeySequence('Escape'), self, lambda: self.video.setFullScreen(False))

    def _theme_apply(self):
        choice = self.settings.value('theme', 'system')
        dark = choice == 'dark'
        if choice == 'system':
            dark = QApplication.instance().styleHints().colorScheme() != Qt.ColorScheme.Light
        QApplication.instance().setStyleSheet(DARK if dark else LIGHT)

    def _theme_changed(self):
        choice = self.theme_select.currentData()
        if choice:
            self.settings.setValue('theme', choice)
            self._theme_apply()

    def _reload_playlists(self, prefer=None):
        desired = self.playlist_id if prefer is None else prefer
        self.playlists.blockSignals(True)
        self.playlists.clear()
        for record in self.library.playlists():
            self.playlists.addItem(record['name'], record['id'])
        index = self.playlists.findData(desired)
        if index >= 0:
            self.playlists.setCurrentIndex(index)
        self.playlist_id = self.playlists.currentData()
        self.playlists.blockSignals(False)

    def _on_playlist(self):
        self._save_progress()
        self.playlist_id = self.playlists.currentData()
        self.navigate('home')

    def navigate(self, mode):
        self.mode = mode
        self.offset = 0
        if mode != 'episodes':
            self.series_name = ''
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        for key, button in self.nav.items():
            button.setChecked(key == mode)
        self._refresh()

    def _search(self):
        self.offset = 0
        self._refresh()

    def _add_result(self, label, record):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, record)
        self.results.addItem(item)

    def _refresh(self):
        titles = {
            'home': 'Continuar assistindo', 'live': 'Canais ao vivo',
            'movie': 'Filmes', 'series': 'Séries', 'episodes': self.series_name,
            'favorites': 'Meus favoritos', 'settings': 'Minhas playlists'
        }
        self.heading.setText(titles.get(self.mode, 'AURORA IPTV'))
        self.search.setVisible(self.mode not in ('settings', 'episodes'))
        self.results.blockSignals(True)
        self.results.clear()
        self.results.blockSignals(False)
        self.selected = None
        self.favorite.setEnabled(False)
        self.previous.setVisible(self.mode == 'episodes' or self.offset > 0)
        paging = self.mode in ('live', 'movie', 'series')
        self.next.setVisible(paging)
        self.page.setVisible(paging)
        self.theme_select.setVisible(self.mode == 'settings')
        self.second_action.setVisible(True)
        if self.mode == 'settings':
            self.subtitle.setText('Selecione uma lista. Clique com o botão direito para editar ou remover.')
            self.action.setText('＋ Adicionar URL M3U')
            self.second_action.setText('＋ Importar arquivo local')
            self.theme_select.blockSignals(True)
            self.theme_select.setCurrentIndex(max(0, self.theme_select.findData(self.settings.value('theme', 'system'))))
            self.theme_select.blockSignals(False)
            for row in self.library.playlists():
                self._add_result(row['name'] + '  ·  ' + str(row['updated_at'] or 'Não importada'), {'kind': 'playlist', **row})
        elif self.playlist_id is None:
            self.subtitle.setText('Nenhuma playlist cadastrada. Abra Configurações para adicionar.')
            self.action.setText('＋ Adicionar playlist')
            self.second_action.setVisible(False)
            self.next.setVisible(False)
        else:
            self.action.setText('↻ Atualizar playlist')
            self.second_action.setText('⚙ Gerenciar playlists')
            query = self.search.text().strip()
            if self.mode == 'home':
                rows = self.library.recent(self.playlist_id)
                self.subtitle.setText('Últimos conteúdos e posições de reprodução.')
            elif self.mode in ('live', 'movie'):
                rows = self.library.items(self.playlist_id, self.mode, query, 101, self.offset)
                self.subtitle.setText('Dê um duplo clique para reproduzir.')
            elif self.mode == 'series':
                rows = self.library.series(self.playlist_id, query, 101, self.offset)
                self.subtitle.setText('Abra a série para ver temporadas e episódios.')
            elif self.mode == 'episodes':
                rows = self.library.episodes(self.playlist_id, self.series_name)
                self.subtitle.setText('Favoritar um episódio salva a série inteira.')
            else:
                rows = self.library.favorites(self.playlist_id, query)
                self.subtitle.setText('Canais, filmes e séries que você favoritou.')
            more = paging and len(rows) > 100
            self.next.setEnabled(more)
            self.page.setText(f'Página {self.offset // 100 + 1}')
            for row in rows[:100] if paging else rows:
                title = row.get('title', '')
                if self.mode == 'series':
                    title += f" · {row['episodes']} episódios"
                elif row.get('kind') == 'series' and row.get('season') is not None:
                    title += f" · T{row['season']:02d} E{row['episode']:02d}"
                elif self.mode == 'home' and row.get('seconds'):
                    title += ' · ' + clock(row['seconds'] * 1000)
                self._add_result(title, row)
            if not rows:
                self._add_result('Nenhum conteúdo encontrado.', {'kind': 'empty'})
        if self.results.count():
            self.results.setCurrentRow(0)

    @staticmethod
    def _favorite_key(record):
        key = record.get('key', '')
        if key.startswith(('item:', 'series:')):
            return key, record.get('kind', 'movie'), record['title']
        if record.get('kind') == 'series':
            title = record.get('series_name') or record['title']
            return 'series:' + title.casefold(), 'series', title
        return 'item:' + key, record.get('kind', 'live'), record['title']

    def _selected(self, current, previous=None):
        self.selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        record = self.selected
        usable = bool(record and record.get('kind') not in ('empty', 'playlist'))
        self.favorite.setEnabled(usable and self.playlist_id is not None)
        if usable and self.playlist_id is not None:
            key, kind, title = self._favorite_key(record)
            self.favorite.setText('★ Remover favorito' if self.library.is_favorite(self.playlist_id, key) else '☆ Favoritar')

    def _favorite(self):
        if not self.selected or self.playlist_id is None:
            return
        key, kind, title = self._favorite_key(self.selected)
        enabled = self.library.is_favorite(self.playlist_id, key)
        self.library.set_favorite(self.playlist_id, key, kind, title, not enabled)
        self.favorite.setText('☆ Favoritar' if enabled else '★ Remover favorito')
        if self.mode == 'favorites':
            self._refresh()

    def _open(self, widget):
        record = widget.data(Qt.ItemDataRole.UserRole)
        if record.get('kind') in ('empty', 'playlist'):
            return
        if self.mode == 'series' or (self.mode == 'favorites' and record.get('kind') == 'series'):
            self.series_name = record.get('series_name') or record['title']
            self.mode = 'episodes'
            self._refresh()
            return
        if self.mode == 'favorites':
            key = record.get('key', '')
            if key.startswith('item:'):
                item = self.library.item(self.playlist_id, key[5:])
                if item is not None:
                    self._start(item)
                else:
                    self.status.setText('Conteúdo removido da playlist; atualize a lista.')
            return
        self._start(record)

    def _start(self, item):
        if not item.get('url'):
            return
        self._save_progress()
        self._completed_playback = False
        self.playing = item
        self.playing_playlist = self.playlist_id
        self.now.setText('REPRODUZINDO · ' + item.get('group_name', '').upper())
        self.video_title.setText(item['title'])
        self.pending_resume = self.library.get_progress(self.playlist_id, item['key']) * 1000 if item.get('kind') != 'live' else 0
        url = item['url']
        source = QUrl.fromLocalFile(url) if Path(url).is_absolute() and urlsplit(url).scheme not in ('http', 'https') else QUrl(url)
        self.player.setSource(source)
        self.player.play()
        self.play.setText('Ⅱ Pausar')
        self.status.setText('Reproduzindo · Espaço para pausar · ⛶ tela cheia.')

    def _toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self._save_progress()
            self.play.setText('▶ Reproduzir')
        elif self.playing:
            if self.player.mediaStatus() == QMediaPlayer.MediaStatus.EndOfMedia:
                self._completed_playback = False
                self.player.setPosition(0)
            self.player.play()
            self.play.setText('Ⅱ Pausar')
        elif self.selected and self.selected.get('url'):
            self._start(self.selected)

    def _duration(self, duration):
        self.seek.setRange(0, max(0, duration))
        if duration and self.pending_resume:
            position = self.pending_resume
            self.pending_resume = 0
            if position < duration * 0.95:
                self.player.setPosition(position)

    def _position(self, position):
        if not self.seek.isSliderDown():
            self.seek.setValue(position)
        self.time.setText(clock(position) + ' / ' + clock(self.player.duration()))

    def _media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._save_progress(completed=True)

    def _save_progress(self, completed=False):
        if (not self.playing or self.playing_playlist is None
                or self.playing.get('kind') == 'live' or self._completed_playback):
            return
        position = self.player.position()
        duration = self.player.duration()
        done = completed or (duration > 0 and position >= duration * 0.95)
        self.library.save_progress(self.playing_playlist, self.playing['key'], 0 if done else position // 1000)
        if done:
            self._completed_playback = True

    def _player_error(self, error, error_string):
        if error == QMediaPlayer.Error.NoError:
            return
        messages = {
            QMediaPlayer.Error.NetworkError: 'Falha de rede ao abrir a transmissão. Confira a conexão e o servidor.',
            QMediaPlayer.Error.FormatError: 'O formato ou codec não é compatível com o reprodutor instalado.',
            QMediaPlayer.Error.AccessDeniedError: 'A transmissão negou o acesso. Verifique permissões e autenticação.',
            QMediaPlayer.Error.ResourceError: 'Não foi possível abrir o endereço. O stream pode estar indisponível.',
        }
        self.status.setText(messages.get(error, 'Não foi possível reproduzir este conteúdo.'))
        self.play.setText('▶ Tentar novamente')

    def _prev(self):
        if self.mode == 'episodes':
            self.navigate('series')
        elif self.offset > 0:
            self.offset = max(0, self.offset - 100)
            self._refresh()

    def _next(self):
        self.offset += 100
        self._refresh()

    def _main_action(self):
        if self.mode == 'settings' or self.playlist_id is None:
            self._add_url()
        else:
            self._import_active()

    def _second_action(self):
        if self.mode == 'settings':
            path, _ = QFileDialog.getOpenFileName(self, 'Escolha uma playlist', '', 'Playlists (*.m3u *.m3u8);;Todos os arquivos (*)')
            if path:
                pid = self.library.add_playlist(Path(path).stem, path)
                self._reload_playlists(pid)
                self._import_active()
        else:
            self.navigate('settings')

    def _add_url(self):
        name, ok = QInputDialog.getText(self, 'Nova playlist', 'Nome:')
        if not ok or not name.strip():
            return
        source, ok = QInputDialog.getText(self, 'Nova playlist', 'URL HTTP/HTTPS M3U:')
        if not ok or not source.strip():
            return
        try:
            pid = self.library.add_playlist(name, source)
        except ValueError as exc:
            QMessageBox.warning(self, 'Dados inválidos', str(exc))
            return
        self._reload_playlists(pid)
        self._import_active()

    def _context(self, position):
        if self.mode != 'settings':
            return
        item = self.results.itemAt(position)
        if item is None:
            return
        row = item.data(Qt.ItemDataRole.UserRole)
        if row.get('kind') != 'playlist':
            return
        menu = QMenu(self)
        edit = menu.addAction('Editar nome e URL')
        activate = menu.addAction('Ativar esta playlist')
        delete = menu.addAction('Excluir esta playlist')
        picked = menu.exec(self.results.mapToGlobal(position))
        if picked is edit:
            name, ok = QInputDialog.getText(self, 'Editar playlist', 'Nome:', text=row['name'])
            if not ok:
                return
            source, ok = QInputDialog.getText(self, 'Editar playlist', 'URL:', text=row['source'])
            if not ok:
                return
            try:
                self.library.update_playlist(row['id'], name, source)
            except ValueError as exc:
                QMessageBox.warning(self, 'Dados inválidos', str(exc))
                return
            self._reload_playlists(row['id'])
            self._refresh()
        elif picked is activate:
            self._reload_playlists(row['id'])
            self.navigate('home')
        elif picked is delete:
            answer = QMessageBox.question(self, 'Excluir playlist', f"Excluir '{row['name']}' e seus favoritos locais?")
            if answer == QMessageBox.StandardButton.Yes:
                if self.playing_playlist == row['id']:
                    self._save_progress()
                    self.player.stop()
                    self.playing = None
                self.library.delete_playlist(row['id'])
                self._reload_playlists()
                self._refresh()

    def _import_active(self):
        if self.playlist_id is None:
            return
        if self.thread and self.thread.isRunning():
            self.status.setText('Uma playlist já está sendo importada.')
            return
        self.import_dialog = QProgressDialog('Importando playlist sem travar a interface...', '', 0, 0, self)
        self.import_dialog.setCancelButton(None)
        self.import_dialog.setWindowTitle('AURORA IPTV')
        self.import_dialog.setWindowModality(Qt.WindowModality.NonModal)
        self.import_dialog.show()
        thread = QThread(self)
        worker = ImportWorker(self.library.path, self.playlist_id)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._import_ok)
        worker.failed.connect(self._import_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._thread_done)
        self.thread, self.worker = thread, worker
        thread.start()

    def _import_ok(self, count):
        self.import_dialog.close()
        self.status.setText(f'Playlist atualizada: {count:,} entradas.'.replace(',', '.'))
        self._refresh()

    def _import_failed(self, message):
        self.import_dialog.close()
        QMessageBox.warning(self, 'Falha ao importar', message)

    def _thread_done(self):
        self.thread = None
        self.worker = None

    def closeEvent(self, event):
        self._save_progress()
        if self.thread and self.thread.isRunning():
            QMessageBox.information(self, 'Importação em andamento', 'Conclua a importação antes de sair.')
            event.ignore()
        else:
            self.player.stop()
            super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('AURORA IPTV')
    app.setOrganizationName('Aurora')
    window = MainWindow()
    app.styleHints().colorSchemeChanged.connect(lambda _: window._theme_apply())
    menu = window.menuBar().addMenu('Aparência')
    for key, title in [('dark', 'Escuro'), ('light', 'Claro'), ('system', 'Conforme o sistema')]:
        action = QAction(title, window)
        action.triggered.connect(lambda checked=False, choice=key: (window.settings.setValue('theme', choice), window._theme_apply()))
        menu.addAction(action)
    playlists = window.menuBar().addMenu('Playlists')
    playlists.addAction('Adicionar URL', window._add_url)
    playlists.addAction('Atualizar ativa', window._import_active)
    playlists.addAction('Gerenciar', lambda: window.navigate('settings'))
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
