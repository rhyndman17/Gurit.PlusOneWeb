param (
    [switch]$InstallPyInstaller
)

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
}
else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}

Push-Location $scriptDir
try {
    if ($InstallPyInstaller) {
        python -m pip install pyinstaller
    }

    $compiledDir = Join-Path $scriptDir 'Compiled'
    New-Item -ItemType Directory -Force -Path $compiledDir | Out-Null

    python -m PyInstaller `
        --noconfirm `
        --name PlusOneWeb `
        --hidden-import pyodbc `
        --hidden-import paramiko `
        --add-data "PlusOneWeb;PlusOneWeb" `
        plusone_web.py

    $compiledExePath = Join-Path $compiledDir 'PlusOneWeb.exe'
    Get-CimInstance Win32_Process |
        Where-Object { $_.ExecutablePath -eq $compiledExePath } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

    $compiledInternalDir = Join-Path $compiledDir '_internal'
    if (Test-Path -LiteralPath $compiledInternalDir) {
        Remove-Item -LiteralPath $compiledInternalDir -Recurse -Force
    }

    Copy-Item -LiteralPath (Join-Path $scriptDir 'dist\PlusOneWeb\PlusOneWeb.exe') -Destination $compiledExePath -Force
    Copy-Item -LiteralPath (Join-Path $scriptDir 'dist\PlusOneWeb\_internal') -Destination $compiledInternalDir -Recurse -Force

    if (-not (Test-Path -LiteralPath (Join-Path $compiledDir 'PlusOneConfig.json'))) {
        Copy-Item -LiteralPath (Join-Path $scriptDir 'PlusOneConfig.json') -Destination (Join-Path $compiledDir 'PlusOneConfig.json') -Force
    }

    Write-Host "Built $compiledDir\PlusOneWeb.exe"
}
finally {
    Pop-Location
}
