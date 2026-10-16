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



def test_verified_download_does_not_trigger_cancel_during_dialog_dismissal(
        tmp_path, monkeypatch):
    """Regression: QProgressDialog.close() previously fired canceled() and aborted install."""
    from pathlib import Path
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QProgressDialog
    import aurora_desktop.update_ui as ui
    # Test the existing Windows in-place upgrade regardless of CI host OS.
    monkeypatch.setattr(ui.sys, "platform", "win32")

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        controller = UpdateController(window)
        window.update_controller = controller
        installer = tmp_path / "AURORA-IPTV-Desktop-Setup.exe"
        installer.write_bytes(b"MZ"+b"TEST"*100)
        dialog = QProgressDialog("Baixando", "Cancelar", 0, 100, window)
        dialog.setAutoReset(False)
        dialog.setAutoClose(False)
        dialog.canceled.connect(controller._cancel)
        controller.download_dialog = dialog
        controller.downloader = QObject()
        controller._target_version = "0.6.0-beta.6"
        controller._downloaded(installer)
        assert dialog.value() == 100
        installer_calls = []
        close_calls = []
        monkeypatch.setattr(ui, "launch_windows_silent", lambda f, **kwargs:
                            installer_calls.append((f,kwargs)))
        monkeypatch.setattr(ui.QTimer, "singleShot", lambda _ms, fn: close_calls.append(fn))
        controller._download_finished()
        assert not controller._cancelled
        assert installer_calls == [(installer, {"target_version": "0.6.0-beta.6"})]
        assert len(close_calls) == 1
        assert controller.downloader is None
        assert controller.download_dialog is None
    finally:
        window.close()


def test_download_progress_shows_real_megabytes_before_hash_validation(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QProgressDialog
    app=QApplication.instance() or QApplication([])
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    window=MainWindow()
    try:
        controller=UpdateController(window)
        dialog=QProgressDialog("Aguardando", "Cancelar", 0, 100,window)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        controller.download_dialog=dialog
        controller._progress(30*1048576,40*1048576)
        assert dialog.value()==75
        assert "30.0 / 40.0 MB" in dialog.labelText()
        controller._progress(40*1048576,40*1048576)
        assert dialog.value()==99
    finally:
        window.close()



def test_debian_update_launches_verified_local_package_without_github_page(tmp_path,monkeypatch):
    from pathlib import Path
    from PySide6.QtCore import QObject
    from PySide6.QtWidgets import QProgressDialog
    import aurora_desktop.update_ui as ui

    monkeypatch.setenv("XDG_CACHE_HOME",str(tmp_path))
    monkeypatch.setattr(ui.sys,"platform","linux")
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        controller=UpdateController(window)
        window.update_controller=controller
        filename=tmp_path/"aurora-iptv_0.6.0-beta9_amd64.deb"
        filename.write_bytes(b"!<arch>\n" + b"test")
        dlg=QProgressDialog("Baixando","Cancelar",0,100,window)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.canceled.connect(controller._cancel)
        controller.download_dialog=dlg
        controller.downloader=QObject()
        controller._target_version="0.6.0-beta.9"
        controller._downloaded(filename)
        calls=[]
        close=[]
        monkeypatch.setattr(ui,"linux_install_supported",lambda:True)
        monkeypatch.setattr(ui,"launch_linux_update",
                            lambda deb, **kwargs: calls.append((deb,kwargs)))
        monkeypatch.setattr(ui.QTimer,"singleShot",lambda ms,fn:close.append(fn))
        controller._download_finished()
        assert not controller._cancelled
        assert calls==[(filename,{"target_version":"0.6.0-beta.9"})]
        assert len(close)==1
        assert controller.downloader is None
    finally:
        window.close()
