<#
Opt-in Windows Task Scheduler installer for local M10 PIT listings.
Default DRY RUN: no task registered until -Register is supplied.
Runs only while this Windows user is logged in, at Windows LOCAL time.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DailyAt,
    [string]$RuntimeRoot="",
    [ValidateRange(1,20)][int]$DailyLimit=20,
    [string]$TaskName="Meridyen PIT Universe Daily",
    [switch]$Register
)
$ErrorActionPreference="Stop"
if ($DailyAt -notmatch '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$') {
    throw "DailyAt must be Windows local HH:mm (example 09:30)"
}
if (-not $RuntimeRoot) {
    if ($env:S153_RUNTIME_ROOT) {
        $RuntimeRoot=$env:S153_RUNTIME_ROOT
    } else {
        $RuntimeRoot=Join-Path $env:LOCALAPPDATA "S153ResearchTerminal\runtime"
    }
}
if (-not (Test-Path -LiteralPath $RuntimeRoot -PathType Container)) {
    throw "M10 writable runtime directory not found"
}
$RuntimeRoot=(Resolve-Path -LiteralPath $RuntimeRoot).Path
$repo=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python=Join-Path $repo ".venv\Scripts\python.exe"
$db=Join-Path $RuntimeRoot "data\runtime\operational.db"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "M10 .venv Python missing (run pip install -e .)"
}
if (-not (Test-Path -LiteralPath $db -PathType Leaf)) {
    throw "Actual installed operational.db missing; refusing wrong runtime"
}
if (-not (Test-Path -LiteralPath (Join-Path $repo ".env") -PathType Leaf)) {
    throw "E:\M10\.env is missing; configure authorized Alpha Vantage key first"
}
$runner=Join-Path $PSScriptRoot "run_phase14_daily_pit.ps1"
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Required PIT daily runner missing"
}
if ($RuntimeRoot.Contains('"') -or $runner.Contains('"') -or $TaskName.Contains('"')) {
    throw "Double quotes in paths/task name are unsupported"
}
$scriptArgs='-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $runner + '" -RuntimeRoot "' + $RuntimeRoot + '" -DailyLimit ' + $DailyLimit
$at=[datetime]::ParseExact($DailyAt,"HH:mm",
    [System.Globalization.CultureInfo]::InvariantCulture)
Write-Host "Task: $TaskName"
Write-Host "Scheduled time (Windows local): $DailyAt"
Write-Host "Real runtime: $RuntimeRoot"
Write-Host "Daily max Alpha Vantage requests by THIS task: $DailyLimit"
Write-Host "Already saved months skipped; API credentials never printed"
Write-Host "Computer must be powered on; task requires user logged in"
if (-not $Register) {
    Write-Host "DRY RUN: Task NOT registered. Add -Register to enable."
    return
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task already exists, refusing to overwrite it"
}
$ps=Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$action=New-ScheduledTaskAction -Execute $ps -Argument $scriptArgs -WorkingDirectory $repo
$trigger=New-ScheduledTaskTrigger -Daily -At $at
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Meridyen local US PIT listings resume, max 20 Alpha Vantage requests per UTC day, no model activation" | Out-Null
Write-Host "REGISTERED: $TaskName"
Write-Host ("Check progress: powershell -File scripts/run_phase14_daily_pit.ps1 -RuntimeRoot " + $RuntimeRoot + " -StatusOnly")
