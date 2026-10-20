param([switch]$Controller,
      [switch]$Staged,
      [switch]$Diagnostics,
      [Parameter(ValueFromRemainingArguments=$true)][string[]]$GameArguments)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$exeName=if($Staged){'psu-staged.exe'}else{'psu.exe'}
$pluginName=if($Staged){'psu-staged'}else{'psu'}
$exe=Join-Path $root "out/build/win-amd64-release/$exeName"
if (-not (Test-Path -LiteralPath $exe)) { throw 'Run tools/build.ps1 first.' }
$plugin=Join-Path $root "out/build/win-amd64-release/rexgpu-$pluginName.dll"
if (-not (Test-Path -LiteralPath $plugin)) { throw 'Build the PSU GPU plugin with tools/build-gpu.ps1 first.' }
$launchArgs=@('--game_data_root',(Join-Path $root 'local'),'--gpu_plugin',$pluginName,
    '--cache_root',(Join-Path $root 'local/cache-xps'),'--resolution','720p','--no-fullscreen')
if (-not $Controller) { $launchArgs+=@('--mnk_mode','--keybind_start','Return','--keybind_a','Space','--keybind_b','Backspace',
    '--keybind_x','X','--keybind_y','P','--keybind_left_trigger','Q','--keybind_right_trigger','E',
    '--keybind_rstick_press','V',
    '--keybind_dpad_up','I','--keybind_dpad_down','K','--keybind_dpad_left','J','--keybind_dpad_right','L') }
if($Diagnostics){
    $traceRoot=Join-Path $root ('local/traces/'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Force -Path $traceRoot | Out-Null
    $launchArgs+=@('--psu_trace_runtime','--psu_trace_gpu','--perf_log_csv',(Join-Path $traceRoot 'frames.csv'))
}
# Piping a Windows GUI executable makes PowerShell wait for its exit code.
& $exe @launchArgs @GameArguments | Out-Host
if ($LASTEXITCODE -ne 0) { throw "PSU exited with code $LASTEXITCODE" }
