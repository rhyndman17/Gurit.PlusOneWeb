<#
.SYNOPSIS
    Runs the compiled PlusOne executable.
.DESCRIPTION
    Wrapper for PlusOneWeb.exe. Keep this script in the same folder as PlusOneWeb.exe
    and PlusOneConfig.json.
.EXAMPLE
    .\Run-PlusOne.ps1 -Command download-import -Site NZ
.EXAMPLE
    .\Run-PlusOne.ps1 -Command extract -Site AU -Extraction GLM,SUP,PUR
.EXAMPLE
    .\Run-PlusOne.ps1 -Command upload -Site NZ
#>

param (
    [Parameter(Mandatory = $true)]
    [ValidateSet('download-import', 'extract', 'upload')]
    [string]$Command,

    [Parameter(Mandatory = $true)]
    [ValidateSet('NZ', 'AU')]
    [string]$Site,

    [string[]]$Extraction = @('All'),

    [datetime]$RunDate = (Get-Date),

    [switch]$SkipDownload,

    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

$scriptDir = if ($PSCommandPath) {
    Split-Path -Parent $PSCommandPath
}
elseif ($PSScriptRoot) {
    $PSScriptRoot
}
elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
else {
    throw 'Cannot determine script directory.'
}

$exePath = Join-Path $scriptDir 'PlusOneWeb.exe'
$configPath = Join-Path $scriptDir 'PlusOneConfig.json'

if (-not (Test-Path -LiteralPath $exePath)) {
    throw "Executable not found: $exePath"
}

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Configuration file not found: $configPath"
}

$arguments = @(
    '--config', $configPath,
    $Command,
    '--site', $Site
)

if ($Command -eq 'download-import' -and $SkipDownload) {
    $arguments += '--skip-download'
}

if ($Command -eq 'extract') {
    $arguments += '--extraction'
    $arguments += $Extraction
    $arguments += '--run-date'
    $arguments += $RunDate.ToString('yyyy-MM-dd')
}

if ($WhatIf) {
    $arguments += '--what-if'
}

& $exePath @arguments
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "PlusOneWeb.exe failed with exit code $exitCode."
}
