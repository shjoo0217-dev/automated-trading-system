$ErrorActionPreference = 'Stop'
foreach ($TaskName in @('KIRSInvestment-Collect','KIRSInvestment-Train')) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output ('Removed '+$TaskName+'; datasets and checkpoints retained.')
    }
}
