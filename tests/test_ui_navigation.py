"""Desktop UI regressions absent from the original headless smoke test."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidgetItem

from aurora_desktop.modern import MainWindow


def test_recent_series_episode_resumes_instead_of_opening_series(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    played=[]
    try:
        window.playlist_id=1
        window.mode="home"
        episode={"kind":"series","title":"A Teia S01E02",
                 "key":"example","series_name":"A Teia",
                 "url":"https://example.org/series/episode/2.mp4"}
        item=QListWidgetItem("A Teia S01E02")
        item.setData(Qt.ItemDataRole.UserRole,episode)
        monkeypatch.setattr(window,"_start",lambda record: played.append(record))
        window._open(item)
        assert played==[episode]
        assert window.mode=="home"
        assert window.video_stage.count()==2
        assert window.video_stage.currentWidget() is window.player_splash
    finally:
        window.close()


def test_episode_series_detail_still_accessible(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        window.mode="series"
        window.playlist_id=window.library.add_playlist("empty","https://example.org/list.m3u")
        item=QListWidgetItem("A Teia")
        item.setData(Qt.ItemDataRole.UserRole,
                     {"kind":"series","title":"A Teia","series_name":"A Teia","episodes":2})
        window._open(item)
        assert window.mode=="episodes"
        assert window.series_name=="A Teia"
    finally:
        window.close()
