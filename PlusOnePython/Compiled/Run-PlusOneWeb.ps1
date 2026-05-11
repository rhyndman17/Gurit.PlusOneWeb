<#
.SYNOPSIS
    Starts the PlusOne web UI and opens it in the default browser.
.DESCRIPTION
    Keep this script in the same folder as PlusOneWeb.exe and PlusOneConfig.json.
    It is suitable for launching from Dynamics GP or a desktop shortcut.
#>

param (
    [ValidateSet('NZ', 'AU')]
    [string]$Site = 'NZ',

    [string]$HostName = '127.0.0.1',
    [int]$Port = 8088
)

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSScriptRoot) {
    $PSScriptRoot
}
else {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}

$exePath = Join-Path $scriptDir 'PlusOneWeb.exe'
$configPath = Join-Path $scriptDir 'PlusOneConfig.json'

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Executable not found: $exePath"
}

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Configuration file not found: $configPath"
}

$resolvedExePath = (Resolve-Path -LiteralPath $exePath).Path
Get-CimInstance Win32_Process |
    Where-Object { $_.ExecutablePath -eq $resolvedExePath } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Process -FilePath $exePath -ArgumentList @(
    '--config', $configPath,
    '--host', $HostName,
    '--port', $Port,
    '--site', $Site,
    '--user', $env:USERNAME,
    '--open-browser'
) -WindowStyle Hidden
