param([Parameter(Mandatory = $true)][string]$Sdk)
$ErrorActionPreference = 'Stop'
$lock = Get-Content -LiteralPath "$PSScriptRoot/sdk-lock.json" -Raw | ConvertFrom-Json
$sdkRoot = (Resolve-Path -LiteralPath $Sdk).Path
$expectedPaths = @{}
foreach ($entry in $lock.files.PSObject.Properties) {
    $expectedPaths[$entry.Name] = $true
    $file = Join-Path $sdkRoot $entry.Name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "SDK file missing: $($entry.Name). Use the pinned $($lock.build) SDK."
    }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
        throw "SDK integrity check failed: $($entry.Name). Do not run or restore flagged files. Use the pinned $($lock.build) SDK."
    }
}
foreach ($file in Get-ChildItem -LiteralPath $sdkRoot -Recurse -File) {
    $relative = $file.FullName.Substring($sdkRoot.Length + 1).Replace('\', '/')
    if (-not $expectedPaths.ContainsKey($relative)) {
        throw "Unexpected SDK file: $relative. Use a fresh pinned SDK directory."
    }
}
Write-Output $sdkRoot
