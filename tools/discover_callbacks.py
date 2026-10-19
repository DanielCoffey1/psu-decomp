"""Report computed callback candidates; never modify the translation manifest.

Requires generated sources and a local mapped-image diagnostic dump. This is
linear constant propagation, not a complete control-flow analysis. Review each
reported registration site and original instruction sequence before seeding it.
"""
import argparse
import json
import re
import struct
from pathlib import Path


def candidates(sources, image):
    mapped = {
        int(value, 16)
        for value in re.findall(
            r"\{ 0x([0-9A-F]+),", (sources / "psu_init.cpp").read_text()
        )
    }
    found = {}

    def plausible(address):
        offset = address - 0x82000000
        if address in mapped or address % 4 or not 4 <= offset < len(image) - 4:
            return False
        if not 0x82110000 <= address < 0x827060C4:
            return False
        previous, first = struct.unpack_from(">II", image, offset - 4)
        # Embedded jump tables can look like instructions after a bctr. Reject
        # entries whose first word is itself a pointer into the guest image.
        if 0x82000000 <= first < 0x84000000:
            return False
        return previous in (0x4E800020, 0x4E800420) or first == 0x7D8802A6

    for path in sorted(sources.glob("psu_recomp.*.cpp")):
        registers = {}
        function = ""
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith("DEFINE_REX_FUNC"):
                function = line
                registers = {}
            instruction = line.strip()
            if not instruction.startswith("// "):
                continue
            instruction = instruction[3:]
            used = []
            store = re.match(r"stw(?:x)? r(\d+),", instruction)
            if store:
                used.append(int(store[1]))
            call = instruction.startswith(("bl ", "bctrl"))
            if call:
                used.extend(range(3, 11))
            for register in used:
                address = registers.get(register, 0)
                if plausible(address):
                    found.setdefault(f"0x{address:08X}", []).append({
                        "function": function,
                        "file": path.name,
                        "line": number,
                        "consumer": instruction,
                        "register": register,
                    })

            destination = None
            value = None
            match = re.fullmatch(r"lis r(\d+),(-?\d+)", instruction)
            if match:
                destination = int(match[1])
                value = (int(match[2]) << 16) & 0xFFFFFFFF
            else:
                match = re.fullmatch(
                    r"(addi|ori) r(\d+),r(\d+),(-?\d+)", instruction
                )
                if match:
                    operation, destination, source, immediate = match.groups()
                    destination, source, immediate = map(
                        int, (destination, source, immediate)
                    )
                    if source in registers:
                        value = (
                            registers[source] + immediate
                            if operation == "addi"
                            else registers[source] | immediate
                        ) & 0xFFFFFFFF
                else:
                    match = re.fullmatch(r"mr r(\d+),r(\d+)", instruction)
                    if match:
                        destination, source = map(int, match.groups())
                        value = registers.get(source)
            if destination is not None:
                if value is None:
                    registers.pop(destination, None)
                else:
                    registers[destination] = value
                continue
            if call:
                for register in range(13):
                    registers.pop(register, None)
            elif not instruction.startswith(
                ("stw", "std", "stb", "sth", "cmp", "cmpl", "mt", "b", "stf", "nop")
            ):
                match = re.match(r"\S+ r(\d+),", instruction)
                if match:
                    registers.pop(int(match[1]), None)
    # Reflection callback tables also live in .data, after .text. Only accept
    # the exact four-instruction virtual-forwarding thunk here, not arbitrary
    # integers that happen to point inside an existing function.
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    section_count = struct.unpack_from("<H", image, pe + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    for index in range(section_count):
        header = pe + 24 + optional_size + index * 40
        name = image[header:header + 8].rstrip(b"\0").decode("ascii")
        if name not in (".data", ".rdata", "BINKDATA"):
            continue
        size, start = struct.unpack_from("<II", image, header + 8)
        for offset in range(start, min(start + size, len(image)) - 3, 4):
            address = struct.unpack_from(">I", image, offset)[0]
            if address in mapped or address % 4:
                continue
            if not 0x82110000 <= address < 0x827060C4:
                continue
            words = struct.unpack_from(">IIII", image, address - 0x82000000)
            if (words[0] == 0x81830000 and
                    words[1] & 0xFFFF0000 == 0x816C0000 and
                    words[2:] == (0x7D6903A6, 0x4E800420)):
                found.setdefault(f"0x{address:08X}", []).append({
                    "section": name,
                    "data_reference": f"0x{offset + 0x82000000:08X}",
                    "consumer": "virtual-forwarding callback table",
                })
    return dict(sorted(found.items()))


def main():
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=root / "generated/default")
    parser.add_argument(
        "--image", type=Path, default=root / "local/loaded-image.bin"
    )
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = candidates(args.sources, args.image.read_bytes())
    for address, uses in report.items():
        first = uses[0]
        location = (f"{first['file']}:{first['line']}" if "file" in first
                    else f"{first['section']}@{first['data_reference']}")
        print(f"{address}: {location} {first['consumer']}")
    print(f"{len(report)} unregistered callback candidates")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
