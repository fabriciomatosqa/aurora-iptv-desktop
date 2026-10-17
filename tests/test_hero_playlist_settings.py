"""AURORA hero banner and playlist-settings navigation smoke regressions."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QLabel

from aurora_desktop.modern import AuroraBanner, MainWindow


def window_with_playlists(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    first = win.library.add_playlist("Minha TV", "https://example.org/one.m3u")
    second = win.library.add_playlist("Filmes HD", "https://example.org/two.m3u")
    win._reload_playlists(first)
    win.show()
    app.processEvents()
    return app, win, first, second


def test_banner_is_full_width_and_does_not_contain_playlist_control(tmp_path, monkeypatch):
    app, win, first, second = window_with_playlists(tmp_path, monkeypatch)
    try:
        assert win.banner.parent() is win.header_widget
        assert isinstance(win.banner, AuroraBanner)
        assert win.banner.width() >= win.header_widget.width() - 18
        assert win.banner.width() > 1100
        assert win.header_widget.parent() is win.centralWidget()
        assert win.header_widget.geometry().width() > win.sidebar.width()
        assert win.banner.gradient_title.text()=="AURORA IPTV"
        assert win.banner.height() >= 150
        assert not win.banner.findChildren(type(win.playlists))
        titles = [w.text() for w in win.banner.findChildren(QLabel)]
        assert "AURORA IPTV" in titles
        assert any("ENTRETENIMENTO" in title for title in titles)
        assert not any("LISTA ATIVA" in title for title in titles)
    finally:
        win.close()


def test_active_playlist_is_only_shown_in_settings_and_switch_keeps_context(tmp_path, monkeypatch):
    app, win, first, second = window_with_playlists(tmp_path, monkeypatch)
    try:
        assert not win.playlist_settings.isVisible()
        assert win.playlists.parent() is win.playlist_settings
        win.navigate("settings")
        app.processEvents()
        assert win.playlist_settings.isVisible()
        assert win.playlists.isVisible()
        assert win.playlists.count() == 2
        assert win.playlists.currentData() == first
        win.playlists.setCurrentIndex(win.playlists.findData(second))
        app.processEvents()
        assert win.playlist_id == second
        assert win.mode == "settings"
        assert win.nav["settings"].isChecked()
        assert "Filmes HD" in win.status.text()
        win.navigate("home")
        app.processEvents()
        assert not win.playlist_settings.isVisible()
        assert win.playlist_id == second
    finally:
        win.close()


def test_banner_resizes_without_covering_main_content(tmp_path, monkeypatch):
    app, win, first, second = window_with_playlists(tmp_path, monkeypatch)
    try:
        initial = win.banner.width()
        win.resize(1700, 950)
        app.processEvents()
        assert win.banner.width() > initial
        assert win.panels.isVisible()
        assert win.banner.height() <= 240
        assert win.header_widget.isVisible()
        win._theme_apply()
        assert win.banner.isVisible()
    finally:
        win.close()
