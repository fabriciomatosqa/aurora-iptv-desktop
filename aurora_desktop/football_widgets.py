"""Real football match cards for Qt Widgets, with bounded asynchronous badges."""
from __future__ import annotations

from collections import deque
from datetime import datetime
import time
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .sports_data import safe_artwork
from .svg_icons import svg_icon_for


class BadgeLoader:
    """Fetch only allowlisted HTTPS badge URLs; no request contains playlist data."""
    def __init__(self, parent: QWidget):
        self.network = QNetworkAccessManager(parent)
        self.cache: dict[str, QPixmap] = {}
        self.pending: dict[str, list[QLabel]] = {}
        self.queue = deque()
        self.active = 0
        self.failed = set()

    def attach(self, label: QLabel, url: str):
        url = safe_artwork(url)
        if not url:
            return
        if url in self.cache:
            self._apply(label, self.cache[url])
        elif url not in self.failed:
            if url in self.pending:
                self.pending[url].append(label)
            elif len(self.queue) < 140:
                self.pending[url] = [label]
                self.queue.append(url)
                self._dispatch()

    @staticmethod
    def _apply(label: QLabel, pixmap: QPixmap):
        try:
            if pixmap.isNull():
                return
            image = pixmap.scaled(label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(image)
        except RuntimeError:
            pass  # Card was destroyed or rebuilt while the network request ran.

    def _dispatch(self):
        while self.active < 4 and self.queue:
            url = self.queue.popleft()
            req = QNetworkRequest(QUrl(url))
            req.setTransferTimeout(8_000)
            self.active += 1
            response = self.network.get(req)
            response.finished.connect(lambda r=response, u=url: self._done(r, u))

    def _done(self, response, url: str):
        self.active -= 1
        try:
            body = bytes(response.readAll())
            if response.error() or not body or len(body) > 1_000_000:
                self.failed.add(url)
                return
            pixmap = QPixmap()
            if not pixmap.loadFromData(body) or pixmap.isNull():
                self.failed.add(url)
                return
            self.cache[url] = pixmap
            if len(self.cache) > 170:
                self.cache.pop(next(iter(self.cache)))
            for label in self.pending.get(url, []):
                self._apply(label, pixmap)
        finally:
            self.pending.pop(url, None)
            response.deleteLater()
            self._dispatch()


def _text(label: QLabel, text: str):
    label.setText(text)
    label.setWordWrap(True)
    return label


class FootballCardWidget(QFrame):
    """A match card with three independent emblems, score and broadcast info.

    Transparent to clicks so QListWidget keeps selection and double-click.
    """
    def __init__(self, row: dict, badge_loader: BadgeLoader, *, dark: bool = True):
        super().__init__()
        self.setObjectName("footballCard")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.loader = badge_loader
        self.dark = dark
        self._badge_urls: dict[str, str] = {}
        self._pulse_on = True
        self._live = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(13, 9, 13, 9)
        outer.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.league_icon = QLabel()
        self.league_icon.setFixedSize(32, 32)
        self.league_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(self.league_icon)
        self.league = QLabel()
        self.league.setObjectName("competitionLabel")
        self.league.setWordWrap(True)
        top.addWidget(self.league, 1)
        self.status_dot = QFrame()
        self.status_dot.setObjectName("liveIndicator")
        self.status_dot.setFixedSize(9, 9)
        top.addWidget(self.status_dot)
        self.status = QLabel()
        self.status.setObjectName("matchStatus")
        top.addWidget(self.status)
        outer.addLayout(top)

        teams = QHBoxLayout()
        teams.setSpacing(9)
        self.home_icon = QLabel()
        self.home_icon.setFixedSize(44, 44)
        self.home_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        teams.addWidget(self.home_icon)
        self.home_label = QLabel()
        self.home_label.setWordWrap(True)
        teams.addWidget(self.home_label, 3)
        self.score = QLabel("X")
        self.score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score.setMinimumWidth(92)
        self.score.setObjectName("matchScore")
        teams.addWidget(self.score, 2)
        self.away_label = QLabel()
        self.away_label.setWordWrap(True)
        self.away_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        teams.addWidget(self.away_label, 3)
        self.away_icon = QLabel()
        self.away_icon.setFixedSize(44, 44)
        self.away_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        teams.addWidget(self.away_icon)
        outer.addLayout(teams)

        self.transmission = QLabel()
        self.transmission.setObjectName("broadcastLabel")
        outer.addWidget(self.transmission)
        self.channel = QLabel()
        self.channel.setObjectName("channelLabel")
        outer.addWidget(self.channel)
        self.update_record(row)
        self.apply_theme(dark)

    def _set_icon(self, label: QLabel, url: str, key: str):
        url = safe_artwork(url)
        if self._badge_urls.get(key) == url:
            return
        self._badge_urls[key] = url
        label.clear()
        label.setPixmap(svg_icon_for("football" if key != "league" else "live",
                                      min(label.width(), 30), light=not self.dark).pixmap(
                                          QSize(min(label.width(),30), min(label.height(),30))))
        self.loader.attach(label, url)

    def apply_theme(self, dark: bool):
        self.dark = dark
        border = "#315066" if dark else "#b5cbd9"
        bg = "#102b40" if dark else "#edf6fa"
        foreground = "#ebf9fd" if dark else "#173a52"
        subdued = "#b5cada" if dark else "#496a7e"
        self.setStyleSheet(
            f"QFrame#footballCard {{border:1px solid {border};border-radius:10px;background:{bg};}}"
            f"QFrame#footballCard QLabel {{border:0;background:transparent;color:{foreground};}}"
            f"QFrame#footballCard QLabel#competitionLabel {{font-weight:600;font-size:12px;}}"
            f"QFrame#footballCard QLabel#matchScore {{font-weight:700;font-size:19px;}}"
            f"QFrame#footballCard QLabel#broadcastLabel,"
            f"QFrame#footballCard QLabel#channelLabel {{color:{subdued};font-size:11px;}}"
            f"QFrame#footballCard QLabel#matchStatus {{color:#38b989;font-size:11px;font-weight:600;}}"
        )

    def set_pulse(self, on: bool):
        self._pulse_on = on
        visible = self._live and self.row.get("broadcast") != "replay"
        self.status_dot.setVisible(visible)
        self.status_dot.setStyleSheet(
            "background:#40d49f;border-radius:4px;" if visible and on
            else "background:transparent;border-radius:4px;")

    def update_record(self, row: dict):
        self.row = dict(row)
        self.league.setText(row.get("competition") or "Competição não informada")
        self.home_label.setText(row.get("home_team", ""))
        self.away_label.setText(row.get("away_team", ""))
        home, away = row.get("home_score"), row.get("away_score")
        state = row.get("score_state", "unknown")
        self.score.setText(f"{home}  X  {away}" if home is not None and away is not None else "X")
        if state in ("live", "halftime") and time.time() - row.get("score_checked", 0) > 125:
            state = "stale"
        # A football match in progress does NOT prove the chosen channel
        # is transmitting it. Only XMLTV can assert the programme slot.
        try:
            begin = datetime.fromisoformat(row.get("start", "")).astimezone()
            end = datetime.fromisoformat(row.get("end", "")).astimezone()
            on_air_epg = row.get("broadcast") == "live" and begin <= datetime.now().astimezone() < end
        except (ValueError, TypeError):
            on_air_epg = False
        self._live = state in ("live", "halftime") or on_air_epg
        self._live_text = "JOGO AO VIVO" if state in ("live", "halftime") else "AO VIVO · EPG"
        if row.get("broadcast") == "replay":
            self.status.setText("REPRISE")
        elif self._live:
            self.status.setText(self._live_text)
        elif state == "finished":
            self.status.setText("ENCERRADO")
        elif state == "stale":
            self.status.setText("PLACAR DESATUALIZADO")
        else:
            self.status.setText("")
        kickoff = row.get("start", "")
        try:
            d = datetime.fromisoformat(kickoff).astimezone()
            days = ("Segunda-Feira","Terça-Feira","Quarta-Feira","Quinta-Feira","Sexta-Feira","Sábado","Domingo")
            months = ("Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro")
            date = f"{days[d.weekday()]} - {d.day} de {months[d.month-1]} · {d:%H:%M}"
        except (TypeError, ValueError):
            date = "Data indisponível"
        if on_air_epg and row.get("broadcast") != "replay":
            clock = row.get("score_clock", "") if state in ("live", "halftime") else ""
            self.transmission.setText("Transmissão: AO VIVO · conforme EPG" + (f" · {clock}" if clock else ""))
        else:
            self.transmission.setText(("REPRISE · " if row.get("broadcast") == "replay" else "Transmissão: ") + date)
        self.channel.setText("Canal: " + (row.get("channel_title") or "Não identificado"))
        self._set_icon(self.league_icon, row.get("competition_badge") or row.get("event_logo") or "", "league")
        self._set_icon(self.home_icon, row.get("home_badge") or "", "home")
        self._set_icon(self.away_icon, row.get("away_badge") or "", "away")
        self.set_pulse(self._pulse_on)
