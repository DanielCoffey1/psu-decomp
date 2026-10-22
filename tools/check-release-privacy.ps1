param([Parameter(Mandatory=$true)][string]$Root)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $Root).Path
# Inspect embedded ASCII and UTF-16 strings as well as ordinary text files.
# Do not print the matched value: a failing build log must not repeat the leak.
$pattern = '(?i:[a-z]:[\\/](?:users|documents and settings)[\\/][^\\/\x00\r\n]+[\\/])|/(?:home|Users)/[^/\x00\r\n]+/'
$checked = 0
foreach ($file in Get-ChildItem -LiteralPath $Root -File -Recurse) {
    $bytes = [IO.File]::ReadAllBytes($file.FullName)
    # Removing NULs also catches UTF-16 strings at odd byte offsets in binaries.
    $text = [Text.Encoding]::GetEncoding(28591).GetString($bytes).Replace([string][char]0, '')
    if ([regex]::IsMatch($text, $pattern)) {
        throw ('Local user-directory path found in release file: ' + [IO.Path]::GetRelativePath($Root, $file.FullName))
    }
    $checked++
}
Write-Output "Privacy path check passed: $checked files."
