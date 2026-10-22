# Phantasy Star Universe Recompiled (experimental)

A native Windows x64 static recompilation of the Xbox 360 executable, using a pinned ReXGlue runtime. This early playable prototype reaches Chapter 1 Linear Line, with movement, HUD, NPC dialogue, initial saber combat and a save restored after restarting. Later progression is still under test. It is not a finished port or matching decompilation.

Game PowerPC instructions are translated ahead of time to C++ and compiled into psu.exe. The runtime supplies Xbox system services, graphics, input and audio. No emulator executable is launched by the project.

## Download and install (Windows)

Download the installer from the [0.1.0-preview.3 prerelease](https://github.com/DanielCoffey1/psu-decomp/releases/tag/v0.1.0-preview.3).
This repository is private, so you must be signed in to a GitHub account with access.

You need Windows 10/11 x64, .NET Framework 4.8, a Direct3D 12 GPU, your own
USA/Europe Xbox 360 **Phantasy Star Universe ISO**, and at least 8 GB of free space
for the installation in addition to the ISO. The verified story-cutscene fix
requires GPU rasterizer-ordered-view (ROV) support. Setup checks that the ISO's
executable matches the [supported revision](FINDINGS.md).

1. In the release's **Assets**, download
   **PSU-Recompiled-0.1.0-preview.3-win-x64-Setup.exe**. The source ZIP is for
   developers; it does not install the game.
2. Run the installer and click **Browse...** beside **Game ISO** to select your ISO.
   You do not need to mount or extract it first.
3. Choose a **new installation folder**, or keep the default
   `%LOCALAPPDATA%\Programs\PSU Recompiled`. Setup will not overwrite an existing folder.
4. Choose your graphics settings. Leave **Borderless windowed** checked to fill
   the desktop without a title bar. Keep **Create a desktop shortcut** checked.
5. Click **Install game**. Setup verifies the disc revision and extracts game
   data locally. No compiler, administrator access or installation-time download
   is required. Your ISO is left unchanged. Setup also extracts the official Xbox
   360 PSU title icon for the desktop shortcut and launcher window.
6. Open **Phantasy Star Universe Recompiled** on your desktop, or **PSU Launcher.exe**
   in the installation folder. Click **Save & Play**, then choose **Story Mode**
   or **Extra Mode**. Use **New Game** to create an Extra Mode character, or
   **Continue** to load an existing save for the selected mode.

The installer supplies the native executable and runtime. Game assets come from
your ISO; no ISO, original XEX, movies or other disc data are included in the download.
This experimental prerelease is unsigned. See the [release notes](release/RELEASE-NOTES.md)
and [validation record](release/VALIDATION.md) for tested behavior and known issues.

### Resolution, borderless mode and frame rate

- **For 4K:** choose **3840 × 2160 (4K)** and **3× — up to 4K** render scale.
  Borderless mode uses your desktop's display mode; use a 3840 × 2160 desktop for
  4K display output. The window-resolution selector applies when borderless mode
  is off. The render-scale selector controls internal rendering in either mode.
- **For a regular window:** uncheck **Borderless windowed** and choose a window
  resolution. Oversized windows fit the screen without reducing internal render scale.
- **Frame rate is currently 60 FPS.** Testing confirmed that 120 FPS speeds up
  gameplay. 30 FPS, 120 FPS and unlocked mode are unavailable until timing is fixed.
  Higher resolution can reduce performance; movies retain their original resolution.
- Change settings in the launcher before starting the game. Settings apply on the
  next launch; close the running game before starting another copy.

### Extra Mode from the start

Available starting with preview.3.

**Unlock Extra Mode and story-gated missions** is checked by default in both
setup and the launcher. You can create your own offline character immediately
and access mission availability normally tied to campaign progress. Character
levels, mission level/rank requirements and earned rewards still follow the
game's rules; this does not restore online services or online-only content.

The option overrides availability checks without marking the story completed
or writing campaign unlock flags. Uncheck it and relaunch to restore the game's
normal story-based availability. Extra Mode characters use the game's normal
save system. Save at a save point before closing the game.

Mission difficulty is unchanged: Evacuation has level-10 enemies with no entry
level requirement. Creature Discomfort starts at enemy level 5; Annihilation has
level-35 enemies and requires a level-30 character.

Developer launches enable this by default too. Pass
`--psu_unlock_extra_mode=false` for original rules and
`--psu_trace_extra_mode=true` to log the stored and effective availability values.

### Saves, updates and troubleshooting

Saves are stored in **Documents\psu**, separate from the installation. Existing
development-build saves use the same location. Launcher settings are stored in
`settings.xml` beside the launcher, and logs are in the installation's `bin\logs`.

To update, close the game and install the newer version into a **new folder**.
Your saves remain available. If a desktop shortcut already exists, setup creates
a second shortcut with a date/time suffix; use the new shortcut for the new build.
To uninstall, close the game and remove its installation folder and shortcut.
Keep Documents\psu if you want to retain saves.

If setup reports an unsupported executable, check that you selected the matching
Xbox 360 USA/Europe disc revision. If it reports an existing destination, choose
a new folder. If no shortcut was created, run `PSU Launcher.exe` directly.
Some opening cutscenes still have a bottom black strip; it also occurs at 1×
rendering and its original-console behavior remains unverified. Later chapters
and a complete story playthrough have not yet been verified.

## Build the installer (developers)

The launcher/installer is built using Windows' .NET Framework C# compiler. Build
the native executable and patched GPU using the instructions below before packaging.

```powershell
# Use the verified SDK and patched source tree from the native build below.
# Pass -BuildNative to rebuild the native executable and GPU as part of packaging.
./tools/build-release.ps1 -Sdk $sdk -GpuSource 'C:/path/to/patched/rexglue-source'
./tools/test-release.ps1 -IsoPath 'D:/Games/Phantasy Star Universe.iso'
```

Output: `out/release/PSU-Recompiled-0.1.0-preview.3-win-x64/`, including a single
Setup.exe, source snapshot, build metadata, release notes, validation record and
SHA-256 checksums. Use `-OutputDirectory` to choose a different artifact folder.
Packaging stays local; this script does not publish a GitHub release.

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
- PSU's Sofdec movie shader has a presentation compatibility path: the native decoder's YUV planes are converted using the game's color constants and uploaded for display. The intro movie now shows video. Decoder, audio and playback timing remain in the translated game. Pass `--no-psu_movie_present` to compare the original graphics path. The movie compatibility path remains enabled.
- The PSU graphics plugin defaults to the D3D12 rasterizer-ordered-view (ROV) render-target path. This fixes the reproduced Chapter 1 corridor/Pannon cutscene blackouts; the host-render-target path lost the final image while the scene texture remained valid. The selected path is logged at startup. `--render_target_path_d3d12=rtv` restores the old path for comparisons. Hardware without ROV support falls back to that path and may retain the issue.
- Keyboard button edges remain available for 120 ms to both UI and game input polling, avoiding missed short taps.

The SDK is pinned by revision and file hashes. Its installed files are not modified. The custom plugin is built separately as rexgpu-psu.dll. Its shader cache is isolated in local/cache-xps.

## Analysis

Launch with `./tools/run.ps1 -Diagnostics` to record file opens, save-container operations, waits of at least 50 ms, guest-present gaps of at least 250 ms, and CSV GPU counters. CSV files stay in ignored `local/traces/`; runtime logs stay beside the executable in `logs/`. Background waits and regular presents during a black image do not by themselves identify its cause. Counters from SDK components compiled without profiling remain zero. Use `--name=value` for GPU options with values (for example `--render_target_path_d3d12=rtv`); the GPU plugin registers its options after initial argument parsing, so separated values are not reliably applied.

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
