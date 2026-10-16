# Windows CI integration: run the actual installer twice with the silent helper.
# No credentials or third-party media streams are used.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot ".." "..")
$installer = (Resolve-Path "installer_out/AURORA-IPTV-Desktop-Setup.exe").Path
$installDir = Join-Path $env:RUNNER_TEMP "AuroraSilentSmoke"
$exe = Join-Path $installDir "AURORA-IPTV.exe"
$logDir = Join-Path $env:RUNNER_TEMP "AuroraSilentUpdateLogs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$log = Join-Path $logDir "inno-update.log"
$statusFile = Join-Path $logDir "update-status.json"
$initialLog = Join-Path $logDir "inno-initial.log"
$version = (python -c "from aurora_desktop import __version__; print(__version__)").Trim()

Write-Host "Installing isolated initial copy $version"
$initialArgs = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NORESTARTAPPLICATIONS /SP- /DIR="' + $installDir + '" /LOG="' + $initialLog + '"'
$initial = Start-Process -FilePath $installer -ArgumentList $initialArgs -Wait -PassThru
if ($initial.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $exe)) {
    throw "Initial silent installation failed, exit $($initial.ExitCode)"
}

# A separate process remains open for 6 seconds; helper must wait first.
$guard = Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -ArgumentList '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 6"' -WindowStyle Hidden -PassThru
$start = Get-Date
$env:QT_QPA_PLATFORM = "offscreen"
Write-Host "Testing helper wait, silent install, and automatic relaunch"
& "$PSScriptRoot/../../aurora_desktop/apply_update.ps1" -ParentProcessId $guard.Id -Installer $installer -InstalledExe $exe -StatusFile $statusFile -InstallLog $log -ExpectedVersion $version
$elapsed = ((Get-Date) - $start).TotalSeconds
if ($elapsed -lt 4) {
    throw "Updater failed to wait for old process (elapsed $elapsed)"
}
if (-not (Test-Path -LiteralPath $statusFile)) {
    throw "Helper did not write update result"
}
$state = Get-Content -LiteralPath $statusFile -Raw | ConvertFrom-Json
if ($state.status -ne "ok" -or $state.version -ne $version -or $state.exit_code -ne 0) {
    if (Test-Path $log) { Get-Content $log -Tail 75 }
    throw "Update helper returned unexpected status $($state | ConvertTo-Json -Compress)"
}
if (-not (Test-Path -LiteralPath $exe)) {
    throw "Installed executable missing after update"
}
Write-Host "Silent install sequence successful, version $version, $([int]$elapsed) seconds"
Start-Sleep -Seconds 2
Get-CimInstance Win32_Process -Filter "Name = 'AURORA-IPTV.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -eq $exe } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
