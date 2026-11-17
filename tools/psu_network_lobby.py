"""Small shared Colony lobby; all socket writes stay on their owning session."""

from dataclasses import dataclass
import math
import struct
import threading

from psu_network_world import WorldData


@dataclass
class Player:
    account: bytes
    character: bytes
    local_id: int
    outgoing: object
    ready: bool = False
    position: tuple = (0.0, 280.0, -1452.0)
    direction: int = 0

    def user(self):
        return WorldData.user(self.account, self.character, self.local_id, self.position, self.direction)


class Lobby:
    def __init__(self, frame, head, capacity=16):
        self.frame, self.head = frame, head
        self.capacity = capacity
        self.lock = threading.Lock()
        self.players = {}

    def join(self, account, character, outgoing):
        with self.lock:
            if account in self.players:
                raise ValueError("This player is already in the lobby")
            used = {player.local_id for player in self.players.values()}
            local_id = next((i for i in range(self.capacity) if i not in used), None)
            if local_id is None:
                raise ValueError("The development lobby is full")
            player = Player(account, character, local_id, outgoing)
            self.players[account] = player
            return player

    @staticmethod
    def about(recipient, player):
        return (struct.pack("<HH", recipient.local_id, 0) + b"\x00\x00\x12\x00"
                + player.account + bytes(8) + b"\x00\x01\x13\x00" + recipient.account + bytes(8))

    def spawn(self, recipient, player):
        header = self.head(recipient.account, recipient.local_id)
        marker = b"\x00\x01\x13\x00" + recipient.account + bytes(8)
        data = player.user()
        return [self.frame(cmd, body) for cmd, body in [
            (0x0111, struct.pack("<H", recipient.local_id) + bytes(6) + player.account
             + bytes(8) + marker + player.account + struct.pack("<III", player.local_id, 6, 0)),
            (0x010D, header + struct.pack("<II", 1, 0) + b"\x00\x00\x03\x00\xff\xff\x00\x00"
             + bytes(4) + player.account + bytes(24) + player.account
             + struct.pack("<II", player.local_id, 0xFFFFFFFF) + data[80:]),
            (0x0205, header + struct.pack("<IIIIIHBB", 0xFFFFFFFF, 2, 4, 0, 1, player.local_id, 0, 0)),
            (0x0203, header + player.account + struct.pack("<I", player.local_id)),
            (0x0201, self.about(recipient, player) + data + bytes(80)),
        ]]

    def update(self, player, command, body):
        # These are the three movement/animation sizes observed on this Xbox
        # executable. Do not broadcast arbitrary guest commands or claimed IDs.
        sizes = {0x0102: 84, 0x0503: 92, 0x0514: 76}
        if command not in sizes or len(body) != sizes[command]:
            raise ValueError("Invalid lobby movement record")
        with self.lock:
            if self.players.get(player.account) is not player:
                return
            if command == 0x0102:
                position = struct.unpack_from("<3f", body, 52)
                if not all(math.isfinite(value) and abs(value) < 1_000_000 for value in position):
                    raise ValueError("Invalid player position")
                player.position = position
                player.direction = struct.unpack_from("<H", body, 46)[0]
                if not player.ready:
                    # The first position arrives after the client's world load.
                    # Exchange complete spawn records only when both can render.
                    player.ready = True
                    for other in self.players.values():
                        if other is not player and other.ready:
                            other.outgoing.post(self.spawn(other, player))
                            player.outgoing.post(self.spawn(player, other))
            if not player.ready:
                return
            clean = bytes(36) + player.account + struct.pack("<I", player.local_id) + body[44:]
            packet = self.frame(command, clean, channel=1)
            for other in self.players.values():
                if other is not player and other.ready:
                    other.outgoing.post([packet])

    def leave(self, player):
        with self.lock:
            if self.players.get(player.account) is not player:
                return
            del self.players[player.account]
            if player.ready:
                for other in self.players.values():
                    if other.ready:
                        body = (self.about(other, player) + player.account
                                + struct.pack("<II", player.local_id, 100))
                        other.outgoing.post([self.frame(0x0204, body)])
