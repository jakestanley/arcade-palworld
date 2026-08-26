# arcade.stanley.arpa adapter

Registers this Palworld server with the [homelab-arcade](https://github.com/jakestanley/homelab-arcade)
control portal so it can be started/stopped from `arcade.stanley.arpa`
alongside the other game servers.

Runs as a plain host process on **adler** (not inside Docker — it shells
out to `docker compose` in this repo, so it needs the Docker socket
available the normal way a host user has it, not passed into a container).

## Contract

Implements the standard arcade adapter contract — see homelab-arcade's
`docs/ARCADE_CONTRACT.md` for the full spec. Summary:

- `GET /arcade/info` → `{id, name, description, actions, status}`
- `POST /arcade/actions/start` / `POST /arcade/actions/stop` → runs
  `docker compose up -d` / `docker compose stop` in this repo
- Registers itself with `POST {ARCADE_BASE_URL}/api/register` every
  `ARCADE_HEARTBEAT_SECONDS` (default 30s)

## Run

```bash
python3 arcade/adapter.py
```

Zero third-party dependencies — stdlib only.

## Config (env vars, no new .env wiring by default)

| Var | Default | Notes |
|---|---|---|
| `ARCADE_SERVER_ID` | `palworld` | unique id in the arcade registry |
| `ARCADE_SERVER_NAME` | `Palworld` | display name |
| `ARCADE_SERVER_DESCRIPTION` | `Palworld dedicated server (docker-palworld)` | |
| `ARCADE_BASE_URL` | `http://arcade.stanley.arpa` | where to register |
| `ARCADE_ADAPTER_PORT` | `8300` | this adapter's own listen port |
| `ARCADE_ADAPTER_BASE_URL` | auto-detected LAN IP | override if auto-detection picks the wrong interface |
| `ARCADE_HEARTBEAT_SECONDS` | `30` | registration heartbeat interval |

## Run as a systemd service

```bash
cp arcade/palworld-arcade-adapter.service.example /etc/systemd/system/palworld-arcade-adapter.service
# edit User / WorkingDirectory / paths for your host
sudo systemctl daemon-reload
sudo systemctl enable --now palworld-arcade-adapter
```

## Gotchas

- Uses `docker compose stop`, not `down`, for the stop action — containers
  and the `data/` volume are left in place, no world data is touched.
- This adapter is **unauthenticated** — it trusts the homelab LAN/VPN, same
  trust model as RCON. Do not expose `ARCADE_ADAPTER_PORT` outside the LAN.
