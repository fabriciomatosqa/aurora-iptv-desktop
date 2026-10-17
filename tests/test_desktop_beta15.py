"""Beta.15 UI controls, floating output and panoramic banner regression."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication

from aurora_desktop.modern import AuroraBanner, MainWindow
from aurora_desktop.pip_player import PiPWindow
from aurora_desktop.svg_icons import svg_icon_for


def window(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    w.show()
    app.processEvents()
    return app,w


def test_banner_draws_at_1150_and_ultrawide_without_stretch_or_crash():
    app=QApplication.instance() or QApplication([])
    banner=AuroraBanner()
    img=QPixmap(1500,800)
    img.fill(QColor("#287ca5"))
    banner._image=img
    for width in (1150,1920,3440):
        banner.resize(width,210)
        rendered=QPixmap(width,210)
        rendered.fill(Qt.GlobalColor.transparent)
        banner.render(rendered)
        assert not rendered.isNull()
        assert rendered.toImage().pixelColor(width//2,90).alpha()>200
        assert rendered.toImage().pixelColor(width-3,90).alpha()>200


def test_pip_moves_single_active_media_output_and_restores(tmp_path,monkeypatch):
    app,win=window(tmp_path,monkeypatch)
    try:
        video=win.video
        media=win.player
        audio=win.audio
        win.playing={"title":"Série teste", "kind":"series", "url":"https://example.test/vod/test.mp4"}
        win._toggle_pip()
        app.processEvents()
        pip=win._pip_window
        assert isinstance(pip,PiPWindow)
        assert pip.isVisible()
        assert pip.minimumWidth()<=pip.width()
        assert pip.top_switch.isChecked()
        assert win.player is media and win.audio is audio
        assert win.video is video
        assert media.videoOutput() is pip.video
        pip.volume.setValue(35)
        assert abs(audio.volume()-.35)<.01
        pip.restore_requested.emit()
        app.processEvents()
        assert win._pip_window is None
        assert media.videoOutput() is video
    finally:
        win.close()


def test_fullscreen_has_real_controls_and_only_supported_aspect_choices(tmp_path,monkeypatch):
    app,win=window(tmp_path,monkeypatch)
    try:
        assert len(win.fs_aspect_menu.actions())==3
        assert all(not btn.icon().isNull() for btn in (
            win.fs_pip,win.fs_aspect,win.fs_rewind,win.fs_forward,
            win.fs_play_center,win.fs_audio,win.fs_subtitles,win.fs_speed))
        assert not svg_icon_for("pip",24).isNull()
        win._set_video_aspect(Qt.AspectRatioMode.IgnoreAspectRatio)
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.IgnoreAspectRatio
        win._set_video_aspect(Qt.AspectRatioMode.KeepAspectRatio)
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.KeepAspectRatio
        win._update_track_buttons()
        assert not win.fs_audio.isVisible()  # No media contains no tracks
        assert not win.fs_subtitles.isVisible()
        assert not win.fs_forward.isEnabled()  # VOD seeking not available
        assert not win.fs_rewind.isEnabled()
        assert len(win._advanced_keys)==6
    finally:
        win.close()
