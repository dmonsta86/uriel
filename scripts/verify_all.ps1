[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Repository = Split-Path -Parent $PSScriptRoot
Push-Location $Repository
try {
    # Prefer the repository venv, then the py launcher, then PATH python.
    $venvPython = Join-Path $Repository '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $python = $venvPython
        $pythonArgs = @()
    }
    elseif ($null -ne (Get-Command py -ErrorAction SilentlyContinue)) {
        $python = (Get-Command py).Source
        $pythonArgs = @('-3')
    }
    else {
        $python = 'python'
        $pythonArgs = @()
    }

    # Bootstrap the source tree when uriel is not installed in the chosen interpreter.
    $probeEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $python @pythonArgs -c 'import uriel' 2>$null
    $urielImportable = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $probeEap
    if (-not $urielImportable) {
        $src = Join-Path $Repository 'src'
        $env:PYTHONPATH = if ($env:PYTHONPATH) { "$src$([IO.Path]::PathSeparator)$env:PYTHONPATH" } else { $src }
        Write-Host "Uriel not importable in $python; using PYTHONPATH=$src"
    }

    & $python @pythonArgs -m compileall -q src tests
    if ($LASTEXITCODE -ne 0) { throw 'compileall failed' }
    & $python @pythonArgs -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'tests failed' }
    & $python @pythonArgs scripts\privacy_sweep.py
    if ($LASTEXITCODE -ne 0) { throw 'privacy sweep failed' }
    & $python @pythonArgs scripts\build_portable.py
    if ($LASTEXITCODE -ne 0) { throw 'portable build failed' }
    & $python @pythonArgs dist\uriel.pyz --version
    if ($LASTEXITCODE -ne 0) { throw 'portable smoke test failed' }
    Write-Host 'Uriel verification: PASS'
}
finally {
    Pop-Location
}
