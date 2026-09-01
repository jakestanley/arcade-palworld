#!/usr/bin/env bash
# Restores a backup archive (as produced by the image's own `backup_now`/
# `bash /usr/local/bin/backup`) as the live save, so you can boot the real
# palworld service against it. Stops palworld, moves the CURRENT live
# Saved/ aside (never deletes it) so it can be put back later, extracts the
# given backup in its place, then starts palworld back up.
#
# Usage: scripts/restore_backup.sh <path-to-backup.tar.gz>
#
# To revert to the live save afterward: stop palworld, remove the
# restored Pal/Saved, rename the preserved Saved.pre-restore-<timestamp>
# back to Saved, start palworld again. This script prints the exact path
# to preserve.
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <path-to-backup.tar.gz>" >&2
  exit 1
fi

BACKUP="$1"
if [[ ! -f "$BACKUP" ]]; then
  echo "ERROR: backup file not found: $BACKUP" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

# .env isn't guaranteed to be valid bash (e.g. unquoted cron expressions
# with spaces), so pull out just the vars we need instead of sourcing it.
env_var() {
  grep -E "^$1=" .env | tail -n1 | cut -d= -f2-
}
DATA_PATH="$(env_var DATA_PATH)"
DATA_PATH="${DATA_PATH:-./data}"
PUID="$(env_var PUID)"
PUID="${PUID:-1000}"
PGID="$(env_var PGID)"
PGID="${PGID:-1000}"

SAVED_DIR="$DATA_PATH/Pal/Saved"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
PRESERVED_DIR="$DATA_PATH/Pal/Saved.pre-restore-${TIMESTAMP}"

echo "==> Validating backup archive..."
gzip -t "$BACKUP"
tar -tzf "$BACKUP" > /dev/null

echo "==> Stopping palworld service..."
docker compose stop palworld

echo "==> Preserving current live save..."
if [[ -d "$SAVED_DIR" ]]; then
  mv "$SAVED_DIR" "$PRESERVED_DIR"
  echo "    Live save moved to: $PRESERVED_DIR"
else
  echo "    No existing $SAVED_DIR found -- nothing to preserve."
fi

echo "==> Extracting backup into $SAVED_DIR ..."
mkdir -p "$SAVED_DIR"
tar -xzf "$BACKUP" -C "$DATA_PATH/Pal"

echo "==> Fixing ownership (PUID:PGID = ${PUID}:${PGID})..."
chown -R "${PUID}:${PGID}" "$SAVED_DIR"

echo "==> Starting palworld service..."
docker compose up -d palworld

cat <<EOF

Done. palworld is now running against:
  $BACKUP

Your previous live save was preserved at:
  $PRESERVED_DIR

To revert back to the live save:
  docker compose stop palworld
  rm -rf "$SAVED_DIR"
  mv "$PRESERVED_DIR" "$SAVED_DIR"
  docker compose up -d palworld
EOF
