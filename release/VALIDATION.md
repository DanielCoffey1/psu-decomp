# 0.1.0-preview.4 validation

Tested October 22, 2026 on Windows x64 with an NVIDIA GeForce RTX 5090.

## Public-release privacy rebuild

The preview.1 through preview.4 downloads were rebuilt before public release
to remove embedded local source paths. Their original installer test suites
passed again (33, 36, 39 and 42 checks respectively), including real ISO
verification. The path guard passed eight positive/negative encoding cases.
A fresh preview.4 installation succeeded and its rebuilt native executable and
GPU plugin rendered the title screen using an isolated profile. The game and
launcher source logic remains unchanged. See [PRIVACY-REPACK.md](PRIVACY-REPACK.md)
for the replacement downloads' provenance and changed checksums.

## Preview.4 installer and launcher

- 42 automated checks passed, including real ISO verification, cancellation and
  rollback, existing-folder preservation, path validation, settings persistence,
  DPI sizing, borderless defaults and rejection of unsupported frame rates. New
  checks verify that direct launch is off for first/older installations, all
  settings survive a round trip with direct launch enabled, and switching it off
  preserves graphics settings.
- A fresh preview.4 installation completed and created PSU Settings.lnk with
  `--settings`, targeting that installation's launcher.
- The new checkbox and recovery instructions fit in the launcher at the current
  Windows display scaling. Save settings persisted `SkipLauncher=true`.
- A normal subsequent start exited the launcher with code 0, started the native
  game with the saved rendering, borderless, 60 FPS, input and Extra Mode values,
  and reached the title screen. Save & Play with the checkbox enabled also
  started the game and closed the launcher.
- Starting again while the game was running opened the settings window with an
  explanatory error and did not start a second game. PSU Settings.lnk reopened
  settings with bypass still enabled and without starting the game.
- The real story save's SHA-256 was unchanged after the launch checks. Holding
  Shift as an alternate settings override was not separately exercised.

## Previous preview.3 checks

The following checks were completed for preview.3. This update changes the
launcher and installer; the native game executable and GPU plugin are unchanged.

- The icon extractor rejects an unsupported executable. The official 64 × 64
  title image from the real ISO loads as a Windows icon, and its PNG bytes match
  the original artwork's SHA-256 after wrapping in an ICO container.
- A fresh preview.3 install generated the expected PSU.ico. Desktop-shortcut icon
  extraction and launcher title-bar display were also verified in preview.2.
- A fresh install from Setup.exe extracted 1,730 game files (6,881,780,470 bytes).
  All 36 packaged payload files matched their SHA-256 manifest, and the extracted
  default.xex matched the required revision.
- Installer and launcher text, Browse buttons and the new Extra Mode checkbox
  fit at the current Windows display scaling. Borderless mode and Extra Mode
  unlock were checked by default. Unchecking the launcher option and clicking
  Save settings wrote `UnlockExtraMode=false` to settings.xml.

## Gameplay and limitations

A separate profile with no story data entered Extra Mode, created a human
character and loaded My Room. The player saved it, reached the city and entered
an Extra Mode mission. The player confirmed both Colony missions appeared.
Combat showed player HP loss and a Rising Strike level-up.
Tracing confirmed stored access 0 / effective 1 and stored chapter 0 / effective
11. Read-only memory inspection after entry still found the actual unlock flag,
story-end flag and all 32 stored Extra Mode chapter ceilings at zero.

After closing the game, disabling the option removed Extra Mode from the title
menu, with stored access 0 / effective 0 in the trace. Re-enabling it restored
the menu and successfully loaded character A (level 1, 00:01:18) into My Room
with 112/112 HP. The stored flags and all 32 chapter ceilings remained zero
after reload. The separate real story save's SHA-256 was unchanged.

The native wrappers do not write these values. The chapter reader returns the
real stored value to the campaign's chapter setter so genuine progress can still
be recorded. Completing the campaign with this option remains unverified.
Later planets and every unlocked mission have not been tested individually.

The following graphics and story checks were established in earlier previews;
this update retains the same GPU plugin and graphics settings. Save & Play
started the installed executable with 3× draw scaling, ROV, movie compatibility,
non-exclusive fullscreen and 60 Hz guest VSync. The GPU log confirmed a
3840 × 2160 output source from the original 1280 × 720 mode. Borderless
presentation had no window title bar or taskbar.

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
