# Native recompilation status

Last tested: October 22, 2026, Windows x64, NVIDIA GeForce RTX 5090.

The published 0.1.0-preview.3 installer and launcher support local ISO extraction, desktop
shortcuts with the game's official title icon, borderless windowed mode, up
to 4K rendering and a default-on Extra Mode/mission availability option. The launcher uses
60 FPS because the 120 FPS story test accelerated gameplay; normal-speed higher
frame rates remain unfinished. See the [installation instructions](README.md#download-and-install-windows)
and [release validation](release/VALIDATION.md).

The preview.4 review build adds an optional direct launch with saved settings.
The installation's PSU Settings shortcut, `--settings`, or holding Shift opens
the launcher again. Startup errors also return to the settings window.

## Verified locally

- Disc inspection and game-data extraction; all file sizes match directory records.
- XEX metadata and system-library import analysis.
- ReXGlue AOT code generation and a Release native executable build.
- Source-built PSU GPU plugin against the same pinned SDK revision.
- Native Direct3D 12, controller, keyboard and audio initialization.
- Full title-screen rendering, including text and first-run save-data prompts.
- Keyboard Start, confirmation and menu navigation.
- Offline Story Mode selection and New Game selection.
- Extra Mode unlocked on a separate profile with no story progress: character
  creation, My Room, city access and entry into a free mission. Stored campaign
  unlock and completion flags remained zero. Mission level requirements still apply.
- Extra Mode's saved level-1 character reloaded into My Room after restarting.
  Disabling the option removed Extra Mode from the title menu; re-enabling restored
  access. The real story save remained unchanged during these isolated tests.
- Opening movie playback and skipping into the first story map.
- Clyez City 1st Floor: Central Table loads as a rendered 3D scene.
- Player movement, HUD and nearby interaction prompts.
- Readable Lumia dialogue and portrait while moving through the city.
- User-driven progression from Clyez City to Linear Line Platform.
- A Chapter 1 Linear Line save created by the user, then read after restarting
  through Continue. Ethan restored in the corridor with his saber, level 1 and
  112/112 HP; the slot records 00:09:12 played. The profile was backed up first.
- Replay after the callback fix reaches Pannon combat in Access Corridor:
  Block B-2. Native rendering shows a saber hit with a 17 damage number,
  subsequent attack animation, a partially filled experience bar and weapon PP
  falling from 85/85 to 78/85. This verifies initial combat, not every mechanic.

The baseline above runs the compiled translated game code in psu.exe. Xenia was closed during its initial setup dialog and was not used to establish gameplay claims.

## Native corrections

The stock GPU plugin rejected scratch-buffer vertex addresses in the 0xC0000000 range. After physical masking, drawing progressed but reused stale XPS scratch vertices. The custom plugin additionally invalidates and reloads those scratch ranges per draw. This restored readable title and menu rendering. A full XPS heap/write-watch implementation remains preferable for performance.

The analyzer omitted several indirect callbacks. Observed callback failures and reviewed static forwarding functions are recorded in the translation manifest. A separate guarded post-generation repair preserves a 198-instruction floating-point loop with two overlapping entry points. Both entries now share one body; all four backward branch destinations remain inside it. The resulting sources contain no unresolved-branch fatal stubs.

Keyboard button edges remain available for 120 ms because both runtime UI and guest code poll state. Losing focus clears those edges. This is an input usability change, not a game-logic bypass.

The launcher explicitly separates D-pad I/K/L from the stock SDK's left trigger,
right-stick click and X bindings. Previously those keys performed two actions.
It also waits for the Windows GUI process before checking its exit status.

Loading Access Corridor: Block B-2 exposed an unregistered callback at
0x82345B70. Its original instructions adjust r3 by 0x80 and tail-branch to
0x82347580. The manifest now includes that entry, four adjacent adjustors and
eight exact table-referenced adjustors with translated destinations. The native
Release build registers these entries; replay passed the prior crash point and
reached combat.

Opt-in runtime and GPU tracing now captures file/container operations, long
waits, present gaps and frame counters. The app opens the CSV file explicitly
because the pinned SDK registers its flag without opening it. GPU counter
instrumentation is compiled into the custom plugin; stock runtime counters may
remain zero.

## Outstanding

- Verify damage to the player, healing, ranged combat, later story progression
  and additional map transitions.
- Verify additional save slots, later checkpoints and repeated save cycles.
- Continue registering any genuinely missing indirect callbacks found during play.
- Check for remaining rendering, audio and timing problems.
- Replace per-draw XPS scratch uploads with proper runtime alias write watches.

The runtime logs an unimplemented XLIVEBASE message (0x0005800E) during city gameplay. The tested gameplay continues, but the message's effect on later features has not been established. Requests for xf_sn_990000_00.nbl also fail; that path is absent from this disc's directory inventory, and loading continues. No replacement game file was fabricated.

The intro movie's missing video was reproduced and corrected on October 20.
The native Sofdec decoder produced recognizable YUV frames while the original
graphics path displayed black. The custom plugin now recognizes the exact PSU
YUV movie shader, validates its three linear 8-bit planes, converts them with
the game's color constants, and uploads a frame for presentation. Upload buffers
are retained until their GPU frame completes. Frames are used only for the swap
following a matching movie draw, so gameplay does not retain a stale movie image.
The installed SDK remains unchanged; the plugin build uses its patched source
headers consistently.

Verified in the native Release build: visible intro movie footage, exiting the
movie, loading the existing Linear Line save, and returning to a rendered
in-game interaction. The user then resumed story testing and reported that black
intervals might be shorter but still remain; that result is inconclusive.
Full movie completion, all story movies, subtitle/overlay behavior, and performance
across later scenes still need verification. This is a targeted compatibility
path, not a demonstrated repair of the underlying graphics fault.

The reproduced Chapter 1 story blackouts were corrected on October 21 by
selecting the D3D12 ROV render-target path in the PSU plugin. With the old RTV
path, GPU captures showed a valid scene and final composition, followed by a
black presentation image. The exact failing RTV clear/ownership/copy operation
has not been isolated. ROV preserves the image through this sequence without
changing story timing, fades, or translated game logic.

The same saved checkpoint was replayed with ROV explicitly confirmed in the
startup log. The corridor dialogue, camera changes and Pannon introduction were
visible, and the user reported that the blackouts appeared fixed. The captured
story segment contained zero completely black samples among 42 captures;
the earlier RTV replay had 12 among 38. These are sampled replays with different
timings, not exhaustive frame-by-frame coverage. Testing continued into saber
combat, displaying damage numbers and EXP +4 for defeated Pannons.

Immediate resolve readback did not fix the RTV failure. Earlier tests using
separated GPU option values were invalid: late-registered plugin options need
`--name=value`. The final change defaults to ROV without forcing readback or
retaining the temporary image/vertex capture code. Explicit RTV selection still
works, and unsupported hardware retains the runtime's RTV fallback. Later
chapters and performance on other GPUs remain unverified.

The clean Release plugin starts with `PSU render target path: rov` without a
command-line override. Intro movie footage remains visible with the existing
Sofdec presentation path. The patch applies cleanly to the pinned SDK source
and the plugin builds successfully. Temporary GPU capture code is excluded.

This is an early playable story-mode prototype. These checks do not establish a complete playthrough, exhaustive combat or save/load correctness, or a finished port.

Logs and diagnostic dumps stay local. Source-generated game translations and binaries are excluded from Git.
