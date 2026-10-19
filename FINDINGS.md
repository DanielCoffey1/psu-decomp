# Initial disc inspection

Inspected locally on October 19, 2026.

| Property | Observed value |
| --- | --- |
| User-supplied filename | Phantasy Star Universe (USA, Europe) (En,Fr,De).iso |
| Disc image size | 7,834,892,288 bytes |
| ISO volume label | XBOX360 |
| XDVDFS partition offset | 265,879,552 bytes (0xFD90000) |
| Filesystem entries including directories | 1,740 |
| Root executable | default.xex |
| Executable signature | XEX2 |
| Executable size | 9,449,472 bytes |
| Executable SHA-256 | 93D208EE55CC89265FBC6B9E95B1CF34AE364E47DF713CD9F3E8ADF6101C825E |

The region/language text above is from the filename, not independently verified title metadata. The executable has 15 optional headers, a security-information offset of 144, and an embedded PE data offset of 12,288.

## Executable analysis

| Property | Observed value |
| --- | --- |
| Title ID | 0x534507E3 |
| Media ID | 0x4D33612E |
| Version | 0.0.0.1 |
| Executable timestamp reported by SDK | 2006-10-02 15:52:28 UTC |
| Entry point | 0x823EE5E0 |
| Image base / mapped size | 0x82000000 / 0x00990000 |
| Code base / size | 0x82110000 / 0x005F60C4 |
| Default stack | 0x40000 bytes |
| File format | Normal encryption, basic compression |
| XAM imports | 83 function imports, 166 address/thunk records |
| Kernel imports | 126 function imports plus 10 variable slots, 262 records |

The loaded-image import analyzer resolves function ordinals using the pinned SDK's export tables. The ten variable slots have already been replaced with runtime pointers in the dump; their original ordinals are not inferred from those pointer values.

Section inventory from the loaded PE: .rdata, .pdata, .text, PSFD00, .data, .idata, .XBLD and .reloc. The disc contains 1,729 game data files under DATA. Every extracted game file's size was checked against the disc directory entry, with zero mismatches.

## Verified

- The inspector traversed this disc's directory trees without encountering bounds or cycle errors.
- The optional extraction produced a file with the XEX2 signature.
- Original content is confined to ignored local output.

## Not yet verified

- Disc authenticity or integrity against a known-good dump.
- Booting or gameplay in an emulator.
- Complete offline story gameplay and save/load.

The executable has now been statically translated, compiled and run with native graphics, audio and input initialization. The title, menus, opening movie and first story map render with the custom GPU plugin. Movement and readable dialogue were observed in Clyez City. See STATUS.md for the limits of current native testing; emulator boot was not used as proof of recompilation progress.
