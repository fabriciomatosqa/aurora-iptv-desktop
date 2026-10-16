"""Offscreen smoke test for the real desktop window, including the Football tab."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from aurora_desktop.modern import MainWindow


def test_desktop_window_opens_with_three_columns_and_football(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window.groups is not None
        assert window.results is not None
        assert window.video is not None
        assert "football" in window.nav
        assert "series" in window.nav
        window.navigate("football")
        assert window.heading.text() == "Agenda de futebol"
        window.navigate("settings")
        assert window.theme_select.count() == 3
    finally:
        window.close()
