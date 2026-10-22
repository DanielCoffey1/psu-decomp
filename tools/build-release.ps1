param(
    [Parameter(Mandatory=$true)][string]$Sdk,
    [Parameter(Mandatory=$true)][string]$GpuSource,
    [switch]$BuildNative,
    [switch]$Staged,
    [string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$Sdk = & "$PSScriptRoot/verify-sdk.ps1" -Sdk $Sdk
$GpuSource = (Resolve-Path -LiteralPath $GpuSource).Path
if ($BuildNative) {
    & "$PSScriptRoot/build.ps1" -Sdk $Sdk -Stage:$Staged
    & "$PSScriptRoot/build-gpu.ps1" -Sdk $Sdk -Source $GpuSource -Stage:$Staged
}
# Packaging must use the source corresponding to the reviewed PSU GPU patch.
git -C $GpuSource apply --reverse --check "$PSScriptRoot/gpu/xps.patch"
if ($LASTEXITCODE) { throw 'GPU source does not match the release patch.' }
$version = [regex]::Match((Get-Content "$root/release/Program.cs" -Raw), 'Version = "([^"]+)"').Groups[1].Value
if (-not $version) { throw 'Missing release version.' }
$name = "PSU-Recompiled-$version-win-x64"
$output = if ($OutputDirectory) { [IO.Path]::GetFullPath($OutputDirectory) } else { Join-Path $root "out/release/$name" }
# A fresh build folder avoids stale or accidental files entering the payload.
$stage = Join-Path $root ('out/release/staging-' + [guid]::NewGuid().ToString('N'))
$payload = Join-Path $stage 'payload'
New-Item -ItemType Directory -Path "$payload/bin", "$payload/licenses", $output -Force | Out-Null
$csc = "$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
if (-not (Test-Path -LiteralPath $csc)) { throw '.NET Framework 4.x C# compiler is required for packaging.' }
$sources = @(Get-ChildItem "$root/release/*.cs" -File | ForEach-Object FullName)
$common = @('/nologo', '/optimize+', '/platform:x64', '/target:winexe', '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll', '/r:System.Core.dll', '/r:System.Xml.dll', '/r:System.IO.Compression.dll', '/r:System.IO.Compression.FileSystem.dll', "/win32manifest:$root/release/app.manifest")
& $csc @common "/out:$payload/PSU Launcher.exe" @sources
if ($LASTEXITCODE) { throw 'Launcher build failed.' }
$native = Join-Path $root 'out/build/win-amd64-release'
$suffix = if ($Staged) { '-staged' } else { '' }
if ((Get-FileHash "$native/rexgpu-psu$suffix.dll").Hash -ne (Get-FileHash "$root/out/gpu/gpu/rexgpu-xenos.dll").Hash) {
    throw 'The selected GPU DLL is stale. Rebuild it with build-gpu.ps1 or use -BuildNative.'
}
Copy-Item -LiteralPath "$native/psu$suffix.exe" -Destination "$payload/bin/psu.exe"
Copy-Item -LiteralPath "$native/rexgpu-psu$suffix.dll" -Destination "$payload/bin/rexgpu-psu.dll"
Copy-Item -LiteralPath "$Sdk/bin/rexruntime.dll" -Destination "$payload/bin/rexruntime.dll"
$vs = & "${env:ProgramFiles(x86)}/Microsoft Visual Studio/Installer/vswhere.exe" -latest -products '*' -property installationPath
$crt = Get-ChildItem "$vs/VC/Redist/MSVC" -Directory | Where-Object Name -Match '^\d+\.' | Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $crt) { throw 'Visual C++ redistributable files were not found.' }
# App-local CRT: no UAC prompt or system-wide installation.
Get-ChildItem "$($crt.FullName)/x64/Microsoft.VC143.CRT/*.dll" -File | Copy-Item -Destination "$payload/bin"
Copy-Item -LiteralPath "$root/third_party/rexglue-LICENSE.txt" -Destination "$payload/licenses/ReXGlue-Xenia.txt"
Copy-Item -LiteralPath "$vs/Licenses/1033/Redist.txt" -Destination "$payload/licenses/Microsoft-Redist.txt"
if (Test-Path "$root/release/licenses") { Get-ChildItem "$root/release/licenses" -File | Copy-Item -Destination "$payload/licenses" }
foreach ($requiredNotice in @('THIRD-PARTY-NOTICES.txt', 'FFmpeg-COPYING.LGPLv2.1.txt', 'libmspack-COPYING.LIB.txt', 'sdl3-LICENSE.txt.txt')) {
    if (-not (Test-Path -LiteralPath "$payload/licenses/$requiredNotice")) { throw "Missing third-party notice: $requiredNotice" }
}
Copy-Item -LiteralPath "$root/release/RELEASE-NOTES.md" -Destination "$payload/Read me.txt"
$revision = git -C $root rev-parse HEAD
$dirty = [bool](git -C $root status --porcelain)
[ordered]@{
    version = $version; source_commit = $revision; source_modified = $dirty
    sdk_revision = (git -C $GpuSource rev-parse HEAD)
    gpu_patch_sha256 = (Get-FileHash "$root/tools/gpu/xps.patch" -Algorithm SHA256).Hash.ToLowerInvariant()
    required_xex_sha256 = '93d208ee55cc89265fbc6b9e95b1cf34ae364e47df713cd9f3e8adf6101c825e'
    build_utc = [DateTime]::UtcNow.ToString('o')
} | ConvertTo-Json | Set-Content -LiteralPath "$payload/build-info.json" -Encoding utf8
$checksums = Get-ChildItem $payload -File -Recurse | Sort-Object FullName | ForEach-Object {
    (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + [IO.Path]::GetRelativePath($payload, $_.FullName).Replace('\', '/')
}
[IO.File]::WriteAllLines("$payload/payload.sha256", $checksums, [Text.UTF8Encoding]::new($false))
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($payload, "$stage/payload.zip", [IO.Compression.CompressionLevel]::Optimal, $false)
$installer = "$output/$name-Setup.exe"
$builtInstaller = "$stage/$name-Setup.exe"
& $csc @common '/define:INSTALLER' "/resource:$stage/payload.zip,payload.zip" "/out:$builtInstaller" @sources
if ($LASTEXITCODE) { throw 'Installer build failed.' }
Copy-Item -LiteralPath $builtInstaller -Destination $installer -Force
Copy-Item -LiteralPath "$root/release/RELEASE-NOTES.md" -Destination "$output/RELEASE-NOTES.md" -Force
Copy-Item -LiteralPath "$root/release/VALIDATION.md" -Destination "$output/VALIDATION.md" -Force
Copy-Item -LiteralPath "$payload/build-info.json" -Destination "$output/build-info.json" -Force
# Review snapshot includes project sources and build instructions, never game data.
$sourceFolder = "$stage/source"
New-Item -ItemType Directory -Path $sourceFolder | Out-Null
$files = git -C $root ls-files -co --exclude-standard
foreach ($relative in ($files | Sort-Object -Unique)) {
    if ($relative -match '^(local|out|generated|build)/' -or $relative -match '\.(iso|xex|exe|dll|pdb|sfd|adx|afs|nbl)$') { throw "Unexpected file in source snapshot: $relative" }
    $destination = Join-Path $sourceFolder $relative
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $relative) -Destination $destination
}
$sourceZip = "$output/$name-source.zip"
if (Test-Path -LiteralPath $sourceZip) { Remove-Item -LiteralPath $sourceZip }
[IO.Compression.ZipFile]::CreateFromDirectory($sourceFolder, $sourceZip, [IO.Compression.CompressionLevel]::Optimal, $false)
$finalHashes = @($installer, $sourceZip, "$output/build-info.json", "$output/RELEASE-NOTES.md", "$output/VALIDATION.md") | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant() + '  ' + [IO.Path]::GetFileName($_) }
[IO.File]::WriteAllLines("$output/SHA256SUMS.txt", $finalHashes, [Text.UTF8Encoding]::new($false))
Write-Output "Prepared local release package: $output"
