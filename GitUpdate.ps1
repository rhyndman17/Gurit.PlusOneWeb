param(
    [string]$Message = "#$(Get-Date -Format 'yyyy.M.d-HHmm')"
)

$ErrorActionPreference = 'Stop'

Set-Location "C:\_______PlusOneDevSpace"

git status --short

if (-not (git status --porcelain)) {
    Write-Host "No changes to commit."
    exit 0
}

git add --all
git commit -m $Message
git push

Write-Host "Pushed commit $Message to GitHub."
