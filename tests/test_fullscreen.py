"""Fullscreen keeps the SAME video renderer on Linux and Windows."""
import os
os.environ["QT_QPA_PLATFORM"]="offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from aurora_desktop.modern import MainWindow


def test_fullscreen_does_not_detach_or_replace_video_output(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.show()
    app.processEvents()
    try:
        original_parent=window.video.parent()
        original_output=window.player.videoOutput()
        minimum=window.minimumSize()
        assert not window._video_fullscreen
        window.video_stage.setCurrentWidget(window.video)
        window._toggle_video_fullscreen()
        app.processEvents()
        assert window._video_fullscreen
        assert window.video.parent() is original_parent
        assert window.player.videoOutput() is original_output
        assert not window.video.isFullScreen()
        assert window.sidebar.isHidden()
        assert window.header_widget.isHidden()
        assert window.categories_panel.isHidden()
        assert window.contents_panel.isHidden()
        assert window.fullscreen_button.isVisible()
        assert "Sair da tela cheia" in window.fullscreen_button.text()
        assert window.exit_fullscreen_shortcut.context() == Qt.ShortcutContext.ApplicationShortcut
        window._leave_video_fullscreen()
        app.processEvents()
        assert not window._video_fullscreen
        assert window.video.parent() is original_parent
        assert window.player.videoOutput() is original_output
        assert not window.video.isFullScreen()
        assert not window.sidebar.isHidden()
        assert not window.header_widget.isHidden()
        assert not window.categories_panel.isHidden()
        assert not window.contents_panel.isHidden()
        assert window.minimumSize()==minimum
        assert window.fullscreen_button.text()=="⛶ Tela cheia"
        assert window.menuBar().isVisible()
    finally:
        window.close()


def test_repeated_fullscreen_toggle_and_esc_action_are_reversible(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.show()
    app.processEvents()
    try:
        for i in range(3):
            window.fullscreen_button.click()
            app.processEvents()
            assert window._video_fullscreen
            window._leave_video_fullscreen()
            app.processEvents()
            assert not window._video_fullscreen
            assert window.fullscreen_button.isVisible()
        # The user can always recover the window using the same button.
        window.fullscreen_button.click()
        window.fullscreen_button.click()
        assert not window._video_fullscreen
    finally:
        window.close()
