<#
Meridyen Phase18 — Run local-only checks against the actual M10 runtime.
No data upload, no provider network request, no DB initialization.
No task scheduling, no WF9 activation. Reports stay on Windows.
#>
[CmdletBinding()]
param(
    [string]$RuntimeRoot = "",
    [string]$OperationalDb = "",
    [string]$LearningDb = "",
    [string]$ParquetRoot = "",
    [string]$Start = "2013-01-01",
    [string]$End = "2024-12-31",
    [switch]$ShowReport
)
$ErrorActionPreference="Stop"
$repo=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $RuntimeRoot) {
    $RuntimeRoot = if ($env:S153_RUNTIME_ROOT) { $env:S153_RUNTIME_ROOT } else { $repo }
}
if (-not (Test-Path $RuntimeRoot -PathType Container)) {
    throw "Runtime root missing. Provide -RuntimeRoot pointing at M10's actual writable runtime."
}
$RuntimeRoot=(Resolve-Path $RuntimeRoot).Path
$output=Join-Path $RuntimeRoot "data/runtime/phase18/activation_report.json"
$parts=@("-m","scripts.phase18_storage_readiness",
         "--runtime-root",$RuntimeRoot,"--start",$Start,"--end",$End,
         "--out",$output,"--report-only")
if ($OperationalDb) { $parts+=@("--db",$OperationalDb) }
if ($LearningDb) { $parts+=@("--learning-db",$LearningDb) }
if ($ParquetRoot) { $parts+=@("--parquet-root",$ParquetRoot) }
Push-Location $repo
try {
    # Python is executed in the checked-out M10 root to find the code.
    & python @parts
    if ($LASTEXITCODE -ne 0) { throw "M10 Phase18 check failed" }
} finally {
    Pop-Location
}
$report=Get-Content -LiteralPath $output -Raw | ConvertFrom-Json
Write-Host ("Phase18 status: " + $report.status)
Write-Host ("Database found: " + $report.market_database.present)
Write-Host ("Learning database found: " + $report.learning_database.present)
Write-Host ("Parquet files detected: " + $report.local_parquet.parquet_files)
Write-Host ("Google Drive required: " + $report.drive.required_for_database_queries)
Write-Host ("Report: " + $output)
if ($ShowReport) {
    Write-Host "NEXT ACTIONS:"
    $report.next_actions | ForEach-Object { Write-Host (" - " + $_) }
}
Write-Host "No Google Drive data was uploaded or modified."
