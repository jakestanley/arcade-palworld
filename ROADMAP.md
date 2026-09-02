# Roadmap

Forward-looking only. Already shipped: the `backup_now` action (invokes the
image's own `bash /usr/local/bin/backup` via `lib-arcade`'s `do_exec`); the
backup restore path has now been verified end-to-end, including live,
against the real server (see below); `scripts/restore_backup.sh` for
restoring a given backup onto the live service; backups now write to
`${BACKUP_PATH}` (`/var/media/Dropbox/backups/Palworld` by default) instead
of `${DATA_PATH}/backups/`, so they sync to Dropbox (see below).

## Backup restore path — verified 2026-09-01

`backup_now` produces structurally-valid archives — confirmed via `gzip -t`
and `tar -tzf` on a real backup: correct entry structure, real
`Level.sav`/`LevelMeta.sav`/`WorldOption.sav`/per-player save sizes,
nothing corrupt or truncated. Restore itself is now also confirmed: copied
the live install (engine/binaries, excluding `backups/`,
`_manual_backups/`, `_archived_worlds/`) to a disposable location, replaced
`Pal/Saved/` with the contents of a real backup
(`palworld-save-2026-09-01_12-00-00.tar.gz`), and booted a second,
disposable `thijsvanloef/palworld-server-docker` container against it on
non-conflicting ports (`18211/udp`, `35575/tcp`), with
`AUTO_UPDATE_ENABLED`/`UPDATE_ON_BOOT`/`BACKUP_ENABLED`/`RCON_ENABLED` all
`false` to keep it isolated and side-effect-free. Result: clean boot, no
restarts, no corruption/exception/crash indicators in the logs, world and
player saves loaded ("Running Palworld dedicated server on :8211", REST API
up). The real server and its `data/` were never touched. Test container and
scratch copy were torn down afterward.

Repeated the same test against the oldest available backup
(`palworld-save-2026-08-26_12-00-00.tar.gz`, ~6 days older, smaller/earlier
save structure — e.g. no `WorldOption.sav`, one player save instead of two)
to check the restore path isn't just trivially fine on a near-identical
latest backup. Same result: clean boot, no restarts, no error indicators.

Followed up with a live rehearsal against the real service itself (not a
disposable side container): wrote `scripts/restore_backup.sh
<path-to-backup.tar.gz>`, which stops `palworld`, moves the current
`Pal/Saved/` aside to `Pal/Saved.pre-restore-<timestamp>` (never deletes
it), extracts the given backup in its place, and starts `palworld` back up
against it. Used it to restore `palworld-save-2026-08-26_12-00-00.tar.gz`
(the same 6-day-old backup) live, confirmed it, then reverted back to the
preserved live save with the script's own printed revert steps — clean
both ways, `RestartCount=0`, no error indicators.

Ran it a second time against `palworld-save-2026-08-31_06-00-00.tar.gz`
(~1 day old), this time with `BACKUP_ENABLED=false` set in `.env` first so
the auto-backup cronjob didn't get regenerated against the rolled-back
save — confirmed via the container's own "GENERATING CRONTAB" log line
that no backup cronjob was added. Reverted back to the live save the same
way afterward and flipped `BACKUP_ENABLED` back to `true`, confirming via
the same log line that the cronjob was re-added on restart.

## Backups now sync to Dropbox — 2026-09-02

`thijsvanloef/palworld-server-docker`'s own backup script hardcodes its
output path to `/palworld/backups/palworld-save-<date>.tar.gz` (not
env-configurable — confirmed by reading `/usr/local/bin/backup` inside the
running container). Rather than touching `DATA_PATH`, added a second,
narrower bind mount in `docker-compose.yml` — `"${BACKUP_PATH}:/palworld/backups"`
alongside the existing `"${DATA_PATH}:/palworld"` — which redirects that
fixed internal path without touching anything else under `/palworld` (world
saves/config stay on `DATA_PATH` as before). `DELETE_OLD_BACKUPS`/
`OLD_BACKUP_DAYS` retention cleanup follows the mount automatically since
it just runs `find` over the same internal path.

`BACKUP_PATH` added to `.env.example`/`.env`, defaulting to
`/var/media/Dropbox/backups/Palworld` so whatever syncs `/var/media/Dropbox/`
to Dropbox picks these up. Migrated the 30 existing backups from
`data/backups/` there: copied (not moved — different filesystems, `/home`
ext4 vs `/var/media` a ZFS pool), verified count/sha256 checksums matched
for all 30, then deleted the originals. Stopped `palworld` before any of
this, redeployed after (`docker compose up -d palworld` — confirmed
`Recreate`d, not just restarted, so the new mount took effect).

Verified end-to-end: triggered the real `backup_now` adapter action over
its actual HTTP endpoint (`POST /arcade/actions/backup_now`, same path
arcade.stanley.arpa would use) — the new backup landed only in
`/var/media/Dropbox/backups/Palworld/` (30 → 31) and did **not** appear in
the old `data/backups/` (stayed at 0), proving the redirect actually took
effect rather than coincidentally writing both places. `gzip -t`/`tar -tzf`
clean on the new backup and on a couple of the migrated ones. Confirmed
`data/Pal/Saved/` (world/player saves) untouched and current after the
redeploy.

## Broaden presets/toggles

Once curated presets/toggles exist for one game (see
`homelab-arcade/ROADMAP.md`), extend the same pattern to this server's own
control surface. Not started — no adapter-side design work done yet for
Palworld specifically.
