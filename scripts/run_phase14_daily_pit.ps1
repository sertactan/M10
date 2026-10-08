<#
Phase14 local daily PIT task entrypoint. Requires local Python and DB.
No API keys are printed.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RuntimeRoot,
    [ValidateRange(1,20)][int]$DailyLimit=20,
    [switch]$StatusOnly
)
$ErrorActionPreference="Stop"
$repo=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python=Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing M10 Python .venv. Install dependencies in E:\M10."
}
if (-not (Test-Path -LiteralPath $RuntimeRoot -PathType Container)) {
    throw "Actual M10 runtime directory not found."
}
$runtime=(Resolve-Path -LiteralPath $RuntimeRoot).Path
$database=Join-Path $runtime "data\runtime\operational.db"
if (-not $StatusOnly -and -not (Test-Path -LiteralPath $database -PathType Leaf)) {
    throw "Actual operational.db not found; refusing new/empty DB."
}
$env:S153_RUNTIME_ROOT=$runtime
Push-Location $repo
try {
    $argsList=@("-m","scripts.pit_daily_sync","--runtime-root",$runtime,
                "--daily-limit",[string]$DailyLimit)
    if ($StatusOnly) { $argsList += "--status-only" }
    & $python @argsList
    $result=$LASTEXITCODE
} finally { Pop-Location }
exit $result
