# Uriel PowerShell 5.1+ convenience wrapper.
# Dot-source this file: . .\scripts\Uriel.ps1

Set-StrictMode -Version 2.0

function Get-UrielPythonCommand {
    [CmdletBinding()]
    param()

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $py) {
        return @($py.Source, '-3')
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @($python.Source)
    }
    $python3 = Get-Command python3 -ErrorAction SilentlyContinue
    if ($null -ne $python3) {
        return @($python3.Source)
    }
    throw 'Python 3.9 or newer was not found on PATH.'
}

function Invoke-Uriel {
    # Keep this as a regular function rather than an advanced function. That
    # makes native CLI tokens such as --version and --json pass through
    # unchanged on Windows PowerShell 5.1 as well as PowerShell 7+.
    $ArgumentList = @($args)

    $python = Get-UrielPythonCommand
    $exe = $python[0]
    $prefix = @()
    if ($python.Count -gt 1) {
        $prefix = $python[1..($python.Count - 1)]
    }

    $portable = Join-Path (Split-Path -Parent $PSScriptRoot) 'dist\uriel.pyz'
    if (Test-Path -LiteralPath $portable) {
        & $exe @prefix $portable @ArgumentList
    }
    else {
        & $exe @prefix -m uriel @ArgumentList
    }
    return $LASTEXITCODE
}

function Initialize-UrielProject {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Question,
        [string] $Title = 'Untitled research question',
        [ValidateSet('public', 'internal', 'confidential', 'restricted')][string] $Privacy = 'public'
    )
    Invoke-Uriel init $Path --title $Title --question $Question --privacy $Privacy
}

function Invoke-UrielAudit {
    [CmdletBinding()]
    param(
        [string] $Root = '.',
        [ValidateSet('exploratory', 'standard', 'strict', 'submission')][string] $Profile = 'standard',
        [switch] $Json
    )
    $arguments = @('audit', '--root', $Root, '--profile', $Profile)
    if ($Json) { $arguments = @('--json') + $arguments }
    Invoke-Uriel @arguments
}

function New-UrielSnapshot {
    [CmdletBinding()]
    param([string] $Root = '.', [switch] $Index)
    $arguments = @('snapshot', '--root', $Root)
    if ($Index) { $arguments += '--index' }
    Invoke-Uriel @arguments
}

function New-UrielBlessing {
    [CmdletBinding()]
    param([string] $Root = '.')
    Invoke-Uriel blessing --root $Root
}

function Test-UrielProject {
    [CmdletBinding()]
    param([string] $Root = '.')
    Invoke-Uriel verify --root $Root
}
