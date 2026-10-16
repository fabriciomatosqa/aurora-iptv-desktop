# AURORA IPTV unattended updater.
# Runs OUTSIDE the app directory. The parent app must exit before Inno Setup.
param(
    [Parameter(Mandatory=$true)][int]$ParentProcessId,
    [Parameter(Mandatory=$true)][string]$Installer,
    [Parameter(Mandatory=$true)][string]$InstalledExe,
    [Parameter(Mandatory=$true)][string]$StatusFile,
    [Parameter(Mandatory=$true)][string]$InstallLog,
    [Parameter(Mandatory=$true)][string]$ExpectedVersion
)
$ErrorActionPreference = 'Stop'

function Save-UpdateStatus([string]$State,[int]$Code,[string]$Detail) {
    try {
        $data = @{
            status = $State
            exit_code = $Code
            version = $ExpectedVersion
            detail = $Detail
            timestamp = (Get-Date).ToUniversalTime().ToString('o')
        } | ConvertTo-Json -Compress
        Set-Content -LiteralPath $StatusFile -Value $data -Encoding UTF8 -Force
    } catch {}
}

try {
    Save-UpdateStatus 'waiting' 0 'Aguardando encerramento do aplicativo'
    $closed = $false
    for ($attempt=0; $attempt -lt 240; $attempt++) {
        if (-not (Get-Process -Id $ParentProcessId -ErrorAction SilentlyContinue)) {
            $closed = $true
            break
        }
        Start-Sleep -Milliseconds 500
    }
    if (-not $closed) {
        Save-UpdateStatus 'failed' 20 'Aplicativo anterior nao encerrou no prazo'
        exit 20
    }
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) {
        Save-UpdateStatus 'failed' 21 'Instalador baixado nao foi encontrado'
        exit 21
    }
    Save-UpdateStatus 'installing' 0 'Atualizacao silenciosa iniciada'
    $args = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS /NORESTARTAPPLICATIONS /SP- /LOG="' + $InstallLog + '"'
    $process = Start-Process -FilePath $Installer -ArgumentList $args -Wait -PassThru -ErrorAction Stop
    $result = [int]$process.ExitCode
    if ($result -ne 0) {
        Save-UpdateStatus 'failed' $result 'Instalador retornou codigo de erro'
    } elseif (-not (Test-Path -LiteralPath $InstalledExe -PathType Leaf)) {
        Save-UpdateStatus 'failed' 22 'Executavel nao encontrado apos instalacao'
    } else {
        Save-UpdateStatus 'ok' 0 'Instalacao concluida'
    }
    # If the installer failed, reopen the intact app so that it can show the error.
    if (Test-Path -LiteralPath $InstalledExe -PathType Leaf) {
        Start-Process -FilePath $InstalledExe -WorkingDirectory (Split-Path -Parent $InstalledExe) -ErrorAction Stop | Out-Null
    }
} catch {
    Save-UpdateStatus 'failed' 23 'Falha ao iniciar o instalador ou reabrir o aplicativo'
    if (Test-Path -LiteralPath $InstalledExe -PathType Leaf) {
        try {
            Start-Process -FilePath $InstalledExe -WorkingDirectory (Split-Path -Parent $InstalledExe) -ErrorAction Stop | Out-Null
        } catch {}
    }
    exit 23
}
