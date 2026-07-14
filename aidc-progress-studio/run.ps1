[CmdletBinding()]
param(
    [string]$HostName = $(if ($env:AIDC_HOST) { $env:AIDC_HOST } else { "127.0.0.1" }),
    [int]$Port = $(if ($env:AIDC_PORT) { [int]$env:AIDC_PORT } else { 8080 }),
    [switch]$ForceInstall
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $Python = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($Python) {
        & $Python.Path -3.12 -m venv $Venv
    }
    else {
        & python.exe -m venv $Venv
    }
}

if ($ForceInstall -or -not (Test-Path (Join-Path $Venv "aidc-installed.txt"))) {
    & $VenvPython -m pip install --disable-pip-version-check -e .
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    Set-Content -Path (Join-Path $Venv "aidc-installed.txt") -Value (Get-Date).ToString("o") -Encoding ASCII
}

Write-Host "AIDC Progress Studio: http://${HostName}:$Port"
& $VenvPython -m uvicorn aidc_progress_studio.api:app --host $HostName --port $Port
exit $LASTEXITCODE
