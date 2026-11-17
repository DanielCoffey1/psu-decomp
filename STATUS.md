# Native recompilation status

Last tested: October 22, 2026, Windows x64, NVIDIA GeForce RTX 5090.

The 0.1.0-preview.4 installer and launcher support local ISO extraction, desktop
shortcuts with the game's official title icon, borderless windowed mode, up
to 4K rendering and a default-on Extra Mode/mission availability option. The launcher uses
60 FPS because the 120 FPS story test accelerated gameplay; normal-speed higher
frame rates remain unfinished. See the [installation instructions](README.md#download-and-install-windows)
and [release validation](release/VALIDATION.md).

Preview.4 adds an optional direct launch with saved settings.
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

## Network Mode

Two native Release game clients now join the same Colony lobby through the
original Xbox Live menu using separate authenticated community profiles. On
November 16, both rendered the other character; the user's sustained movement
of character A appeared in the second client, with matching remote coordinates.
Closing the second client removed its character while A stayed connected.
This verification used two processes on one Windows PC. Internet hosting and
cross-computer testing are still pending. Missions, combat, inventory, chat,
parties and travel between areas are not implemented.

Verified with the supported retail Xbox 360 executable and native Release build:

- Select **Xbox Live** with the development profile enabled to connect to the
  loopback server, complete login and redeem a one-time game-session ticket.
- Create a character using the original editor. Name validation completes locally;
  the game sends a 324-byte `0D02` packet, including its 316-byte character body.
- Restart the client and server: the saved name, level and appearance reappear in
  the character-selection screen. Character records persist in SQLite.
- Stay in the editor for several minutes without disconnecting. The server sends
  keepalives every five seconds after authentication.
- Restart the server while at character selection and choose **Retry**: the client
  reconnects and reloads the saved character without restarting the executable.
- Select **Enter** with the server's `--game-data` option: the client loads the
  disc's native Colony lobby, renders the saved character with 100/100 HP and
  accepts movement. Matching the player's quest ID to the archive's actual ID
  (13001) fixed the invisible avatar; Xbox status fields also differ from PS2.

### Shared community lobby

The community server has a 16-player lobby limit (two native clients tested),
separate character storage per account, one-time login tickets, a TLS listener
and per-player private connection profiles. The loopback adapter checks the
server's certificate fingerprint before sending the profile token. The original
Xbox Live menu connects through that adapter; no Microsoft account is used.

Build the native client and GPU plugin, install Python 3.11 or newer, then create
the first profile. Initial certificate generation also requires `cryptography`:

```powershell
python -m pip install cryptography
python ./tools/run-community-server.py add-player --profile ./local/community/player.json
python ./tools/run-community-server.py serve --game-data ./local
```

In another terminal:

```powershell
python ./tools/run-network.py --game-data ./local
```

Choose **Xbox Live**, select/create a character, then **Enter**. The launcher
starts its own adapter, verifies the server, and closes the adapter when the game
exits. It reports a missing server, rejected certificate or occupied adapter port
before launching the game. `--check` checks assets and connectivity without
starting the game; `--controller` uses controller input; `--trace` enables network
diagnostics. The game-data directory must contain the extracted `default.xex`
and `DATA` directory. Client settings and caches are isolated beside its profile.

For a second client on the same PC, create a different account and adapter port:

```powershell
python ./tools/run-community-server.py add-player --profile ./local/community/second.json
python ./tools/run-network.py --profile ./local/community/second.json --bridge-port 15022 --game-data ./local
```

Profiles contain credentials: distribute each one only to its intended player.
The server keeps only token hashes. The default state, profiles, certificates and
character databases remain under ignored `local/community/`. Preserve that state
when moving the server. See [deployment instructions](deploy/community/README.md)
for the Linux service and public endpoint configuration.

Six community integration tests pass with `python ./tools/test-community-server.py`.
They cover account isolation and restart persistence, cross-account/replayed
tickets, concurrent fragmented world loading, spawn/movement/disconnect/rejoin,
invalid movement, adapter login, and wrong token/certificate rejection. The full
capacity check connects 16 TLS protocol clients, verifies mutual spawn records,
rejects a 17th player, and admits that player after a vacancy opens. This is a
functional capacity test on the development PC, not a hosted performance test. Native
verification additionally covered remote spawn, movement and removal, a nonzero
local player ID, separate adapters, and launcher cleanup after game exit.

Xbox remote avatars need `location[18] = 1` and a matching quest/zone/map in the
transform at location offsets 64/68/72. Without these fields, the client creates
the character at `(0, -10000, 0)` and culls it. The packet regression test now
checks both fields and the announced position.

### Original single-account probe

Build the client and GPU plugin with the normal repository tools, then start:

```powershell
python ./tools/run-network-probe.py --login-test --game-data ./local
```

In another terminal, launch:

```powershell
./tools/run.ps1 --psu_trace_network=true --psu_network_dev_profile=true
```

Both switches default to false. The server binds only `127.0.0.1:15020`, uses one
shared development account and handles one active connection at a time. The
short-lived session ticket is a protocol test, not production authentication.
There are no firewall changes or public endpoints. Character storage defaults to
`local/network-probe/characters.sqlite3`; `--state-dir PATH` selects a separate
local test database. Without `--login-test`, the probe only counts incoming bytes.

Use `python ./tools/test-network-probe.py` for the TCP integration checks. They
cover split/coalesced frames, login handoff, idle keepalives beyond the old login
timeout, ticket replay rejection, malformed frames, character persistence across
server restart, initial character-load replies, invalid character records and
acknowledged lobby fragments with interleaved TCP commands. Six tests pass,
including after the account-storage migration. Real-client verification covers
the editor, persisted character, Retry, lobby rendering and user-confirmed movement;
synthetic tests alone do not establish compatibility.

The November 15 pause checkpoint has been superseded by the verified community
lobby above. The latest machine-specific handoff is
`local/network-resume-2026-11-16.md` (ignored by Git).

### Compatibility repairs

The pinned ReXGlue runtime supplies regular TCP sockets, but this disc also needs
Xbox sign-in, privileges, service discovery, title-server discovery and XNet calls
that the runtime does not fully implement. The opt-in profile supplies the local
responses at the specific call sites used by this executable. The service-info
layout was cross-checked against the
[Xenia Canary definition](https://github.com/AdrianCassar/xenia-canary/blob/netplay_canary_experimental/src/xenia/kernel/xnet.h).

The code-generation repair compares socket handles with the invalid sentinel;
valid ReXGlue handles have their high bit set. The development connection hook
preserves Winsock's nonblocking error so the client can poll instead of aborting.
The numeric loopback DNS result is completed locally. Disconnect clears the
32-byte title-server hostname while Retry skips discovery; the scoped development
handoff restores that field before reconnecting.

This disc's older `XStringVerify` call uses packed six-byte input and ten-byte
output structures. The development hook validates the supplied name and completes
synchronously. It does not contact Microsoft's name-verification service.

`psu_trace_network` logs call sites, return values, destinations and state changes;
server diagnostics log packet commands and sizes. Login payloads and session keys
are not logged. The game data, profiles, databases and diagnostic traces stay local
and are excluded from source control.

Protocol investigation used the
[Gurhal source](https://github.com/princebyyourlogic/gurhal) as a reference for shared
PSU packet layouts. Its supported PS2 discs differ from this Xbox disc. In
particular, the Xbox area archives use big-endian `NMLB` data; PS2 archives cannot
simply be substituted. Native lobby transfer and the local player's world record
are verified, including remote players in two native clients. Internet latency
and multi-computer compatibility still require testing. Archive/quest investigation also consulted
[prettystellaruniverse](https://github.com/PSChuze/prettystellaruniverse).
