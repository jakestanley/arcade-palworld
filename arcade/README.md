# arcade.stanley.arpa adapter

Registers this Palworld server with the [homelab-arcade](https://github.com/jakestanley/homelab-arcade)
control portal so it can be started/stopped from `arcade.stanley.arpa` alongside other game
servers.

Runs as its own `docker-compose` service (`arcade-adapter`, see `../docker-compose.yml`) —
`scripts/up.sh` at the repo root starts both `palworld` and `arcade-adapter` together, in one
idempotent step. The adapter talks to the Docker Engine API directly over the mounted Docker
socket (`docker` Python SDK, no CLI needed) to control the sibling `palworld` container — it
does not shell out to `docker compose` and doesn't need the compose plugin installed.

## Contract

Implements the standard arcade adapter contract — see homelab-arcade's
`docs/ARCADE_CONTRACT.md` for the full spec. Summary:

- `GET /arcade/info` → `{id, name, description, actions, status}`
- `POST /arcade/actions/start` / `POST /arcade/actions/stop` → starts/stops the sibling
  `palworld` container directly (identified by its `com.docker.compose.project`/`.service`
  labels, not a hardcoded container name)
- Registers itself with `POST {ARCADE_BASE_URL}/api/register` every
  `ARCADE_HEARTBEAT_SECONDS` (default 30s)

## Run

```bash
./scripts/up.sh
```

That's the entire deployment — `docker compose up -d` for both services. No systemd, no host
Python, no sudo.

## Config (`.env`, see `.env.example`)

| Var | Default | Notes |
|---|---|---|
| `ARCADE_SERVER_ID` | `palworld` | unique id in the arcade registry |
| `ARCADE_SERVER_NAME` | `Palworld` | display name |
| `ARCADE_SERVER_DESCRIPTION` | `Palworld dedicated server (docker-palworld)` | |
| `ARCADE_BASE_URL` | `http://arcade.stanley.arpa` | where to register |
| `ARCADE_ADAPTER_PORT` | `8300` | this adapter's own listen port |
| `ARCADE_ADAPTER_BASE_URL` | auto-detected LAN IP | override if auto-detection picks the wrong interface |
| `ARCADE_HEARTBEAT_SECONDS` | `30` | registration heartbeat interval |

## Gotchas

- Uses `container.stop()`, not removing it — the container and the `data/` volume are left in
  place, no world data is touched. `start()` on an already-running container is a no-op.
- The adapter container has the host Docker socket mounted in — this is root-equivalent host
  access, scoped to this one container only. Standard pattern for control agents (Portainer,
  Watchtower use the same approach), but worth knowing.
- This adapter is **unauthenticated** — it trusts the homelab LAN/VPN, same trust model as
  RCON. Do not expose `ARCADE_ADAPTER_PORT` outside the LAN.
