#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python build_assets.py
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --onedir --name AURORA-IPTV --add-data "assets/aurora_icon.png:assets" --add-data "assets/aurora_banner.jpg:assets" run.py
mkdir -p releases
tar -czf releases/AURORA-IPTV-Desktop-linux-x86_64.tar.gz -C dist AURORA-IPTV
stage="build/aurora-iptv-deb"
rm -rf "$stage"
mkdir -p "$stage/DEBIAN" "$stage/opt/aurora-iptv" "$stage/usr/bin" "$stage/usr/share/applications"
cp -a dist/AURORA-IPTV/. "$stage/opt/aurora-iptv/"
cat > "$stage/usr/bin/aurora-iptv" <<'ENDSH'
#!/bin/sh
exec /opt/aurora-iptv/AURORA-IPTV "$@"
ENDSH
chmod +x "$stage/usr/bin/aurora-iptv"
cat > "$stage/usr/share/applications/aurora-iptv.desktop" <<'ENDDESKTOP'
[Desktop Entry]
Name=AURORA IPTV
Comment=Player IPTV para Windows e Linux
Exec=aurora-iptv
Terminal=false
Type=Application
Categories=AudioVideo;Video;Player;
ENDDESKTOP
cat > "$stage/DEBIAN/control" <<'ENDCONTROL'
Package: aurora-iptv
Version: 0.5.0
Section: video
Priority: optional
Architecture: amd64
Maintainer: AURORA IPTV <noreply@example.invalid>
Depends: libc6, libgl1, libegl1, libxkbcommon0
Description: AURORA IPTV Desktop
 Player M3U para Windows e Linux. Nenhum conteudo incluido.
ENDCONTROL
dpkg-deb --root-owner-group --build "$stage" releases/aurora-iptv_0.5.0_amd64.deb
echo 'Pacotes criados em releases/'
