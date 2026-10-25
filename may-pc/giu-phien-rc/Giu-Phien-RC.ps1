# Tu mo lai phien Claude Remote Control, xu ly 4 nguyen nhan rot:
#  1. Tac vu/nguoi tat tien trinh  -> tac vu canh gac moi 5 phut mo lai vong lap bi tat.
#  2. Mat mang                      -> vong lap doi co mang roi moi mo lai phien.
#  3. Windows cap nhat / khoi dong  -> chay luc dang nhap + chan Windows tu khoi dong lai khi dang dang nhap.
#  4. Het han dang nhap Claude      -> phien tat nhanh 3 lan lien tiep: bao len Bridge + bat hop thoai, doi 30 phut.
# Danh sach thu muc: thu-muc-phien.txt (moi dong 1 thu muc lam viec). Toi da 5 phien de khong can RAM.
# Tham so: -CaiLich => dang ky tac vu (can Admin). -GoCai => go tac vu va tra lai cai dat Windows Update.
param([switch]$CaiLich, [switch]$GoCai, [string]$ThuMuc)
$noi  = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $noi 'giu-phien-rc.log'
$ten  = 'DMV Giu Phien Remote Control'
$auKey = 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU'
$auSaoLuu = Join-Path $noi 'windows-update-truoc-khi-cai.txt'
function Ghi($s) { Add-Content -Path $log -Value ((Get-Date).ToString('dd/MM HH:mm:ss') + '  ' + $s) -Encoding UTF8 }
function CoMang {
  try { $c = New-Object System.Net.Sockets.TcpClient; $ok = $c.ConnectAsync('api.anthropic.com', 443).Wait(5000); $c.Close(); return $ok } catch { return $false }
}

if ($CaiLich) {
  $act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$($MyInvocation.MyCommand.Path)`""
  $t1 = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  $t1.Delay = 'PT2M'   # doi 2 phut cho mang + Google Drive len truoc
  $t2 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes 5)
  $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
  Register-ScheduledTask -TaskName $ten -Action $act -Trigger @($t1, $t2) -Settings $set -Force | Out-Null
  # (3) Khong cho Windows Update tu khoi dong lai khi co nguoi dang dang nhap. Luu gia tri cu de go.
  if (-not (Test-Path $auSaoLuu)) {
    $cu = (Get-ItemProperty -Path $auKey -Name NoAutoRebootWithLoggedOnUsers -ErrorAction SilentlyContinue).NoAutoRebootWithLoggedOnUsers
    Set-Content -Path $auSaoLuu -Value $(if ($null -eq $cu) { 'khong-co' } else { $cu }) -Encoding ASCII
  }
  if (-not (Test-Path $auKey)) { New-Item -Path $auKey -Force | Out-Null }
  Set-ItemProperty -Path $auKey -Name NoAutoRebootWithLoggedOnUsers -Value 1 -Type DWord
  Write-Host "Da dang ky `"$ten`": chay khi dang nhap + canh gac moi 5 phut. Da chan Windows Update tu khoi dong lai khi dang dang nhap."
  exit
}
if ($GoCai) {
  Unregister-ScheduledTask -TaskName $ten -Confirm:$false -ErrorAction SilentlyContinue
  if (Test-Path $auSaoLuu) {
    $cu = (Get-Content $auSaoLuu -Raw).Trim()
    if ($cu -eq 'khong-co') { Remove-ItemProperty -Path $auKey -Name NoAutoRebootWithLoggedOnUsers -ErrorAction SilentlyContinue }
    else { Set-ItemProperty -Path $auKey -Name NoAutoRebootWithLoggedOnUsers -Value ([int]$cu) -Type DWord }
    Remove-Item $auSaoLuu
  }
  Write-Host "Da go `"$ten`" va tra lai cai dat Windows Update."; exit
}

if ($ThuMuc) {
  # Vong lap cho 1 thu muc (chay trong cua so rieng)
  Set-Location $ThuMuc
  $tenPhien = Split-Path -Leaf $ThuMuc
  $nhanh = 0
  while ($true) {
    # (2) Doi co mang moi mo, tranh mo roi tat lien tuc khi mat mang
    if (-not (CoMang)) { Ghi "Mat mang, doi: $ThuMuc"; while (-not (CoMang)) { Start-Sleep -Seconds 30 }; Ghi "Co mang lai: $ThuMuc" }
    Ghi "Mo phien: $ThuMuc"
    $bd = Get-Date
    & claude remote-control --name $tenPhien
    $giay = [int]((Get-Date) - $bd).TotalSeconds
    Ghi "Phien tat (ma $LASTEXITCODE, chay $giay giay): $ThuMuc"
    if ($giay -lt 120) { $nhanh++ } else { $nhanh = 0 }
    if ($nhanh -ge 3) {
      # (4) Tat nhanh 3 lan lien tiep: thuong la het han dang nhap. Can nguoi go /login - bao ngay.
      $bridge = @('G:\My Drive\DMV-Cloud-Bridge','C:\DMV-Cloud-Bridge') | Where-Object { Test-Path $_ } | Select-Object -First 1
      $bao = "Remote Control tai $env:COMPUTERNAME tat ngay sau khi mo 3 lan lien tiep ($ThuMuc). Nhieu kha nang het han dang nhap Claude: mo Claude Code, go /login, roi /remote-control."
      if ($bridge) { Set-Content -Path (Join-Path $bridge "ket-qua-PC-RC-CAN-LOGIN-$env:COMPUTERNAME.md") -Value ("# " + (Get-Date).ToString('dd/MM/yyyy HH:mm') + "`n`n" + $bao) -Encoding UTF8 }
      try { & msg.exe * /TIME:3600 $bao } catch {}
      Ghi "CAN DANG NHAP LAI: $ThuMuc - doi 30 phut"
      Start-Sleep -Seconds 1800; $nhanh = 0
    } else { Start-Sleep -Seconds 60 }
  }
}

# (1) Canh gac: thu muc nao chua co vong lap (bi tat, may vua khoi dong) thi mo lai
$ds = Get-Content (Join-Path $noi 'thu-muc-phien.txt') -ErrorAction SilentlyContinue | Where-Object { $_.Trim() -and -not $_.StartsWith('#') } | Select-Object -First 5
if (-not $ds) { Ghi 'Chua co thu muc nao trong thu-muc-phien.txt'; exit }
$dangChay = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*Giu-Phien-RC.ps1*-ThuMuc*' } | ForEach-Object { $_.CommandLine })
foreach ($d in $ds) {
  $d = $d.Trim()
  if (-not (Test-Path $d)) { Ghi "Bo qua, khong co thu muc: $d"; continue }
  if ($dangChay | Where-Object { $_.Contains("`"$d`"") }) { continue }   # da co vong lap, khong mo trung
  Ghi "Canh gac mo lai vong lap: $d"
  Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -NoExit -File `"$($MyInvocation.MyCommand.Path)`" -ThuMuc `"$d`"" -WindowStyle Minimized
  Start-Sleep -Seconds 20   # mo lan luot, tranh dung CPU luc khoi dong
}
