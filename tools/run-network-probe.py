"""Listen for PSU development connections on this computer."""

import argparse
from collections import deque
from pathlib import Path
import queue
import secrets
import socket
import sqlite3
import struct
import time
import threading


LOCAL_ACCOUNT = struct.pack("<I", 0x10000001)


def open_database(path):
    database = sqlite3.connect(path, timeout=10)
    database.execute("PRAGMA journal_mode=WAL")
    with database:
        database.execute("CREATE TABLE IF NOT EXISTS player_characters "
                         "(account BLOB NOT NULL, slot INTEGER CHECK(slot BETWEEN 0 AND 3), "
                         "raw BLOB NOT NULL, PRIMARY KEY(account, slot))")
        # Retain and migrate the original single-account development database.
        if database.execute("PRAGMA user_version").fetchone()[0] == 0:
            if database.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='characters'").fetchone():
                database.execute("INSERT OR IGNORE INTO player_characters SELECT ?, slot, raw FROM characters",
                                 (LOCAL_ACCOUNT,))
            database.execute("PRAGMA user_version=1")
    return database


class Tickets:
    def __init__(self):
        self.lock = threading.Lock()
        self.pending = {}

    def issue(self, ticket):
        with self.lock:
            now = time.monotonic()
            self.pending = {key: expiry for key, expiry in self.pending.items() if expiry > now}
            self.pending[ticket] = now + 15

    def redeem(self, ticket, account):
        with self.lock:
            if ticket[:4] != account:
                return False
            return self.pending.pop(ticket, 0) > time.monotonic()


def packets(client, authenticated, outgoing):
    """Reassemble TCP frames; keep authenticated sessions alive while in menus."""
    buffer = bytearray()
    deadline = time.monotonic() + 10
    next_ping = time.monotonic() + 5
    while True:
        now = time.monotonic()
        outgoing.poll(now)
        if authenticated():
            if now >= next_ping:
                client.sendall(bytes.fromhex("0800000000000000"))
                next_ping = now + 5
            client.settimeout(max(0.01, min(0.05, next_ping - now)))
        else:
            if now >= deadline:
                raise TimeoutError("Login timed out")
            client.settimeout(deadline - now)
        try:
            chunk = client.recv(4096)
        except TimeoutError:
            continue
        if not chunk:
            return
        buffer.extend(chunk)
        while len(buffer) >= 8:
            length, = struct.unpack_from("<I", buffer)
            if not 8 <= length <= 4096 or length % 4:
                raise ValueError("Invalid PSU frame size")
            if len(buffer) < length:
                break
            command, = struct.unpack_from(">H", buffer, 4)
            body = bytes(buffer[8:length])
            del buffer[:length]
            yield command, body


def frame(command, body, channel=3):
    return struct.pack("<I", len(body) + 8) + struct.pack(">HBB", command, channel, 0) + body


class Outgoing:
    """Serialize large replies using PSU's acknowledged 0B03 fragments.

    Acknowledgements go through the same TCP parser as other client messages,
    including when a movement frame and an acknowledgement arrive together.
    """

    CHUNK = 0x4000

    def __init__(self, client):
        self.client = client
        self.queue = deque()
        self.offset = 0
        self.deadline = None
        self.inbox = queue.Queue(maxsize=128)
        self.overloaded = threading.Event()

    def post(self, replies):
        """Called by other sessions; never write to this socket from their threads."""
        try:
            self.inbox.put_nowait(replies)
        except queue.Full:
            self.overloaded.set()

    def send(self, replies):
        if self.queue:
            raise ValueError("Previous reply sequence is still in flight")
        self.queue.extend(replies)
        self._advance()

    def _advance(self):
        while self.queue:
            packet = self.queue[0]
            if len(packet) <= self.CHUNK:
                self.client.sendall(self.queue.popleft())
                continue
            chunk = packet[self.offset:self.offset + self.CHUNK]
            fragment = (struct.pack("<I", len(chunk) + 16) + b"\x0b\x03\x00\x00"
                        + struct.pack("<II", len(packet), self.offset) + chunk)
            self.client.sendall(fragment)
            self.offset += len(chunk)
            self.deadline = time.monotonic() + 10
            return

    def acknowledge(self, body):
        if body or self.deadline is None:
            raise ValueError("Unexpected fragment acknowledgement")
        self.deadline = None
        if self.offset == len(self.queue[0]):
            self.queue.popleft()
            self.offset = 0
        self._advance()

    def poll(self, now):
        if self.overloaded.is_set():
            raise OSError("Slow lobby client exceeded its outgoing queue")
        if self.deadline is not None and now >= self.deadline:
            raise TimeoutError("Fragment acknowledgement timed out")
        while not self.queue:
            try:
                self.send(self.inbox.get_nowait())
            except queue.Empty:
                break


def character_slot(raw):
    """Build a level-one selection record from a development character."""
    record = bytearray(348)
    record[1] = 1
    record[8:172] = raw[40:204]
    struct.pack_into("<H", record, 172, 1)
    for offset in range(220, 284, 4):
        struct.pack_into("<I", record, offset, 1)
    return record


def game_header(account, local_id=0xFFFF):
    return struct.pack("<H", local_id) + bytes(18) + b"\x00\x01\x13\x00" + account + bytes(8)


def load_character(client, account, raw):
    """Send the character/work/options record and finish the initial load."""
    character = character_slot(raw)[8:284]
    options = bytes(16) + struct.pack("<I", 4)
    client.sendall(frame(0x0D01, game_header(account) + character + bytes(1016) + options))
    client.sendall(frame(0x0210, game_header(account, 0) + struct.pack("<II", 0, int(time.time()))))
    client.sendall(frame(0x021B, game_header(account, 0)))


def probe_login(client, port, pending, database, world=None, identity=LOCAL_ACCOUNT, lobby=None):
    session = {"player": None}
    try:
        _probe_login(client, port, pending, database, world, identity, lobby, session)
    finally:
        if lobby is not None and session["player"] is not None:
            lobby.leave(session["player"])


def _probe_login(client, port, pending, database, world, identity, lobby, session):
    """Exercise login and the game-server handoff over loopback."""
    account = struct.pack("<I", 0x10000000 | secrets.randbits(24))
    key = None
    game_account = None
    selected = None
    entered = False
    outgoing = Outgoing(client)
    greeting = frame(0x0202, b"\xff\xff" + bytes(34) + account + bytes(128))
    client.settimeout(10)
    client.sendall(greeting)
    for command, body in packets(client, lambda: game_account is not None, outgoing):
        length = len(body) + 8
        print(f"PSU command {command:04x}, {length} bytes", flush=True)
        if command == 0x0B05:
            outgoing.acknowledge(body)
        elif command == 0x0219 and length == 100:
            # Issue a temporary test identity. The request body is never logged.
            # The direct probe uses one local account. The community transport
            # supplies an authenticated identity independent of guest claims.
            account = identity
            key = secrets.token_bytes(4)
            reply = bytes(20) + b"\x00\x00\x0f\x00" + account + bytes(8)
            client.sendall(frame(0x0223, reply + account + key))
        elif command == 0x0217 and length == 44 and key is not None:
            pending.issue(account + key)
            redirect = (b"\xff\xff" + bytes(18) + b"\x00\x00\x0f\x00" + account
                        + bytes(8) + struct.pack("<IHH", 0x7F000001, port, 0))
            client.sendall(frame(0x0216, redirect))
            # Let the client finish consuming the redirect and close the
            # login socket before accepting its game connection.
            client.settimeout(1)
            client.recv(1)
            return
        elif command == 0x020D and len(body) >= 44 and game_account is None:
            ticket = body[36:44]
            if not pending.redeem(ticket, identity):
                print("Game session ticket was rejected", flush=True)
                return
            game_account = ticket[:4]
            marker = b"\x00\x01\x13\x00" + game_account + bytes(8)
            flags = struct.pack("<16s16s16sIII", b"PSU_VALUE_FLAG", b"PSU_BOOL_FLAG",
                                b"PSU_TEMP_FLAG", 1, 1, 1)
            client.sendall(frame(0x0D05, bytes(4) + marker * 2 + flags))
            print("Game session ticket accepted", flush=True)
        elif command == 0x0D06 and game_account is not None:
            marker = b"\x00\x01\x13\x00" + game_account + bytes(8)
            slots = [bytes(348) for _ in range(4)]
            for slot, raw in database.execute("SELECT slot, raw FROM player_characters WHERE account = ?",
                                              (game_account,)):
                slots[slot] = character_slot(raw)
            client.sendall(frame(0x0D03, bytes(4) + marker * 2 + bytes(4) + b"".join(slots)))
            print("Sent four character slots", flush=True)
        elif command == 0x0D02 and game_account is not None:
            # This Xbox disc sends a 316-byte body, including its initial
            # level block. Derive progression on the server when returning it.
            if len(body) != 316:
                raise ValueError("Unexpected character record length")
            slot, = struct.unpack_from("<I", body, 36)
            if slot > 3 or body[104] > 3 or body[105] > 1:
                raise ValueError("Invalid character record")
            name = body[40:104].decode("utf-16-le").split("\0", 1)[0]
            if not name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in name):
                raise ValueError("Invalid character name")
            with database:
                database.execute("INSERT INTO player_characters(account, slot, raw) VALUES (?, ?, ?) "
                                 "ON CONFLICT(account, slot) DO UPDATE SET raw = excluded.raw",
                                 (game_account, slot, body))
            print(f"Saved development character in slot {slot + 1}", flush=True)
        elif command == 0x020B and game_account is not None:
            if len(body) != 44:
                raise ValueError("Unexpected character selection length")
            slot, = struct.unpack_from("<I", body, 36)
            if entered:
                raise ValueError("Cannot select another character after entering the lobby")
            row = database.execute("SELECT raw FROM player_characters WHERE account = ? AND slot = ?",
                                   (game_account, slot)).fetchone()
            if row is None:
                raise ValueError("Selected character does not exist")
            selected = row[0]
            load_character(client, game_account, selected)
            print(f"Sent initial load for slot {slot + 1}", flush=True)
        elif command == 0x021C and game_account is not None:
            if selected is None or entered:
                raise ValueError("Unexpected lobby entry request")
            if world is None:
                print("Lobby entry requires --game-data pointing to extracted Xbox game data", flush=True)
                continue
            entered = True
            local_id = 0
            character = character_slot(selected)[8:284]
            if lobby is not None:
                session["player"] = lobby.join(game_account, character, outgoing)
                local_id = session["player"].local_id
            outgoing.send([frame(cmd, data) for cmd, data in
                           world.lobby(game_account, character, game_header, local_id)])
            print("Sent development lobby sequence", flush=True)
        elif command in (0x0102, 0x0503, 0x0514) and session["player"] is not None:
            lobby.update(session["player"], command, body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=15020)
    parser.add_argument("--login-test", action="store_true",
                        help="Test PSU login and the game-server handoff")
    parser.add_argument("--state-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "local" / "network-probe",
                        help="Local development character storage (one shared test account)")
    parser.add_argument("--game-data", type=Path,
                        help="Enable experimental lobby loading from extracted Xbox game data")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    world = None
    if args.game_data:
        if not args.login_test:
            parser.error("--game-data requires --login-test")
        from psu_network_world import WorldData
        try:
            world = WorldData(args.game_data)
        except (OSError, ValueError) as error:
            parser.error(str(error))

    database = None
    if args.login_test:
        args.state_dir.mkdir(parents=True, exist_ok=True)
        database = open_database(args.state_dir / "characters.sqlite3")
    with socket.create_server(("127.0.0.1", args.port)) as listener:
        host, port = listener.getsockname()
        pending = Tickets()
        print(f"Listening on {host}:{port}", flush=True)
        while True:
            client, (_, peer_port) = listener.accept()
            with client:
                print(f"Accepted TCP connection from local port {peer_port}", flush=True)
                if args.login_test:
                    try:
                        probe_login(client, port, pending, database, world)
                    except (OSError, ValueError) as error:
                        print(type(error).__name__, flush=True)
                    continue
                deadline = time.monotonic() + 5
                received = 0
                while received < 65536:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    client.settimeout(remaining)
                    try:
                        chunk = client.recv(min(4096, 65536 - received))
                    except OSError:
                        break
                    if not chunk:
                        break
                    received += len(chunk)
                print(f"Received {received} bytes", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
