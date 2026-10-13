# Tu mo lai phien Claude Remote Control sau khi may khoi dong lai hoac phien bi tat.
# Danh sach thu muc: thu-muc-phien.txt (moi dong 1 thu muc lam viec). Toi da 5 phien de khong can RAM.
# Moi thu muc chay 'claude remote-control' trong vong lap: tat thi doi 60 giay roi mo lai.
# Tham so: -CaiLich => dang ky chay luc dang nhap Windows (can Admin).
param([switch]$CaiLich, [string]$ThuMuc)
$noi = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $noi 'giu-phien-rc.log'
function Ghi($s) { Add-Content -Path $log -Value ((Get-Date).ToString('dd/MM HH:mm:ss') + '  ' + $s) -Encoding UTF8 }
if ($CaiLich) {
  $act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`""
  $trg = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  $trg.Delay = 'PT2M'   # doi 2 phut cho mang + Google Drive len truoc
  Register-ScheduledTask -TaskName 'DMV Giu Phien Remote Control' -Action $act -Trigger $trg -Force | Out-Null
  Write-Host 'Da dang ky "DMV Giu Phien Remote Control" chay khi dang nhap.'; exit
}
if ($ThuMuc) {
  # Vong lap cho 1 thu muc (chay trong cua so rieng)
  Set-Location $ThuMuc
  while ($true) {
    Ghi "Mo phien: $ThuMuc"
    & claude remote-control
    Ghi "Phien tat (ma $LASTEXITCODE): $ThuMuc - mo lai sau 60 giay"
    Start-Sleep -Seconds 60
  }
}
$ds = Get-Content (Join-Path $noi 'thu-muc-phien.txt') -ErrorAction SilentlyContinue | Where-Object { $_.Trim() -and -not $_.StartsWith('#') } | Select-Object -First 5
if (-not $ds) { Ghi 'Chua co thu muc nao trong thu-muc-phien.txt'; exit }
foreach ($d in $ds) {
  if (-not (Test-Path $d)) { Ghi "Bo qua, khong co thu muc: $d"; continue }
  # Khong mo trung: neu da co cua so dang giu thu muc nay thi bo qua
  $dang = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like "*Giu-Phien-RC.ps1*-ThuMuc*$d*" }
  if ($dang) { Ghi "Da dang chay: $d"; continue }
  Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -NoExit -File `"$($MyInvocation.MyCommand.Path)`" -ThuMuc `"$d`"" -WindowStyle Minimized
  Start-Sleep -Seconds 20   # mo lan luot, tranh dung CPU luc khoi dong
}
