$ErrorActionPreference = 'Stop'
$temporary = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$fixture = Join-Path $temporary ('psu-privacy-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$file = Join-Path $fixture 'fixture.bin'
$checked = 0
try {
    # Assemble synthetic paths so this test's source itself passes the check.
    $windows = @('C:', 'Users', 'ExampleUser', 'project', 'file.cpp') -join '\'
    $cases = @(
        [Text.Encoding]::ASCII.GetBytes($windows),
        [Text.Encoding]::Unicode.GetBytes($windows),
        [Text.Encoding]::BigEndianUnicode.GetBytes($windows),
        ([byte[]]@(127) + [Text.Encoding]::Unicode.GetBytes($windows)),
        [Text.Encoding]::ASCII.GetBytes($windows.Replace('\', '/')),
        [Text.Encoding]::ASCII.GetBytes((@('', 'home', 'example', 'file.cpp') -join '/')),
        [Text.Encoding]::ASCII.GetBytes((@('', 'Users', 'example', 'file.cpp') -join '/'))
    )
    foreach ($bytes in $cases) {
        [IO.File]::WriteAllBytes($file, $bytes)
        $rejected = $false
        try { & "$PSScriptRoot/check-release-privacy.ps1" -Root $fixture | Out-Null }
        catch {
            if ($_.Exception.Message -ne 'Local user-directory path found in release file: fixture.bin') { throw }
            $rejected = $true
        }
        if (-not $rejected) { throw "Private path fixture $checked was accepted." }
        $checked++
    }
    [IO.File]::WriteAllText($file, 'psu/src/main.cpp rexglue/src/gpu.cpp https://api.github.com/users/example')
    & "$PSScriptRoot/check-release-privacy.ps1" -Root $fixture | Out-Null
    $checked++
    Write-Output "Privacy guard tests passed: $checked cases."
} finally {
    $resolved = [IO.Path]::GetFullPath($fixture)
    if (-not $resolved.StartsWith($temporary, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolved) -notlike 'psu-privacy-test-*') { throw 'Unexpected cleanup path.' }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
