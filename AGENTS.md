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
- **A subset of `PalWorldSettings.ini` values get baked into `WorldOption.sav`
  at world creation and then ignore the ini forever** — confirmed for
  `BaseCampWorkerMaxNum`/`BASE_CAMP_WORKER_MAX_NUM`: raising it in `.env` and
  redeploying compiled correctly into `PalWorldSettings.ini` but had zero
  effect in-game on the existing world, because the dedicated server reads
  this value from the save's `WorldOption.sav` instead once one exists. Fix
  for an existing save is to edit `WorldOption.sav` directly — convert with
  [`palworld-save-tools`](https://github.com/cheahjs/palworld-save-tools)
  (`palworld-save-tools --to-json`/`--from-json`), patch the field under
  `properties.OptionWorldData.value.Settings.value.<Key>.value`, back up the
  original save file first, stop `palworld` before swapping it in. No
  general rule for *which* settings are affected — this one is confirmed,
  treat others as suspect until tested the same way. Also confirmed for
  `PlayerStomachDecreaceRate`/`PalStomachDecreaceRate`
  (`PLAYER_STOMACH_DECREASE_RATE`/`PAL_STOMACH_DECREASE_RATE`, used to
  disable hunger) — same fix applied the same way.
- **Guild auto-reset wiped every base and structure once — it's pinned off.**
  The world was created on Windows with `bAutoResetGuildNoOnlinePlayers=True`
  (`AutoResetGuildTimeNoOnlinePlayers=72` hours) baked into `WorldOption.sav`,
  while `PalWorldSettings.ini` said `False` — the save won, same as the
  worker-cap/hunger gotcha above. On 2026-09-19 between 12:30 and 18:30 all
  three bases (palboxes, buildings, `BaseCampSaveData`, `WorkSaveData`) were
  removed completely. It was noticed on 2026-10-09 and fixed on 2026-10-14:
  the flag was flipped in `WorldOption.sav`, and `Level.sav`, `LevelMeta.sav`
  and `Players/` were rolled back to the `palworld-save-2026-09-19_18-00-00`
  image backup. `docker-compose.yml`
  hardcodes `AUTO_RESET_GUILD_NO_ONLINE_PLAYERS: "false"` so the ini can't
  drift either. Never re-enable. If a restored or imported world appears,
  check its `WorldOption.sav` for this flag before letting it run.
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
- **Idle server pausing uses the image's native `AUTO_PAUSE_ENABLED` /
  `AUTO_PAUSE_TIMEOUT_EST`** (seconds, default `1800` here = 30 min here),
  not anything custom. Confirmed via the image's own `autopause/` scripts:
  it saves the world (REST API or RCON) before pausing, actually suspends
  the `PalServer` process itself (real CPU savings, not just "reject new
  joins"), and runs a `knockd` watcher that auto-resumes the instant
  someone tries to connect — no manual start needed. A generic
  portal-driven idle-shutdown mechanism was built into
  [`lib-arcade`](https://github.com/jakestanley/lib-arcade) (opt-in
  `ARCADE_IDLE_SHUTDOWN_ENABLED`/`player_count_fn`) before this native
  option was found; it's merged upstream but deliberately left unwired
  here since native auto-pause covers the same need better. Don't rebuild
  it — if a future consumer needs idle-shutdown and has no native
  equivalent, that's what it's for.
- **A paused server still reports `running`/`healthy` to Docker and the
  arcade portal** — pausing suspends the process, it doesn't stop the
  container, so this is a different flavor of the existing
  "`healthy` only means the process didn't crash" gotcha above. Don't read
  portal/container status as proof players can currently see activity;
  check logs for `[AUTO PAUSE]` lines if you need to know whether it's
  actually paused right now.
