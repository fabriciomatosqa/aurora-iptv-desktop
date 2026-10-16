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
from typing import Callable

import requests

from . import __version__

REPOSITORY = "fabriciomatosqa/aurora-iptv-desktop"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
USER_AGENT = f"AURORA-IPTV-Desktop/{__version__}"
MAX_INSTALLER_BYTES = 350 * 1024 * 1024

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-.](beta|b|rc)[.-]?(\d+))?$",re.I)
_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    rank: int
    iteration: int

    def comparison(self):
        return (self.major,self.minor,self.patch,self.rank,self.iteration)


def parse_version(value: str) -> Version | None:
    found = _VERSION_RE.fullmatch(value.strip())
    if not found:
        return None
    major, minor, patch, label, number = found.groups()
    rank = 2 if label is None else 1 if label.lower() == "rc" else 0
    return Version(int(major),int(minor),int(patch),rank,int(number or 0))


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
        prerelease = bool(item.get("prerelease") or version.rank < 2)
        if channel == "stable" and prerelease:
            continue
        page = str(item.get("html_url",""))
        if not _trusted_url(page, asset=True) or urlsplit(page).hostname != "github.com":
            continue
        assets = item.get("assets") or []
        expected_name = "AURORA-IPTV-Desktop-Setup.exe" if platform == "windows" else "AURORA-IPTV-Desktop-linux-x86_64.tar.gz"
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


def download_verified(installer: ReleaseAsset, folder: Path | None = None,
                      progress: Callable[[int,int],None] | None = None,
                      cancelled: Callable[[],bool] | None = None,
                      client=requests) -> Path:
    if (not _trusted_url(installer.url,asset=True)
            or urlsplit(installer.url).hostname != "github.com"
            or installer.name not in (
                "AURORA-IPTV-Desktop-Setup.exe",
                "AURORA-IPTV-Desktop-linux-x86_64.tar.gz")):
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
        return target
    except requests.RequestException as exc:
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
