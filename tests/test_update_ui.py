"""Offscreen checks for the update menu; no real network requests."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"

from PySide6.QtWidgets import QApplication
from aurora_desktop import __version__
from aurora_desktop.modern import MainWindow
from aurora_desktop.update_ui import UpdateController


def test_update_menu_displays_actual_installed_version(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        update=UpdateController(window)
        update.attach_menu(window.menuBar())
        menus=[a.menu() for a in window.menuBar().actions() if a.menu()]
        updates=next(menu for menu in menus if menu.title()=="Atualizações")
        assert any(__version__ in action.text() for action in updates.actions())
        assert any("Verificar atualizações" in action.text() for action in updates.actions())
        assert not any("Histórico" in action.text() for action in updates.actions())
    finally:
        window.close()
