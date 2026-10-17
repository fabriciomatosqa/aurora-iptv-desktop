"""Settings are the sole home of playlists, appearance and update controls."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMenu
from aurora_desktop.modern import MainWindow
from aurora_desktop.svg_icons import PATHS, svg_icon_for


def start(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    win.show()
    app.processEvents()
    return app,win


def test_header_has_full_aurora_and_version_moves_to_lower_right(tmp_path,monkeypatch):
    app,win=start(tmp_path,monkeypatch)
    try:
        assert not win.menuBar().isVisible()
        assert not win.menuBar().actions()
        assert win.banner.width()==win.header_widget.width()
        # Artwork is fetched and bundled during packaging; source tests may\n        # legitimately have no JPEG until build_assets.py has run.\n        from aurora_desktop.modern import asset\n        if asset("aurora_banner.jpg").exists():\n            assert not win.banner._image.isNull()
        assert win.banner.height()>=198
        labels=[w.text() for w in win.banner.findChildren(QLabel)]
        assert not any("DESKTOP" in label or "v0." in label for label in labels)
        assert not any("Luzes da aurora" in x.text()
                       for x in win.sidebar.findChildren(QLabel))
        from aurora_desktop import __version__
        footer=win.sidebar.findChild(QLabel,"versionFooter")
        assert footer is not None
        assert __version__ in footer.text()
        assert footer.alignment() & Qt.AlignmentFlag.AlignRight
    finally:
        win.close()


def test_navigation_and_bottom_actions_use_real_svg_with_taller_buttons(tmp_path,monkeypatch):
    app,win=start(tmp_path,monkeypatch)
    try:
        assert set(("home","live","movie","series","football","favorites","settings")).issubset(PATHS)
        assert all(not svg_icon_for(name,30).isNull() for name in win.nav)
        assert all(btn.minimumHeight()>=55 for btn in win.nav.values())
        assert all(btn.iconSize().width()>=28 for btn in win.nav.values())
        assert not win.action.icon().isNull()
        assert not win.second_action.icon().isNull()
        assert not win.previous.icon().isNull()
        assert not any(symbol in win.action.text() for symbol in "↻＋⚙")
        assert not any(symbol in win.second_action.text() for symbol in "↻＋⚙")
    finally:
        win.close()


def test_settings_sections_keep_all_top_bar_features_reachable(tmp_path,monkeypatch):
    app,win=start(tmp_path,monkeypatch)
    try:
        win.navigate("settings")
        app.processEvents()
        cats=[win.groups.item(i).data(Qt.ItemDataRole.UserRole)
              for i in range(win.groups.count())]
        assert cats==["playlists","appearance","updates","guide"]
        assert win.playlist_settings.isVisible()
        assert win.results.isVisible()
        assert win.playlists.parent() is win.playlist_settings
        assert win.playlists.objectName()=="activePlaylistSelector"
        for index,active in enumerate(cats):
            win.groups.setCurrentRow(index)
            app.processEvents()
            assert win.settings_sections[active].isVisible()
            assert all(not item.isVisible() for key,item in win.settings_sections.items()
                       if key!=active)
            assert win.results.isVisible()==(active=="playlists")
        assert win.theme_select.count()==3
        assert win.update_channel.count()==2
        assert "Versão instalada" in win.updates_version.text()
        assert win.epg_settings.isVisible()
        win.navigate("home")
        app.processEvents()
        assert not any(item.isVisible() for item in win.settings_sections.values())
        assert win.results.isVisible()
    finally:
        win.close()


def test_update_controls_call_existing_controller_without_new_download_code(tmp_path,monkeypatch):
    app,win=start(tmp_path,monkeypatch)
    try:
        class Stub:
            def __init__(self):
                self.channels=[]
                self.checks=[]\n                self.downloader=None\n                self.checker=None
            def set_channel(self,channel):
                self.channels.append(channel)
            def check(self,manual=False):
                self.checks.append(manual)
        dummy=Stub()
        win.update_controller=dummy
        win.navigate("settings")
        win.groups.setCurrentRow(2)
        app.processEvents()
        index=win.update_channel.findData("stable")
        win.update_channel.setCurrentIndex(win.update_channel.findData("beta"))
        win.update_channel.setCurrentIndex(index)
        win.check_updates_button.click()
        assert dummy.channels[-1]=="stable"
        assert dummy.checks==[True]
        assert win.mode=="settings"
    finally:
        win.close()
