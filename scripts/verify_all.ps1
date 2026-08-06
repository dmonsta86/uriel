[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Repository = Split-Path -Parent $PSScriptRoot
Push-Location $Repository
try {
    $python = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        & $python.Source -3 -m compileall -q src tests
        if ($LASTEXITCODE -ne 0) { throw 'compileall failed' }
        & $python.Source -3 -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
        & $python.Source -3 scripts\privacy_sweep.py
        if ($LASTEXITCODE -ne 0) { throw 'privacy sweep failed' }
        & $python.Source -3 scripts\build_portable.py
        if ($LASTEXITCODE -ne 0) { throw 'portable build failed' }
        & $python.Source -3 dist\uriel.pyz --version
        if ($LASTEXITCODE -ne 0) { throw 'portable smoke test failed' }
    }
    else {
        & python -m compileall -q src tests
        if ($LASTEXITCODE -ne 0) { throw 'compileall failed' }
        & python -m unittest discover -s tests -v
        if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
        & python scripts\privacy_sweep.py
        if ($LASTEXITCODE -ne 0) { throw 'privacy sweep failed' }
        & python scripts\build_portable.py
        if ($LASTEXITCODE -ne 0) { throw 'portable build failed' }
        & python dist\uriel.pyz --version
        if ($LASTEXITCODE -ne 0) { throw 'portable smoke test failed' }
    }
    Write-Host 'Uriel verification: PASS'
}
finally {
    Pop-Location
}
