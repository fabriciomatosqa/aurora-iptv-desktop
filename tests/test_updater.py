"""Tests for update protocol, signatures, version ordering, and noninteractive installation."""
from hashlib import sha256
from pathlib import Path
import json
import sys

import pytest

from aurora_desktop import __version__
from aurora_desktop.updater import (
    RELEASES_API, ReleaseAsset, UpdateError, WINDOWS_SILENT_ARGS, discover_release,
    download_verified, parse_version, launch_windows_silent
)
from build_version import native_versions, prepare


class FakeResponse:
    def __init__(self, data, url, *, binary=False):
        self._data=data
        self.url=url
        self.binary=binary
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def raise_for_status(self): return None
    def json(self): return self._data
    def iter_content(self, chunk_size=131072):
        data=self._data
        for start in range(0,len(data),chunk_size):
            yield data[start:start+chunk_size]


class FakeClient:
    def __init__(self, response):
        self.response=response
        self.urls=[]
    def get(self, url, **kwargs):
        self.urls.append(url)
        return self.response


def test_version_orders_prerelease_and_stable():
    versions=["v0.5.0","v0.6.0-beta.1","0.6.0-beta.2","v0.6.0-rc.1","0.6.0","v0.6.1"]
    numbers=[parse_version(v).comparison() for v in versions]
    assert numbers==sorted(numbers)
    assert parse_version("v1.2") is None
    assert parse_version("1.2.3+untrusted") is None


def a_release(tag, *, prerelease=False, executable=True):
    asset={
        "name":"AURORA-IPTV-Desktop-Setup.exe",
        "browser_download_url":"https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/"+tag+"/AURORA-IPTV-Desktop-Setup.exe",
        "size":400,
        "digest":"sha256:"+("a"*64)
    }
    return {
        "tag_name":tag,"prerelease":prerelease,"draft":False,
        "html_url":"https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/tag/"+tag,
        "assets":[asset] if executable else [],
        "body":"Improvements"
    }


def test_select_latest_release_respects_channel_and_installer():
    response=FakeResponse([
        a_release("v0.7.0-beta.1",prerelease=True,executable=False),
        a_release("v0.6.1-beta.1",prerelease=True),
        a_release("v0.6.0"),
        a_release("v0.5.9"),
        a_release("v0.6.2",executable=False),
    ],RELEASES_API+"?per_page=40")
    client=FakeClient(response)
    latest=discover_release("0.5.0","beta","windows",client=client)
    assert latest.tag=="v0.6.1-beta.1"
    stable=discover_release("0.5.0","stable","windows",client=client)
    assert stable.tag=="v0.6.0"
    assert discover_release("0.6.1","stable","windows",client=client) is None
    assert client.urls==[RELEASES_API+"?per_page=40"]*3


def test_unverified_and_offsite_release_not_executable():
    fake=a_release("v0.7.0")
    fake["assets"][0]["digest"]=""
    spoof=a_release("v0.8.0")
    spoof["assets"][0]["browser_download_url"]="https://evil.example.org/payload.exe"
    client=FakeClient(FakeResponse([fake,spoof],RELEASES_API+"?per_page=40"))
    assert discover_release("0.5.0","beta","windows",client=client) is None


def test_sha256_download_is_atomic_and_verified(tmp_path):
    body=b"MZ"+b"AURORA-TEST"*850
    digest="sha256:"+sha256(body).hexdigest()
    asset=ReleaseAsset("AURORA-IPTV-Desktop-Setup.exe",len(body),
        "https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/v0.6.0/AURORA-IPTV-Desktop-Setup.exe",
        digest)
    client=FakeClient(FakeResponse(body,"https://release-assets.githubusercontent.com/test",binary=True))
    progress=[]
    result=download_verified(asset,tmp_path,progress=lambda n,t:progress.append((n,t)),client=client)
    assert result.read_bytes()==body
    assert progress[-1]==(len(body),len(body))
    assert not list(tmp_path.glob("*.part"))
    wrong=ReleaseAsset(asset.name,asset.size,asset.url,"sha256:"+("0"*64))
    with pytest.raises(UpdateError,match="SHA-256"):
        download_verified(wrong,tmp_path,client=client)
    assert result.read_bytes()==body


def test_download_rejects_untrusted_redirect_and_cancel(tmp_path):
    body=b"Hello"*100
    asset=ReleaseAsset("AURORA-IPTV-Desktop-Setup.exe",len(body),
        "https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/v0.6.0/file.exe",
        "sha256:"+sha256(body).hexdigest())
    with pytest.raises(UpdateError,match="confiável"):
        download_verified(asset,tmp_path,client=FakeClient(
            FakeResponse(body,"https://evil.example.org/file.exe",binary=True)))
    with pytest.raises(UpdateError,match="cancelado"):
        download_verified(asset,tmp_path,client=FakeClient(
            FakeResponse(body,"https://objects.githubusercontent.com/data",binary=True)),cancelled=lambda:True)


def test_silent_update_stages_detached_helper_and_waits_for_parent(tmp_path,monkeypatch):
    installer=tmp_path/"AURORA-IPTV-Desktop-Setup.exe"
    installer.write_bytes(b"MZ")
    installed=tmp_path/"Installed"/"AURORA-IPTV.exe"
    installed.parent.mkdir()
    installed.write_bytes(b"MZ")
    helper=tmp_path/"apply_update.ps1"
    helper.write_text("# Script fixture",encoding="utf-8")
    monkeypatch.setattr(sys,"platform","win32")
    monkeypatch.setattr(sys,"frozen",True,raising=False)
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    calls=[]
    status=launch_windows_silent(
        installer, installed_exe=installed, helper_source=helper,
        parent_pid=12345, target_version="0.6.0-beta.4",
        popen=lambda *args,**kwargs:calls.append((args,kwargs)))
    assert len(calls)==1
    cmd=calls[0][0][0]
    assert "powershell.exe" in cmd[0].lower()
    assert "-File" in cmd
    assert "-ParentProcessId" in cmd
    assert "12345" in cmd
    assert "-ExpectedVersion" in cmd
    assert "0.6.0-beta.4" in cmd
    assert str(installer) in cmd
    assert str(installed) in cmd
    assert not any(x.startswith("/VERYSILENT") for x in cmd)
    staged=tmp_path/"AURORA IPTV"/"updates"/"aurora-apply-update.ps1"
    assert staged.read_text(encoding="utf-8")=="# Script fixture"
    assert status.name=="update-status.json"
    assert status.parent==staged.parent


def test_real_helper_waits_installs_then_reopens():
    from aurora_desktop.updater import _updater_script
    source=_updater_script().read_text(encoding="utf-8")
    assert "Get-Process -Id $ParentProcessId" in source
    assert "Start-Process -FilePath $Installer" in source
    assert "-Wait -PassThru" in source
    assert "Start-Process -FilePath $InstalledExe" in source
    for flag in WINDOWS_SILENT_ARGS:
        assert flag in source


def test_update_status_is_consumed_once(tmp_path,monkeypatch):
    from aurora_desktop.updater import take_update_status
    monkeypatch.setattr(sys,"platform","win32")
    monkeypatch.setenv("LOCALAPPDATA",str(tmp_path))
    state=tmp_path/"AURORA IPTV"/"updates"/"update-status.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"status":"ok","version":"0.6.0-beta.4","exit_code":0}',encoding="utf-8")
    assert take_update_status()["version"]=="0.6.0-beta.4"
    assert take_update_status() is None



def test_single_version_source_for_windows_and_debian(tmp_path):
    native,deb=native_versions(__version__)
    assert deb==native_versions("0.6.0-171026.01")[1] if "-171026." in __version__ else deb==__version__.replace("-beta.","~beta").replace("-rc.","~rc")
    assert native[:3]==(0,6,0)
    prepare(tmp_path)
    assert __version__ in (tmp_path/"windows_version.txt").read_text()
    assert (tmp_path/"debian_version.txt").read_text().strip()==deb

def test_date_based_versions_upgrade_legacy_beta_without_misordering():
    # UI tags: DDMMYY.NN; comparison: Gregorian date then daily revision.
    values = [
        "v0.6.0-beta.14", "v0.6.0-beta.15",
        "v0.6.0-171026.01", "v0.6.0-171026.02",
        "v0.6.0-181026.01", "v0.6.0-011126.01",
        "v0.6.0-010127.01",
    ]
    parsed = [parse_version(v) for v in values]
    assert all(v is not None for v in parsed)
    assert [v.comparison() for v in parsed] == sorted(v.comparison() for v in parsed)
    assert parse_version("v0.6.0-311126.01") is None  # invalid November 31
    assert parse_version("v0.6.0-171026.00") is None
    assert parse_version("v0.6.0-171026.01").date_stamp == 20261017
    assert parse_version("v0.6.0-010127.01").date_stamp == 20270101


def test_discovery_date_release_on_beta_channel_from_beta15():
    current="0.6.0-beta.15"
    dated="v0.6.0-171026.01"
    fixture=FakeResponse([
        a_release("v0.6.0-beta.14",prerelease=True),
        a_release(dated,prerelease=True),
        a_release("v0.6.0-171026.02",prerelease=True,executable=False),
    ], RELEASES_API+"?per_page=40")
    result=discover_release(current,"beta","windows",FakeClient(fixture))
    assert result.tag==dated
    assert discover_release(current,"stable","windows",FakeClient(fixture)) is None
    assert discover_release("0.6.0-171026.02","beta","windows",FakeClient(fixture)) is None


def test_dated_release_native_metadata_and_debian_name():
    from aurora_desktop.updater import debian_asset_name
    native, deb = native_versions("0.6.0-171026.01")
    assert native[:3] == (0,6,0)
    assert native[3] == 29001
    assert deb == "0.6.0~date20261017.01"
    assert debian_asset_name("v0.6.0-171026.01") == (
        "aurora-iptv_0.6.0-date20261017.01_amd64.deb")
    assert debian_asset_name("v0.6.0-beta.14") == (
        "aurora-iptv_0.6.0-beta14_amd64.deb")
