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
        assert window.fs_overlay.isVisible()
        assert window.fs_bottom.isVisible()
        assert window.fs_exit.isVisible()
        assert not window.player_controls.isVisible()
        assert not window.player_actions.isVisible()
        assert window.player_panel.layout().contentsMargins().left() == 0
        assert window.video.aspectRatioMode() == Qt.AspectRatioMode.KeepAspectRatioByExpanding
        assert window.fs_overlay.geometry() == window.video_stage.rect()
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
        assert window.fullscreen_button.text()=="Tela cheia"
        assert window.player_controls.isVisible()
        assert window.player_actions.isVisible()
        assert not window.fs_overlay.isVisible()
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



def test_overlay_auto_fades_from_three_to_five_seconds(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    win.show()
    app.processEvents()
    try:
        win.video_stage.setCurrentWidget(win.video)
        win._toggle_video_fullscreen()
        app.processEvents()
        assert win._fs_idle.interval()==3000
        assert win._fs_fade.duration()==2000
        assert win.fs_overlay.isVisible()
        win._begin_fullscreen_fade()
        assert win._fs_fade.state()==win._fs_fade.State.Running
        win._fs_fade.stop()
        win._fs_opacity.setOpacity(0)
        win._hide_fullscreen_overlay()
        assert not win.fs_overlay.isVisible()
        win._show_fullscreen_overlay()
        app.processEvents()
        assert win.fs_overlay.isVisible()
        assert win._fs_opacity.opacity()==1
        assert win._fs_idle.isActive()
        assert win.fs_bottom.parent() is win.fs_overlay
    finally:
        win._leave_video_fullscreen()
        win.close()


def test_vector_play_pause_and_star_seek(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    win=MainWindow()
    try:
        assert win.play.text()=="Reproduzir"
        assert "Ⅱ" not in win.play.text()
        assert not win.play.icon().isNull()
        assert not win.fs_play.icon().isNull()
        assert not win.fs_volume_icon.icon().isNull()
        assert not win.volume_button.icon().isNull()
        assert win.seek.objectName()=="auroraSeek"
        assert win.fs_seek.objectName()=="auroraSeek"
        assert win.fs_favorite.text()=="Favoritar"
    finally:
        win.close()
