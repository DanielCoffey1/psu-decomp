"""Host an experimental shared Xbox Colony lobby over authenticated TLS."""

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import ssl
import struct
import threading

from psu_network_lobby import Lobby
from psu_network_transport import HELLO, ACCEPTED, exact, certificate_pin
from psu_network_world import WorldData

spec = importlib.util.spec_from_file_location("network_probe", Path(__file__).with_name("run-network-probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def database(state):
    state.mkdir(parents=True, exist_ok=True)
    connection = probe.open_database(state / "characters.sqlite3")
    with connection:
        connection.execute("CREATE TABLE IF NOT EXISTS accounts "
                           "(id INTEGER PRIMARY KEY, token_hash BLOB UNIQUE NOT NULL)")
    return connection


def create_certificate(state):
    certificate, key_file = state / "server.pem", state / "server.key"
    if certificate.exists() and key_file.exists():
        return
    if certificate.exists() or key_file.exists():
        raise ValueError("Incomplete server certificate: retain or restore the matching certificate and key")
    # Only server initialization needs this optional package; clients and the
    # running server use the standard library. Never fetch it implicitly.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PSU community development server")])
    now = datetime.now(timezone.utc)
    signed = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
              .public_key(private_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
              .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
              .sign(private_key, hashes.SHA256()))
    key_file.write_bytes(private_key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    certificate.write_bytes(signed.public_bytes(serialization.Encoding.PEM))


def add_player(args):
    connection = database(args.state_dir)
    try:
        create_certificate(args.state_dir)
        # Refuse to replace an existing profile and accidentally lose its token.
        args.profile.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.profile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output, connection:
            connection.execute("BEGIN IMMEDIATE")
            last = connection.execute("SELECT MAX(id) FROM accounts").fetchone()[0]
            account = max(last or 0, 0x10000001) + 1
            if account > 0x1FFFFFFF:
                raise ValueError("No player IDs remaining")
            token = secrets.token_bytes(32)
            connection.execute("INSERT INTO accounts(id, token_hash) VALUES (?, ?)",
                               (account, hashlib.sha256(token).digest()))
            json.dump({"version": 1, "server": args.server, "port": args.port,
                       "token": token.hex(), "certificate_sha256": certificate_pin(args.state_dir / "server.pem")},
                      output, indent=2)
        print(f"Created player {account:08x}; profile saved to {args.profile}")
    finally:
        connection.close()


def serve(args):
    world = WorldData(args.game_data)
    connection = database(args.state_dir)
    connection.close()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(args.state_dir / "server.pem", args.state_dir / "server.key")
    tickets = probe.Tickets()
    lobby = Lobby(probe.frame, probe.game_header)
    # Includes login and game sockets. A connection must authenticate promptly.
    slots = threading.BoundedSemaphore(32)

    def session(raw):
        database_connection = None
        try:
            raw.settimeout(10)
            with context.wrap_socket(raw, server_side=True) as client:
                if exact(client, len(HELLO)) != HELLO:
                    raise ValueError("Invalid transport handshake")
                digest = hashlib.sha256(exact(client, 32)).digest()
                database_connection = database(args.state_dir)
                row = database_connection.execute("SELECT id FROM accounts WHERE token_hash = ?", (digest,)).fetchone()
                if row is None:
                    raise ValueError("Unknown player credential")
                client.sendall(ACCEPTED)
                identity = struct.pack("<I", row[0])
                probe.probe_login(client, 15020, tickets, database_connection, world, identity, lobby)
        except (OSError, ValueError, sqlite3.Error):
            # Never log authentication input, tokens, or player packet bodies.
            print("Closed a failed or disconnected community session", flush=True)
        finally:
            if database_connection is not None:
                database_connection.close()
            raw.close()
            slots.release()

    with socket.create_server((args.bind, args.port)) as listener:
        print(f"Community server listening on {listener.getsockname()[0]}:{listener.getsockname()[1]} (TLS)", flush=True)
        while True:
            raw, _ = listener.accept()
            if not slots.acquire(blocking=False):
                raw.close()
                continue
            threading.Thread(target=session, args=(raw,), daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(__file__).resolve().parents[1] / "local/community")
    subcommands = parser.add_subparsers(dest="command", required=True)
    player = subcommands.add_parser("add-player", help="Create a private connection profile (requires cryptography)")
    player.add_argument("--profile", type=Path, required=True)
    player.add_argument("--server", default="127.0.0.1", help="Host name or address players will connect to")
    player.add_argument("--port", type=int, default=15021)
    server = subcommands.add_parser("serve")
    server.add_argument("--game-data", type=Path, required=True)
    server.add_argument("--bind", default="127.0.0.1")
    server.add_argument("--port", type=int, default=15021)
    args = parser.parse_args()
    if not (0 if args.command == "serve" else 1) <= args.port <= 65535:
        parser.error("Invalid port")
    try:
        if args.command == "add-player":
            add_player(args)
        else:
            serve(args)
    except (OSError, ValueError, ImportError, sqlite3.Error) as error:
        parser.exit(1, f"Network setup failed: {error}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
