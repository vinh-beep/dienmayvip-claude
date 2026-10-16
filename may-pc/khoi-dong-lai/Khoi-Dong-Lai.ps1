# Sua loi "Restart khong duoc, phai bam nut reset".
#  -SuaLoi  : (1) doc nhat ky Windows xem chuong trinh/dich vu nao lam treo luc tat may, ghi len Bridge;
#             (2) cho Windows tu dong ket thuc chuong trinh bi treo khi tat/khoi dong lai (sao luu gia tri cu).
#  -KhoiDong: dong em cac phien Claude/node/WSL roi moi khoi dong lai (thay cho Start > Restart).
#  -GoCai   : tra cac cai dat ve nhu cu.
param([switch]$SuaLoi, [switch]$KhoiDong, [switch]$GoCai)
$ErrorActionPreference = 'Continue'
$noi = Split-Path -Parent $MyInvocation.MyCommand.Path
$saoLuu = Join-Path $noi 'cai-dat-truoc-khi-sua.json'
$log = Join-Path $noi 'khoi-dong-lai.log'
function Ghi($s) { Add-Content -Path $log -Value ((Get-Date).ToString('dd/MM HH:mm:ss') + '  ' + $s) -Encoding UTF8; Write-Host $s }
# Cac gia tri lam Windows tu ket thuc chuong trinh treo khi tat may
$dsSua = @(
  @{ Key = 'HKCU:\Control Panel\Desktop'; Name = 'AutoEndTasks';          Value = '1';    Type = 'String' },
  @{ Key = 'HKCU:\Control Panel\Desktop'; Name = 'WaitToKillAppTimeout';  Value = '5000'; Type = 'String' },
  @{ Key = 'HKCU:\Control Panel\Desktop'; Name = 'HungAppTimeout';        Value = '3000'; Type = 'String' },
  @{ Key = 'HKLM:\SYSTEM\CurrentControlSet\Control'; Name = 'WaitToKillServiceTimeout'; Value = '5000'; Type = 'String' }
)

if ($GoCai) {
  if (-not (Test-Path $saoLuu)) { Write-Host 'Khong co ban sao luu, khong doi gi.'; exit }
  foreach ($m in (Get-Content $saoLuu -Raw | ConvertFrom-Json)) {
    if ($m.Cu -eq $null) { Remove-ItemProperty -Path $m.Key -Name $m.Name -ErrorAction SilentlyContinue }
    else { Set-ItemProperty -Path $m.Key -Name $m.Name -Value $m.Cu }
  }
  Remove-Item $saoLuu; Write-Host 'Da tra cai dat tat may ve nhu cu.'; exit
}

if ($SuaLoi) {
  $tz = [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time')
  $gio = [TimeZoneInfo]::ConvertTime([DateTime]::Now, $tz)
  $tu = (Get-Date).AddDays(-14)
  # (1a) Windows tu do: chuong trinh (202) / dich vu (203) lam cham tat may, tong thoi gian tat may (200)
  $cham = Get-WinEvent -FilterHashtable @{ LogName = 'Microsoft-Windows-Diagnostics-Performance/Operational'; Id = 200,202,203; StartTime = $tu } -ErrorAction SilentlyContinue |
    Sort-Object TimeCreated -Descending | Select-Object -First 40 | ForEach-Object {
      $x = [xml]$_.ToXml(); $d = @{}; $x.Event.EventData.Data | ForEach-Object { $d[$_.Name] = $_.'#text' }
      $ten = if ($d['FriendlyName']) { $d['FriendlyName'] } elseif ($d['Name']) { $d['Name'] } else { '' }
      $ms = if ($d['TotalTime']) { $d['TotalTime'] } elseif ($d['ShutdownTime']) { $d['ShutdownTime'] } else { '' }
      $loai = @{ 200 = 'Tong thoi gian tat may'; 202 = 'Chuong trinh lam cham'; 203 = 'Dich vu lam cham' }[$_.Id]
      "| $($_.TimeCreated.ToString('dd/MM HH:mm')) | $loai | $ten | $ms ms |"
    }
  # (1b) Lan tat may dot ngot (bam reset) va lan khoi dong lai co chu dich
  $tat = Get-WinEvent -FilterHashtable @{ LogName = 'System'; Id = 41,6008,1074; StartTime = $tu } -ErrorAction SilentlyContinue |
    Sort-Object TimeCreated -Descending | Select-Object -First 30 | ForEach-Object {
      $m = ($_.Message -split "`n")[0].Trim(); if ($m.Length -gt 120) { $m = $m.Substring(0,120) + '...' }
      "| $($_.TimeCreated.ToString('dd/MM HH:mm')) | $($_.Id) | $m |"
    }
  # (1c) Ung dung bi treo / dung (Application Hang 1002, Error 1000)
  $treo = Get-WinEvent -FilterHashtable @{ LogName = 'Application'; Id = 1000,1002; StartTime = $tu } -ErrorAction SilentlyContinue |
    Sort-Object TimeCreated -Descending | Select-Object -First 25 | ForEach-Object {
      $m = ($_.Message -split "`n")[0].Trim(); if ($m.Length -gt 120) { $m = $m.Substring(0,120) + '...' }
      "| $($_.TimeCreated.ToString('dd/MM HH:mm')) | $($_.Id) | $m |"
    }
  $sl = @(Get-Process node -ErrorAction SilentlyContinue).Count
  $cl = @(Get-Process | Where-Object { $_.ProcessName -match '^(claude|Claude)' }).Count
  $wsl = @(Get-Process vmmem*, wsl* -ErrorAction SilentlyContinue).Count

  # (2) Cho Windows tu ket thuc chuong trinh treo khi tat may (sao luu 1 lan)
  if (-not (Test-Path $saoLuu)) {
    $cu = foreach ($m in $dsSua) { [pscustomobject]@{ Key = $m.Key; Name = $m.Name; Cu = (Get-ItemProperty -Path $m.Key -Name $m.Name -ErrorAction SilentlyContinue).($m.Name) } }
    $cu | ConvertTo-Json | Set-Content -Path $saoLuu -Encoding UTF8
  }
  foreach ($m in $dsSua) { Set-ItemProperty -Path $m.Key -Name $m.Name -Value $m.Value -Type $m.Type }

  $md = @"
# Loi khoi dong lai - may $env:COMPUTERNAME - $($gio.ToString('dd/MM/yyyy HH:mm')) (gio VN)
14 ngay gan nhat. Chi doc nhat ky; da bat "tu ket thuc chuong trinh treo khi tat may" (go: Go-Khoi-Dong-Lai.bat).

Dang chay: $cl tien trinh Claude, $sl tien trinh node, $wsl tien trinh WSL.

## 1. Windows ghi lai cai gi lam cham / treo luc tat may (200 = tong, 202 = chuong trinh, 203 = dich vu)
| Luc | Loai | Ten | Thoi gian |
|---|---|---|---|
$($cham -join "`n")

## 2. Tat may dot ngot (41, 6008 = bam reset / mat dien) va khoi dong lai co chu dich (1074)
| Luc | Ma | Noi dung |
|---|---|---|
$($tat -join "`n")

## 3. Chuong trinh bi treo / sap
| Luc | Ma | Noi dung |
|---|---|---|
$($treo -join "`n")
"@
  $bridge = @('G:\My Drive\DMV-Cloud-Bridge','C:\DMV-Cloud-Bridge') | Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $bridge) { $bridge = $noi }
  $out = Join-Path $bridge "ket-qua-PC-KHOI-DONG-LAI-$env:COMPUTERNAME-moi-nhat.md"
  Set-Content -Path $out -Value $md -Encoding UTF8
  Ghi "Da ghi bao cao: $out. Da bat tu ket thuc chuong trinh treo khi tat may."
  exit
}

if ($KhoiDong) {
  # Dong em truoc, sau 20 giay moi buoc dong, roi khoi dong lai co /f (ep dong chuong trinh con lai)
  Ghi 'Bat dau khoi dong lai an toan.'
  foreach ($ten in @('claude','Claude','node')) {
    Get-Process -Name $ten -ErrorAction SilentlyContinue | ForEach-Object { try { $_.CloseMainWindow() | Out-Null } catch {} }
  }
  Start-Sleep -Seconds 20
  $con = @(Get-Process -Name claude, Claude, node -ErrorAction SilentlyContinue)
  if ($con.Count) { Ghi "Buoc dong $($con.Count) tien trinh claude/node con lai"; $con | Stop-Process -Force -ErrorAction SilentlyContinue }
  if (Get-Command wsl.exe -ErrorAction SilentlyContinue) { Ghi 'Tat WSL'; & wsl.exe --shutdown 2>$null }
  Ghi 'Khoi dong lai sau 10 giay (shutdown /r /f).'
  & shutdown.exe /r /f /t 10 /c "DMV: khoi dong lai an toan"
  exit
}
Write-Host 'Dung: -SuaLoi | -KhoiDong | -GoCai'
