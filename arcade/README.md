# arcade.stanley.arpa adapter

Registers this Palworld server with the [homelab-arcade](https://github.com/jakestanley/homelab-arcade)
control portal so it can be started/stopped from `arcade.stanley.arpa` alongside other game
servers.

Runs as its own `docker-compose` service (`arcade-adapter`, see `../docker-compose.yml`) —
`scripts/up.sh` at the repo root starts both `palworld` and `arcade-adapter` together, in one
idempotent step. The adapter talks to the Docker Engine API directly over the mounted Docker
socket (`docker` Python SDK, no CLI needed) to control the sibling `palworld` container — it
does not shell out to `docker compose` and doesn't need the compose plugin installed.

`adapter.py` here is just this repo's own config (server id/name, compose project/service,
`ARCADE_FORWARD_PROTOCOL`, etc.) — the actual HTTP server, Docker control, heartbeat loop, and
UPnP logic live in [`lib-arcade`](https://github.com/jakestanley/lib-arcade), installed as a git
dependency tracking its `main` branch (see `requirements.txt`). `arcade-minecraft` and
`arcade-cs2` share the same library — see its own README for the unpinned-dependency and
adapter-trust-model caveats that apply here too, not just repeated per consumer. The `CACHEBUST`
build arg in the `Dockerfile` exists to force a rebuild to actually pick up new `lib-arcade`
commits (see that README for why).

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
| `DOCKER_SOCKET_GID` | `999` | GID of the host's `docker` group (owns `/var/run/docker.sock`) — used by the `docker-socket-proxy` service, not the adapter directly. Verify with `stat -c '%g' /var/run/docker.sock`, don't assume the default. |

## Gotchas

- Uses `container.stop()`, not removing it — the container and the `data/` volume are left in
  place, no world data is touched. `start()` on an already-running container is a no-op.
- Unauthenticated — `lib-arcade`'s HTTP endpoints have no auth of their own, trusting the
  homelab LAN/VPN instead (same trust model as RCON, standard for control agents like
  Portainer/Watchtower). See [`lib-arcade`'s README](https://github.com/jakestanley/lib-arcade#gotchas)
  for the full reasoning. Don't expose `ARCADE_ADAPTER_PORT` outside the LAN.
- **Does not have `docker.sock` mounted directly** — talks to Docker through the
  `docker-socket-proxy` service (`docker-socket-proxy.command` in `docker-compose.yml`, image
  [`wollomatic/socket-proxy`](https://github.com/wollomatic/socket-proxy)) instead, via
  `DOCKER_HOST=tcp://127.0.0.1:2375`. The proxy allow-lists exactly the Docker API calls
  `lib_arcade.docker_control` actually makes (container list/inspect/start/stop/exec, image
  pull+inspect) and default-denies everything else, including `POST /containers/create` and any
  `DELETE` — those are the calls `do_update`'s container-recreate needs, and a raw `docker.sock`
  mount would otherwise make container create/exec root-equivalent (a compromised adapter could
  spin up a privileged container with the host root filesystem bind-mounted). Verified live: a
  raw `curl` to the proxy's `/containers/create` returns `403`, `DELETE` returns `405`, while
  `containers/json` (list) still returns `200`.
  - **Consequence: `lib-arcade`'s baseline `update` action will always fail cleanly through this
    adapter** (`do_update` can pull+inspect the new image fine, but the delete+recreate step it
    needs gets blocked). This is intentional, not a bug — updates for this server are deliberately
    manual (`docker compose pull` + restart) because per-server update caveats (see the
    `WorldOption.sav`/`AUTO_PAUSE`/etc. gotchas throughout this doc) make an unattended one-click
    "update" too flaky to trust as a generic portal feature.
  - `docker-socket-proxy` also runs `network_mode: host` (not a custom bridge network) —
    deliberately, so its default `-allowfrom=127.0.0.1/32` matches the adapter's real connecting
    address instead of a NAT-rewritten bridge-gateway IP, and so `palworld` (which stays on the
    project's own bridge network) has no network path to it at all. Requires
    `DOCKER_SOCKET_GID` in `.env` to match the host's `docker` group
    (`stat -c '%g' /var/run/docker.sock`) so the proxy can read the socket without running as root.
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
