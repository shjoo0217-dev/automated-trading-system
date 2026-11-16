param([string]$DatasetRoot = (Split-Path -Parent $PSScriptRoot))
$ErrorActionPreference = 'Stop'
$DatasetRoot = (Resolve-Path $DatasetRoot).Path
if ((Get-TimeZone).Id -ne 'Korea Standard Time') {
    throw 'Tasks use KST. Confirm the Windows time zone is Korea Standard Time before installation.'
}
$PythonExe = Join-Path $DatasetRoot '.venv\Scripts\python.exe'
$JobScript = Join-Path $DatasetRoot 'windows\run_job.py'
$PlanScript = Join-Path $DatasetRoot 'windows\schedule_plan.py'
if (-not (Test-Path $PythonExe)) { throw 'Run windows\setup_windows.cmd first.' }
$PlanJson = & $PythonExe -X utf8 $PlanScript --root $DatasetRoot
if ($LASTEXITCODE -ne 0) { throw 'Invalid schedule configuration.' }
$Plan = $PlanJson | ConvertFrom-Json
$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $Identity -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $Plan.timeout_minutes) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 3)
foreach ($Mode in @('collect','train')) {
    $TaskName = if ($Mode -eq 'collect') {'KIRSInvestment-Collect'} else {'KIRSInvestment-Train'}
    $Arguments = '-X utf8 "{0}" --root "{1}" --mode {2}' -f $JobScript,$DatasetRoot,$Mode
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument $Arguments -WorkingDirectory $DatasetRoot
    if ($Mode -eq 'collect') {
        $Triggers = @($Plan.collect_times | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ })
    } else {
        $Triggers = @(New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek $Plan.train_day -At $Plan.train_time)
    }
    $Task = New-ScheduledTask -Action $Action -Trigger $Triggers -Settings $Settings -Principal $Principal `
        -Description 'KIRS metadata collection / data validation. No trading orders.'
    Register-ScheduledTask -TaskName $TaskName -InputObject $Task -Force | Out-Null
    Get-ScheduledTaskInfo -TaskName $TaskName | Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
}
