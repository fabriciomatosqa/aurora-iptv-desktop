"""Regression: update discovery cadence, footer action and idle synopsis."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import datetime, timedelta, timezone
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QLabel
from aurora_desktop.modern import MainWindow
from aurora_desktop.update_ui import UpdateController
from aurora_desktop.svg_icons import svg_icon_for


class DictSettings:
    def __init__(self): self.values={}
    def value(self,k,default=""): return self.values.get(k,default)
    def setValue(self,k,v): self.values[k]=v
    def remove(self,k): self.values.pop(k,None)


class FakeCheckWorker(QObject):
    result_ready=Signal(object)
    failed=Signal(str)
    finished=Signal()
    workers=[]
    def __init__(self,channel,parent=None):
        super().__init__(parent)
        self.channel=channel
        self.started=False
        self.workers.append(self)
    def start(self): self.started=True


def test_auto_update_rechecks_after_30_minutes_without_24hour_lockout(tmp_path,monkeypatch):
    import aurora_desktop.update_ui as update_ui
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    monkeypatch.setattr(update_ui,"CheckWorker",FakeCheckWorker)
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        ctrl=UpdateController(window)
        settings=ctrl.settings=DictSettings()
        # beta14's 24-hour timestamp must be ignored during migration.
        settings.setValue("updates/last_check",datetime.now(timezone.utc).isoformat())
        ctrl.check(manual=False)
        assert ctrl.checker is not None and ctrl.checker.started
        assert "updates/last_successful_check" not in settings.values
        ctrl._checked(None)
        assert "updates/last_successful_check" in settings.values
        ctrl._check_finished()
        ctrl.check(manual=False)
        assert ctrl.checker is None
        settings.setValue("updates/last_attempt",
                          (datetime.now(timezone.utc)-timedelta(minutes=31)).isoformat())
        settings.setValue("updates/last_successful_check",
                          (datetime.now(timezone.utc)-timedelta(minutes=31)).isoformat())
        ctrl.check(manual=False)
        assert ctrl.checker is not None
        ctrl._check_finished()
    finally:
        window.close()


def test_auto_update_failed_network_does_not_mark_success(tmp_path,monkeypatch):
    import aurora_desktop.update_ui as update_ui
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    monkeypatch.setattr(update_ui,"CheckWorker",FakeCheckWorker)
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    try:
        ctrl=UpdateController(window)
        settings=ctrl.settings=DictSettings()
        ctrl.check(manual=False)
        ctrl._failed_check("offline")
        assert "updates/last_successful_check" not in settings.values
        ctrl._check_finished()
        settings.setValue("updates/last_attempt",
                          (datetime.now(timezone.utc)-timedelta(minutes=6)).isoformat())
        ctrl.check(manual=False)
        assert ctrl.checker is not None
        ctrl._check_finished()
    finally:
        window.close()


def test_footer_update_button_is_clickable_and_primary_icon_has_contrast(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    requests=[]
    # Use the production controller, only stub its network entrypoint.
    # A duck-typed fake without downloader/checker broke closeEvent and made
    # the Qt event filter repeatedly emit errors during window shutdown.
    controller=UpdateController(window)
    controller.check=lambda manual=False: requests.append(manual)
    window.update_controller=controller
    try:
        window.show()
        app.processEvents()
        assert window.footer_update_button.isVisible()
        assert window.footer_update_button.toolTip()
        assert not window.footer_update_button.icon().isNull()
        window.footer_update_button.click()
        assert requests == [True]
        # Without a playlist the action is "Adicionar URL M3U".
        assert window.action.icon().cacheKey()==svg_icon_for("add",24,light=True).cacheKey()
        playlist=tmp_path/"sample.m3u"
        playlist.write_text('#EXTM3U\n#EXTINF:-1 group-title="Filmes",Um filme\nhttps://example.org/movie/1.mp4\n',
                            encoding="utf-8")
        pid=window.library.add_playlist("Teste",str(playlist))
        window.library.import_playlist(pid)
        window._indexed.add(pid)
        window._reload_playlists(pid)
        window.navigate("movie")
        assert window.action.text()=="Atualizar playlist"
        assert window.action.icon().cacheKey()==svg_icon_for("refresh",24,light=True).cacheKey()
    finally:
        window.close()


def test_selected_synopsis_replaces_idle_splash_without_starting_media(tmp_path,monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME",str(tmp_path))
    app=QApplication.instance() or QApplication([])
    window=MainWindow()
    window.show()
    app.processEvents()
    try:
        record={"kind":"movie","title":"Um filme", "synopsis":"Resumo do roteiro real.",
                "category":"Aventura","key":"key1","url":"https://example.org/movie.mp4"}
        window._add_result("Um filme",record)
        window.results.setCurrentRow(window.results.count()-1)
        app.processEvents()
        assert window.video_stage.currentWidget() is window.idle_synopsis
        assert "Resumo do roteiro real." in window.idle_synopsis_text.toPlainText()
        assert window.idle_synopsis_title.text()=="Um filme"
        assert window.playing is None
        assert window.player.videoOutput() is window.video
        window._update_idle_synopsis({"kind":"movie","title":"Outro", "synopsis":""})
        assert "Sinopse não disponível" in window.idle_synopsis_text.toPlainText()
        # An ongoing movie is never replaced by a preview during browsing.
        window.playing=record
        window.video_stage.setCurrentWidget(window.video)
        window._update_idle_synopsis({"kind":"movie","title":"Outro","synopsis":"Outro resumo"})
        assert window.video_stage.currentWidget() is window.video
        window.playing=None
        window._update_idle_synopsis(None)
        assert window.video_stage.currentWidget() is window.idle_synopsis
    finally:
        window.close()
