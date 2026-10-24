# Giu Claude Mods qua moi lan mo phien moi.
# Ly do: mod do mot phien Claude tao nam o %USERPROFILE%\.claude\dev-mods\<ma-phien>\<ten-mod>\ va
# CHI nap cho dung phien do. Phien Remote Control mo lai la phien MOI (ma moi) nen khong co mod.
# Cach sua: chep moi mod vao %USERPROFILE%\.claude\mods-co-dinh\<ten-mod>\ (ban moi nhat) va ghi
# duong dan vao env CLAUDE_CODE_PLUGIN_DIRS trong %USERPROFILE%\.claude\settings.json,
# de MOI phien (terminal, remote-control, Claude Desktop) deu nap mod.
# Tham so: -GoCai => tra settings.json ve ban sao luu. Chay lai nhieu lan khong sao (idempotent).
param([switch]$GoCai)
$ErrorActionPreference = 'Stop'
$cl   = Join-Path $env:USERPROFILE '.claude'
$dev  = Join-Path $cl 'dev-mods'
$dich = Join-Path $cl 'mods-co-dinh'
$set  = Join-Path $cl 'settings.json'
$sl   = Join-Path $cl 'settings.truoc-giu-mods.json'
$noi  = Split-Path -Parent $MyInvocation.MyCommand.Path
$bao  = @()

if ($GoCai) {
  if (Test-Path $sl) { Copy-Item $sl $set -Force; Remove-Item $sl; Write-Host 'Da tra settings.json ve ban truoc khi cai.' }
  else { Write-Host 'Khong co ban sao luu, khong doi gi.' }
  exit
}

# 1. Tim moi mod: thu muc co .claude-plugin\plugin.json, lay ban sua gan nhat cho moi ten
$mods = @{}
if (Test-Path $dev) {
  Get-ChildItem $dev -Recurse -Filter plugin.json -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq '.claude-plugin' -and $_.FullName -notmatch '\\types\\' } | ForEach-Object {
      $thuMuc = $_.Directory.Parent
      try { $ten = (Get-Content $_.FullName -Raw | ConvertFrom-Json).name } catch { $ten = $thuMuc.Name }
      $moi = (Get-ChildItem $thuMuc.FullName -Recurse -File | Measure-Object LastWriteTime -Maximum).Maximum
      if (-not $mods.ContainsKey($ten) -or $moi -gt $mods[$ten].Moi) { $mods[$ten] = @{ Nguon = $thuMuc.FullName; Moi = $moi } }
    }
}
if ($mods.Count -eq 0) { $bao += "Khong tim thay mod nao trong $dev." }

# 2. Chep vao mods-co-dinh (bo thu muc types tu sinh)
New-Item -ItemType Directory -Force -Path $dich | Out-Null
foreach ($ten in $mods.Keys) {
  $d = Join-Path $dich $ten
  & robocopy $mods[$ten].Nguon $d /MIR /XD types node_modules /XJ /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { $bao += "LOI chep mod $ten (robocopy $LASTEXITCODE)" } else { $bao += "Mod $ten <- $($mods[$ten].Nguon) (sua $($mods[$ten].Moi.ToString('dd/MM HH:mm')))" }
}

# 3. Ghi CLAUDE_CODE_PLUGIN_DIRS vao settings.json (sao luu 1 lan truoc khi sua)
$dsThuMuc = @(Get-ChildItem $dich -Directory | Where-Object { Test-Path (Join-Path $_.FullName '.claude-plugin\plugin.json') } | ForEach-Object { $_.FullName })
if ($dsThuMuc.Count -gt 0) {
  if (Test-Path $set) {
    if (-not (Test-Path $sl)) { Copy-Item $set $sl }
    try { $j = Get-Content $set -Raw | ConvertFrom-Json } catch { $bao += "settings.json khong doc duoc (JSON loi) - KHONG sua."; $j = $null }
  } else { $j = New-Object PSObject }
  if ($j) {
    if (-not ($j.PSObject.Properties.Name -contains 'env')) { $j | Add-Member -NotePropertyName env -NotePropertyValue (New-Object PSObject) }
    $giaTri = ($dsThuMuc -join ';')
    if ($j.env.PSObject.Properties.Name -contains 'CLAUDE_CODE_PLUGIN_DIRS') {
      # giu cac thu muc anh da tu them truoc do
      $cu = @($j.env.CLAUDE_CODE_PLUGIN_DIRS -split ';' | Where-Object { $_ -and ($_ -notlike "$dich*") })
      $giaTri = (@($cu) + $dsThuMuc) -join ';'
      $j.env.CLAUDE_CODE_PLUGIN_DIRS = $giaTri
    } else { $j.env | Add-Member -NotePropertyName CLAUDE_CODE_PLUGIN_DIRS -NotePropertyValue $giaTri }
    Remove-TypeData System.Array -ErrorAction SilentlyContinue   # PS 5.1: tranh mang bi boc {value,Count}
    $txt = $j | ConvertTo-Json -Depth 32
    [IO.File]::WriteAllText($set, $txt, (New-Object Text.UTF8Encoding($false)))
    $bao += "Da ghi CLAUDE_CODE_PLUGIN_DIRS ($($dsThuMuc.Count) mod) vao $set. Ban cu: $sl"
  }
}

$gio = [TimeZoneInfo]::ConvertTime([DateTime]::Now, [TimeZoneInfo]::FindSystemTimeZoneById('SE Asia Standard Time'))
$md = "# Giu Claude Mods - may $env:COMPUTERNAME - $($gio.ToString('dd/MM/yyyy HH:mm'))`n`n" + (($bao | ForEach-Object { "- $_" }) -join "`n") +
      "`n`nCan dong va mo lai Claude Desktop / cac phien Claude Code de nap mod. Phien moi mo se tu co mod."
$bridge = @('G:\My Drive\DMV-Cloud-Bridge','C:\DMV-Cloud-Bridge') | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $bridge) { $bridge = $noi }
Set-Content -Path (Join-Path $bridge "ket-qua-PC-GIU-MODS-$env:COMPUTERNAME-moi-nhat.md") -Value $md -Encoding UTF8
$bao | ForEach-Object { Write-Host $_ }
