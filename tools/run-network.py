"""Launch PSU with its private community connection, then choose Xbox Live."""

import argparse
from datetime import datetime
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from psu_network_transport import profile


def launch(args):
    settings = profile(args.profile)
    executable = args.exe.resolve()
    game_data = args.game_data.resolve()
    if not executable.is_file() or not executable.with_name("rexgpu-psu.dll").is_file():
        raise ValueError("Build PSU and its GPU plugin before using this launcher")
    if not (game_data / "default.xex").is_file() or not (game_data / "DATA").is_dir():
        raise ValueError("--game-data must contain your extracted default.xex and DATA directory")
    runtime = (args.client_data or args.profile.resolve().parent / (args.profile.stem + "-client")).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    server_log = runtime / (stamp + "-connection.log")
    ready = queue.Queue(maxsize=1)
    bridge = subprocess.Popen([sys.executable, str(Path(__file__).with_name("psu_network_bridge.py")),
                               "--profile", str(args.profile.resolve()), "--port", str(args.bridge_port)],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def drain():
        first = True
        with server_log.open("w", encoding="utf-8") as output:
            for line in bridge.stdout:
                output.write(line)
                output.flush()
                if first:
                    ready.put(line.strip())
                    first = False
        if first:
            ready.put("Connection adapter exited before becoming ready")

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    game = None
    try:
        try:
            status = ready.get(timeout=25)
        except queue.Empty:
            raise ValueError(f"Connection adapter timed out; see {server_log}") from None
        if status != f"Network bridge listening on 127.0.0.1:{args.bridge_port}":
            raise ValueError(status)
        print(f"Connected to {settings['server']}:{settings['port']}; choose Xbox Live in the game.", flush=True)
        if args.check:
            return 0
        command = [str(executable), "--game_data_root", str(game_data),
                   "--user_data_root", str(runtime / "profile"), "--cache_root", str(runtime / "cache"),
                   "--log_file", str(runtime / (stamp + "-game.log")),
                   "--gpu_plugin", "psu", "--resolution", "720p", "--no-fullscreen",
                   "--psu_network_dev_profile=true", f"--psu_network_bridge_port={args.bridge_port}"]
        if not args.controller:
            command.extend(["--mnk_mode", "--keybind_start", "Return", "--keybind_a", "Space",
                            "--keybind_b", "Backspace", "--keybind_x", "X", "--keybind_y", "P",
                            "--keybind_left_trigger", "Q", "--keybind_right_trigger", "E",
                            "--keybind_rstick_press", "V", "--keybind_dpad_up", "I",
                            "--keybind_dpad_down", "K", "--keybind_dpad_left", "J", "--keybind_dpad_right", "L"])
        if args.trace:
            command.append("--psu_trace_network=true")
        with (runtime / (stamp + "-console.log")).open("w", encoding="utf-8") as output:
            game = subprocess.Popen(command, cwd=executable.parent, stdout=output, stderr=subprocess.STDOUT)
            reported = False
            while game.poll() is None:
                if bridge.poll() is not None and not reported:
                    print(f"The connection adapter stopped; see {server_log}", flush=True)
                    reported = True
                time.sleep(0.2)
            return game.returncode
    except KeyboardInterrupt:
        if game is not None and game.poll() is None:
            game.terminate()
            game.wait(timeout=5)
        return 130
    finally:
        # Never kill a process discovered by port or executable name: this is
        # exactly the adapter we started, even if another launcher is running.
        if bridge.poll() is None:
            bridge.terminate()
            bridge.wait(timeout=5)
        reader.join(timeout=5)
        bridge.stdout.close()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=root / "local/community/player.json")
    parser.add_argument("--game-data", type=Path, default=root / "local")
    parser.add_argument("--exe", type=Path, default=root / "out/build/win-amd64-release/psu.exe")
    parser.add_argument("--client-data", type=Path)
    parser.add_argument("--bridge-port", type=int, default=15020,
                        help="Local adapter port; use different ports for clients on the same PC")
    parser.add_argument("--controller", action="store_true")
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check assets and connection without starting the game")
    args = parser.parse_args()
    if not 1 <= args.bridge_port <= 65535:
        parser.error("--bridge-port must be between 1 and 65535")
    try:
        return launch(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot start network play: {error}\n")


if __name__ == "__main__":
    sys.exit(main())
