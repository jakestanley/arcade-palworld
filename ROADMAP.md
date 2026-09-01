# Roadmap

Forward-looking only. Already shipped: the `backup_now` action (invokes the
image's own `bash /usr/local/bin/backup` via `lib-arcade`'s `do_exec`).

## Backup restore path is untested

`backup_now` produces structurally-valid archives — confirmed via `gzip -t`
and `tar -tzf` on a real backup: correct entry structure, real
`Level.sav`/`LevelMeta.sav`/`WorldOption.sav`/per-player save sizes,
nothing corrupt or truncated. But nobody has actually tried restoring from
one. Proposed test, not yet run: spin up a second, disposable Palworld
container pointed at an extracted copy of a backup, confirm it boots
clean, without touching the real server or its live data.

## Broaden presets/toggles

Once curated presets/toggles exist for one game (see
`homelab-arcade/ROADMAP.md`), extend the same pattern to this server's own
control surface. Not started — no adapter-side design work done yet for
Palworld specifically.
