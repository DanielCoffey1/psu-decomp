# Phantasy Star Universe: Xbox 360 research

An early reverse-engineering project working toward a playable native PC build of Phantasy Star Universe. **There is no playable build or decompiled game source yet.**

The initial tool reads an owner-supplied Xbox 360 XDVDFS disc, inventories its filesystem, and optionally extracts the root executable for local analysis. It does not modify the disc.

## Inspect your disc

In PowerShell, from this repository:

```powershell
./tools/Inspect-Disc.ps1 -IsoPath 'D:/Games/Phantasy Star Universe.iso'
# Optional: also extract default.xex locally
./tools/Inspect-Disc.ps1 -IsoPath 'D:/Games/Phantasy Star Universe.iso' -ExtractExecutable
```

Results go into ignored `local/`. The inspector supports common Xbox disc partition offsets; it is not a general ISO extractor. Keep game binaries, assets, generated translations, keys, and disc images out of commits.

## Route to a playable build

1. Identify the disc and executable, record hashes, and establish a repeatable local extraction process.
2. Establish an emulator baseline for offline story mode: boot, menus, new game, movement, battle, saving and loading. Record behavior and failures.
3. Analyze the XEX imports, entry point, code boundaries, indirect branches, and executable modules. Select and pin a recompilation toolchain after testing this executable.
4. Translate PowerPC code and implement the required kernel, memory, threading, filesystem, graphics, shader, audio, and input behavior.
5. Reach the title screen, then an offline story scene, then a complete gameplay loop with save/load. Compare each milestone with the baseline.
6. Package an asset import process and reproducible build without distributing original game content.

A matching decompilation reconstructs readable source and verifies machine-code equivalence. Static recompilation translates machine code to host code and still requires a runtime. The final approach is not selected yet; neither is a one-command conversion from an ISO.

## Starting references

- [XenonRecomp](https://github.com/hedge-dev/XenonRecomp): Xbox 360 static recompilation; a game runtime must also be supplied.
- [Xenia](https://github.com/xenia-project/xenia): Xbox 360 emulator and reference for a local behavior baseline.
- [tenora-works](https://github.com/Agrathejagged/tenora-works): existing PSU format research and tools; evaluate platform compatibility before reuse.

Online services are a separate research effort. Initial scope is offline story mode.
