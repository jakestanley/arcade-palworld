#!/usr/bin/env bash
# Canonical, idempotent entrypoint: starts the Palworld server and its
# arcade.stanley.arpa control adapter, both as docker-compose services.
# Safe to re-run any time (docker compose up -d only touches what changed).
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

docker compose up -d
