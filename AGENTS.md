# docker-palworld

## Overview

Single-service Docker Compose stack running a Palworld dedicated server via
[thijsvanloef/palworld-server-docker](https://github.com/thijsvanloef/palworld-server-docker)
(SteamCMD-based install/update, RCON, auto backups, crossplay).

This is a standalone game-server repo, not a `homelab-standards` /
`homelab-service-template` service — no `registry.yaml` wiring, no
`homelab-infra` dependency. It follows the same lightweight pattern as
sibling repos `docker-minecraft` and the retired `docker-gameservers-deprecated`
stacks: one repo per game, `docker-compose.yml` + `.env` + git-ignored `data/`.

## Files

- `docker-compose.yml` — the `palworld` service definition
- `.env.example` — documented template, committed
- `.env` — actual secrets/config, **git-ignored**, created by copying `.env.example`
- `data/` — bind-mounted to `/palworld` in the container: world saves,
  `PalWorldSettings.ini`, backups. **Git-ignored.** This is the only
  persistent state — treat it like a production data volume, not scratch space.
- `arcade/` — optional adapter that registers this server with the
  [homelab-arcade](https://github.com/jakestanley/homelab-arcade) control
  portal (`arcade.stanley.arpa`) for start/stop from a shared UI. Runs as
  its own `docker-compose` service (`arcade-adapter`), controlling the
  `palworld` container via the Docker socket. See `arcade/README.md`.

## Common commands

```bash
./scripts/up.sh                # idempotent entrypoint: docker compose up -d (palworld + arcade-adapter)
docker compose up -d          # start (first boot downloads server via SteamCMD — can take a while)
docker compose logs -f        # follow logs, especially useful during first-boot install
docker compose pull           # update the container image itself
docker compose down           # stop (data/ persists)
docker compose config         # validate compose + .env substitution without starting anything
```

## Gotchas

- **Crossplay is set via `CROSSPLAY_PLATFORMS`**, not a well-known/obvious
  var name, and takes a parenthesized value (e.g. `(Steam,Xbox)`), not a bare
  comma list. Defaults to `(Steam,Xbox)` in `.env.example` so Xbox/Game Pass
  players can join. Server-side alone isn't sufficient — Xbox/Game Pass
  players also need crossplay enabled in their own in-game settings. (The
  old `ALLOW_CONNECT_PLATFORM` var is deprecated by the image and no longer
  used here.)
- **Multithreading is set via `ENABLE_PERF_THREADING_ARGS` + `WORKER_THREADS_SERVER`**,
  replacing the deprecated `MULTITHREADING` var. `WORKER_THREADS_SERVER`
  should track the host's core count (`.env.example` defaults to `4`).
- **`RCON_PORT` is always published** in `docker-compose.yml` regardless of
  `RCON_ENABLED` — harmless (nothing listens if disabled) but don't assume
  the port mapping implies RCON is on.
- **`ADMIN_PASSWORD` defaults to `changeme`** in `.env.example` — real `.env`
  should never ship with this; check before assuming a deployment is secured.
- Most `PalWorldSettings.ini` values (difficulty, drop rates, PvP, day/night
  speed, etc.) aren't in `.env.example` yet — they're addable as extra env
  vars per the [image's README](https://github.com/thijsvanloef/palworld-server-docker#environment-variables)
  if the user asks for gameplay tuning. Adding one isn't just a `.env`
  change: `docker-compose.yml` explicitly whitelists every var it passes
  through to the image under `environment:`, so a new var needs a line
  there too or the container never sees it (`BASE_CAMP_WORKER_MAX_NUM`, for
  the base pal-worker cap, is the first example of this).
- **Docker's `healthy` status only means the process didn't crash** — the
  image's healthcheck is `pgrep "PalServer-Linux" > /dev/null`, nothing
  app-level. Confirmed directly during backup-restore testing: a `healthy`
  container can still be sitting on a save that failed to load properly.
  When verifying a restore (or any boot) actually worked, check the logs
  for real signals (`Running Palworld dedicated server on :PORT`, REST API
  up, no corruption/exception/crash lines) — don't stop at `healthy`.
- No GitHub remote has been created/pushed for this repo yet (as of initial
  scaffold) — only a local git init. Confirm with the user before creating
  a remote or pushing, per their standing "confirm outward-facing actions"
  preference.
