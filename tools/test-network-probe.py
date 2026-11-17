"""Loopback integration tests for the development protocol probe."""

from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import unittest


def request(command, body=b""):
    return struct.pack("<I", 8 + len(body)) + struct.pack(">HBB", command, 2, 0) + body


def receive(client):
    def exact(size):
        result = bytearray()
        while len(result) < size:
            chunk = client.recv(size - len(result))
            if not chunk:
                raise EOFError("Probe disconnected")
            result.extend(chunk)
        return result
    header = exact(8)
    length, = struct.unpack_from("<I", header)
    if not 8 <= length <= 0x4010:
        raise ValueError("Invalid response size")
    return struct.unpack_from(">H", header, 4)[0], exact(length - 8)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.start()

    def start(self, extra=()):
        self.process = subprocess.Popen(
            [sys.executable, str(Path(__file__).with_name("run-network-probe.py")),
             "--login-test", "--port", "0", "--state-dir", self.directory.name, *extra],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.addCleanup(self.stop)
        line = self.process.stdout.readline().strip()
        self.assertTrue(line.startswith("Listening on 127.0.0.1:"), line)
        self.port = int(line.rsplit(":", 1)[1])

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.process.stdout.close()

    def connect(self):
        client = socket.create_connection(("127.0.0.1", self.port), timeout=7)
        self.addCleanup(client.close)
        self.assertEqual(receive(client)[0], 0x0202)
        return client

    def login(self):
        with self.connect() as client:
            # Split the length header, then combine the rest with another frame.
            data = request(0x080E, bytes(60)) + request(0x0219, bytes(92))
            client.sendall(data[:3])
            client.sendall(data[3:])
            command, body = receive(client)
            self.assertEqual(command, 0x0223)
            ticket = body[36:44]
            client.sendall(request(0x0217, bytes(36)))
            command, body = receive(client)
            self.assertEqual(command, 0x0216)
            self.assertEqual(struct.unpack_from("<IH", body, 36), (0x7F000001, self.port))
        return ticket

    def game(self, ticket):
        client = self.connect()
        client.sendall(request(0x080E, bytes(60)) + request(0x020D, bytes(36) + ticket + bytes(8)))
        return client

    def slots(self, client):
        client.sendall(request(0x0D06, bytes(36)))
        command, body = receive(client)
        self.assertEqual(command, 0x0D03)
        self.assertEqual(len(body), 40 + 4 * 348)
        return body[40:]

    def test_handoff_keepalive_and_ticket_replay(self):
        ticket = self.login()
        with self.game(ticket) as client:
            self.assertEqual(receive(client)[0], 0x0D05)
            self.assertEqual(self.slots(client), bytes(4 * 348))
            # Remain idle beyond the old ten-second login deadline.
            for _ in range(3):
                self.assertEqual(receive(client), (0, b""))
            self.assertEqual(self.slots(client), bytes(4 * 348))
        with self.game(ticket) as client:
            with self.assertRaises((EOFError, ConnectionResetError)):
                receive(client)

    def test_character_survives_server_restart(self):
        with self.game(self.login()) as client:
            self.assertEqual(receive(client)[0], 0x0D05)
            raw = bytearray(316)
            struct.pack_into("<I", raw, 36, 2)
            raw[40:48] = "Test".encode("utf-16-le")
            client.sendall(request(0x0D02, raw))
            slots = self.slots(client)
            self.assertEqual(slots[2 * 348 + 1], 1)
            self.assertEqual(slots[2 * 348 + 8:2 * 348 + 16], raw[40:48])
        self.stop()
        self.start()
        with self.game(self.login()) as client:
            self.assertEqual(receive(client)[0], 0x0D05)
            self.assertEqual(self.slots(client), slots)
            client.sendall(request(0x020B, bytes(36) + struct.pack("<II", 2, 0)))
            command, body = receive(client)
            self.assertEqual(command, 0x0D01)
            self.assertEqual(len(body), 36 + 276 + 1016 + 20)
            self.assertEqual(body[36:44], "Test".encode("utf-16-le"))
            self.assertEqual(struct.unpack_from("<H", body, 36 + 164)[0], 1)
            self.assertEqual(receive(client)[0], 0x0210)
            self.assertEqual(receive(client)[0], 0x021B)

    def test_malformed_frame_does_not_stop_listener(self):
        with self.connect() as client:
            client.sendall(struct.pack("<I", 0xFFFFFFFF) + bytes(4))
            with self.assertRaises((EOFError, ConnectionResetError)):
                receive(client)
        with self.game(self.login()) as client:
            self.assertEqual(receive(client)[0], 0x0D05)

    def test_invalid_character_is_not_saved(self):
        valid = bytearray(316)
        valid[40:48] = "Test".encode("utf-16-le")
        bad_slot = bytearray(valid)
        struct.pack_into("<I", bad_slot, 36, 4)
        bad_race = bytearray(valid)
        bad_race[104] = 4
        bad_name = bytearray(valid)
        bad_name[40:42] = b"\x01\x00"
        for raw in (valid[:204], bad_slot, bad_race, bytes(316), bad_name):
            with self.subTest(record_length=len(raw)):
                with self.game(self.login()) as client:
                    self.assertEqual(receive(client)[0], 0x0D05)
                    client.sendall(request(0x0D02, raw))
                    with self.assertRaises((EOFError, ConnectionResetError)):
                        receive(client)
                with self.game(self.login()) as client:
                    self.assertEqual(receive(client)[0], 0x0D05)
                    self.assertEqual(self.slots(client), bytes(4 * 348))

    def test_unissued_ticket_is_rejected(self):
        with self.game(bytes(8)) as client:
            with self.assertRaises((EOFError, ConnectionResetError)):
                receive(client)

    def test_lobby_fragments_and_interleaved_commands(self):
        # Synthetic archives exercise the transport without shipping disc assets.
        # They are not valid game worlds and do not establish game compatibility.
        self.stop()
        directory = Path(self.directory.name) / "DATA" / "Quest"
        directory.mkdir(parents=True)
        quest = b"NMLB" + bytes(60)
        zone = b"NMLB" + bytes(range(256)) * 287 + bytes(4)
        names = b"quest_ae.nbl".ljust(48, b"\0") + b"zone02_ae.nbl".ljust(48, b"\0")
        archive = (b"AFS\0" + struct.pack("<I", 2)
                   + struct.pack("<IIIIII", 128, len(quest), 128 + len(quest), len(zone), 32, 96)
                   + names + quest + zone)
        (directory / "xf_qe_off_extra_lobby01.afs").write_bytes(archive)
        self.start(("--game-data", self.directory.name))
        with self.game(self.login()) as client:
            self.assertEqual(receive(client)[0], 0x0D05)
            raw = bytearray(316)
            raw[40:48] = "Test".encode("utf-16-le")
            client.sendall(request(0x0D02, raw) + request(0x020B, bytes(44)))
            for command in (0x0D01, 0x0210, 0x021B):
                self.assertEqual(receive(client)[0], command)
            client.sendall(request(0x021C, bytes(36)))
            for command in (0x0C00, 0x020E, 0x0A05, 0x0111, 0x010D, 0x0200):
                received, body = receive(client)
                self.assertEqual(received, command)
                if command == 0x0C00:
                    self.assertEqual(struct.unpack_from("<I", body, 36)[0], 13001)
            assembled = bytearray()
            total = 1
            while len(assembled) < total:
                command, body = receive(client)
                self.assertEqual(command, 0x0B03)
                total, offset = struct.unpack_from("<II", body)
                self.assertEqual(offset, len(assembled))
                assembled.extend(body[8:])
                # Coalesce a normal client command with a split acknowledgement.
                ack = request(0x0B05)
                client.sendall(request(0x0102, bytes(84)) + ack[:3])
                client.sendall(ack[3:])
            self.assertEqual(struct.unpack_from("<I", assembled)[0], len(assembled))
            self.assertEqual(assembled[4:6], b"\x02\x0f")
            self.assertEqual(assembled[52:], zone)
            for command in (0x0205, 0x1212, 0x0201, 0x0A06, 0x0208, 0x0236):
                received, body = receive(client)
                self.assertEqual(received, command)
                if command == 0x0201:
                    self.assertEqual(struct.unpack_from("<III", body, 36 + 24), (13001, 2, 4))
                    self.assertEqual(body[36 + 80:36 + 88], "Test".encode("utf-16-le"))
                    self.assertEqual(struct.unpack_from("<II", body, 36 + 80 + 276 + 60), (100, 100))
            # An unsolicited acknowledgement must not index an empty queue.
            client.sendall(request(0x0B05))
            with self.assertRaises((EOFError, ConnectionResetError)):
                receive(client)
        with self.game(self.login()) as client:
            self.assertEqual(receive(client)[0], 0x0D05)


if __name__ == "__main__":
    unittest.main()
