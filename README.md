# Phantasy Star Universe Recompiled (experimental)

A native Windows x64 static recompilation of the Xbox 360 executable, using a pinned ReXGlue runtime. This early playable prototype reaches Chapter 1 Linear Line, with movement, HUD, NPC dialogue, initial saber combat and a save restored after restarting. Later progression is still under test. It is not a finished port or matching decompilation.

Game PowerPC instructions are translated ahead of time to C++ and compiled into psu.exe. The runtime supplies Xbox system services, graphics, input and audio. No emulator executable is launched by the project.

## Build

Requires Windows x64, PowerShell 7, Git, and Visual Studio C++ Build Tools with LLVM/Clang, CMake and Ninja. Use the recorded disc revision in [FINDINGS.md](FINDINGS.md); the build rejects other executable hashes.

```powershell
# Extract your disc locally, excluding the console system-update installer.
./tools/Inspect-Disc.ps1 -IsoPath 'D:/Games/Phantasy Star Universe.iso' -ExtractGame

# Download and verify the pinned SDK, then translate and compile the game.
$sdk = ./tools/setup-sdk.ps1
./tools/build.ps1 -Sdk $sdk

# Build the PSU graphics plugin from the same pinned SDK source.
./tools/build-gpu.ps1 -Sdk $sdk

# Launch the native executable.
./tools/run.ps1
```

Play PSU.cmd launches an already-built project. Keyboard defaults: Enter = Start, Space = A, Backspace = B, X = X/attack, P = Y, I/J/K/L = D-pad, WASD = left stick, Q/E = triggers, V = right-stick click. A controller can also be used; ./tools/run.ps1 -Controller disables keyboard gamepad emulation. Runtime settings expose the other keybindings.

Extracted content, mapped executable dumps, generated translations, caches and binaries stay in ignored local/, generated/ and out/ directories. The original ISO is never modified.

## Native fixes

- Explicit entry points for direct branches and runtime-discovered indirect callbacks.
- Verified virtual-forwarding callbacks referenced by constant tables and registration code.
- A guarded code-generation repair shares one translated loop body between two overlapping entry points, preserving its four backward branches.
- A custom D3D12 GPU plugin wraps XPS/writeback vertex and index addresses to physical backing and applies the corresponding shader-fetch mask. Scratch vertex buffers are re-uploaded on each draw because the pinned runtime does not watch CPU writes through the XPS alias. This correctness workaround may cost performance.
- PSU's Sofdec movie shader has a presentation compatibility path: the native decoder's YUV planes are converted using the game's color constants and uploaded for display. The intro movie now shows video. Decoder, audio and playback timing remain in the translated game. Pass `--no-psu_movie_present` to compare the original graphics path. Remaining story black intervals are still under investigation.
- Keyboard button edges remain available for 120 ms to both UI and game input polling, avoiding missed short taps.

The SDK is pinned by revision and file hashes. Its installed files are not modified. The custom plugin is built separately as rexgpu-psu.dll. Its shader cache is isolated in local/cache-xps.

## Analysis

Launch with `./tools/run.ps1 -Diagnostics` to record file opens, save-container operations, waits of at least 50 ms, guest-present gaps of at least 250 ms, and CSV GPU counters. CSV files stay in ignored `local/traces/`; runtime logs stay beside the executable in `logs/`. Background waits and regular presents during a black image do not by themselves identify its cause. Counters from SDK components compiled without profiling remain zero.

Use `-Stage` with both build scripts to produce `psu-staged.exe` and `rexgpu-psu-staged.dll` while the normal build is running. `./tools/run.ps1 -Staged -Diagnostics` launches that pair. Close the running game before replacing its executable or plugin.

Saves use the runtime's Documents/psu profile directory, independently of the repository. Back up that directory before destructive save tests. Save files, screenshots and diagnostics are never committed.

```powershell
./tools/Analyze-Xex.ps1
$env:PSU_DUMP_IMAGE = '1'
./tools/run.ps1
# After closing the game:
Remove-Item Env:PSU_DUMP_IMAGE
python ./tools/discover_callbacks.py --json local/callback-candidates.json
python ./tools/analyze_imports.py --sdk-source local/gpu-source
```

Callback candidates require review before adding manifest hints. Loaded variable imports have already been replaced by runtime addresses, so the import analyzer reports those slots separately instead of inventing ordinals. See [STATUS.md](STATUS.md) for verification and outstanding work.

## Upstream work

- [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk/tree/bd833a2ab69d305f99ddf57418fc38ffec8af93d): translation, runtime and graphics infrastructure.
- [Xenia Canary XPS fix](https://github.com/xenia-canary/xenia-canary/commit/22708301ba76d10aae6f7d7caac8b1cac9e4a8e6): reference for physical address masking. The prototype does not incorporate that commit's full runtime heap implementation.
- [tenora-works](https://github.com/Agrathejagged/tenora-works): PSU format research.

ReXGlue and Xenia notices are retained in [third_party/rexglue-LICENSE.txt](third_party/rexglue-LICENSE.txt). Online services remain outside the initial offline story-mode scope.
