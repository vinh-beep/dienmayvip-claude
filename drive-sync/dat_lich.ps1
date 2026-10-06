# Dat lich Task Scheduler cho dong bo Drive. Mac dinh CHI IN ra, khong dang ky gi.
# Chay that:  powershell -ExecutionPolicy Bypass -File dat_lich.ps1 -XacNhan
param(
    [string]$Python = "python",
    [string]$Thu_Muc = "C:\DMV_DongBoDrive",
    [string]$Gio = "02:30",
    [switch]$XacNhan
)

$script = Join-Path $Thu_Muc "dong_bo_drive.py"
$config = Join-Path $Thu_Muc "dong_bo.config.json"

$tasks = @(
    @{ Ten = "DMV DongBo Drive";          Args = "`"$script`" --config `"$config`" --chay-that"; Trigger = (New-ScheduledTaskTrigger -Daily -At $Gio) },
    @{ Ten = "DMV DongBo Drive KiemTuoi"; Args = "`"$script`" --config `"$config`" --kiem-tuoi";  Trigger = (New-ScheduledTaskTrigger -Once -At "06:00" -RepetitionInterval (New-TimeSpan -Hours 6)) }
)

foreach ($t in $tasks) {
    Write-Host ("Task: {0}`n  Lenh: {1} {2}" -f $t.Ten, $Python, $t.Args)
    if (-not $XacNhan) { continue }
    $action   = New-ScheduledTaskAction -Execute $Python -Argument $t.Args -WorkingDirectory $Thu_Muc
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $t.Ten -Action $action -Trigger $t.Trigger -Settings $settings -Force | Out-Null
    Write-Host "  Da dang ky."
}
if (-not $XacNhan) { Write-Host "`nChua dang ky gi. Them -XacNhan de dang ky that." }
