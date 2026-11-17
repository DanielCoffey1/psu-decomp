"""Experimental Xbox lobby records, using archives from the user's own disc.

This deliberately serves one development location and placeholder level-one
statistics. It does not implement missions, inventory or combat.
"""

from pathlib import Path
import struct

QUEST_ID = 13001  # quest.ynr main block +8 in this disc's Extra lobby archive.


def read_lobby_archive(path):
    """Read two named entries without extracting or redistributing disc assets."""
    wanted = {b"quest_ae.nbl", b"zone02_ae.nbl"}
    blobs = {}
    with path.open("rb") as archive:
        archive.seek(0, 2)
        size = archive.tell()

        def read(offset, length):
            if offset < 0 or length < 0 or offset + length > size:
                raise ValueError("Lobby AFS entry is outside the archive")
            archive.seek(offset)
            data = archive.read(length)
            if len(data) != length:
                raise ValueError("Truncated lobby AFS")
            return data

        magic, count = struct.unpack("<4sI", read(0, 8))
        if magic != b"AFS\0" or not 1 <= count <= 4096:
            raise ValueError("Invalid lobby AFS header")
        table = read(8, (count + 1) * 8)
        names, names_size = struct.unpack_from("<II", table, count * 8)
        if names_size < count * 48:
            raise ValueError("Missing lobby AFS names")
        directory = read(names, count * 48)
        for index in range(count):
            name = directory[index * 48:index * 48 + 32].split(b"\0", 1)[0]
            if name not in wanted:
                continue
            offset, length = struct.unpack_from("<II", table, index * 8)
            if name in blobs or not 32 <= length <= 4 * 1024 * 1024 or length % 4:
                raise ValueError("Invalid or duplicate lobby archive member")
            blob = read(offset, length)
            if blob[:4] != b"NMLB":
                raise ValueError("Lobby requires Xbox NMLB archives")
            blobs[name] = blob
    if blobs.keys() != wanted:
        raise ValueError("Lobby AFS is missing the English quest or Colony zone")
    return blobs[b"quest_ae.nbl"], blobs[b"zone02_ae.nbl"]


class WorldData:
    def __init__(self, game_data):
        archive = Path(game_data) / "DATA" / "Quest" / "xf_qe_off_extra_lobby01.afs"
        self.quest, self.zone = read_lobby_archive(archive)

    @staticmethod
    def user(account, character, local_id=0, position=(0.0, 280.0, -1452.0), direction=0):
        location = bytearray(80)
        location[:4] = b"\x00\x00\x12\x00"
        location[4:8] = account
        struct.pack_into("<H", location, 16, local_id)
        # Xbox 82165580/82165BE0 only apply the transform when this flag is set.
        location[18] = 1
        # The player's quest must match quest.ynr or the client's area check
        # hides the avatar and prevents control after an otherwise valid load.
        struct.pack_into("<III", location, 24, QUEST_ID, 2, 4)
        location[40] = 1
        struct.pack_into("<H3f", location, 42, direction, *position)
        # 82235A48 rejects a transform whose embedded area differs from the
        # player's area above, leaving remote avatars at (0, -10000, 0).
        struct.pack_into("<III", location, 64, QUEST_ID, 2, 4)

        status = bytearray(356)
        struct.pack_into("<III8H", status, 0, 100, 0, 100, *([10] * 8))
        # Xbox's 82217770/82170AA0 converters place level at +40, stats at
        # +44 and current/max HP at +60/+64 (four bytes before the PS2 layout).
        struct.pack_into("<I8HII", status, 40, 1, *([10] * 8), 100, 100)
        for offset in (236, 248, 260, 272, 284, 308):
            struct.pack_into("<f", status, offset, 1.0)
        return bytes(location) + character + status

    def lobby(self, account, character, head, local_id=0):
        """Enter the disc's Extra Mode Colony lobby (quest 13001, zone 2)."""
        header = head(account, local_id)
        account_marker = b"\x00\x01\x13\x00" + account + bytes(8)
        about = struct.pack("<HH", local_id, 0) + b"\x00\x00\x12\x00" + account + bytes(8) + account_marker
        user = self.user(account, character, local_id)

        return [
            (0x0C00, header + struct.pack("<I", QUEST_ID) + b"\xff" * 128),
            (0x020E, b"\xff\xff" + bytes(34) + struct.pack("<I", len(self.quest))
             + self.quest + bytes(4)),
            (0x0A05, header),
            (0x0111, struct.pack("<H", local_id) + bytes(6) + account + bytes(8) + account_marker + account
             + struct.pack("<III", local_id, 6, 0)),
            (0x010D, header + struct.pack("<II", 1, 0) + b"\x00\x00\x03\x00\xff\xff\x00\x00"
             + bytes(4) + account + bytes(24) + account + struct.pack("<II", local_id, 0xFFFFFFFF)
             + user[80:] + bytes(4)),
            (0x0200, header + struct.pack("<HHII", local_id, 2, 1, 0xFFFFFFFF)
             + b"\x00\x04\x00\x00" + bytes(20) + b"\x00\x14\x00\x00" + b"\xff" * 8),
            (0x020F, b"\xff\xff" + bytes(34) + b"\x00\xff\x00\x00"
             + struct.pack("<I", len(self.zone)) + self.zone),
            (0x0205, header + struct.pack("<IIIIIHBB", 0xFFFFFFFF, 2, 4, 0, 1, local_id, 0, 0)),
            (0x1212, head(account) + bytes(2400)),
            (0x0201, about + user + bytes(80)),
            (0x0A06, struct.pack("<H", local_id) + bytes(6) + account + bytes(8) + account_marker + b"\xff" * 240),
            (0x0208, header + struct.pack("<I", 2)),
            (0x0236, header),
        ]
