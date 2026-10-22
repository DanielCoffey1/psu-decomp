param([Parameter(Mandatory=$true)][string]$GpuSource)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$destination = Join-Path $root 'release/licenses'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
# Use the exact submodule revisions in the pinned SDK, not changing default branches.
$dependencies = @(
    @('sdl3','libsdl-org/SDL','LICENSE.txt'),
    @('fmt','fmtlib/fmt','LICENSE'),
    @('spdlog','gabime/spdlog','LICENSE'),
    @('xxHash','Cyan4973/xxHash','LICENSE'),
    @('imgui','ocornut/imgui','LICENSE.txt'),
    @('simde','simd-everywhere/simde','COPYING'),
    @('tomlplusplus','marzer/tomlplusplus','LICENSE'),
    @('utfcpp','nemtrif/utfcpp','LICENSE'),
    @('o1heap','pavel-kirienko/o1heap','LICENSE'),
    @('cli11','CLIUtils/CLI11','LICENSE'),
    @('libmspack','kyz/libmspack','libmspack/COPYING.LIB'),
    @('FFmpeg','wmarti/FFmpeg','COPYING.LGPLv2.1'),
    @('FFmpeg','wmarti/FFmpeg','LICENSE.md')
)
$index = @('Third-party notices for the pinned ReXGlue runtime and PSU GPU plugin.', '', 'The following source revisions and license texts accompany this review build:')
foreach ($item in $dependencies) {
    $line = git -C $GpuSource ls-tree HEAD "thirdparty/$($item[0])"
    if ($line -notmatch '^160000 commit ([a-f0-9]{40})') { throw "Missing pinned revision: $($item[0])" }
    $revision = $matches[1]
    $url = "https://raw.githubusercontent.com/$($item[1])/$revision/$($item[2])"
    $file = "$($item[0])-$([IO.Path]::GetFileName($item[2])).txt"
    Invoke-WebRequest -Uri $url -OutFile (Join-Path $destination $file)
    $index += "$file - https://github.com/$($item[1])/tree/$revision"
}
Copy-Item "$GpuSource/thirdparty/aes_128/LICENSE" "$destination/aes_128-LICENSE.txt"
Copy-Item "$GpuSource/thirdparty/crypto/des/LICENSE" "$destination/des-LICENSE.txt"
(Get-Content "$GpuSource/thirdparty/renderdoc/renderdoc_app.h" -TotalCount 23) | Set-Content "$destination/RenderDoc-LICENSE.txt" -Encoding utf8
$stb = Get-Content "$GpuSource/thirdparty/stb/stb_image.h" -Raw
$stb.Substring($stb.LastIndexOf('This software is available under 2 licenses')) | Set-Content "$destination/stb-LICENSE.txt" -Encoding utf8
$index += @('', 'FFmpeg/libmspack are linked into rexruntime.dll by the pinned SDK. Their corresponding source and build configuration are available from the pinned source revisions above and the ReXGlue source tree. The project source snapshot includes the PSU GPU patch and build scripts.', '', 'ReXGlue source and submodules: https://github.com/rexglue/rexglue-sdk/tree/bd833a2ab69d305f99ddf57418fc38ffec8af93d')
$index | Set-Content -LiteralPath "$destination/THIRD-PARTY-NOTICES.txt" -Encoding utf8
