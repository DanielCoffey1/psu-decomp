# Native recompilation status

Last tested: October 19, 2026, Windows x64, NVIDIA GeForce RTX 5090.

## Verified locally

- Disc inspection and game-data extraction; all file sizes match directory records.
- XEX metadata and system-library import analysis.
- ReXGlue AOT code generation and a Release native executable build.
- Source-built PSU GPU plugin against the same pinned SDK revision.
- Native Direct3D 12, controller, keyboard and audio initialization.
- Full title-screen rendering, including text and first-run save-data prompts.
- Keyboard Start, confirmation and menu navigation.
- Offline Story Mode selection and New Game selection.
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

Other black transitions remain unresolved. One observed black interval continued
to present around 60 frames per second with about 303 draws per frame. The
observed save-file opens took about 0.1 ms. Neither result identifies the cause
of the visual pause, and no blanket fade skip or timing bypass has been applied.

This is an early playable story-mode prototype. These checks do not establish a complete playthrough, exhaustive combat or save/load correctness, or a finished port.

Logs and diagnostic dumps stay local. Source-generated game translations and binaries are excluded from Git.
