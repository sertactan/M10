<#
 Phase 13 single-entry Windows diagnostic and optional production execution.
 Runs on the SAME Windows host/volume as the actual M10 operational.db.
 No market data download and no trading. By default diagnostic ONLY.
 Full WF9 execution/activation requires -Execute and passing native preflight.
#>
[CmdletBinding()]
param(
    [string]$DbPath = "",
    [string]$Start = "2013-01-01",
    [string]$End = "2024-12-31",
    [switch]$Execute
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
$reportDir = Join-Path (Get-Location) "data/runtime/phase13_readiness"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$reportArgs = @("scripts/phase13_readiness_report.py", "--start", $Start, "--end", $End, "--out-dir", $reportDir, "--report-only")
if ($DbPath) { $reportArgs += @("--db", $DbPath) }
python @reportArgs
if ($LASTEXITCODE -ne 0) { throw "Readiness report could not be produced" }
$reportFile = Join-Path $reportDir "PHASE13_READINESS.json"
$report = Get-Content $reportFile -Raw | ConvertFrom-Json
Write-Host "Phase 13: $($report.status)"
Write-Host "Readiness report: $reportFile"
if ($report.status -ne "PREFLIGHT_READY_NOT_ACTIVATED") {
    Write-Warning "Blocked. Resolve the report's missing PIT/fundamental/adjusted-price inputs first."
    exit 2
}
if (-not $Execute) {
    Write-Host "Preflight ready, but WF9 has NOT been executed or activated. Supply -Execute to authorize it."
    exit 0
}
if (-not $DbPath -and -not $env:S153_RUNTIME_ROOT) {
    Write-Host "Using default source checkout data/runtime/operational.db."
}
if ($DbPath) {
    # Native M10 AppContainer must point at the same runtime data root.
    # An arbitrary external DB passed to the reporter cannot be used to
    # activate a different native M10 DB.
    $expected = if ($env:S153_RUNTIME_ROOT) {
        Join-Path $env:S153_RUNTIME_ROOT "data/runtime/operational.db"
    } else {
        Join-Path (Get-Location) "data/runtime/operational.db"
    }
    if (([IO.Path]::GetFullPath($DbPath)) -ne ([IO.Path]::GetFullPath($expected))) {
        throw "Refusing WF9 activation: --db does not match M10 AppContainer native runtime. Configure S153_RUNTIME_ROOT first."
    }
}
$codeIdentity = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or -not $codeIdentity) {
    throw "Cannot determine code identity for native WF9 run"
}
python scripts/run_wf9_full_execution.py --start $Start --end $End --code-identity $codeIdentity --preflight-only
if ($LASTEXITCODE -ne 0) { throw "Native WF9 preflight failed; production activation blocked" }
$evidencePath = Join-Path (Get-Location) "data/runtime/phase13_readiness/WF9_PRODUCTION_EVIDENCE.json"
python scripts/run_wf9_full_execution.py --start $Start --end $End --code-identity $codeIdentity --output $evidencePath
if ($LASTEXITCODE -ne 0) { throw "WF9 did not return COMPLETE_AND_ACTIVATED" }
$evidence = Get-Content $evidencePath -Raw | ConvertFrom-Json
if ($evidence.report.status -ne "COMPLETE_AND_ACTIVATED") {
    throw "WF9 activation evidence is not complete"
}
Write-Host "WF9 COMPLETE_AND_ACTIVATED. Evidence: $evidencePath"
Write-Host "Next: export historical WF5 signals with scripts/phase13_export_signals.py."
