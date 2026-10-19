param([string]$XexPath = (Join-Path $PSScriptRoot '../local/default.xex'),
      [string]$OutputPath = (Join-Path $PSScriptRoot '../local/xex-analysis.json'))
$ErrorActionPreference = 'Stop'
$bytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $XexPath))
function U32([int]$Offset) {
    if ($Offset -lt 0 -or $Offset + 4 -gt $bytes.Length) { throw 'XEX offset out of bounds.' }
    return [uint32]([uint64]$bytes[$Offset] * 16777216 + [uint64]$bytes[$Offset+1] * 65536 + [uint64]$bytes[$Offset+2] * 256 + $bytes[$Offset+3])
}
function U16([int]$Offset) { return [int]$bytes[$Offset] * 256 + $bytes[$Offset+1] }
function Hex([uint32]$Value) { return '0x{0:X8}' -f $Value }
if ($bytes.Length -lt 24 -or [Text.Encoding]::ASCII.GetString($bytes,0,4) -ne 'XEX2') { throw 'Not an XEX2 executable.' }
$headers = @{}
$count = U32 20
if ($count -gt 256) { throw 'Unreasonable optional header count.' }
for ($i=0; $i -lt $count; $i++) { $headers[(U32 (24+$i*8))] = U32 (28+$i*8) }
$report = [ordered]@{SHA256=(Get-FileHash -LiteralPath $XexPath -Algorithm SHA256).Hash; Size=$bytes.Length; OptionalHeaderCount=$count}
foreach ($field in @(@('EntryPoint',0x10100),@('ImageBase',0x10201),@('DefaultStackSize',0x20200))) {
    if ($headers.ContainsKey([uint32]$field[1])) { $report[$field[0]]=Hex $headers[[uint32]$field[1]] }
}
if ($headers.ContainsKey([uint32]0x40006)) {
    $o = $headers[[uint32]0x40006]
    $report.TitleId=Hex (U32 ($o+12)); $report.MediaId=Hex (U32 $o)
    $report.VersionRaw=Hex (U32 ($o+4))
}
if ($headers.ContainsKey([uint32]0x3FF)) {
    $o = $headers[[uint32]0x3FF]
    $report.EncryptionType=U16 ($o+4); $report.CompressionType=U16 ($o+6)
}
if ($headers.ContainsKey([uint32]0x103FF)) {
    $o = $headers[[uint32]0x103FF]; $end = $o + (U32 $o)
    $stringSize = U32 ($o+4); $libraryCount = U32 ($o+8)
    if ($end -gt $bytes.Length -or $o+12+$stringSize -gt $end) { throw 'Invalid import table.' }
    $names = @([Text.Encoding]::ASCII.GetString($bytes,$o+12,$stringSize).Split([char]0) | Where-Object { $_ })
    $cursor = $o+12+$stringSize
    $libraries = @()
    for ($i=0; $i -lt $libraryCount; $i++) {
        $size=U32 $cursor
        if ($size -lt 40 -or $cursor+$size -gt $end) { throw 'Invalid import library size.' }
        $nameIndex=U16 ($cursor+36); $recordCount=U16 ($cursor+38)
        if ($nameIndex -ge $names.Count -or 40+4*$recordCount -gt $size) { throw 'Invalid import library records.' }
        $libraries += [ordered]@{Name=$names[$nameIndex]; RecordCount=$recordCount; VersionRaw=Hex (U32 ($cursor+28)); MinimumVersionRaw=Hex (U32 ($cursor+32))}
        $cursor += $size
    }
    $report.ImportLibraries=$libraries
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding UTF8
$report | ConvertTo-Json -Depth 6
