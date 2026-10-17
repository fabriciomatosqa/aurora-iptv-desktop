"""Secure update discovery and download for AURORA IPTV Desktop.

The sole update channel is the project's GitHub Releases, not Actions artifacts.
Downloads must provide a SHA256 digest, must use TLS and must never execute until
the user explicitly approves. No IPTV credentials are used by the updater.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from typing import Callable

import requests

from . import __version__

REPOSITORY = "fabriciomatosqa/aurora-iptv-desktop"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
USER_AGENT = f"AURORA-IPTV-Desktop/{__version__}"
MAX_INSTALLER_BYTES = 350 * 1024 * 1024

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.](beta|b|rc)[.-]?(\d+))?$",re.I)
_DATED_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)-(\d{6})\.(\d{2})$",re.I)
_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    rank: int
    iteration: int
    date_stamp: int = 0

    def comparison(self):
        # Calendar ordering is ISO (YYYYMMDD), NOT the displayed DDMMYY,
        # so releases are ordered correctly across years and months.
        return (self.major,self.minor,self.patch,self.rank,self.date_stamp,self.iteration)


def parse_version(value: str) -> Version | None:
    """Support published legacy beta tags and dated DDMMYY.NN releases."""
    text = value.strip()
    dated = _DATED_VERSION_RE.fullmatch(text)
    if dated:
        major, minor, patch, date_code, sequence = dated.groups()
        day, month, year = int(date_code[:2]), int(date_code[2:4]), 2000+int(date_code[4:])
        try:
            date = datetime(year,month,day)
        except ValueError:
            return None
        number = int(sequence)
        if number < 1:
            return None
        return Version(int(major),int(minor),int(patch),2,number,
                       int(date.strftime("%Y%m%d")))
    found = _VERSION_RE.fullmatch(text)
    if not found:
        return None
    major, minor, patch, label, number = found.groups()
    rank = 3 if label is None else 1 if label.lower() == "rc" else 0
    return Version(int(major),int(minor),int(patch),rank,int(number or 0))


def debian_asset_name(tag: str) -> str | None:
    """Expected DEB filename for dated and existing GitHub release tags."""
    version = parse_version(tag)
    if version is None:
        return None
    base = f"{version.major}.{version.minor}.{version.patch}"
    if version.date_stamp:
        suffix = f"-date{version.date_stamp}.{version.iteration:02d}"
    else:
        found = _VERSION_RE.fullmatch(tag)
        if found is None:
            return None
        _, _, _, qualifier, number = found.groups()
        suffix = (f"-{('beta' if qualifier.lower() == 'b' else qualifier.lower())}{number}"
                  if qualifier else "")
    return f"aurora-iptv_{base}{suffix}_amd64.deb"

@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    size: int
    url: str
    digest: str


@dataclass(frozen=True)
class Release:
    version: str
    tag: str
    prerelease: bool
    url: str
    notes: str
    installer: ReleaseAsset | None


class UpdateError(Exception):
    """Safe user-facing update failure (never embed passwords or token-bearing URLs)."""


def _trusted_url(url: str, *, asset: bool = False) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        return False
    hostname = parsed.hostname.lower()
    if asset:
        return (hostname == "github.com" or hostname == "release-assets.githubusercontent.com"
                or hostname == "objects.githubusercontent.com")
    return hostname == "api.github.com"


def _get_json(url: str, client=requests):
    if not _trusted_url(url):
        raise UpdateError("Origem da atualização não é confiável.")
    try:
        response = client.get(url,timeout=(8,20),headers={
            "Accept":"application/vnd.github+json","User-Agent":USER_AGENT
        })
        response.raise_for_status()
        if not _trusted_url(response.url):
            raise UpdateError("A verificação foi redirecionada para uma origem não confiável.")
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpdateError("Não foi possível consultar o GitHub Releases. Verifique a conexão.") from exc


def discover_release(current: str = __version__, channel: str = "beta",
                     platform: str | None = None, client=requests) -> Release | None:
    existing = parse_version(current)
    if existing is None:
        raise UpdateError("A versão instalada não pôde ser identificada.")
    if channel not in ("stable","beta"):
        raise ValueError("Canal de atualizações inválido.")
    if platform is None:
        platform = "windows" if sys.platform == "win32" else "linux"
    candidates = _get_json(RELEASES_API + "?per_page=40",client)
    if not isinstance(candidates,list):
        raise UpdateError("O servidor retornou uma lista de versões inválida.")
    selected = None
    for item in candidates:
        if not isinstance(item,dict) or item.get("draft") or not item.get("tag_name"):
            continue
        tag = str(item["tag_name"])
        version = parse_version(tag)
        if version is None or version.comparison() <= existing.comparison():
            continue
        prerelease = bool(item.get("prerelease") or version.rank < 3)
        if channel == "stable" and prerelease:
            continue
        page = str(item.get("html_url",""))
        if not _trusted_url(page, asset=True) or urlsplit(page).hostname != "github.com":
            continue
        assets = item.get("assets") or []
        if platform == "windows":
            expected_name = "AURORA-IPTV-Desktop-Setup.exe"
        elif platform == "linux":
            # Linux installation uses the versioned Debian package, never the portable tarball.
            expected_name = debian_asset_name(tag)
        else:
            raise UpdateError("Sistema operacional não suportado para atualização.")
        match = next((a for a in assets if isinstance(a,dict) and a.get("name")==expected_name),None)
        asset = None
        if match:
            direct_url = str(match.get("browser_download_url",""))
            digest = str(match.get("digest") or "")
            # A beta may be visible before artifacts finish uploading. Only accept
            # a release as installable when its required verified asset exists.
            if _trusted_url(direct_url, asset=True) and urlsplit(direct_url).hostname == "github.com":
                asset = ReleaseAsset(expected_name,int(match.get("size") or 0),direct_url,digest)
        if asset is None or not _DIGEST_RE.fullmatch(asset.digest):
            continue
        new = Release(tag.lstrip("v"),tag,prerelease,page,
                      str(item.get("body") or "")[:2500],asset)
        if selected is None or version.comparison() > parse_version(selected.tag).comparison():
            selected = new
    return selected


def update_directory() -> Path:
    if sys.platform=="win32":
        root=Path(os.environ.get("LOCALAPPDATA") or (Path.home()/"AppData"/"Local"))/"AURORA IPTV"/"updates"
    else:
        root=Path(os.environ.get("XDG_CACHE_HOME") or Path.home()/".cache")/"aurora-iptv"/"updates"
    root.mkdir(parents=True,exist_ok=True)
    return root


def record_update_step(stage: str, detail: str = "", version: str | None = None) -> None:
    """Keep a local, bounded troubleshooting log (no playlist URLs/credentials)."""
    if not re.fullmatch(r"[a-z-]{1,35}", stage):
        return
    try:
        folder = update_directory()
        path = folder / "update-debug.log"
        if path.exists() and path.stat().st_size > 256 * 1024:
            previous = folder / "update-debug.previous.log"
            path.replace(previous)
        safe_detail = detail.replace("\r", " ").replace("\n", " ")[:200]
        with path.open("a", encoding="utf-8") as log:
            stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            log.write(f"{stamp} | {stage} | v{version or __version__} | {safe_detail}\n")
    except OSError:
        pass


def download_verified(installer: ReleaseAsset, folder: Path | None = None,
                      progress: Callable[[int,int],None] | None = None,
                      cancelled: Callable[[],bool] | None = None,
                      client=requests) -> Path:
    if (not _trusted_url(installer.url,asset=True)
            or urlsplit(installer.url).hostname != "github.com"
            or not (installer.name == "AURORA-IPTV-Desktop-Setup.exe"
                    or re.fullmatch(r"aurora-iptv_[0-9]+\.[0-9]+\.[0-9]+(?:-(?:(?:beta|rc)[0-9]+|date20[0-9]{6}\.[0-9]{2}))?_amd64\.deb",
                                    installer.name))):
        raise UpdateError("Arquivo de atualização não autorizado.")
    match = _DIGEST_RE.fullmatch(installer.digest)
    if not match:
        raise UpdateError("Atualização sem verificação de integridade SHA-256.")
    if installer.size <= 0 or installer.size > MAX_INSTALLER_BYTES:
        raise UpdateError("Tamanho do instalador inesperado.")
    folder = folder or update_directory()
    folder.mkdir(parents=True,exist_ok=True)
    target = folder / installer.name
    temp = None
    digest = hashlib.sha256()
    received = 0
    started = time.monotonic()
    record_update_step("download-network", f"Iniciando {installer.name} ({installer.size} bytes)")
    try:
        with client.get(installer.url,stream=True,timeout=(10,90),
                        headers={"User-Agent":USER_AGENT}) as response:
            response.raise_for_status()
            if not _trusted_url(response.url,asset=True):
                raise UpdateError("Download redirecionado para endereço não confiável.")
            fd,name=tempfile.mkstemp(prefix=".aurora-",suffix=".part",dir=folder)
            temp=Path(name)
            with os.fdopen(fd,"wb") as output:
                for chunk in response.iter_content(chunk_size=131072):
                    if cancelled and cancelled():
                        raise UpdateError("Download cancelado.")
                    if not chunk:
                        continue
                    received+=len(chunk)
                    if received>MAX_INSTALLER_BYTES or received>installer.size:
                        raise UpdateError("O download excedeu o tamanho esperado.")
                    digest.update(chunk)
                    output.write(chunk)
                    if progress:
                        progress(received,installer.size)
        if received!=installer.size or digest.hexdigest().lower()!=match.group(1).lower():
            raise UpdateError("A verificação SHA-256 falhou. O instalador não será executado.")
        os.replace(temp,target)
        elapsed = max(0.001, time.monotonic() - started)
        record_update_step("download-complete",
                           f"{received} bytes; SHA-256 válido; {elapsed:.1f}s; {received / elapsed / 1048576:.1f} MB/s")
        return target
    except requests.RequestException as exc:
        record_update_step("download-network-failed", "Conexão ou resposta HTTPS interrompida")
        raise UpdateError("Falha no download. A instalação atual foi preservada.") from exc
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


WINDOWS_SILENT_ARGS = (
    "/VERYSILENT","/SUPPRESSMSGBOXES","/NORESTART",
    "/CLOSEAPPLICATIONS","/NORESTARTAPPLICATIONS","/SP-",
)


def install_supported() -> bool:
    # In source mode there is no installed executable to replace.
    return sys.platform=="win32" and bool(getattr(sys,"frozen",False))


def _updater_script() -> Path:
    """Resolve the bundled helper inside the PyInstaller data directory."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "aurora_desktop" / "apply_update.ps1"


def update_status_path() -> Path:
    return update_directory() / "update-status.json"


def take_update_status() -> dict | None:
    """Show an installation outcome only once after the updated app reopens."""
    path = update_status_path()
    try:
        info = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(info, dict):
            return None
        if info.get("status") not in ("ok", "failed"):
            return None
        return {
            "status": info["status"],
            "version": str(info.get("version", ""))[:40],
            "exit_code": int(info.get("exit_code", 0)),
        }
    except (OSError, ValueError, TypeError):
        return None
    finally:
        # Never delete "waiting"/"installing" status from a helper still running.
        try:
            if path.exists():
                state = json.loads(path.read_text(encoding="utf-8-sig")).get("status")
                if state in ("ok", "failed"):
                    path.unlink(missing_ok=True)
        except (OSError, ValueError, TypeError, AttributeError):
            pass


def launch_windows_silent(installer: Path, popen=None,
                          installed_exe: Path | None = None,
                          helper_source: Path | None = None,
                          parent_pid: int | None = None,
                          target_version: str | None = None) -> Path:
    """Stage a detached updater that waits for THIS process before installing.

    The helper must run outside the installed application tree. Otherwise Inno
    Setup cannot replace the running exe. After completion it restarts the
    installed exe, not the downloaded installer. Returns the status file path.
    """
    if not install_supported():
        raise UpdateError("Instalação automática disponível somente na edição Windows instalada.")
    installer = installer.resolve()
    if installer.name != "AURORA-IPTV-Desktop-Setup.exe" or not installer.is_file():
        raise UpdateError("O instalador verificado não foi encontrado.")
    installed_exe = (installed_exe or Path(sys.executable)).resolve()
    if installed_exe.name.lower() != "aurora-iptv.exe" or not installed_exe.is_file():
        raise UpdateError("O executável da instalação atual não foi identificado.")
    source = helper_source or _updater_script()
    if not source.is_file():
        raise UpdateError("O auxiliar de atualização não foi incluído no instalador.")
    folder = update_directory()
    helper = folder / "aurora-apply-update.ps1"
    try:
        shutil.copyfile(source, helper)
    except OSError as exc:
        raise UpdateError("Não foi possível preparar a atualização silenciosa.") from exc
    status = folder / "update-status.json"
    log = folder / "innosetup-update.log"
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    command = [
        str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", str(helper),
        "-ParentProcessId", str(parent_pid if parent_pid is not None else os.getpid()),
        "-Installer", str(installer),
        "-InstalledExe", str(installed_exe),
        "-StatusFile", str(status),
        "-InstallLog", str(log),
        "-ExpectedVersion", target_version or __version__,
    ]
    if popen is None:
        popen = subprocess.Popen
    try:
        # The helper survives when Qt exits and waits before touching any files.
        popen(command, cwd=str(folder),
              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, close_fds=True,
              creationflags=(getattr(subprocess, "CREATE_NO_WINDOW", 0)
                             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)))
    except OSError as exc:
        raise UpdateError("Não foi possível iniciar o auxiliar. A versão atual foi mantida.") from exc
    return status


def linux_install_supported() -> bool:
    """Only a system-installed DEB can be updated through apt.

    Portable TAR.GZ editions must not silently install into /opt or change
    their installation method.
    """
    return (sys.platform.startswith("linux")
            and bool(getattr(sys, "frozen", False))
            and Path(sys.executable).resolve() == Path("/opt/aurora-iptv/AURORA-IPTV"))


def _linux_script() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "aurora_desktop" / "apply_update_linux.sh"


def launch_linux_update(package: Path, *, target_version: str,
                        popen=None, installed_exe: Path | None = None,
                        helper_source: Path | None = None,
                        parent_pid: int | None = None) -> Path:
    """Launch a detached, unprivileged helper for authenticated DEB update.

    Only apt-get runs as root, and only after a PolicyKit prompt.
    """
    if not linux_install_supported():
        raise UpdateError("Atualização automática requer a edição Debian instalada.")
    if not shutil.which("pkexec"):
        raise UpdateError("Autorização PolicyKit indisponível neste Linux.")
    if parse_version(target_version) is None:
        raise UpdateError("Versão de destino inválida.")
    package = package.resolve()
    if not re.fullmatch(r"aurora-iptv_[0-9]+\.[0-9]+\.[0-9]+(?:-(?:beta|rc)[0-9]+)?_amd64\.deb",
                        package.name) or not package.is_file():
        raise UpdateError("Pacote Debian verificado não encontrado.")
    exe = (installed_exe or Path(sys.executable)).resolve()
    if exe.name != "AURORA-IPTV" or not exe.is_file():
        raise UpdateError("Executável Debian instalado não encontrado.")
    original = helper_source or _linux_script()
    if not original.is_file():
        raise UpdateError("O auxiliar Linux não foi incluído nesta versão.")
    folder = update_directory()
    helper = folder / "aurora-apply-update.sh"
    status = update_status_path()
    log = folder / "debian-update.log"
    try:
        shutil.copyfile(original,helper)
        helper.chmod(0o700)
    except OSError as exc:
        raise UpdateError("Não foi possível preparar a atualização Debian.") from exc
    if popen is None:
        popen = subprocess.Popen
    cmd = ["/bin/sh",str(helper),str(parent_pid if parent_pid is not None else os.getpid()),
           str(package),str(exe),str(status),str(log),target_version]
    try:
        popen(cmd,cwd=str(folder),
              stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
              close_fds=True,start_new_session=True)
    except OSError as exc:
        raise UpdateError("Não foi possível iniciar o auxiliar Debian.") from exc
    return status
