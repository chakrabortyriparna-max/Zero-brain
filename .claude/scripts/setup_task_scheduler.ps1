# Requires -RunAsAdministrator
<#
.SYNOPSIS
    Set up Windows Task Scheduler jobs for Second Brain Phase 6.

.DESCRIPTION
    Creates two scheduled tasks:
      1. SecondBrain-Heartbeat  — runs every 30 minutes, 8 AM – 10 PM IST
      2. SecondBrain-DailyReflect — runs daily at 8:00 AM IST

.PARAMETER WorkingDirectory
    Absolute path to the second-brain-starter project root.

.PARAMETER PythonPath
    Path to python.exe. Defaults to the python in PATH.

.EXAMPLE
    .\setup_task_scheduler.ps1 -WorkingDirectory "C:\Users\chakr\OneDrive\Desktop\zero BRAIN\second-brain-starter"
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$WorkingDirectory,

    [string]$PythonPath = (Get-Command python).Source
)

$heartbeatScript   = Join-Path $WorkingDirectory ".claude\scripts\heartbeat.py"
$reflectScript     = Join-Path $WorkingDirectory ".claude\scripts\memory_reflect.py"
$darkFactoryScript = Join-Path $WorkingDirectory ".claude\dark-factory\orchestrator.py"

# Remove old tasks if they exist (idempotent re-run)
$tasks = @("SecondBrain-Heartbeat", "SecondBrain-DailyReflect", "SecondBrain-DarkFactory")
foreach ($t in $tasks) {
    $existing = Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $t -Confirm:$false
        Write-Host "Removed old task: $t"
    }
}

# Heartbeat: every 30 min, 8 AM – 10 PM IST
$heartbeatAction  = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$heartbeatScript`"" -WorkingDirectory $WorkingDirectory
$heartbeatTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$heartbeatTrigger.Repetition = $(New-ScheduledTaskTrigger -Once -At "08:00" -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 14)).Repetition
$heartbeatSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "SecondBrain-Heartbeat" -Action $heartbeatAction -Trigger $heartbeatTrigger -Settings $heartbeatSettings -Description "Second Brain Heartbeat: polls Gmail/Slack/GitHub every 30 minutes"
Write-Host "Created: SecondBrain-Heartbeat (every 30 min, 8 AM – 10 PM)"

# Daily Reflection: once daily at 8:00 AM IST
$reflectAction  = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$reflectScript`"" -WorkingDirectory $WorkingDirectory
$reflectTrigger = New-ScheduledTaskTrigger -Daily -At "08:00"
$reflectSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "SecondBrain-DailyReflect" -Action $reflectAction -Trigger $reflectTrigger -Settings $reflectSettings -Description "Second Brain Daily Reflection: promotes items to MEMORY.md at 8 AM"
Write-Host "Created: SecondBrain-DailyReflect (daily at 8:00 AM)"

# Dark Factory: every 30 minutes, all day (needs network)
$dfAction  = New-ScheduledTaskAction -Execute $PythonPath -Argument "`"$darkFactoryScript`" --once" -WorkingDirectory $WorkingDirectory
$dfTrigger = New-ScheduledTaskTrigger -Daily -At "00:00"
$dfTrigger.Repetition = $(New-ScheduledTaskTrigger -Once -At "00:00" -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 24)).Repetition
$dfSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable
Register-ScheduledTask -TaskName "SecondBrain-DarkFactory" -Action $dfAction -Trigger $dfTrigger -Settings $dfSettings -Description "Dark Factory: polls GitHub issues/PRs and dispatches Archon workflows every 30 minutes"
Write-Host "Created: SecondBrain-DarkFactory (every 30 min, 24/7)"

Write-Host "`nDone. Verify with: Get-ScheduledTask | Where-Object { `$_.TaskName -like 'SecondBrain*' }"
