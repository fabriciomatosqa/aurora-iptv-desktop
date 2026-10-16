$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r requirements-build.txt
python build_assets.py
python -m PyInstaller --noconfirm --clean --windowed --onedir --name AURORA-IPTV --icon assets/aurora_icon.ico --add-data "assets/aurora_icon.png;assets" --add-data "assets/aurora_banner.jpg;assets" run.py
$inno = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (Test-Path $inno) {
    & $inno installer_windows.iss
    Write-Host 'Instalador em installer_out/AURORA-IPTV-Desktop-Setup.exe'
} else {
    throw 'Inno Setup 6 nao encontrado. Instale-o para gerar o .exe instalador.'
}
