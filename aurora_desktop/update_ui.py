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
    install_supported, launch_windows_silent, linux_install_supported,
    launch_linux_update, take_update_status, record_update_step
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
        self._target_version = None
        self._download_problem = None

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

    def set_channel(self, channel):
        self.settings.setValue("updates/channel",channel)
        self.settings.remove("updates/last_check")
        self.settings.remove("updates/last_attempt")
        self.settings.remove("updates/last_successful_check")
        self.window.status.setText("Canal alterado. Buscaremos versões desse canal.")

    def check(self, manual: bool = False):
        if self.checker is not None or self.downloader is not None:
            if manual:
                self.window.status.setText("Uma verificação ou download já está em andamento.")
            return
        now = datetime.now(timezone.utc)
        if not manual:
            # The beta.14 implementation recorded a 24-hour success BEFORE
            # querying GitHub. A release published minutes later was missed.
            # Also ignore that legacy timestamp: it may represent a failed
            # network request rather than a successful check.
            for key, cooldown in (
                ("updates/last_successful_check", timedelta(minutes=30)),
                ("updates/last_attempt", timedelta(minutes=5)),
            ):
                previous = self.settings.value(key, "")
                try:
                    date = datetime.fromisoformat(previous)
                    if date.tzinfo and now - date < cooldown:
                        return
                except (ValueError, TypeError):
                    pass
        self.settings.setValue("updates/last_attempt",now.isoformat())
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
        # A connection failure must not block automatic discovery for a day.
        self.settings.remove("updates/last_successful_check")
        if self._manual:
            QMessageBox.warning(self.window,"AURORA IPTV · Atualizações",message)
        else:
            self.window.status.setText("Verificação de atualizações indisponível.")

    def _checked(self, release: Release | None):
        # Mark success only after a complete response from GitHub. A newer
        # release must still be checked on subsequent starts/30-minute ticks.
        self.settings.setValue("updates/last_successful_check",
                               datetime.now(timezone.utc).isoformat())
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
        explanation = (
            "No Debian, o pacote será baixado e verificado dentro do AURORA. "
            "O sistema poderá solicitar autorização de administrador para instalar e reabrir o aplicativo."
            if sys.platform.startswith("linux") else
            "No Windows, a instalação será silenciosa depois da confirmação, "
            "sem telas de Avançar e sem desinstalar a versão atual."
        )
        box.setInformativeText(
            f"Versão instalada: {__version__}\n\n"
            "Deseja baixar a atualização agora?\n"
            + explanation)
        install=box.addButton("Atualizar agora",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Depois",QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(install)
        box.exec()
        if box.clickedButton()!=install:
            self.settings.setValue("updates/dismissed_version",release.tag)
            return
        if not sys.platform.startswith("linux") and not install_supported():
            QMessageBox.information(self.window, "Versão de desenvolvimento",
                "A instalação integrada requer um AURORA Desktop instalado.")
            return
        self._download(release)

    def _download(self, release):
        if not release.installer:
            QMessageBox.warning(self.window,"AURORA IPTV",
                "Esta versão não possui um instalador verificável.")
            return
        self._installed_file=None
        self._cancelled=False
        self._target_version=release.version
        self._download_problem=None
        record_update_step("download-started", f"Preparando instalador de {release.installer.size} bytes", release.version)
        dialog=QProgressDialog("Baixando atualização verificada...","Cancelar",0,100,self.window)
        dialog.setWindowTitle(f"Atualizando para {release.version}")
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(False)
        dialog.setAutoReset(False)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
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
            # 100% is shown only once SHA-256 is actually verified.
            progress = max(0,min(99,int(bytes_received * 100 / total)))
            self.download_dialog.setValue(progress)
            self.download_dialog.setLabelText(
                f"Baixando instalador: {bytes_received / 1048576:.1f} / "
                f"{total / 1048576:.1f} MB")

    def _cancel(self):
        self._cancelled=True
        record_update_step("cancelled", "Cancelamento solicitado pelo usuário", self._target_version)
        if self.downloader:
            self.downloader.abort.set()

    def _downloaded(self, filename: Path):
        # download_verified() reached here only after byte count and SHA-256 match.
        self._installed_file=filename
        record_update_step("download-verified", f"SHA-256 validado: {filename.stat().st_size} bytes", self._target_version)
        if self.download_dialog:
            self.download_dialog.setCancelButton(None)
            self.download_dialog.setLabelText("Download completo e verificado. Preparando atualização...")
            self.download_dialog.setValue(100)

    def _download_error(self, message):
        self._download_problem=message
        record_update_step("download-failed", message, self._target_version)

    def _download_finished(self):
        worker=self.downloader
        self.downloader=None
        if worker:
            worker.deleteLater()
        dialog=self.download_dialog
        self.download_dialog=None
        if dialog:
            # QProgressDialog.close() may emit canceled(). NEVER call it when
            # finishing a verified download: the prior implementation set
            # _cancelled=True here and silently skipped the installer.
            try:
                dialog.canceled.disconnect(self._cancel)
            except (TypeError, RuntimeError):
                pass
            dialog.hide()
            dialog.deleteLater()
        if self._cancelled:
            self.window.status.setText("Download cancelado; versão atual preservada.")
            self._installed_file=None
            return
        if self._download_problem:
            QMessageBox.warning(self.window, "Falha ao baixar atualização",
                                self._download_problem)
            self.window.status.setText("Download não concluído. O aplicativo atual não foi alterado.")
            self._installed_file=None
            return
        if not self._installed_file:
            record_update_step("download-failed", "Download finalizado sem arquivo verificado", self._target_version)
            QMessageBox.warning(self.window, "Falha ao baixar atualização",
                                "O download não forneceu um instalador verificado. Nenhuma instalação foi iniciada.")
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
        if sys.platform.startswith("linux"):
            if not linux_install_supported():
                self._open_local_deb(file,
                    "Esta é uma edição portátil ou de desenvolvimento. "
                    "O pacote .deb já foi baixado e será aberto no instalador do sistema.")
                return
            try:
                record_update_step("helper-launch", "Pacote Debian verificado; solicitando instalação com PolicyKit",
                                   self._target_version)
                launch_linux_update(file, target_version=self._target_version)
            except UpdateError as exc:
                record_update_step("helper-failed", str(exc), self._target_version)
                self._open_local_deb(file, str(exc))
                return
            self.window.status.setText("Pacote Debian verificado. Fechando para instalar e reabrir; autorize a operação se solicitado.")
        else:
            try:
                record_update_step("helper-launch", "Arquivo verificado; iniciando instalador externo", self._target_version)
                launch_windows_silent(file, target_version=self._target_version)
            except UpdateError as exc:
                record_update_step("helper-failed", str(exc), self._target_version)
                QMessageBox.warning(self.window,"AURORA IPTV · Instalação",str(exc))
                return
            self.window.status.setText("Download conferido. Fechando o AURORA para instalar e reabrir automaticamente.")
        QTimer.singleShot(0,self.window.close)

    def _open_local_deb(self, filename: Path, explanation: str):
        """Fallback when PolicyKit is unavailable: use downloaded DEB locally."""
        QMessageBox.information(
            self.window, "Instalação Debian",
            explanation + "\n\nO AURORA abrirá o arquivo .deb já baixado no gerenciador de pacotes. "
            "Não é necessário acessar o GitHub. O sistema poderá pedir sua senha.")
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(filename))):
            QMessageBox.warning(
                self.window, "Instalação Debian",
                "Não foi possível abrir o instalador gráfico de pacotes. "
                "O arquivo verificado está salvo em:\n" + str(filename))

    def show_previous_result(self):
        result = take_update_status()
        if not result:
            return
        if result["status"] == "ok" and result["version"] == __version__:
            self.window.status.setText(f"AURORA atualizado com sucesso para v{__version__}.")
        elif result["status"] == "failed":
            details = ("A atualização não foi concluída. "
                       f"Código: {result['exit_code']}. A instalação anterior foi preservada. ")
            if sys.platform.startswith("linux"):
                from .updater import update_directory, parse_version
                version = result["version"]
                safe = version.replace("-beta.", "-beta").replace("-rc.", "-rc")
                deb = update_directory() / f"aurora-iptv_{safe}_amd64.deb"
                if parse_version(version) is not None and deb.is_file():
                    answer = QMessageBox.question(
                        self.window, "Falha na instalação Debian",
                        details + "O pacote .deb foi baixado e verificado. "
                        "A autorização administrativa pode ter sido recusada ou indisponível. "
                        "Deseja abrir o pacote no gerenciador de programas do Linux? "
                        "Você não precisa acessar o GitHub.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if answer == QMessageBox.StandardButton.Yes:
                        self._open_local_deb(
                            deb,"O pacote oficial já está no computador.")
                    return
            QMessageBox.warning(self.window, "Falha na atualização",
                details + "Consulte o registro na pasta de atualizações: "
                + ("debian-update.log" if sys.platform.startswith("linux") else "innosetup-update.log") + ".")
        else:
            self.window.status.setText("Atualização não confirmada. Confira a versão instalada.")

    def shutdown(self):
        if self.downloader is not None:
            self._cancel()
