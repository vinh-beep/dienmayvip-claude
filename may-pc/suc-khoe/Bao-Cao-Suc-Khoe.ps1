# Bao cao RAM / CPU / tien trinh Claude cua may nay, ghi len Bridge de Claude Cloud doc duoc.
# Chay tren CA may PC va may SQL Server. Chi DOC, khong sua gi.
# Tham so: -CaiLich  => dang ky Task Scheduler chay moi 30 phut (can Admin).
param([switch]$CaiLich)
$ErrorActionPreference = 'Continue'
$noi = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($CaiLich) {
  $act = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$($MyInvocation.MyCommand.Path)`""
  $trg = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30)
  Register-ScheduledTask -TaskName 'DMV Bao Cao Suc Khoe May' -Action $act -Trigger $trg -RunLevel Highest -Force | Out-Null
  Write-Host 'Da dang ky tac vu "DMV Bao Cao Suc Khoe May" moi 30 phut.'; exit
}
$tz  = [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time')
$gio = [TimeZoneInfo]::ConvertTime([DateTime]::Now, $tz)
$tem = $gio.ToString('dd MM yyyy HH') + 'h' + $gio.ToString('mm') + 'p'
$may = $env:COMPUTERNAME
# Noi ghi: Bridge neu co, khong thi canh script
$bridge = @('G:\My Drive\DMV-Cloud-Bridge','C:\DMV-Cloud-Bridge') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bridge) { $bridge = $noi }
# 1 tep moi nhat / may (ghi de) de Bridge khong day 48 tep/ngay; lich su giu tai may trong suc-khoe.csv
$out = Join-Path $bridge "ket-qua-PC-SUC-KHOE-$may-moi-nhat.md"

$os  = Get-CimInstance Win32_OperatingSystem
$cs  = Get-CimInstance Win32_ComputerSystem
$ramTong = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
$ramTrong = [math]::Round($os.FreePhysicalMemory/1MB,1)
$ramPct = [math]::Round(100*(1-$os.FreePhysicalMemory/$os.TotalVisibleMemorySize),0)
$commitPct = [math]::Round(100*(1-$os.FreeVirtualMemory/$os.TotalVirtualMemorySize),0)
$cpu = [math]::Round((Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average,0)
$upt = (Get-Date) - $os.LastBootUpTime
$dia = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { "$($_.DeviceID) trong $([math]::Round($_.FreeSpace/1GB,0))/$([math]::Round($_.Size/1GB,0)) GB" }

$ps = Get-Process | Sort-Object WorkingSet64 -Descending
$top = $ps | Select-Object -First 12 | ForEach-Object { "| $($_.ProcessName) | $($_.Id) | $([math]::Round($_.WorkingSet64/1MB,0)) MB | $([math]::Round($_.CPU,0)) s |" }
$claude = @($ps | Where-Object { $_.ProcessName -match '^(claude|Claude)' })
$node   = @($ps | Where-Object { $_.ProcessName -eq 'node' })
$ramClaude = [math]::Round((($claude + $node) | Measure-Object WorkingSet64 -Sum).Sum/1GB,1)
$rc = @(Get-CimInstance Win32_Process -Filter "Name like '%claude%' or Name='node.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'remote-control' })
$ver = try { (& claude --version 2>$null) -join ' ' } catch { 'khong tim thay lenh claude' }
$sql = Get-Service -Name 'MSSQL*' -ErrorAction SilentlyContinue | ForEach-Object { "$($_.Name)=$($_.Status)" }

$canh = @()
if ($ramPct -ge 90) { $canh += "RAM dung $ramPct% (>=90%)" }
if ($commitPct -ge 90) { $canh += "Bo nho cam ket $commitPct% (>=90%) - nguy co treo may" }
if ($cpu -ge 90) { $canh += "CPU $cpu%" }
if ($node.Count -ge 40) { $canh += "$($node.Count) tien trinh node (MCP) - qua nhieu" }

$md = @"
# Suc khoe may $may - $($gio.ToString('dd/MM/yyyy HH:mm')) (gio VN)

Canh bao: $(if ($canh) { $canh -join ' ; ' } else { 'khong' })

| Chi so | Gia tri |
|---|---|
| CPU | $cpu % |
| RAM | dung $ramPct % ($ramTrong GB trong / $ramTong GB) |
| Bo nho cam ket (RAM + pagefile) | $commitPct % |
| May chay lien tuc | $([int]$upt.TotalDays) ngay $($upt.Hours) gio (khoi dong $([TimeZoneInfo]::ConvertTime($os.LastBootUpTime,$tz).ToString('dd/MM HH:mm'))) |
| O dia | $($dia -join ' ; ') |
| Claude Code | $ver |
| Tien trinh Claude / node | $($claude.Count) / $($node.Count) (tong $ramClaude GB) |
| Phien Remote Control dang chay | $($rc.Count) |
| SQL Server | $(if ($sql) { $sql -join ' ; ' } else { 'khong co tren may nay' }) |

## 12 tien trinh ton RAM nhat
| Ten | PID | RAM | CPU |
|---|---|---|---|
$($top -join "`n")
"@
Set-Content -Path $out -Value $md -Encoding UTF8
$csv = Join-Path $noi 'suc-khoe.csv'
if (-not (Test-Path $csv)) { Set-Content -Path $csv -Value 'thoi_gian,may,cpu,ram_pct,commit_pct,claude,node,rc,canh_bao' -Encoding UTF8 }
Add-Content -Path $csv -Value ("{0},{1},{2},{3},{4},{5},{6},{7},""{8}""" -f $gio.ToString('dd/MM/yyyy HH:mm'),$may,$cpu,$ramPct,$commitPct,$claude.Count,$node.Count,$rc.Count,($canh -join '; ')) -Encoding UTF8
Write-Host "Da ghi: $out"
