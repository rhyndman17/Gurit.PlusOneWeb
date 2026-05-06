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

    python -m PyInstaller `
        --onefile `
        --name PlusOneWeb `
        --hidden-import pyodbc `
        --hidden-import paramiko `
        --add-data "PlusOneWebSample;PlusOneWebSample" `
        plusone_web.py

    $compiledDir = Join-Path $scriptDir 'Compiled'
    New-Item -ItemType Directory -Force -Path $compiledDir | Out-Null

    $compiledExePath = Join-Path $compiledDir 'PlusOneWeb.exe'
    Get-CimInstance Win32_Process |
        Where-Object { $_.ExecutablePath -eq $compiledExePath } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

    Copy-Item -LiteralPath (Join-Path $scriptDir 'dist\PlusOneWeb.exe') -Destination $compiledExePath -Force

    if (-not (Test-Path -LiteralPath (Join-Path $compiledDir 'PlusOneConfig.json'))) {
        Copy-Item -LiteralPath (Join-Path $scriptDir 'PlusOneConfig.json') -Destination (Join-Path $compiledDir 'PlusOneConfig.json') -Force
    }

    Write-Host "Built $compiledDir\PlusOneWeb.exe"
}
finally {
    Pop-Location
}
