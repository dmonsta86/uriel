<#
.SYNOPSIS
Publishes a local Uriel source checkout to GitHub using official browser authentication.

.DESCRIPTION
The script never asks for or stores a GitHub password, cookie, recovery code, or
personal access token. It uses GitHub CLI's browser/device-code flow, binds the
package metadata to the authenticated OWNER/REPOSITORY, runs Uriel's offline
release check, initializes Git when needed, commits the verified source under
the authenticated maintainer's GitHub noreply identity, creates or attaches the
repository, and pushes main.
#>
[CmdletBinding()]
param(
    [string]$Repository = "uriel",
    [ValidateSet("public", "private", "internal")]
    [string]$Visibility = "public",
    [string]$Description = "Offline-first research integrity harness, Three-Gate auditor, and SHA-256 provenance ledger",
    [switch]$OpenInBrowser,
    [switch]$SkipLocalCheck
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $RepoRoot

function Require-Command {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$InstallHint
    )
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. $InstallHint"
    }
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE. No source files were deleted."
    }
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    if (Get-Command "py" -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
    }
    elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
        & python @Arguments
    }
    elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
        & python3 @Arguments
    }
    else {
        throw "Python 3.9+ was not found. Install Python, then reopen PowerShell."
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE. No source files were deleted."
    }
}

function Normalize-Remote {
    param([string]$Value)
    if (-not $Value) { return "" }
    $normalized = $Value.Trim()
    $normalized = $normalized -replace '^git@github\.com:', 'https://github.com/'
    $normalized = $normalized -replace '^ssh://git@github\.com/', 'https://github.com/'
    $normalized = $normalized.TrimEnd('/')
    if (-not $normalized.EndsWith('.git')) { $normalized += '.git' }
    return $normalized.ToLowerInvariant()
}

try {
    Require-Command -Name "git" -InstallHint "Install Git for Windows or GitHub Desktop, then reopen PowerShell."
    Require-Command -Name "gh" -InstallHint "Install GitHub CLI with: winget install --id GitHub.cli"

    & gh auth status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "GitHub will open its official browser/device-code sign-in." -ForegroundColor Cyan
        Write-Host "Do not paste a password, token, cookie, or recovery code into this script." -ForegroundColor Cyan
        Invoke-Checked -Label "GitHub authentication" -Command { & gh auth login --web --git-protocol https }
    }
    Invoke-Checked -Label "Git credential setup" -Command { & gh auth setup-git }

    $Owner = (& gh api user --jq '.login').Trim()
    $UserId = (& gh api user --jq '.id').Trim()
    if (-not $Owner -or -not $UserId) {
        throw "Could not determine the authenticated GitHub account."
    }

    if ($Repository -notmatch '^[A-Za-z0-9._-]{1,100}$') {
        throw "Repository must contain only letters, numbers, periods, underscores, or hyphens."
    }
    $Slug = "$Owner/$Repository"
    $ExpectedOrigin = "https://github.com/$Slug.git"

    Write-Host "Binding release metadata to https://github.com/$Slug" -ForegroundColor Cyan
    Invoke-Python -Arguments @("scripts/configure_repository.py", "--slug", $Slug)

    if (-not $SkipLocalCheck) {
        Write-Host "Running the offline Uriel release check before any push..." -ForegroundColor Cyan
        Invoke-Python -Arguments @("scripts/release_check.py")
    }

    if (-not (Test-Path ".git")) {
        & git init -b main 2>$null
        if ($LASTEXITCODE -ne 0) {
            Invoke-Checked -Label "git init" -Command { & git init }
            Invoke-Checked -Label "main branch creation" -Command { & git branch -M main }
        }
    }
    else {
        Invoke-Checked -Label "main branch selection" -Command { & git branch -M main }
    }

    $CurrentName = (& git config --local user.name 2>$null)
    $CurrentEmail = (& git config --local user.email 2>$null)
    if (-not $CurrentName -or $CurrentName -eq "Uriel Bootstrap") {
        Invoke-Checked -Label "Git author configuration" -Command { & git config --local user.name $Owner }
    }
    if (-not $CurrentEmail -or $CurrentEmail -eq "uriel-bootstrap@example.invalid" -or $CurrentEmail -match '@example\.invalid$') {
        Invoke-Checked -Label "Git email configuration" -Command { & git config --local user.email "$UserId+$Owner@users.noreply.github.com" }
    }

    $Origin = (& git remote get-url origin 2>$null)
    if ($Origin -and (Normalize-Remote $Origin) -ne (Normalize-Remote $ExpectedOrigin)) {
        throw "The existing origin points to '$Origin', not '$ExpectedOrigin'. Remove or rename that remote before publishing."
    }

    Invoke-Checked -Label "git add" -Command { & git add --all }
    & git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        $HasHead = $true
        & git rev-parse --verify HEAD *> $null
        if ($LASTEXITCODE -ne 0) { $HasHead = $false }
        if ($HasHead) {
            Invoke-Checked -Label "git commit" -Command { & git commit -m "Prepare Uriel for public GitHub release" }
        }
        else {
            Invoke-Checked -Label "git commit" -Command { & git commit -m "Initial public release candidate for Uriel 1.0.0" }
        }
    }

    & gh repo view $Slug *> $null
    $RepoExists = ($LASTEXITCODE -eq 0)

    if (-not $Origin) {
        if (-not $RepoExists) {
            $VisibilityFlag = "--$Visibility"
            Invoke-Checked -Label "GitHub repository creation" -Command {
                & gh repo create $Slug $VisibilityFlag --description $Description --source $RepoRoot --remote origin
            }
        }
        else {
            Invoke-Checked -Label "origin configuration" -Command { & git remote add origin $ExpectedOrigin }
        }
    }

    Invoke-Checked -Label "Git push" -Command { & git push -u origin main }

    # These repository settings are conveniences. Their failure does not undo a successful push.
    & gh repo edit $Slug --enable-issues=true --enable-wiki=false *> $null

    Write-Host ""
    Write-Host "Published: https://github.com/$Slug" -ForegroundColor Green
    Write-Host "Next: open Actions and confirm every CI job is green before tagging a release." -ForegroundColor Yellow
    Write-Host "Release-candidate command: git tag -a v1.0.0-rc1 -m 'Uriel 1.0.0 release candidate 1'; git push origin v1.0.0-rc1" -ForegroundColor Yellow

    if ($OpenInBrowser) {
        & gh repo view $Slug --web
    }
}
finally {
    Pop-Location
}
