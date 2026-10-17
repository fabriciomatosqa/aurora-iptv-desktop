"""Qt Football card and score worker integration, no external network needed."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import QApplication
from aurora_desktop.football_widgets import FootballCardWidget
from aurora_desktop.modern import MainWindow
from aurora_desktop.sports_data import fixture_key


class DummyBadgeLoader:
    def __init__(self):
        self.loaded = []

    def attach(self, label, url, *, allow_epg=False):
        self.loaded.append(url)


def row():
    now = datetime.now(timezone.utc)
    return {
        "playlist_id": 5, "channel_id": "sp1", "kind": "football",
        "home_team": "Fluminense", "away_team": "Santos",
        "competition": "Campeonato Brasileiro",
        "channel_title": "Canal da lista", "broadcast": "unknown",
        "start": (now - timedelta(minutes=25)).isoformat(),
        "end": (now + timedelta(minutes=75)).isoformat(),
        "url": "https://stream.example/01.ts",
    }


def test_card_has_independent_logo_slots_and_confirmed_score():
    app = QApplication.instance() or QApplication([])
    source = row()
    loader = DummyBadgeLoader()
    card = FootballCardWidget(source,loader,dark=True)
    assert card.league_icon.width() > 0
    assert card.home_icon.width() > 0
    assert card.away_icon.width() > 0
    assert card.home_label.text() == "Fluminense"
    assert card.away_label.text() == "Santos"
    assert card.score.text() == "X"
    card.update_record({**source, "score_state":"live","home_score":2,"away_score":1,
                        "score_checked": datetime.now(timezone.utc).timestamp(),"score_clock":"65'"})
    assert card.score.text() == "2  X  1"
    assert "JOGO AO VIVO" in card.status.text()
    assert "AO VIVO" not in card.transmission.text()  # EPG did not assert live broadcast
    card.set_pulse(False)
    assert "JOGO AO VIVO" in card.status.text()
    card.apply_theme(False)
    assert card.dark is False
    card.close()


def test_epg_replay_never_becomes_live_even_with_real_game_score():
    app = QApplication.instance() or QApplication([])
    source = row()
    card = FootballCardWidget({**source, "broadcast":"replay", "score_state":"finished",
                               "home_score":2,"away_score":1},DummyBadgeLoader())
    assert "REPRISE" in card.status.text()
    assert "AO VIVO" not in card.transmission.text()
    card.set_pulse(True)
    assert "REPRISE" in card.status.text()
    card.close()


def test_ui_enriches_existing_item_without_resetting_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    try:
        win.playlist_id = 5
        win.mode = "football"
        win._add_many([row()])
        assert win.results.count() == 1
        item = win.results.item(0)
        card = win.results.itemWidget(item)
        assert isinstance(card, FootballCardWidget)
        win.results.setCurrentRow(0)
        key = fixture_key(row())
        # Using the actual item key avoids clock differences across datetime.now() calls.
        key = fixture_key(item.data(256))
        win._scores_ready(5, {key: {"home_score":3,"away_score":0,
                                    "score_state":"finished",
                                    "score_checked":datetime.now(timezone.utc).timestamp()}})
        assert card.score.text() == "3  X  0"
        assert win.results.currentRow() == 0
        assert win.results.itemWidget(win.results.item(0)) is card
        assert win.results.item(0).data(256)["home_score"] == 3
    finally:
        win.close()
