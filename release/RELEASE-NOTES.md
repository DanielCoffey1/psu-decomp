# PSU Recompiled 0.1.0-preview.4 — experimental prerelease

Experimental Windows x64 native recompilation of the Xbox 360 offline modes.
This is an early playable build; later chapters and a complete playthrough are
not yet verified.

This update adds **Skip launcher next time (use saved settings)**. Check it and
click Save settings or Save & Play; future desktop-shortcut launches start the
game with all saved settings. Open **PSU Settings** in the installation folder
to change them again, or hold Shift while opening your desktop shortcut. The
`--settings` launcher argument also opens settings. Startup errors return to the
launcher. The option is off by default, including when updating older settings.

**Unlock Extra Mode and story-gated missions**, introduced in preview.3, remains
enabled by default. Create a custom offline character immediately
and use the mission availability normally unlocked through the campaign.
Character levels and mission level/rank requirements still apply.

The option changes availability checks, without writing campaign completion or
unlock flags. Uncheck it and relaunch to restore normal story-based availability.
Extra Mode uses the game's normal save system; save at a save point before quitting.
This provides the disc's offline Extra Mode, not online services or online-only
content. The official title icon, borderless mode and 60 FPS settings are retained.

## Install and play

1. Download **PSU-Recompiled-0.1.0-preview.4-win-x64-Setup.exe** from this
   [prerelease's Assets](https://github.com/DanielCoffey1/psu-decomp/releases/tag/v0.1.0-preview.4)
   and run it. The source ZIP is for developers and does not install the game.
2. Browse to your USA/Europe Xbox 360 PSU ISO and choose a new installation folder.
3. Choose graphics settings and click Install game. The installer verifies the
   executable revision, extracts your game data and creates a desktop shortcut.
4. Use that shortcut to open the launcher, change settings and click Save & Play.
5. Choose Extra Mode, then New Game to create a character, or Continue to load
   one. Story Mode remains available separately.

Mission difficulty is unchanged. Evacuation has level-10 enemies and no entry
level requirement. Creature Discomfort starts at enemy level 5. Annihilation has
level-35 enemies and requires a level-30 character.

The installer includes a precompiled native executable, the patched GPU plugin,
runtime libraries and notices. It extracts data from your ISO locally; installation
does not run a compiler. It includes no ISO, original XEX, movies or other disc data.
Your ISO is opened read-only. Setup skips console system-update files.

Requires Windows 10/11 x64 with .NET Framework 4.8 and a Direct3D 12 GPU. ROV support
is needed for the verified cutscene fix. GPUs without ROV may retain blackouts.
Installation needs the extracted game's size plus 512 MB free. No administrator
access, internet download or development tools are needed during installation.
This prerelease is unsigned.

## Graphics

- Borderless windowed is enabled by default and fills the desktop without changing
  its display mode. Turn it off for a resizable window. Window sizes: 720p, 1080p,
  1440p and 4K; this selection applies to windowed mode.
  Windows display scaling is accounted for; oversized windows fit the screen
  while retaining the selected internal render scale.
- Internal draw scales: 1x, 2x and 3x. 3x scales the game's 720p output to 4K;
  individual game render passes may start below 720p. 1080p defaults to 2x rendering
  downsampled to the window. Movies retain their source resolution.
- Frame rate: 60 FPS. A 120 FPS story test confirmed that gameplay runs too fast.
  30 FPS, 120 FPS and unlocked settings are unavailable; normal-speed support at
  other frame rates requires further simulation-timing work. The 60 FPS target
  does not guarantee that every GPU can sustain 4K at that rate.
- Settings take effect on the next game launch. The ROV cutscene fix and movie fix
  remain enabled at every preset.

Keyboard: Enter = Start, Space = A, Backspace = B, X = attack, P = Y, WASD = move,
I/J/K/L = D-pad, Q/E = triggers, V = right-stick click. Controllers are supported.

## Saves and maintenance

Saves remain in Documents/psu, separate from the installation. Existing development
build saves use this same location. Shader caches use LocalAppData/PSU Recompiled.
Settings live in settings.xml beside the launcher. Logs live in bin/logs.

Setup will not overwrite an existing folder. To try a newer build, install it to a
new folder. To remove this portable installation, close the game and delete its
installation folder and desktop shortcut; saves are retained.

## Scope

The baseline has been tested through the opening Linear Line corridor, Pannon
introduction, initial saber combat, and checkpoint loading. Intro movie video and
the reproduced story-cutscene blackouts are fixed. Later chapters and full story
completion are not yet verified. Online mode is outside this release's scope.

A bottom black strip remains in some opening story cutscenes. Earlier 1x captures
also contain it (80 rows of the 720-row frame), so it predates 4K scaling. Whether
this matches the original console presentation is still unverified.

Source snapshot, build metadata and SHA-256 checksums accompany the installer.
See licenses in the installed folder and third_party in the source snapshot.
Runtime source: https://github.com/rexglue/rexglue-sdk/tree/bd833a2ab69d305f99ddf57418fc38ffec8af93d
Microsoft CRT deployment: https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files
