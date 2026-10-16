"""Windows CI: download an actual published GitHub EXE and verify ALL bytes/SHA-256.

Unlike the synthetic unit tests, this hits the same GitHub Releases URLs that
the installed AURORA uses. Only official public releases are considered.
"""
from pathlib import Path
import os
import sys
import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tempfile import TemporaryDirectory
from time import monotonic

from aurora_desktop.updater import discover_release, download_verified


def main():
    client=requests.Session()
    token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        client.headers["Authorization"]="Bearer "+token
    release = discover_release(current="0.6.0-beta.4", channel="beta", platform="windows",client=client)
    if release is None or release.installer is None:
        raise RuntimeError("No valid newer GitHub Release installer was discovered")
    asset = release.installer
    if not (40_000_000 < asset.size < 150_000_000):
        raise RuntimeError("Downloaded asset is not a full-size Windows installer")
    print(f"Live GitHub asset: {release.tag}, expected {asset.size} bytes",flush=True)
    started = monotonic()
    progress = [0]
    def update(received: int,total: int):
        if received - progress[0] >= 5_000_000 or received == total:
            print(f"Live transfer: {received}/{total} bytes", flush=True)
            progress[0] = received
    with TemporaryDirectory(prefix="aurora-live-download-") as tmp:
        result = download_verified(asset,folder=Path(tmp),progress=update,client=client)
        actual = result.stat().st_size
        if actual != asset.size:
            raise RuntimeError(f"Incomplete file: expected {asset.size}, got {actual}")
        elapsed = monotonic() - started
        print(f"Verified REAL Windows installer from GitHub: {actual} bytes,"
              f" SHA-256 matched, {elapsed:.2f}s", flush=True)


if __name__=="__main__":
    main()
