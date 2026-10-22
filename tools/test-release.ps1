param([string]$IsoPath)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$stage = Get-ChildItem "$root/out/release/staging-*" -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $stage -or -not (Test-Path "$($stage.FullName)/payload.zip")) { throw 'Run build-release.ps1 first.' }
$csc = "$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
$sources = @(Get-ChildItem "$root/release/*.cs" -File | ForEach-Object FullName) + (Get-Item "$root/release/tests/ReleaseTests.cs").FullName
$exe = "$root/out/release/ReleaseTests.exe"
& $csc /nologo /optimize+ /platform:x64 /target:exe /main:PsuRelease.ReleaseTests /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Core.dll /r:System.Xml.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll "/resource:$($stage.FullName)/payload.zip,payload.zip" "/out:$exe" @sources
if ($LASTEXITCODE) { throw 'Release tests did not compile.' }
if ($IsoPath) { & $exe $IsoPath } else { & $exe }
if ($LASTEXITCODE) { throw 'Release tests failed.' }
