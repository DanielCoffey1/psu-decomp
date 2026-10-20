param(
    [ValidateSet('Debug', 'Release', 'RelWithDebInfo')]
    [string]$Configuration = 'Release',
    [string]$Sdk,
    [ValidateRange(1, 64)]
    [int]$Jobs = 8,
    [switch]$GenerateOnly,
    [switch]$Stage
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$xex = Join-Path $root 'local/default.xex'
$expectedXex = '93d208ee55cc89265fbc6b9e95b1cf34ae364e47df713cd9f3e8adf6101c825e'
if (-not (Test-Path -LiteralPath $xex)) { throw 'Extract the executable with tools/Inspect-Disc.ps1 first' }
if ((Get-FileHash -LiteralPath $xex -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedXex) {
    throw 'Unsupported executable revision: these analysis hints target the recorded USA disc build'
}
if (-not $Sdk) { $Sdk = & "$PSScriptRoot/setup-sdk.ps1" }
$Sdk = & "$PSScriptRoot/verify-sdk.ps1" -Sdk $Sdk
$sdkLock = Get-Content -LiteralPath "$PSScriptRoot/sdk-lock.json" -Raw | ConvertFrom-Json
Push-Location $root
try {
    & "$Sdk/bin/rexglue.exe" codegen psu_manifest.toml
    if ($LASTEXITCODE -ne 0) { throw 'Code generation failed; see diagnostics above' }
    if (-not (Test-Path generated/default/psu_init.h)) { throw 'No generated entrypoint header' }
    & "$PSScriptRoot/Repair-Codegen.ps1"
    if ($GenerateOnly) { return }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    $vs = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
    if (-not $vs) { throw 'Install Visual Studio C++ Build Tools with LLVM/Clang and CMake first' }
    $devcmd = Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
    # Capture the developer environment in this process; no permanent PATH changes.
    $environment = & $env:ComSpec /d /s /c "`"`"$devcmd`" -arch=x64 -host_arch=x64 >nul && set`""
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize Visual Studio build environment' }
    foreach ($line in $environment) {
        if ($line -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process')
        }
    }
    $llvm = Join-Path $vs 'VC/Tools/Llvm/bin'
    if (Test-Path "$vs/VC/Tools/Llvm/x64/bin/clang++.exe") { $llvm = "$vs/VC/Tools/Llvm/x64/bin" }
    $env:PATH = "$llvm;$env:PATH"
    $preset = 'win-amd64-' + $Configuration.ToLowerInvariant()
    $stageValue = if ($Stage) { 'ON' } else { 'OFF' }
    & cmake --preset $preset "-DCMAKE_PREFIX_PATH=$Sdk" "-Drexglue_DIR=$Sdk/lib/cmake/rexglue" "-DREXSDK_VERSION=$($sdkLock.version)" "-DPSU_STAGE_BINARY=$stageValue"
    if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed' }
    & cmake --build --preset $preset --parallel $Jobs
    if ($LASTEXITCODE -ne 0) { throw 'C++ build failed' }
    $name = if ($Stage) { 'psu-staged.exe' } else { 'psu.exe' }
    Write-Output "Built: $root/out/build/$preset/$name"
} finally {
    Pop-Location
}
