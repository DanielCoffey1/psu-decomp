param([Parameter(Mandatory=$true)][string]$Sdk,
      [string]$Source,
      [int]$Jobs=12)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$Sdk=& "$PSScriptRoot/verify-sdk.ps1" -Sdk $Sdk
$revision='bd833a2ab69d305f99ddf57418fc38ffec8af93d'
if (-not $Source) {
    $Source=Join-Path $root 'local/gpu-source'
    if (-not (Test-Path $Source)) {
        git clone --filter=blob:none https://github.com/rexglue/rexglue-sdk.git $Source
        if ($LASTEXITCODE) { throw 'SDK source clone failed' }
        git -C $Source checkout $revision
        if ($LASTEXITCODE) { throw 'SDK source checkout failed' }
        git -C $Source apply "$PSScriptRoot/gpu/xps.patch"
        if ($LASTEXITCODE) { throw 'GPU source patch failed' }
    }
}
$actual=git -C $Source rev-parse HEAD
if ($actual -ne $revision) { throw 'GPU source revision does not match pinned SDK.' }
git -C $Source apply --reverse --check "$PSScriptRoot/gpu/xps.patch"
if ($LASTEXITCODE) { throw 'GPU source does not contain the required XPS patch.' }
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw 'Visual Studio C++ Build Tools required.' }
$devcmd=Join-Path $vs 'Common7/Tools/VsDevCmd.bat'
$environment=& $env:ComSpec /d /s /c "`"`"$devcmd`" -arch=x64 -host_arch=x64 >nul && set`""
if ($LASTEXITCODE) { throw 'Developer environment initialization failed.' }
foreach($line in $environment) { if($line -match '^([^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1],$matches[2],'Process') } }
$llvm=Join-Path $vs 'VC/Tools/Llvm/x64/bin'
$env:PATH="$llvm;$env:PATH"
$build=Join-Path $root 'out/gpu'
& cmake -S "$PSScriptRoot/gpu" -B $build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=clang++ "-DCMAKE_PREFIX_PATH=$Sdk" "-DREXGLUE_ROOT=$Source"
if ($LASTEXITCODE) { throw 'GPU CMake configure failed.' }
& cmake --build $build --parallel $Jobs
if ($LASTEXITCODE) { throw 'GPU build failed.' }
$output=Join-Path $root 'out/build/win-amd64-release/rexgpu-psu.dll'
Copy-Item -LiteralPath (Join-Path $build 'gpu/rexgpu-xenos.dll') -Destination $output -Force
Write-Output "Built custom GPU plugin: $output"
