# Roadmap

- **De-duplicate the `arcade/` adapter code.** `arcade/adapter.py` and
  `arcade/upnp.py` here are currently a hand copy+sed of the same files in
  `arcade-minecraft` — any future bugfix or `ARCADE_CONTRACT.md` protocol
  change has to be manually re-applied to every adapter repo. Plan: once
  `homelab-standards` vendors a shared adapter library through its
  `scripts/sync_imports.py` mechanism (the same way it already vendors
  `PATTERNS/*.md` into sibling repos), switch this repo's `arcade/` to pull
  the shared HTTP-server/Docker-control/UPnP scaffolding from there instead
  of carrying its own copy. Game-server-specific bits (env var defaults,
  `ARCADE_FORWARD_PROTOCOL`, etc.) stay local.
