"""Authenticated TLS transport around the unchanged Xbox game protocol."""

import hashlib
import json
import ssl
from pathlib import Path

HELLO = b"PSUNET1\n"
ACCEPTED = b"PSUOK1\n"


def exact(connection, size):
    result = bytearray()
    while len(result) < size:
        chunk = connection.recv(size - len(result))
        if not chunk:
            raise ConnectionError("Connection closed during authentication")
        result.extend(chunk)
    return bytes(result)


def profile(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("server"), str) or not data["server"]:
        raise ValueError("Invalid network profile")
    if type(data.get("port")) is not int or not 1 <= data["port"] <= 65535:
        raise ValueError("Invalid network profile port")
    for field in ("token", "certificate_sha256"):
        if not isinstance(data.get(field), str) or len(bytes.fromhex(data[field])) != 32:
            raise ValueError("Invalid network profile credential or certificate pin")
    return data


def certificate_pin(path):
    pem = Path(path).read_text(encoding="ascii")
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
