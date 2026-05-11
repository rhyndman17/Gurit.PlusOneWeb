<#
.SYNOPSIS
    Runs PlusOne extract and upload for NZ and AU.
.DESCRIPTION
    Wrapper for PlusOneWeb.exe. Keep this script in the same folder as PlusOneWeb.exe
    and PlusOneConfig.json.
.EXAMPLE
    .\Run-ExtractUpload.ps1
.EXAMPLE
    .\Run-ExtractUpload.ps1 -WhatIf
.EXAMPLE
    .\Run-ExtractUpload.ps1 -Sites NZ -Extraction GLM,SUP,PUR
#>

param (
    [Parameter(Position = 0)]
    [ValidateSet('NZ', 'AU')]
    [string[]]$Sites = @('NZ', 'AU'),

    [Parameter(Position = 1)]
    [string[]]$Extraction = @('All'),

    [datetime]$RunDate = (Get-Date),

    [switch]$WhatIf,

    [switch]$KeepGoing
)

$ErrorActionPreference = 'Stop'

foreach ($name in $Extraction) {
    if ($name -in @('NZ', 'AU')) {
        throw "Site '$name' was passed as an extraction. Use -Sites NZ,AU instead of -Sites NZ AU."
    }
}

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

$failedSites = New-Object System.Collections.Generic.List[string]

foreach ($site in $Sites) {
    Write-Host ""
    Write-Host "=== $site`: extract then upload ==="

    $extractArguments = @(
        '--config', $configPath,
        'extract',
        '--site', $site,
        '--extraction'
    )
    $extractArguments += $Extraction
    $extractArguments += @('--run-date', $RunDate.ToString('yyyy-MM-dd'))

    if ($WhatIf) {
        $extractArguments += '--what-if'
    }

    & $exePath @extractArguments
    if ($LASTEXITCODE -ne 0) {
        $failedSites.Add($site)
        Write-Warning "$site extract failed; upload skipped."
        if (-not $KeepGoing) {
            break
        }
        continue
    }

    $uploadArguments = @(
        '--config', $configPath,
        'upload',
        '--site', $site
    )

    if ($WhatIf) {
        $uploadArguments += '--what-if'
    }

    & $exePath @uploadArguments
    if ($LASTEXITCODE -ne 0) {
        $failedSites.Add($site)
        if (-not $KeepGoing) {
            break
        }
    }
}

if ($failedSites.Count -gt 0) {
    throw "Extract/upload failed for site(s): $($failedSites -join ', ')"
}

Write-Host ""
Write-Host "Extract/upload completed successfully."
