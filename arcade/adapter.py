#!/usr/bin/env python3
"""arcade.stanley.arpa control adapter for arcade-palworld.

Thin wrapper around lib_arcade -- see that repo for the actual HTTP
server, Docker control, heartbeat loop, and UPnP port-forwarding logic.
This file only supplies this repo's own defaults.
"""

from __future__ import annotations

from lib_arcade import AdapterConfig, run_adapter

config = AdapterConfig.from_env(
    default_server_id="arcade-palworld",
    default_server_name="Palworld",
    default_server_description="Palworld dedicated server (arcade-palworld)",
    default_adapter_port=8300,
    default_compose_project="arcade-palworld",
    default_compose_service="palworld",
    default_stop_timeout_seconds=30,
    default_forward_protocol="udp",
)

if __name__ == "__main__":
    run_adapter(config)
