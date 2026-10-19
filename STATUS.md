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

The baseline above runs the compiled translated game code in psu.exe. Xenia was closed during its initial setup dialog and was not used to establish gameplay claims.

## Native corrections

The stock GPU plugin rejected scratch-buffer vertex addresses in the 0xC0000000 range. After physical masking, drawing progressed but reused stale XPS scratch vertices. The custom plugin additionally invalidates and reloads those scratch ranges per draw. This restored readable title and menu rendering. A full XPS heap/write-watch implementation remains preferable for performance.

The analyzer omitted several indirect callbacks. Observed callback failures and reviewed static forwarding functions are recorded in the translation manifest. A separate guarded post-generation repair preserves a 198-instruction floating-point loop with two overlapping entry points. Both entries now share one body; all four backward branch destinations remain inside it. The resulting sources contain no unresolved-branch fatal stubs.

Keyboard button edges remain available for 120 ms because both runtime UI and guest code poll state. Losing focus clears those edges. This is an input usability change, not a game-logic bypass.

## Outstanding

- Finish verifying the opening story scene, player movement, battle and transitions.
- Verify creating a save and loading it after restarting.
- Continue registering any genuinely missing indirect callbacks found during play.
- Check for remaining rendering, audio and timing problems.
- Replace per-draw XPS scratch uploads with proper runtime alias write watches.

Logs and diagnostic dumps stay local. Source-generated game translations and binaries are excluded from Git.
