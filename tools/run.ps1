param([switch]$Controller,
      [Parameter(ValueFromRemainingArguments=$true)][string[]]$GameArguments)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$exe=Join-Path $root 'out/build/win-amd64-release/psu.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'Run tools/build.ps1 first.' }
$plugin=Join-Path $root 'out/build/win-amd64-release/rexgpu-psu.dll'
if (-not (Test-Path -LiteralPath $plugin)) { throw 'Build the PSU GPU plugin with tools/build-gpu.ps1 first.' }
$launchArgs=@('--game_data_root',(Join-Path $root 'local'),'--gpu_plugin','psu',
    '--cache_root',(Join-Path $root 'local/cache-xps'),'--resolution','720p','--no-fullscreen')
if (-not $Controller) { $launchArgs+=@('--mnk_mode','--keybind_start','Return','--keybind_a','Space','--keybind_b','Backspace',
    '--keybind_dpad_up','I','--keybind_dpad_down','K','--keybind_dpad_left','J','--keybind_dpad_right','L') }
& $exe @launchArgs @GameArguments
if ($LASTEXITCODE -ne 0) { throw "PSU exited with code $LASTEXITCODE" }
