# 0.1.0-preview.3 validation

Tested October 22, 2026 on Windows x64 with an NVIDIA GeForce RTX 5090.

## Installer and launcher

- 39 automated checks passed, including real ISO verification, cancellation and
  rollback, existing-folder preservation, path validation, settings persistence,
  DPI sizing, borderless defaults and rejection of unsupported frame rates. The
  added checks cover Extra Mode's enabled default, persisted opt-out and migration
  of older settings files.
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
