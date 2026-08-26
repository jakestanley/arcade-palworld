# docker-palworld

Dockerized Palworld dedicated server using
[thijsvanloef/palworld-server-docker](https://github.com/thijsvanloef/palworld-server-docker).

## Setup

1. Copy the example env file and edit it:
   ```
   cp .env.example .env
   ```
   At minimum, set `ADMIN_PASSWORD` and `SERVER_NAME`. Set `SERVER_PASSWORD`
   if you want to require a password to join.

2. Start the server:
   ```
   docker compose up -d
   ```

   First boot downloads the Palworld dedicated server via SteamCMD into
   `${DATA_PATH}` (default `./data`), so it can take a while — follow logs
   with `docker compose logs -f`.

3. Forward/open UDP port `${SERVER_PORT}` (default `8211`) on your router
   and firewall so players outside your LAN can connect.

## Data

World saves, config (`PalWorldSettings.ini`), and backups live under
`${DATA_PATH}` and are bind-mounted into the container — they persist across
`docker compose down`/`up` and image updates. Both `.env` and `data/` are
git-ignored.

## Updating

The server auto-updates on container start when `AUTO_UPDATE_ENABLED=true`.
To update the container image itself:
```
docker compose pull
docker compose up -d
```

## Config reference

Most `PalWorldSettings.ini` values (difficulty, drop rates, PvP, day/night
speed, etc.) can be set via additional environment variables in
`docker-compose.yml`/`.env` — see the full list in the
[image's README](https://github.com/thijsvanloef/palworld-server-docker#environment-variables).
