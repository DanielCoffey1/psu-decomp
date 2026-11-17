"""Loopback adapter: the Xbox Live menu connects through a pinned TLS profile."""

import argparse
import asyncio
import hashlib
import hmac
import ssl
import struct

from psu_network_transport import HELLO, ACCEPTED, profile


async def close_stream(writer):
    writer.close()
    try:
        await asyncio.wait_for(writer.wait_closed(), 2)
    except (OSError, TimeoutError):
        writer.transport.abort()


async def upstream(settings):
    # The private profile pins the exact server certificate. A different cert,
    # including a publicly trusted one, is rejected before sending the token.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    reader, writer = await asyncio.wait_for(asyncio.open_connection(
        settings["server"], settings["port"], ssl=context, server_hostname=settings["server"]), 10)
    try:
        certificate = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
        pin = hashlib.sha256(certificate).digest()
        if not hmac.compare_digest(pin, bytes.fromhex(settings["certificate_sha256"])):
            raise ValueError("Server certificate does not match this profile")
        writer.write(HELLO + bytes.fromhex(settings["token"]))
        await writer.drain()
        if await asyncio.wait_for(reader.readexactly(len(ACCEPTED)), 10) != ACCEPTED:
            raise ValueError("Server rejected this player profile")
        return reader, writer
    except BaseException:
        await close_stream(writer)
        raise


async def bridge(settings, port=15020):
    async def client(reader, writer):
        remote_writer = None
        tasks = []
        try:
            remote_reader, remote_writer = await upstream(settings)

            async def copy(source, destination):
                while data := await source.read(32768):
                    destination.write(data)
                    await destination.drain()

            tasks = [asyncio.create_task(copy(reader, remote_writer)),
                     asyncio.create_task(copy(remote_reader, writer))]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except (OSError, ValueError, asyncio.IncompleteReadError):
            print("Community connection failed; check the server and private player profile", flush=True)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for stream in (writer, remote_writer):
                if stream:
                    await close_stream(stream)

    # Validate the server before reporting ready or starting the game.
    reader, connection = await upstream(settings)
    try:
        # Authentication is immediately followed by the native PSU greeting.
        # Drain it before TLS shutdown; otherwise OpenSSL can reject application
        # bytes arriving after our close_notify during this readiness check.
        greeting = await asyncio.wait_for(reader.readexactly(176), 10)
        if struct.unpack_from("<I", greeting)[0] != 176 or greeting[4:6] != b"\x02\x02":
            raise ValueError("Unexpected game-server greeting")
    finally:
        await close_stream(connection)
    server = await asyncio.start_server(client, "127.0.0.1", port)
    async with server:
        print(f"Network bridge listening on 127.0.0.1:{server.sockets[0].getsockname()[1]}", flush=True)
        await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--port", type=int, default=15020)
    args = parser.parse_args()
    try:
        asyncio.run(bridge(profile(args.profile), args.port))
    except (OSError, ValueError, asyncio.IncompleteReadError) as error:
        parser.exit(1, f"Cannot start network bridge: {error}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
