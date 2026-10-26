# Tim nguyen nhan phien Remote Control rot quanh 00h va 12h. CHI DOC, khong sua gi.
# Doc 4 ngay gan nhat: tac vu theo lich chay quanh gio rot, su kien Windows (ngu, tat may,
# mat mang, doi gio, cap nhat), chuong trinh claude/node bi sap. Ghi ket qua len Bridge.
$ErrorActionPreference = 'SilentlyContinue'
$noi = Split-Path -Parent $MyInvocation.MyCommand.Path
$tz  = [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time')
$gio = [TimeZoneInfo]::ConvertTime([DateTime]::Now, $tz)
$may = $env:COMPUTERNAME
$bridge = @('G:\My Drive\DMV-Cloud-Bridge','C:\DMV-Cloud-Bridge') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bridge) { $bridge = $noi }
$out = Join-Path $bridge "ket-qua-PC-RC-ROT-$may-moi-nhat.md"
$tu  = (Get-Date).AddDays(-4)
# Khung gio nghi van: 23:00-01:59 va 11:00-12:59
function TrongKhung($t) { $h = $t.Hour; return ($h -eq 23 -or $h -le 1 -or $h -eq 11 -or $h -eq 12) }

# 1. Tac vu theo lich co gio chay trong khung nghi van
$tasks = @()
foreach ($t in (Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' })) {
  $info = $t | Get-ScheduledTaskInfo
  $hit = $false; $gioTrg = @()
  foreach ($trg in $t.Triggers) {
    if ($trg.StartBoundary) { $sb = [DateTime]$trg.StartBoundary; $gioTrg += $sb.ToString('HH:mm'); if (TrongKhung $sb) { $hit = $true } }
    if ($trg.Repetition -and $trg.Repetition.Interval) { $gioTrg += ('lap ' + $trg.Repetition.Interval) }
  }
  if ($info.LastRunTime -and $info.LastRunTime -gt $tu -and (TrongKhung $info.LastRunTime)) { $hit = $true }
  if ($hit) {
    $act = ($t.Actions | ForEach-Object { ($_.Execute + ' ' + $_.Arguments).Trim() }) -join ' ; '
    if ($act.Length -gt 140) { $act = $act.Substring(0,140) + '...' }
    $tasks += "| $($t.TaskPath)$($t.TaskName) | $($gioTrg -join ', ') | $(if ($info.LastRunTime) { $info.LastRunTime.ToString('dd/MM HH:mm') }) | $($info.LastTaskResult) | $act |"
  }
}
# Tac vu co chu kill / restart / claude / node / don RAM (bat ke gio)
$nghi = @()
foreach ($t in (Get-ScheduledTask | Where-Object { $_.State -ne 'Disabled' })) {
  $act = ($t.Actions | ForEach-Object { ($_.Execute + ' ' + $_.Arguments) }) -join ' '
  if ($act -match '(?i)taskkill|Stop-Process|shutdown|restart|claude|node\.exe|wsl --shutdown|don.?ram|clean') {
    $info = $t | Get-ScheduledTaskInfo
    $a = $act.Trim(); if ($a.Length -gt 140) { $a = $a.Substring(0,140) + '...' }
    $nghi += "| $($t.TaskPath)$($t.TaskName) | $(if ($info.LastRunTime) { $info.LastRunTime.ToString('dd/MM HH:mm') }) | $(if ($info.NextRunTime) { $info.NextRunTime.ToString('dd/MM HH:mm') }) | $a |"
  }
}

# 2. Su kien Windows trong khung nghi van
$ids = @{
  1='Doi gio he thong / thuc day'; 41='Mat dien / treo cung'; 42='Vao che do ngu'; 107='Thuc day tu ngu';
  1074='Tat/khoi dong lai co chu dich'; 6005='Windows khoi dong'; 6006='Windows tat'; 6008='Tat dot ngot';
  27='Mat ket noi mang (card)'; 32='Card mang noi lai'; 4201='Mang noi'; 4202='Mang ngat'; 10400='Mang ngat (NDIS)';
  19='Cai cap nhat Windows'; 43='Bat dau cai cap nhat'; 7036='Dich vu doi trang thai'; 1014='Loi phan giai ten mien (DNS)'
}
$sk = Get-WinEvent -FilterHashtable @{ LogName='System'; StartTime=$tu } -MaxEvents 20000 |
  Where-Object { $ids.ContainsKey($_.Id) -and (TrongKhung $_.TimeCreated) -and ($_.Id -ne 7036 -or $_.Message -match '(?i)network|mang|wlan|dhcp|dns|windows update|google drive') }
$suKien = $sk | Sort-Object TimeCreated | Select-Object -Last 80 | ForEach-Object {
  $m = ($_.Message -split "`n")[0].Trim(); if ($m.Length -gt 110) { $m = $m.Substring(0,110) + '...' }
  "| $($_.TimeCreated.ToString('dd/MM HH:mm:ss')) | $($_.Id) $($ids[$_.Id]) | $($_.ProviderName) | $m |"
}

# 3. Chuong trinh claude / node / Claude Desktop bi sap (Application log)
$sap = Get-WinEvent -FilterHashtable @{ LogName='Application'; StartTime=$tu; Id=1000,1002,1026 } -MaxEvents 3000 |
  Where-Object { $_.Message -match '(?i)claude|node\.exe' } | Sort-Object TimeCreated | Select-Object -Last 30 | ForEach-Object {
  $m = ($_.Message -split "`n")[0].Trim(); if ($m.Length -gt 110) { $m = $m.Substring(0,110) + '...' }
  "| $($_.TimeCreated.ToString('dd/MM HH:mm:ss')) | $($_.Id) | $m |"
}

# 4. Gio khoi dong may + gio bat cac tien trinh claude dang chay
$os = Get-CimInstance Win32_OperatingSystem
$boot = [TimeZoneInfo]::ConvertTime($os.LastBootUpTime, $tz).ToString('dd/MM HH:mm')
$cl = Get-CimInstance Win32_Process -Filter "Name like '%claude%'" | ForEach-Object {
  $st = $_.CreationDate; "$($_.Name) pid $($_.ProcessId) bat luc $(if ($st) { $st.ToString('dd/MM HH:mm') })"
} | Select-Object -First 25

# 5. Dang nhap Claude: tep thong tin dang nhap va lan sua cuoi (khong doc noi dung)
$cred = @("$env:USERPROFILE\.claude\.credentials.json","$env:USERPROFILE\.claude.json") | Where-Object { Test-Path $_ } | ForEach-Object {
  "$_ sua lan cuoi $((Get-Item $_).LastWriteTime.ToString('dd/MM HH:mm'))" }

$md = @"
# Tim nguyen nhan Remote Control rot - may $may - $($gio.ToString('dd/MM/yyyy HH:mm')) (gio VN)
Khung nghi van: 23:00-01:59 va 11:00-12:59, 4 ngay gan nhat. Chi doc, khong sua gi.

May khoi dong lan cuoi: $boot

## 1. Tac vu theo lich chay trong khung nghi van
| Tac vu | Gio kich hoat | Chay lan cuoi | Ma ket qua | Lenh |
|---|---|---|---|---|
$($tasks -join "`n")

## 2. Tac vu co lenh tat/khoi dong lai/claude/node/don RAM
| Tac vu | Chay lan cuoi | Lan toi | Lenh |
|---|---|---|---|
$($nghi -join "`n")

## 3. Su kien Windows trong khung nghi van
| Luc | Su kien | Nguon | Noi dung |
|---|---|---|---|
$($suKien -join "`n")

## 4. claude / node bi sap
| Luc | Ma | Noi dung |
|---|---|---|
$($sap -join "`n")

## 5. Tien trinh claude dang chay
$(($cl | ForEach-Object { "- $_" }) -join "`n")

## 6. Tep dang nhap Claude (chi xem gio sua, khong doc noi dung)
$(($cred | ForEach-Object { "- $_" }) -join "`n")
"@
Set-Content -Path $out -Value $md -Encoding UTF8
Write-Host "Da ghi: $out"
