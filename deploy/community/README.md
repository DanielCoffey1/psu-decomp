# Hosting the community lobby

The server is Python 3.11+ and needs no GPU or native game process. A small Linux
VM is a starting point for this development lobby; only two native clients have
been tested, not a 16-player load. The included systemd unit is a deployment
template and has not yet been exercised on a remote host.

## Files and state

Place these source files in `/srv/psu-community/tools/`:

- `run-community-server.py`
- `run-network-probe.py`
- `psu_network_world.py`
- `psu_network_lobby.py`
- `psu_network_transport.py`

The server currently needs only the user's extracted
`DATA/Quest/xf_qe_off_extra_lobby01.afs` under `/srv/psu-community/game/`.
No native executable, GPU plugin, entire disc image or client cache is needed on
the server. Game assets are not included in the repository.

Create a system user and writable state directory:

```sh
sudo useradd --system --home-dir /var/lib/psu-community --shell /usr/sbin/nologin psu-community
sudo install -d -o psu-community -g psu-community -m 0700 /var/lib/psu-community
```

For a fresh server, install the distribution's `python3-cryptography` package
and create a profile as the service user. Replace `SERVER_ADDRESS` with the
public IPv4 address or DNS name clients will use:

```sh
sudo -u psu-community python3 /srv/psu-community/tools/run-community-server.py \
  --state-dir /var/lib/psu-community add-player \
  --profile /var/lib/psu-community/player.json --server SERVER_ADDRESS
```

Alternatively, preserve the existing local accounts by migrating the contents of
`local/community/` that comprise server state: `characters.sqlite3`, `server.pem`
and `server.key`. Stop the source server and ensure SQLite has checkpointed its
WAL before copying, or use SQLite's online backup API for a consistent database.
Do not discard a live `-wal` file. Set ownership to the service user and restrict
the state directory to that user. Update the `server` field in each existing
private profile; retain its token and certificate fingerprint.

## Service

Copy `psu-community.service` into `/etc/systemd/system/`, then run:

```sh
sudo systemctl daemon-reload
sudo systemctl enable --now psu-community
sudo systemctl status psu-community
sudo journalctl -u psu-community -n 50
```

The service restarts after failure and starts at boot. Allow inbound TCP 15021
through the host/provider firewall, plus SSH from the administrator's address.
The loopback adapter port 15020 stays on each player's own PC; it is not a public
server port. This implementation does not need UDP. A domain is optional.

Create a separate profile for each invited player using `add-player` and a unique
output filename. Transfer that profile privately to its player. Keep the server
key and database on the host, backed up separately. Restoring the same certificate
and database retains existing profiles and characters.

## Player connection and acceptance check

Each player runs the recompiled Windows build with their own extracted game data:

```powershell
python ./tools/run-network.py --profile ./local/community/player.json --game-data ./local --check
python ./tools/run-network.py --profile ./local/community/player.json --game-data ./local
```

The launcher supplies the connection automatically; the player chooses **Xbox
Live** in the original menu. Verify two different PCs can join, see movement in
both directions, and disconnect/rejoin without disturbing the survivor. Verify
the service returns after reboot and characters survive a restart. These remote
checks remain required before describing the host as working over the internet.

The current lobby has placeholder level-one statistics and no implemented chat,
inventory, combat, missions, parties or travel between areas. Character creation
persists; world position/progression do not persist. This is a development service.
