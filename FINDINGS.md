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

The region/language text above is from the filename, not independently verified title metadata. The executable has 15 optional headers, a security-information offset of 144, and an embedded PE data offset of 12,288. Imports and executable sections have not yet been analyzed.

## Verified

- The inspector traversed this disc's directory trees without encountering bounds or cycle errors.
- The optional extraction produced a file with the XEX2 signature.
- Original content is confined to ignored local output.

## Not yet verified

- Disc authenticity or integrity against a known-good dump.
- Booting or gameplay in an emulator.
- Compatibility of this executable with a static recompiler.
- Any native runtime or playable build.
