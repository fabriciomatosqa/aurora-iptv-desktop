"""Qt integration for Aurora Releases updates. Work stays off the UI thread."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event
import sys

from PySide6.QtCore import QObject, QSettings, QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from . import __version__
from .updater import (
    RELEASES_PAGE, Release, UpdateError, discover_release, download_verified,
    install_supported, launch_windows_silent
)


class CheckWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, channel: str, parent=None):
        super().__init__(parent)
        self.channel = channel

    def run(self):
        try:
            self.result_ready.emit(discover_release(channel=self.channel))
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("Não foi possível verificar as atualizações.")


class DownloadWorker(QThread):
    downloaded = Signal(object)
    progress = Signal(int, int)
    failed = Signal(str)

    def __init__(self, asset, parent=None):
        super().__init__(parent)
        self.asset = asset
        self.abort = Event()

    def run(self):
        try:
            path = download_verified(
                self.asset, progress=lambda n,t: self.progress.emit(n,t),
                cancelled=self.abort.is_set)
            self.downloaded.emit(path)
        except UpdateError as exc:
            self.failed.emit(str(exc))
        except Exception:
            self.failed.emit("O download falhou. A instalação antiga não foi alterada.")


class UpdateController(QObject):
    """Displays one confirmation; everything after Update is silent on Windows."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.settings = QSettings("Aurora","AURORA IPTV Desktop")
        self.checker = None
        self.downloader = None
        self.download_dialog = None
        self._manual = False
        self._installed_file = None
        self._cancelled = False

    def attach_menu(self, menu_bar):
        menu = menu_bar.addMenu("Atualizações")
        version = menu.addAction(f"Instalada: v{__version__}")
        version.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Verificar atualizações agora",lambda:self.check(manual=True))
        channels = menu.addMenu("Canal de atualizações")
        choices = QActionGroup(self)
        choices.setExclusive(True)
        stored = self.settings.value("updates/channel","beta")
        for label,channel in (("Estável","stable"),("Beta e estável","beta")):
            action=QAction(label,self)
            action.setCheckable(True)
            action.setChecked(channel == stored)
            action.triggered.connect(lambda checked=False,c=channel:self.set_channel(c))
            channels.addAction(action)
            choices.addAction(action)
        menu.addSeparator()
        menu.addAction("Histórico de versões (GitHub Releases)",
                       lambda: QDesktopServices.openUrl(QUrl(RELEASES_PAGE)))

    def set_channel(self, channel):
        self.settings.setValue("updates/channel",channel)
        self.settings.remove("updates/last_check")
        self.window.status.setText("Canal alterado. Use Atualizações para verificar novas versões.")

    def check(self, manual: bool = False):
        if self.checker is not None or self.downloader is not None:
            if manual:
                self.window.status.setText("Uma verificação ou download já está em andamento.")
            return
        now = datetime.now(timezone.utc)
        if not manual:
            previous = self.settings.value("updates/last_check","")
            try:
                date = datetime.fromisoformat(previous)
                if date.tzinfo and now - date < timedelta(hours=24):
                    return
            except (ValueError, TypeError):
                pass
        self.settings.setValue("updates/last_check",now.isoformat())
        self._manual=manual
        worker=CheckWorker(self.settings.value("updates/channel","beta"),self)
        self.checker=worker
        worker.result_ready.connect(self._checked)
        worker.failed.connect(self._failed_check)
        worker.finished.connect(self._check_finished)
        worker.start()
        if manual:
            self.window.status.setText("Consultando versões no GitHub Releases...")

    def _check_finished(self):
        worker=self.checker
        self.checker=None
        if worker:
            worker.deleteLater()

    def _failed_check(self, message):
        if self._manual:
            QMessageBox.warning(self.window,"AURORA IPTV · Atualizações",message)
        else:
            self.window.status.setText("Verificação de atualizações indisponível.")

    def _checked(self, release: Release | None):
        if release is None:
            if self._manual:
                QMessageBox.information(self.window,"AURORA IPTV · Atualizações",
                    f"Você está usando a versão mais recente do canal selecionado.\n\nVersão instalada: {__version__}")
            return
        if (not self._manual and
                self.settings.value("updates/dismissed_version","") == release.tag):
            return
        box=QMessageBox(self.window)
        box.setWindowTitle("Atualização do AURORA IPTV")
        box.setIcon(QMessageBox.Icon.Information)
        box.setTextFormat(Qt.TextFormat.PlainText)
        channel="Beta" if release.prerelease else "Estável"
        box.setText(f"Nova versão disponível: {release.version} ({channel})")
        box.setInformativeText(
            f"Versão instalada: {__version__}\n\n"
            "Deseja baixar a atualização agora?\n"
            "No Windows, a instalação será silenciosa após você confirmar, "
            "sem telas de Avançar e sem desinstalar a versão atual.")
        install=box.addButton("Atualizar agora",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Depois",QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(install)
        box.exec()
        if box.clickedButton()!=install:
            self.settings.setValue("updates/dismissed_version",release.tag)
            return
        if not install_supported():
            QMessageBox.information(self.window,"Atualização no Linux ou versão de desenvolvimento",
                "O instalador silencioso está disponível na versão Windows instalada.\n"
                "No Linux, a instalação DEB pode exigir permissão administrativa. "
                "Use o pacote adequado no GitHub Releases.")
            QDesktopServices.openUrl(QUrl(release.url))
            return
        self._download(release)

    def _download(self, release):
        if not release.installer:
            QMessageBox.warning(self.window,"AURORA IPTV",
                "Esta versão não possui um instalador verificável.")
            return
        self._installed_file=None
        self._cancelled=False
        dialog=QProgressDialog("Baixando atualização verificada...","Cancelar",0,100,self.window)
        dialog.setWindowTitle(f"Atualizando para {release.version}")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setValue(0)
        worker=DownloadWorker(release.installer,self)
        self.download_dialog=dialog
        self.downloader=worker
        dialog.canceled.connect(self._cancel)
        worker.progress.connect(self._progress)
        worker.failed.connect(self._download_error)
        worker.downloaded.connect(self._downloaded)
        worker.finished.connect(self._download_finished)
        dialog.show()
        worker.start()

    def _progress(self, bytes_received, total):
        if self.download_dialog and total:
            self.download_dialog.setValue(max(0,min(100,round(bytes_received*100/total))))

    def _cancel(self):
        self._cancelled=True
        if self.downloader:
            self.downloader.abort.set()

    def _downloaded(self, filename: Path):
        self._installed_file=filename

    def _download_error(self, message):
        if self._cancelled or message=="Download cancelado.":
            self.window.status.setText("Download cancelado; versão atual preservada.")
        else:
            QMessageBox.warning(self.window,"AURORA IPTV · Download",message)

    def _download_finished(self):
        worker=self.downloader
        self.downloader=None
        if worker:
            worker.deleteLater()
        if self.download_dialog:
            self.download_dialog.close()
            self.download_dialog.deleteLater()
            self.download_dialog=None
        if not self._installed_file or self._cancelled:
            self._installed_file=None
            return
        file=self._installed_file
        self._installed_file=None
        # Avoid closing during concurrent database operations.
        for attr in ("thread","index_thread","guide_thread"):
            task=getattr(self.window,attr,None)
            if task is not None and task.isRunning():
                QMessageBox.information(self.window,"Atualização pronta",
                    "Conclua a importação ou a atualização do guia e tente novamente.")
                return
        try:
            launch_windows_silent(file)
        except UpdateError as exc:
            QMessageBox.warning(self.window,"AURORA IPTV · Instalação",str(exc))
            return
        self.window.status.setText("Atualização iniciada. O aplicativo será fechado.")
        # Inno Setup per-user installer will replace the existing installation.
        QTimer.singleShot(0,self.window.close)

    def shutdown(self):
        if self.downloader is not None:
            self._cancel()
