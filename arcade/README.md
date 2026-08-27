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
| `ARCADE_SERVER_ID` | `arcade-palworld` | unique id in the arcade registry |
| `ARCADE_SERVER_NAME` | `Palworld` | display name |
| `ARCADE_SERVER_DESCRIPTION` | `Palworld dedicated server (arcade-palworld)` | |
| `ARCADE_BASE_URL` | `https://arcade.stanley.arpa` | where to register |
| `ARCADE_ADAPTER_PORT` | `8300` | this adapter's own listen port |
| `ARCADE_ADAPTER_BASE_URL` | **required, no default** | this host's reachable address — prefer its `*.stanley.arpa` DNS name (e.g. `http://adler.stanley.arpa:8300`) over a raw IP if one exists; auto-detection from inside a container can never see the host's real address |
| `ARCADE_HEARTBEAT_SECONDS` | `30` | registration heartbeat interval |
| `ARCADE_COMPOSE_PROJECT` | `arcade-palworld` | compose project label this adapter looks for |
| `ARCADE_COMPOSE_SERVICE` | `palworld` | compose service label this adapter looks for |
| `ARCADE_STOP_TIMEOUT_SECONDS` | `30` | must match this repo's `stop_grace_period` |
| `ARCADE_UPNP_ENABLED` | `true` | opens/closes a router port-forward for `SERVER_PORT` on start/stop via UPnP; set `false` to fall back to a manually-configured forward |
| `ARCADE_FORWARD_PROTOCOL` | `udp` | protocol of the mapping UPnP opens — matches `palworld`'s game port (`SERVER_PORT`, reused from the top-level `.env`, not a separate value) |

## Gotchas

- Uses `container.stop()`, not removing it — the container and the `data/` volume are left in
  place, no world data is touched. `start()` on an already-running container is a no-op.
- The adapter container has the host Docker socket mounted in — this is root-equivalent host
  access, scoped to this one container only. Standard pattern for control agents (Portainer,
  Watchtower use the same approach), but worth knowing.
- This adapter is **unauthenticated** — it trusts the homelab LAN/VPN, same trust model as
  RCON. Do not expose `ARCADE_ADAPTER_PORT` outside the LAN.
- Runs with `network_mode: host` — required for UPnP router discovery (SSDP multicast), which
  doesn't reliably work across Docker's default bridge network. This means the adapter binds
  `ARCADE_ADAPTER_PORT` directly on the host's network stack, not through a published port
  mapping.
- UPnP port-forwarding only ever touches `SERVER_PORT`/`ARCADE_FORWARD_PROTOCOL` — RCON's port is
  never forwarded, regardless of `RCON_ENABLED`. A UPnP failure (router unreachable, UPnP
  disabled, lease rejected) is logged as a warning and never blocks the start/stop action itself.
  The mapping is re-asserted once per heartbeat while running, so a router-side lease expiry or
  reboot self-heals within one heartbeat interval, and once on adapter boot so an adapter restart
  while the game server is already running converges to the correct forwarding state immediately.
