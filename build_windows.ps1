$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean --windowed --onedir --name AURORA-IPTV run.py
$inno = 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
if (Test-Path $inno) {
    & $inno installer_windows.iss
    Write-Host 'Instalador em installer_out/AURORA-IPTV-Desktop-Setup.exe'
} else {
    throw 'Inno Setup 6 nao encontrado. Instale-o para gerar o .exe instalador.'
}
