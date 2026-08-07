[CmdletBinding()]
param(
    [string]$Repository = "dmonsta86/uriel",
    [string]$Branch = "main",
    [string]$CommitPrefix = "",
    [string]$OutputDirectory = "$HOME\Desktop\uriel-ci-diagnostics"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI is not installed. Install it with: winget install --id GitHub.cli --exact --source winget"
}

& gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run: gh auth login --web"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$runs = & gh run list `
    --repo $Repository `
    --branch $Branch `
    --limit 30 `
    --json databaseId,headSha,conclusion,status,url,workflowName,createdAt |
    ConvertFrom-Json

$candidates = @($runs | Where-Object { $_.workflowName -eq "CI" })
if ($CommitPrefix) {
    $run = $candidates | Where-Object { $_.headSha -like "$CommitPrefix*" } | Select-Object -First 1
}
else {
    $run = $candidates | Select-Object -First 1
}

if ($null -eq $run) {
    throw "No matching CI workflow run was found for $Repository on $Branch."
}

$summaryPath = Join-Path $OutputDirectory "run-$($run.databaseId)-summary.txt"
$failedPath = Join-Path $OutputDirectory "run-$($run.databaseId)-failed-steps.txt"

@(
    "Uriel GitHub Actions diagnostic",
    "repository: $Repository",
    "branch: $Branch",
    "run_id: $($run.databaseId)",
    "head_sha: $($run.headSha)",
    "status: $($run.status)",
    "conclusion: $($run.conclusion)",
    "url: $($run.url)",
    "captured_utc: $([DateTime]::UtcNow.ToString('o'))",
    "",
    "===== RUN SUMMARY ====="
) | Set-Content -LiteralPath $summaryPath -Encoding UTF8

& gh run view $run.databaseId --repo $Repository --verbose 2>&1 |
    Add-Content -LiteralPath $summaryPath -Encoding UTF8

& gh run view $run.databaseId --repo $Repository --log-failed 2>&1 |
    Set-Content -LiteralPath $failedPath -Encoding UTF8

Write-Host "CI run: $($run.url)" -ForegroundColor Cyan
Write-Host "Summary: $summaryPath" -ForegroundColor Green
Write-Host "Failed logs: $failedPath" -ForegroundColor Green
Write-Host "The files contain no GitHub password or token, but inspect them before sharing because job output can include project paths or environment details." -ForegroundColor Yellow
