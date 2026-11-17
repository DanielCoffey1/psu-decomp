"""TLS and two-client integration checks; fixtures contain no disc assets."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import queue
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import unittest

from psu_network_transport import HELLO, ACCEPTED, exact

TOOLS = Path(__file__).resolve().parent


def request(command, body=b""):
    return struct.pack("<I", len(body) + 8) + struct.pack(">HBB", command, 2, 0) + body


class Process:
    def __init__(self, arguments, ready):
        self.lines = []
        self.first = queue.Queue()
        self.process = subprocess.Popen([sys.executable, *map(str, arguments)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

        def drain():
            for line in self.process.stdout:
                self.lines.append(line.rstrip())
                self.first.put(line.rstrip())
            self.first.put(None)

        self.thread = threading.Thread(target=drain, daemon=True)
        self.thread.start()
        try:
            line = self.first.get(timeout=15)
            if line is None or not line.startswith(ready):
                raise AssertionError(f"Process did not become ready: {line}")
            self.port = int(line.split(":")[-1].split()[0])
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.thread.join(timeout=5)
        self.process.stdout.close()


class Peer:
    def __init__(self, settings, bridge_port=None):
        if bridge_port is not None:
            self.socket = socket.create_connection(("127.0.0.1", bridge_port), timeout=5)
        else:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            raw = socket.create_connection((settings["server"], settings["port"]), timeout=5)
            self.socket = context.wrap_socket(raw, server_hostname=settings["server"])
            actual = hashlib.sha256(self.socket.getpeercert(binary_form=True)).hexdigest()
            if actual != settings["certificate_sha256"]:
                self.close()
                raise ValueError("Unexpected test server certificate")
            self.socket.sendall(HELLO + bytes.fromhex(settings["token"]))
            try:
                if exact(self.socket, len(ACCEPTED)) != ACCEPTED:
                    raise ValueError("Invalid authentication response")
            except BaseException:
                self.close()
                raise
        self.fragments = 0
        assert self.receive()[0] == 0x0202

    def close(self):
        self.socket.close()

    def send(self, command, body=b""):
        self.socket.sendall(request(command, body))

    def receive(self):
        assembled = bytearray()
        while True:
            header = exact(self.socket, 8)
            size, = struct.unpack_from("<I", header)
            if not 8 <= size <= 0x4010:
                raise ValueError("Invalid test response length")
            command, = struct.unpack_from(">H", header, 4)
            body = exact(self.socket, size - 8)
            if command == 0:
                continue
            if command != 0x0B03:
                return command, body, header[6]
            total, offset = struct.unpack_from("<II", body)
            assert offset == len(assembled) and total <= 4 * 1024 * 1024
            assembled.extend(body[8:])
            self.fragments += 1
            ack = request(0x0B05)
            # Deliberately split acknowledgements and coalesce another command.
            self.socket.sendall(request(0x080E, bytes(60)) + ack[:3])
            self.socket.sendall(ack[3:])
            if len(assembled) == total:
                return struct.unpack_from(">H", assembled, 4)[0], bytes(assembled[8:]), assembled[6]

    def until(self, wanted):
        for _ in range(40):
            packet = self.receive()
            if packet[0] == wanted:
                return packet
        raise AssertionError(f"Did not receive {wanted:04x}")

    def slots(self):
        self.send(0x0D06, bytes(36))
        return self.until(0x0D03)[1][40:]

    def create(self, name, raw=None):
        data = bytearray(raw or bytes(316))
        data[40:104] = name.encode("utf-16-le").ljust(64, b"\0")
        self.send(0x0D02, data)
        return self.slots()

    def enter(self):
        self.send(0x020B, bytes(44))
        self.until(0x021B)
        self.send(0x021C, bytes(36))
        own = self.until(0x0201)[1]
        self.local_id = struct.unpack_from("<H", own, 36 + 16)[0]
        self.until(0x0236)
        return own

    def move(self, x, y=280.0, z=-1452.0):
        body = bytearray(84)
        # An untrusted sender cannot choose another player's identity.
        body[:44] = b"\xff" * 44
        struct.pack_into("<3f", body, 52, x, y, z)
        self.send(0x0102, body)


def login(settings, bridge_port=None):
    peer = Peer(settings, bridge_port)
    try:
        peer.send(0x0219, bytes(92))
        ticket = peer.until(0x0223)[1][36:44]
        peer.send(0x0217, bytes(36))
        reply = peer.until(0x0216)[1]
        assert struct.unpack_from("<IH", reply, 36) == (0x7F000001, 15020)
        return ticket
    finally:
        peer.close()


def game(settings, bridge_port=None, ticket=None):
    ticket = ticket if ticket is not None else login(settings, bridge_port)
    peer = Peer(settings, bridge_port)
    peer.send(0x020D, bytes(36) + ticket + bytes(8))
    try:
        assert peer.receive()[0] == 0x0D05
    except BaseException:
        peer.close()
        raise
    peer.account = ticket[:4]
    return peer


def fixture(root):
    directory = root / "DATA/Quest"
    directory.mkdir(parents=True)
    quest, zone = b"NMLB" + bytes(60), b"NMLB" + bytes(range(256)) * 287 + bytes(4)
    names = b"quest_ae.nbl".ljust(48, b"\0") + b"zone02_ae.nbl".ljust(48, b"\0")
    archive = (b"AFS\0" + struct.pack("<I", 2)
               + struct.pack("<6I", 128, len(quest), 128 + len(quest), len(zone), 32, 96)
               + names + quest + zone)
    (directory / "xf_qe_off_extra_lobby01.afs").write_bytes(archive)


class CommunityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.state = self.root / "state"
        fixture(self.root)
        self.paths = [self.root / "alice.json", self.root / "bob.json"]
        for path in self.paths:
            subprocess.run([sys.executable, TOOLS / "run-community-server.py", "--state-dir", self.state,
                            "add-player", "--profile", path], check=True, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.settings = [json.loads(path.read_text()) for path in self.paths]
        self.start()

    def start(self):
        self.server = Process([TOOLS / "run-community-server.py", "--state-dir", self.state,
                               "serve", "--game-data", self.root, "--port", "0"],
                              "Community server listening on ")
        self.addCleanup(self.server.close)
        for settings, path in zip(self.settings, self.paths):
            settings["port"] = self.server.port
            path.write_text(json.dumps(settings))

    def player(self, index):
        peer = game(self.settings[index])
        self.addCleanup(peer.close)
        return peer

    def test_accounts_persist_independently(self):
        alice, bob = self.player(0), self.player(1)
        self.assertNotEqual(alice.account, bob.account)
        alice_slots = alice.create("Alice")
        self.assertEqual(bob.slots(), bytes(348 * 4))
        bob_slots = bob.create("Bob")
        self.assertEqual(alice.slots(), alice_slots)
        alice.close()
        bob.close()
        self.server.close()
        self.start()
        self.assertEqual(self.player(0).slots(), alice_slots)
        self.assertEqual(self.player(1).slots(), bob_slots)

    def test_ticket_cannot_cross_profiles_or_be_replayed(self):
        ticket = login(self.settings[0])
        with self.assertRaises((ConnectionError, OSError)):
            game(self.settings[1], ticket=ticket)
        alice = game(self.settings[0], ticket=ticket)
        alice.close()
        with self.assertRaises((ConnectionError, OSError)):
            game(self.settings[0], ticket=ticket)

    def test_concurrent_load_spawn_movement_and_disconnect(self):
        alice, bob = self.player(0), self.player(1)
        alice.create("Alice")
        bob.create("Bob")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(peer.enter) for peer in (alice, bob)]
            for future in futures:
                future.result(timeout=8)
        self.assertEqual({alice.local_id, bob.local_id}, {0, 1})
        self.assertGreaterEqual(alice.fragments, 5)
        self.assertGreaterEqual(bob.fragments, 5)
        alice.move(10)
        bob.move(50)
        alice_view, bob_view = alice.until(0x0201)[1], bob.until(0x0201)[1]
        self.assertEqual(alice_view[8:12], bob.account)
        self.assertEqual(bob_view[8:12], alice.account)
        self.assertEqual(alice_view[116:122], "Bob".encode("utf-16-le"))
        self.assertEqual(bob_view[116:126], "Alice".encode("utf-16-le"))
        # Native Xbox clients otherwise create the avatar at (0, -10000, 0).
        # Both the apply-position flag and matching transform area are needed.
        for view, expected_x in ((alice_view, 50), (bob_view, 10)):
            self.assertEqual(view[36 + 18], 1)
            self.assertEqual(struct.unpack_from("<III", view, 36 + 24), (13001, 2, 4))
            self.assertEqual(struct.unpack_from("<III", view, 36 + 64), (13001, 2, 4))
            self.assertEqual(struct.unpack_from("<3f", view, 36 + 44), (expected_x, 280, -1452))
        bob.move(120)
        while True:
            _, body, channel = alice.until(0x0102)
            if struct.unpack_from("<f", body, 52)[0] == 120:
                break
        self.assertEqual(channel, 1)
        self.assertEqual(body[:36], bytes(36))
        self.assertEqual(body[36:40], bob.account)
        self.assertEqual(struct.unpack_from("<I", body, 40)[0], bob.local_id)
        bob.close()
        removed = alice.until(0x0204)[1]
        self.assertEqual(removed[36:40], bob.account)
        self.assertEqual(struct.unpack_from("<I", removed, 40)[0], bob.local_id)
        # The survivor stays usable and receives the returning player's spawn.
        bob = self.player(1)
        bob.enter()
        bob.move(80)
        self.assertEqual(alice.until(0x0201)[1][8:12], bob.account)

    def test_bad_position_disconnects_only_its_sender(self):
        alice, bob = self.player(0), self.player(1)
        for peer, name in ((alice, "Alice"), (bob, "Bob")):
            peer.create(name)
            peer.enter()
            peer.move(20)
        alice.until(0x0201)
        bob.move(float("nan"))
        self.assertEqual(alice.until(0x0204)[1][36:40], bob.account)
        self.assertEqual(alice.slots()[8:18], "Alice".encode("utf-16-le"))

    def test_full_lobby_rejects_extra_player_and_reuses_vacancy(self):
        # Exercise real TLS sessions at the configured capacity. This verifies
        # protocol/account behavior, not native rendering or VPS performance.
        for index in range(2, 17):
            path = self.root / f"player-{index}.json"
            subprocess.run([sys.executable, TOOLS / "run-community-server.py", "--state-dir", self.state,
                            "add-player", "--profile", path], check=True, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            settings = json.loads(path.read_text())
            settings["port"] = self.server.port
            self.settings.append(settings)
        peers = []
        for index in range(16):
            peer = self.player(index)
            peer.create(f"Player {index}")
            peer.enter()
            peer.move(index)
            peers.append(peer)
        self.assertEqual({peer.local_id for peer in peers}, set(range(16)))
        for peer in peers:
            seen = {peer.until(0x0201)[1][8:12] for _ in range(15)}
            self.assertEqual(seen, {other.account for other in peers if other is not peer})
        extra = self.player(16)
        extra.create("Waiting player")
        with self.assertRaises((ConnectionError, OSError)):
            extra.enter()
        departed = peers.pop()
        departed.close()
        for peer in peers:
            self.assertEqual(peer.until(0x0204)[1][36:40], departed.account)
        extra = self.player(16)
        extra.enter()
        self.assertEqual(extra.local_id, departed.local_id)
        extra.move(99)
        for peer in peers:
            self.assertEqual(peer.until(0x0201)[1][8:12], extra.account)

    def test_bridge_login_and_invalid_credentials(self):
        bridge = Process([TOOLS / "psu_network_bridge.py", "--profile", self.paths[0], "--port", "0"],
                         "Network bridge listening on ")
        self.addCleanup(bridge.close)
        peer = game(self.settings[0], bridge.port)
        self.addCleanup(peer.close)
        self.assertEqual(peer.slots(), bytes(348 * 4))
        for field in ("token", "certificate_sha256"):
            settings = dict(self.settings[1], **{field: "00" * 32})
            invalid = self.root / (field + ".json")
            invalid.write_text(json.dumps(settings))
            result = subprocess.run([sys.executable, TOOLS / "psu_network_bridge.py",
                                     "--profile", invalid, "--port", "0"],
                                    capture_output=True, text=True, timeout=15,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Network bridge listening", result.stdout)
            self.assertNotIn(settings["token"], result.stdout + result.stderr)
        self.assertEqual(self.player(1).slots(), bytes(348 * 4))


if __name__ == "__main__":
    unittest.main()
