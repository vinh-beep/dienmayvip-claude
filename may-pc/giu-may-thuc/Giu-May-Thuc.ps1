# Giu may PC thuc de cac phien Claude Remote Control khong bi rot.
# Chay bang Giu-May-Thuc.bat (tu xin quyen Admin). Idempotent: chay lai bao nhieu lan cung duoc.
# Khoi phuc: Khoi-Phuc-Nguon-Dien.bat
$ErrorActionPreference = 'Continue'
$tz   = [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time')
$gio  = [TimeZoneInfo]::ConvertTime([DateTime]::Now, $tz)
$tem  = $gio.ToString('dd MM yyyy HH') + 'h' + $gio.ToString('mm') + 'p'
$noi  = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $noi "Giu May Thuc Result $tem.txt"
function Ghi($s) { $d = (Get-Date).ToString('HH:mm:ss') + '  ' + $s; Write-Host $d; Add-Content -Path $log -Value $d -Encoding UTF8 }

Ghi "=== GIU MAY THUC - bat dau ==="
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Ghi "Quyen Admin: $admin"

# 1. Sao luu cau hinh nguon dien hien tai (de khoi phuc)
$bk = Join-Path $noi 'SaoLuu-NguonDien.pow'
if (-not (Test-Path $bk)) {
  $guid = ([regex]::Match((powercfg /getactivescheme | Out-String), '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')).Value
  powercfg /export "$bk" $guid | Out-Null
  Set-Content -Path (Join-Path $noi 'SaoLuu-GUID.txt') -Value $guid
  Ghi "Da sao luu so do nguon dien $guid -> $bk"
} else { Ghi "Da co ban sao luu tu truoc, giu nguyen: $bk" }

# 2. Khong Sleep / khong Hibernate khi cam dien (AC). Man hinh van tat sau 15 phut cho do ton dien.
powercfg /change standby-timeout-ac 0   | Out-Null; Ghi "Sleep khi cam dien: Never"
powercfg /change hibernate-timeout-ac 0 | Out-Null; Ghi "Hibernate khi cam dien: Never"
powercfg /change monitor-timeout-ac 15  | Out-Null; Ghi "Tat man hinh sau 15 phut (khong anh huong phien)"
# Tat 'sleep sau khi he thong khong dung' an trong so do + khong cho USB/mang ngu
powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP UNATTENDSLEEP 0 2>$null | Out-Null
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0 2>$null | Out-Null
powercfg /setactive SCHEME_CURRENT | Out-Null
Ghi "Tat ngu tu dong an + USB selective suspend (khi cam dien)"

if ($admin) {
  # 3. Khong cho Windows tat card mang de tiet kiem dien
  try {
    Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | ForEach-Object {
      Disable-NetAdapterPowerManagement -Name $_.Name -NoRestart -ErrorAction Stop
      Ghi "Card mang '$($_.Name)': tat tiet kiem dien"
    }
  } catch { Ghi "Card mang: bo qua ($($_.Exception.Message))" }

  # 4. Windows Update: gio hoat dong 06:00-23:59 (khong tu khoi dong lai trong gio nay)
  $ux = 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings'
  if (-not (Test-Path $ux)) { New-Item -Path $ux -Force | Out-Null }
  Set-ItemProperty -Path $ux -Name SmartActiveHoursState -Value 0 -Type DWord
  Set-ItemProperty -Path $ux -Name ActiveHoursStart -Value 6 -Type DWord
  Set-ItemProperty -Path $ux -Name ActiveHoursEnd -Value 23 -Type DWord
  Ghi "Windows Update: gio hoat dong 06h-23h, khong tu khoi dong lai trong khung nay"
} else {
  Ghi "KHONG co quyen Admin: bo qua card mang + Windows Update (chay lai bang file .bat de duoc hoi quyen)"
}

# 5. Kiem tra lai
$q = powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String 'Current AC Power Setting Index'
Ghi "Kiem tra Sleep AC: $q (0x00000000 = Never)"

# 6. Truy vet nguyen nhan rot 14 ngay qua: Sleep(42), khoi dong lai(1074), tat(6006), mat dien bat ngo(41, 6008)
Ghi "--- Su kien Sleep/Restart 14 ngay qua (gio VN) ---"
try {
  Get-WinEvent -FilterHashtable @{LogName='System'; Id=42,41,1074,6006,6008; StartTime=(Get-Date).AddDays(-14)} -ErrorAction Stop |
    Select-Object -First 60 | ForEach-Object {
      $loai = switch ($_.Id) { 42 {'SLEEP'} 41 {'MAT DIEN/TREO'} 1074 {'KHOI DONG LAI/TAT'} 6006 {'TAT MAY'} 6008 {'TAT BAT THUONG'} }
      $t = [TimeZoneInfo]::ConvertTime($_.TimeCreated, $tz).ToString('dd/MM HH:mm')
      $nguon = if ($_.Id -eq 1074) { ' | ' + (($_.Message -split "`n")[0]).Trim() } else { '' }
      Ghi "$t  $loai$nguon"
    }
} catch { Ghi "Khong doc duoc nhat ky System ($($_.Exception.Message))" }

Ghi "=== XONG. Log: $log ==="
