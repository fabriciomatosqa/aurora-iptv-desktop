"""Beta.15 regression tests: responsive banner, PiP, controls and catalog."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QColor
from PySide6.QtWidgets import QApplication, QLineEdit
from aurora_desktop.modern import MainWindow, AuroraBanner
from aurora_desktop.pip_window import PiPWindow
from aurora_desktop.catalog import LibraryV2
from aurora_desktop.android_rules import classify_content
from aurora_desktop.svg_icons import svg_icon_for, PATHS


def gui():
    return QApplication.instance() or QApplication([])


def test_hero_is_not_zoom_cropped_on_ultrawide(tmp_path,monkeypatch):
    app=gui()
    banner=AuroraBanner()
    image=QPixmap(1000,260)
    image.fill(QColor("#174254"))
    banner._image=image
    banner.resize(500,210)
    small=QPixmap(banner.size())
    banner.render(small)
    banner.resize(2440,210)
    big=QPixmap(banner.size())
    banner.render(big)
    assert not small.isNull() and not big.isNull()
    assert small.width()==500 and big.width()==2440
    # A 1000x260 image painted at 210px tall spans ~808px, so extending
    # an ultrawide window cannot justify cropping its main image.
    assert image.width()*210/image.height()<big.width()


def test_pip_uses_same_player_without_second_decoder(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=gui()
    win=MainWindow()
    win.show()
    app.processEvents()
    try:
        original_player=win.player
        original_video=win.video
        win.playing={"url":"https://example.org/movie/demo.mp4","kind":"movie","title":"Teste"}
        win._enter_pip()
        app.processEvents()
        pip=win._pip_window
        assert isinstance(pip,PiPWindow)
        assert pip.isWindow()
        assert pip.minimumWidth()>=280
        assert pip.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)==False
        assert win.player is original_player
        assert win.player.videoOutput() is pip.video
        assert pip.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
        pip.pin.setChecked(False)
        assert not (pip.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        win._exit_pip()
        app.processEvents()
        assert win._pip_window is None
        assert win.player is original_player
        assert win.player.videoOutput() is original_video
        assert win.audio is original_player.audioOutput()
    finally:
        win.close()


def test_fullscreen_controls_aspect_and_player_shortcuts(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=gui()
    win=MainWindow()
    win.show()
    app.processEvents()
    try:
        for name in ("pip","aspect","rewind","forward","subtitle"):
            assert name in PATHS
            assert not svg_icon_for(name).isNull()
        win._toggle_video_fullscreen()
        app.processEvents()
        assert win._video_fullscreen
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.KeepAspectRatio
        assert win.fs_rewind.isVisible() and win.fs_forward.isVisible()
        assert not win.fs_seek.isEnabled()  # no seekable media
        assert win._fs_idle.interval()==3000 and win._fs_fade.duration()==2000
        win._set_aspect_mode("fill")
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.KeepAspectRatioByExpanding
        win._set_aspect_mode("stretch")
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.IgnoreAspectRatio
        win._set_aspect_mode("fit")
        assert win.video.aspectRatioMode()==Qt.AspectRatioMode.KeepAspectRatio
        win._leave_video_fullscreen()
        assert not win._video_fullscreen
    finally:
        win.close()


def test_catalog_ambiguous_manual_kind_persists_without_duplicate(tmp_path):
    source=tmp_path/"catalog.m3u"
    source.write_text(
        '#EXTM3U\n'
        '#EXTINF:-1 group-title="Diversos",Sem categoria\n'
        'https://example.org/play/opaque\n'
        '#EXTINF:-1 group-title="Filmes",Filme de teste\n'
        'https://example.org/movie/1.mp4\n'
        '#EXTINF:-1 group-title="Séries",Série S01E01\n'
        'https://example.org/series/1.mp4\n'
        '#EXTINF:-1 group-title="Ao vivo",TV Canal\n'
        'https://example.org/live/1.m3u8\n',encoding="utf-8")
    library=LibraryV2(tmp_path/"catalog.db")
    pid=library.add_playlist("Teste",str(source))
    assert library.import_playlist(pid)==4
    unknown=library.browse(pid,"uncategorized",None)
    assert len(unknown)==1
    key=unknown[0]["key"]
    library.set_favorite(pid,"item:"+key,"uncategorized","Sem categoria",True)
    library.save_progress(pid,key,86)
    library.set_kind_override(pid,key,"movie")
    assert any(x["key"]==key for x in library.browse(pid,"movie",None))
    assert library.get_progress(pid,key)==86
    assert library.is_favorite(pid,"item:"+key)
    assert library.import_playlist(pid)==4
    library.ensure_categories(pid,force=True)
    assert any(x["key"]==key for x in library.browse(pid,"movie",None))
    assert len(library.browse(pid,"uncategorized",None))==0
    with library.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM items WHERE playlist_id=?",(pid,)).fetchone()[0]==4
    library.set_kind_override(pid,key,None)
    assert len(library.browse(pid,"uncategorized",None))==1


def test_priority_rules():
    assert classify_content("Canal","Filmes","https://example.org/live/5.ts")=="live"
    assert classify_content("Filme","TV ao vivo","https://example.org/movie/5.mp4")=="movie"
    assert classify_content("Meu programa S02E04","Filmes","https://example.org/vod/5.mp4")=="series"
    assert classify_content("Desconhecido","Outros","https://example.org/play/opaque")=="uncategorized"
    assert classify_content("Outro","Diversos","https://example.org/random.m3u8")=="live"
    assert classify_content("Filme","Ao vivo","https://example.org/movie/2", "movie")=="movie"
