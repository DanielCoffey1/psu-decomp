"""Resolve XEX imports from an opt-in loaded-image dump and pinned SDK sources."""
import argparse
import json
import re
import struct
from pathlib import Path


def analyze(xex, image, source):
    def u32(offset):
        return struct.unpack_from('>I', xex, offset)[0]

    headers = {u32(24+i*8): u32(28+i*8) for i in range(u32(20))}
    base = headers[0x10201]
    offset = headers[0x103FF]
    length, string_size, library_count = struct.unpack_from('>III', xex, offset)
    end = offset + length
    names = [s.decode('ascii') for s in xex[offset+12:offset+12+string_size].split(b'\0') if s]
    cursor = offset+12+string_size
    libraries = []
    for _ in range(library_count):
        size = u32(cursor)
        name_index, count = struct.unpack_from('>HH', xex, cursor+36)
        if size < 40+count*4 or cursor+size > end:
            raise ValueError('Invalid import library')
        library = names[name_index]
        table = source / 'src/kernel' / Path(library).stem / 'export_table.inc'
        exports = {
            int(ordinal, 16): name for ordinal, name in re.findall(
                r'XE_EXPORT\(\w+,\s*(0x[0-9A-Fa-f]+),\s*(\w+),', table.read_text())
        }
        records = {}
        unresolved_data = []
        for i in range(count):
            address = u32(cursor+40+i*4)
            value = struct.unpack_from('>I', image, address-base)[0]
            # The runtime has already replaced variable import words with
            # addresses. Those words no longer encode an ordinal.
            if value >> 24 not in (0, 1):
                unresolved_data.append(f'0x{address:08X}')
                continue
            ordinal = value & 0xFFFF
            record = records.setdefault(ordinal, {
                'ordinal': ordinal, 'name': exports.get(ordinal, 'UNKNOWN'), 'records': []})
            record['records'].append({'address': f'0x{address:08X}', 'type': value >> 24})
        libraries.append({'library': library, 'imports': sorted(records.values(), key=lambda r:r['ordinal']),
                          'unresolved_variable_slots': unresolved_data})
        cursor += size
    return libraries


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk-source', type=Path, required=True)
    parser.add_argument('--xex', type=Path, default=root/'local/default.xex')
    parser.add_argument('--image', type=Path, default=root/'local/loaded-image.bin')
    parser.add_argument('--output', type=Path, default=root/'local/imports.json')
    args = parser.parse_args()
    result = analyze(args.xex.read_bytes(), args.image.read_bytes(), args.sdk_source)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    for library in result:
        print(f"{library['library']}: {len(library['imports'])} resolved imports; "
              f"{len(library['unresolved_variable_slots'])} patched variable slots")
        print(', '.join(record['name'] for record in library['imports']))
