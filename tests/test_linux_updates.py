"""Linux DEB release, download and detached updater regression tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from aurora_desktop.updater import (
    RELEASES_API, ReleaseAsset, UpdateError, discover_release, download_verified,
    launch_linux_update, linux_install_supported,
)
class FakeResponse:
    def __init__(self, payload, url):
        self.payload, self.url = payload, url
    def raise_for_status(self):
        return None
    def json(self):
        return self.payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size=131072):
        data=self.payload
        for i in range(0,len(data),chunk_size):
            yield data[i:i+chunk_size]


class FakeClient:
    def __init__(self, response):
        self.response=response
    def get(self, url, **kwargs):
        return self.response


def _deb_release(tag: str):
    ver=tag.lstrip("v").replace("-beta.","-beta").replace("-rc.","-rc")
    filename=f"aurora-iptv_{ver}_amd64.deb"
    return {
        "tag_name":tag,"draft":False,"prerelease":"beta" in tag,
        "html_url":f"https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/tag/{tag}",
        "assets":[{
            "name":filename,"size":132,
            "digest":"sha256:"+("a"*64),
            "browser_download_url":f"https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/{tag}/{filename}",
        }]
    }


def test_linux_selects_verified_deb_instead_of_portable_tarball():
    fixture=_deb_release("v0.6.0-beta.9")
    fixture["assets"].append({
        "name":"AURORA-IPTV-Desktop-linux-x86_64.tar.gz","size":100,
        "digest":"sha256:"+("f"*64),
        "browser_download_url":"https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/v0.6.0-beta.9/AURORA-IPTV-Desktop-linux-x86_64.tar.gz",
    })
    fixture2=_deb_release("v0.6.0-beta.10")
    fixture2["assets"][0]["digest"]=""
    client=FakeClient(FakeResponse([fixture,fixture2],RELEASES_API+"?per_page=40"))
    release=discover_release("0.6.0-beta.8","beta","linux",client)
    assert release.version=="0.6.0-beta.9"
    assert release.installer.name=="aurora-iptv_0.6.0-beta9_amd64.deb"
    assert release.installer.url.endswith(".deb")
    assert release.installer.size==132


def test_linux_deb_download_integrity_and_rejects_tarball(tmp_path):
    data=b"!<arch>\n"+b"AURORA-TEST"*60
    digest="sha256:"+hashlib.sha256(data).hexdigest()
    package=ReleaseAsset(
        "aurora-iptv_0.6.0-beta9_amd64.deb",len(data),
        "https://github.com/fabriciomatosqa/aurora-iptv-desktop/releases/download/v0.6.0-beta.9/aurora-iptv_0.6.0-beta9_amd64.deb",
        digest
    )
    downloaded=download_verified(
        package,folder=tmp_path,client=FakeClient(
            FakeResponse(data,"https://release-assets.githubusercontent.com/dummy")))
    assert downloaded.read_bytes()==data
    assert downloaded.stat().st_size==len(data)
    other=ReleaseAsset("AURORA-IPTV-Desktop-linux-x86_64.tar.gz",len(data),package.url,digest)
    with pytest.raises(UpdateError,match="não autorizado"):
        download_verified(other,folder=tmp_path)


def test_linux_update_launcher_detaches_and_never_installs_in_source(tmp_path,monkeypatch):
    import aurora_desktop.updater as updater
    pkg=tmp_path/"aurora-iptv_0.6.0-beta9_amd64.deb"
    pkg.write_bytes(b"!<arch>\n")
    exe=tmp_path/"AURORA-IPTV"
    exe.write_bytes(b"compiled")
    helper=tmp_path/"apply_update_linux.sh"
    helper.write_text("#!/bin/sh\n",encoding="utf8")
    monkeypatch.setenv("XDG_CACHE_HOME",str(tmp_path/"cache"))
    monkeypatch.setattr(updater.sys,"platform","linux")
    monkeypatch.setattr(updater,"linux_install_supported",lambda:True)
    monkeypatch.setattr(updater.shutil,"which",lambda name:"/usr/bin/pkexec" if name=="pkexec" else None)
    spawned=[]
    status=launch_linux_update(pkg,target_version="0.6.0-beta.9",
                helper_source=helper,installed_exe=exe,parent_pid=74210,
                popen=lambda *args,**kwargs: spawned.append((args,kwargs)))
    assert status.name=="update-status.json"
    assert len(spawned)==1
    args=spawned[0][0][0]
    assert args[:2]==["/bin/sh",str(tmp_path/"cache"/"aurora-iptv"/"updates"/"aurora-apply-update.sh")]
    assert args[2]=="74210"
    assert str(pkg) in args and str(exe) in args
    assert args[-1]=="0.6.0-beta.9"
    assert spawned[0][1]["start_new_session"] is True
    assert status.parent.joinpath("aurora-apply-update.sh").is_file()


@pytest.mark.skipif(sys.platform=="win32",reason="Detached shell helper needs Linux /bin/sh")
def test_linux_script_waits_for_exit_runs_mock_pkexec_and_reopens(tmp_path):
    """Run the real helper with a fake polkit, never elevate or install software."""
    source=Path(__file__).resolve().parents[1]/"aurora_desktop"/"apply_update_linux.sh"
    pkg=tmp_path/"aurora-iptv_0.6.0-beta9_amd64.deb"
    pkg.write_bytes(b"!<arch>\n")
    marker=tmp_path/"apt-requested"
    restart=tmp_path/"restarted"
    exe=tmp_path/"AURORA-IPTV"
    exe.write_text('#!/bin/sh\nprintf "restarted" > "$AURORA_TEST_RESTART"\n')
    exe.chmod(0o700)
    bindir=tmp_path/"bin"
    bindir.mkdir()
    pkexec=bindir/"pkexec"
    pkexec.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$AURORA_TEST_PKEXEC"\n')
    pkexec.chmod(0o700)
    status=tmp_path/"update-status.json"
    log=tmp_path/"apt.log"
    env={**os.environ, "PATH":str(bindir)+os.pathsep+os.environ.get("PATH",""),
         "AURORA_TEST_PKEXEC":str(marker),"AURORA_TEST_RESTART":str(restart)}
    parent=subprocess.Popen([sys.executable,"-c","import time; time.sleep(0.7)"])
    try:
        helper=subprocess.Popen(["/bin/sh",str(source),str(parent.pid),str(pkg),str(exe),
                                 str(status),str(log),"0.6.0-beta.9"],env=env)
        time.sleep(0.2)
        assert not marker.exists(), "Apt should not run while parent is alive"
        # Reap the fake app; otherwise kill -0 still sees its zombie PID.
        parent.wait(timeout=5)
        helper.wait(timeout=10)
        assert helper.returncode==0
        deadline=time.monotonic()+5
        while not restart.exists() and time.monotonic()<deadline:
            time.sleep(0.05)
        assert restart.exists()
        assert "apt-get" in marker.read_text()
        assert str(pkg) in marker.read_text()
        assert json.loads(status.read_text())["status"]=="ok"
    finally:
        parent.wait(timeout=5)
