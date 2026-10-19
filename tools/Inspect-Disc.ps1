param(
    [Parameter(Mandatory=$true)][string]$IsoPath,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../local'),
    [switch]$ExtractExecutable,
    [switch]$ExtractGame
)
$ErrorActionPreference = 'Stop'
$stream = [IO.File]::OpenRead((Resolve-Path -LiteralPath $IsoPath).Path)
function Read-Bytes([long]$Offset, [int]$Count) {
    if ($Offset -lt 0 -or $Count -lt 0 -or $Offset + $Count -gt $stream.Length) { throw 'Disc read outside image bounds.' }
    $stream.Position = $Offset
    $bytes = New-Object byte[] $Count
    $read = 0
    while ($read -lt $Count) {
        $n = $stream.Read($bytes, $read, $Count - $read)
        if ($n -eq 0) { throw 'Unexpected end of disc.' }
        $read += $n
    }
    return ,$bytes
}
try {
    $partition = $null
    foreach ($candidate in @(0L, 0xFD90000L, 0x2080000L, 0x2000000L)) {
        if ($candidate + 65572 -gt $stream.Length) { continue }
        $header = Read-Bytes ($candidate + 65536) 36
        if ([Text.Encoding]::ASCII.GetString($header, 0, 20) -eq 'MICROSOFT*XBOX*MEDIA') {
            $partition = $candidate
            break
        }
    }
    if ($null -eq $partition) { throw 'No XDVDFS descriptor found at supported partition offsets.' }
    $rootSector = [BitConverter]::ToUInt32($header, 20)
    $rootSize = [BitConverter]::ToUInt32($header, 24)
    $entries = [Collections.Generic.List[object]]::new()
    $visitedDirectories = [Collections.Generic.HashSet[long]]::new()
    function Read-Directory([uint32]$Sector, [uint32]$Size, [string]$Parent, [int]$Depth) {
        if ($Depth -gt 64 -or $Size -gt 16777216) { throw 'Directory safety limit exceeded.' }
        if (-not $visitedDirectories.Add([long]$Sector)) { throw 'Repeated directory sector.' }
        if ($Size -eq 0) { return }
        $table = Read-Bytes ($partition + [long]$Sector * 2048) ([int]$Size)
        $pending = [Collections.Generic.Stack[int]]::new()
        $seen = [Collections.Generic.HashSet[int]]::new()
        $pending.Push(0)
        while ($pending.Count) {
            $offset = $pending.Pop()
            if (-not $seen.Add($offset)) { throw 'Directory tree cycle.' }
            if ($offset + 14 -gt $table.Length) { throw 'Invalid directory entry.' }
            $left = [BitConverter]::ToUInt16($table, $offset)
            $right = [BitConverter]::ToUInt16($table, $offset + 2)
            $fileSector = [BitConverter]::ToUInt32($table, $offset + 4)
            $fileSize = [BitConverter]::ToUInt32($table, $offset + 8)
            $attributes = $table[$offset + 12]
            $nameLength = $table[$offset + 13]
            if ($offset + 14 + $nameLength -gt $table.Length) { throw 'Invalid filename length.' }
            $name = [Text.Encoding]::ASCII.GetString($table, $offset + 14, $nameLength)
            $path = if ($Parent) { "$Parent/$name" } else { $name }
            $directory = ($attributes -band 16) -ne 0
            $entries.Add([pscustomobject]@{Path=$path; Sector=$fileSector; Size=$fileSize; Directory=$directory})
            if ($left) { $pending.Push([int]$left * 4) }
            if ($right) { $pending.Push([int]$right * 4) }
            if ($directory) { Read-Directory $fileSector $fileSize $path ($Depth + 1) }
        }
    }
    Read-Directory $rootSector $rootSize '' 0
    New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
    $report = [ordered]@{Format='XDVDFS'; ImageSize=$stream.Length; PartitionOffset=$partition; Entries=@($entries | Sort-Object Path)}
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $OutputDirectory 'disc.json') -Encoding UTF8
    if ($ExtractExecutable) {
        $exe = @($entries | Where-Object { $_.Path -ieq 'default.xex' -and -not $_.Directory })
        if ($exe.Count -ne 1) { throw 'Expected one root default.xex.' }
        $data = Read-Bytes ($partition + [long]$exe[0].Sector * 2048) ([int]$exe[0].Size)
        if ([Text.Encoding]::ASCII.GetString($data, 0, 4) -ne 'XEX2') { throw 'Executable lacks XEX2 signature.' }
        [IO.File]::WriteAllBytes((Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) 'default.xex'), $data)
    }
    if ($ExtractGame) {
        $destinationRoot = [IO.Path]::GetFullPath($OutputDirectory).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        $copyBuffer = New-Object byte[] 1048576
        foreach ($entry in $entries) {
            # System updates are console installers, not game data.
            if ($entry.Path -eq '$SystemUpdate' -or $entry.Path.StartsWith('$SystemUpdate/')) { continue }
            foreach ($component in $entry.Path.Split('/')) {
                if ($component -eq '.' -or $component -eq '..' -or $component.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) { throw 'Unsafe disc path.' }
            }
            $destination = [IO.Path]::GetFullPath((Join-Path $destinationRoot $entry.Path))
            if (-not $destination.StartsWith($destinationRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Disc path escapes output directory.' }
            if ($entry.Directory) { New-Item -ItemType Directory -Force -Path $destination | Out-Null; continue }
            if ($partition + [long]$entry.Sector * 2048 + [long]$entry.Size -gt $stream.Length) { throw 'File outside image bounds.' }
            New-Item -ItemType Directory -Force -Path ([IO.Path]::GetDirectoryName($destination)) | Out-Null
            $output = [IO.File]::Create($destination)
            try {
                $stream.Position = $partition + [long]$entry.Sector * 2048
                $remaining = [long]$entry.Size
                while ($remaining -gt 0) {
                    $count = $stream.Read($copyBuffer, 0, [int][Math]::Min($remaining, $copyBuffer.Length))
                    if ($count -eq 0) { throw 'Unexpected end of image during extraction.' }
                    $output.Write($copyBuffer, 0, $count)
                    $remaining -= $count
                }
            } finally { $output.Dispose() }
        }
    }
    Write-Output "Inspected $($entries.Count) entries. Local report: $(Join-Path $OutputDirectory 'disc.json')"
} finally { $stream.Dispose() }
