# 0.1.0-preview.2 validation

Tested October 22, 2026 on Windows x64 with an NVIDIA GeForce RTX 5090.

## Installer and launcher

- 36 automated checks passed, including real ISO verification, cancellation and
  rollback, existing-folder preservation, path validation, settings persistence,
  DPI sizing, borderless defaults and rejection of unsupported frame rates.
- The icon extractor rejects an unsupported executable. The official 64 × 64
  title image from the real ISO loads as a Windows icon, and its PNG bytes match
  the original artwork's SHA-256 after wrapping in an ICO container.
- A fresh preview.2 install generated the expected PSU.ico. The existing desktop
  shortcut was updated to use it, and the launcher title-bar icon was inspected.
- A fresh install from Setup.exe extracted 1,730 game files (6,881,780,470 bytes).
  All 36 packaged payload files matched their SHA-256 manifest, and the extracted
  default.xex matched the required revision.
- Installer and launcher text and Browse buttons fit at the tested 150% display
  scaling. Borderless windowed is selected by default.
- Save & Play started the installed native executable with 3× draw scaling, ROV,
  movie compatibility, non-exclusive fullscreen and 60 Hz guest VSync.
- The GPU log confirmed a 3840 × 2160 output source from the original 1280 × 720
  mode. Borderless presentation had no window title bar or taskbar.

## Gameplay and limitations

The baseline has loaded the saved opening Linear Line checkpoint, replayed the
corridor/Pannon cutscene and reached initial saber combat with damage and EXP
gain. The movie-video and reproduced story-blackout fixes remain enabled.

A 120 FPS story test ran too fast, as confirmed by the player. The launcher now
exposes only 60 FPS and rejects 30, 120 and unlocked settings. A present limiter
alone does not provide normal-speed gameplay at higher frame rates; that timing
work is unfinished.

Some opening story cutscenes retain a bottom black strip. Earlier 1× captures also
have 80 black rows at the bottom of a 1280 × 720 frame. This predates 4K scaling;
whether it matches the original console presentation remains unverified.

These checks do not establish a complete playthrough, exhaustive combat or save
correctness, 4K/60 performance in every scene, or compatibility with other GPUs.
Online mode is outside this prerelease's scope.
