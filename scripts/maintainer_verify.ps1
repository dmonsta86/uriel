[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
    [switch]$Fast,
    [switch]$KeepEnvironment
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $RepositoryRoot

function Assert-Exit([string]$Label) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

if (-not (Test-Path -LiteralPath "pyproject.toml")) {
    throw "pyproject.toml was not found at $RepositoryRoot"
}

$venv = Join-Path $RepositoryRoot ".maintainer-venv"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $launcher) {
        & $launcher.Source -3 -m venv $venv
    }
    else {
        $systemPython = Get-Command python -ErrorAction Stop
        & $systemPython.Source -m venv $venv
    }
    Assert-Exit "creating maintainer virtual environment"
}

& $python -m pip install --upgrade pip "setuptools>=77" wheel build
Assert-Exit "installing maintainer build tools"

& $python -m pip install --no-deps --no-build-isolation -e .
Assert-Exit "installing Uriel in editable mode"

& $python -m compileall -q src tests scripts examples
Assert-Exit "compilation"

& $python -m unittest discover -s tests -v
Assert-Exit "unit tests"

& $python scripts\privacy_sweep.py
Assert-Exit "privacy sweep"

if (-not $Fast) {
    & $python scripts\release_check.py --full --command-timeout 600
    Assert-Exit "full release check"
}

Write-Host "URIEL MAINTAINER VERIFICATION: PASS" -ForegroundColor Green
Write-Host "Repository: $RepositoryRoot"
Write-Host "Python: $python"

if (-not $KeepEnvironment) {
    Write-Host "The reusable environment remains at .maintainer-venv (ignored by Git). Use -KeepEnvironment only as an explicit note; the environment is never deleted automatically."
}
