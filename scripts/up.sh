#!/usr/bin/env bash
# Canonical, idempotent entrypoint: starts the Palworld server and its
# arcade.stanley.arpa control adapter, both as docker-compose services.
# Safe to re-run any time. Always rebuilds arcade-adapter with a fresh
# CACHEBUST so it picks up the latest lib-arcade commit -- requirements.txt
# pins it to @main, so its own content never changes to naturally
# invalidate Docker's build cache. (--build is a no-op for palworld
# itself, which has no build: section, just a pulled image.)
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and configure it first." >&2
  exit 1
fi

CACHEBUST=$(date +%s) docker compose up -d --build
