<#
Phase16 — Explicit opt-in Windows Task Scheduler installer.
Defaults to DRY RUN; will not register a task unless -Register is present.
Only schedules a one-shot local Learning V2 cycle; no model auto-training.
The user's Windows session must be logged on for Interactive logon.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DailyAt,
    [Parameter(Mandatory=$true)][string]$LearningDb,
    [Parameter(Mandatory=$true)][string]$BackupDir,
    [string]$TaskName = "Meridyen Learning V2 Daily",
    [string]$RemoteCrypt = "",
    [switch]$EnableCloud,
    [switch]$Register
)
$ErrorActionPreference = "Stop"
$projectRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ($DailyAt -notmatch '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$') {
    throw "DailyAt must be HH:mm in Windows LOCAL time (e.g. 03:00)"
}
if ($LearningDb.Contains('"') -or $BackupDir.Contains('"') -or
    $RemoteCrypt.Contains('"')) {
    throw "Double quotes in path or remote name are unsupported"
}
if (-not [IO.Path]::IsPathRooted($LearningDb) -or -not [IO.Path]::IsPathRooted($BackupDir)) {
    throw "Use absolute LearningDb and BackupDir paths for scheduled jobs"
}
if ($EnableCloud -and -not $RemoteCrypt) {
    throw "EnableCloud requires RemoteCrypt name"
}
if (-not $EnableCloud -and $RemoteCrypt) {
    throw "RemoteCrypt requires explicit EnableCloud"
}
$python=(Get-Command python -ErrorAction Stop).Source
if (-not (Test-Path $python)) { throw "Python executable unavailable" }
if ($EnableCloud) {
    # Test actual remote type=crypt without emitting rclone configuration secrets.
    $env:MERIDYEN_PHASE16_REMOTE=$RemoteCrypt
    Push-Location $projectRoot
    try {
        python -c "import os; from scripts.sync_learning_backup import validate_crypt_remote; validate_crypt_remote(os.environ['MERIDYEN_PHASE16_REMOTE'])"
        if ($LASTEXITCODE -ne 0) { throw "Configured rclone remote is not a verified crypt remote" }
    } finally {
        Pop-Location
        Remove-Item Env:\MERIDYEN_PHASE16_REMOTE -ErrorAction SilentlyContinue
    }
}
$pieces=@('-m','scripts.phase16_learning_cycle',
    '--learning-db',('"' + $LearningDb + '"'),
    '--backup-dir',('"' + $BackupDir + '"'))
if ($EnableCloud) {
    $pieces+=@('--cloud-crypt-remote',$RemoteCrypt,'--execute-cloud')
}
$argsString=$pieces -join ' '
Write-Host "Phase16 task: $TaskName"
Write-Host "Runs daily (Windows local time): $DailyAt"
Write-Host "Working directory: $projectRoot"
Write-Host "Local backup folder: $BackupDir"
Write-Host "Cloud enabled: $EnableCloud"
if (-not $Register) {
    Write-Host "DRY RUN ONLY — no task registered. Add -Register to opt in."
    return
}
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    throw "Task name already exists; refusing overwrite"
}
$at=[datetime]::ParseExact($DailyAt,'HH:mm',
    [System.Globalization.CultureInfo]::InvariantCulture)
$action=New-ScheduledTaskAction -Execute $python -Argument $argsString -WorkingDirectory $projectRoot
$trigger=New-ScheduledTaskTrigger -Daily -At $at
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Meridyen Learning V2 evidence audit and verified SQLite backup (no model deployment)" | Out-Null
Write-Host "Task registered. It runs only while this Windows account is logged in."
