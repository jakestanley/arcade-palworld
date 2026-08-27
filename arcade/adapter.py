#!/usr/bin/env python3
"""arcade.stanley.arpa control adapter for docker-palworld.

Runs as its own docker-compose service (see ../docker-compose.yml), with
the host Docker socket mounted in, so it can control the sibling `palworld`
service directly via the Docker Engine API — no docker CLI/compose plugin
needed inside this container, just the `docker` Python SDK.

Exposes the shared arcade adapter contract (GET /arcade/info, POST
/arcade/actions/<action>), and periodically registers itself with the
arcade portal so it shows up as a managed server with start/stop actions.

See docs/ARCADE_CONTRACT.md (in homelab-standards / homelab-arcade) for
the protocol this implements.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import docker
from docker.errors import DockerException, NotFound

SERVER_ID = os.environ.get("ARCADE_SERVER_ID", "arcade-palworld")
SERVER_NAME = os.environ.get("ARCADE_SERVER_NAME", "Palworld")
SERVER_DESCRIPTION = os.environ.get(
    "ARCADE_SERVER_DESCRIPTION", "Palworld dedicated server (docker-palworld)"
)
ADAPTER_PORT = int(os.environ.get("ARCADE_ADAPTER_PORT", "8300"))
ARCADE_BASE_URL = os.environ.get("ARCADE_BASE_URL", "https://arcade.stanley.arpa").rstrip("/")
HEARTBEAT_SECONDS = float(os.environ.get("ARCADE_HEARTBEAT_SECONDS", "30"))
ADAPTER_BASE_URL_OVERRIDE = os.environ.get("ARCADE_ADAPTER_BASE_URL", "").rstrip("/")

# Internal HTTPS uses the homelab's private CA (see homelab-standards'
# internal-ca-trust.md) — never disable verification instead.
HOMELAB_CA_FILE = os.environ.get("HOMELAB_CA_FILE", "/etc/ssl/certs/homelab-ca.crt")
_ssl_context = None
if os.path.isfile(HOMELAB_CA_FILE):
    _ssl_context = ssl.create_default_context(cafile=HOMELAB_CA_FILE)

# Which compose-managed container this adapter controls, identified by the
# labels docker compose itself sets — not a hardcoded container name, so it
# still works if the project/container naming ever changes.
COMPOSE_PROJECT = os.environ.get("ARCADE_COMPOSE_PROJECT", "docker-palworld")
COMPOSE_SERVICE = os.environ.get("ARCADE_COMPOSE_SERVICE", "palworld")

# Should match docker-compose.yml's stop_grace_period for the target service.
STOP_TIMEOUT_SECONDS = int(os.environ.get("ARCADE_STOP_TIMEOUT_SECONDS", "30"))

ACTIONS = ["start", "stop"]

docker_client = docker.from_env()


def detect_primary_ip() -> str:
    """Best-effort LAN IP detection, same trick homelab-arcade's portal uses."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def adapter_base_url() -> str:
    if ADAPTER_BASE_URL_OVERRIDE:
        return ADAPTER_BASE_URL_OVERRIDE
    return f"http://{detect_primary_ip()}:{ADAPTER_PORT}"


def find_target_container():
    containers = docker_client.containers.list(
        all=True,
        filters={
            "label": [
                f"com.docker.compose.project={COMPOSE_PROJECT}",
                f"com.docker.compose.service={COMPOSE_SERVICE}",
            ]
        },
    )
    return containers[0] if containers else None


def current_status() -> str:
    """running | stopped | unknown"""
    try:
        container = find_target_container()
    except DockerException:
        return "unknown"
    if container is None:
        return "unknown"
    container.reload()
    return "running" if container.status == "running" else "stopped"


def do_start() -> tuple[bool, str]:
    try:
        container = find_target_container()
        if container is None:
            return False, f"no container found for {COMPOSE_PROJECT}/{COMPOSE_SERVICE}"
        container.start()
    except (DockerException, NotFound) as exc:
        return False, str(exc)
    return True, current_status()


def do_stop() -> tuple[bool, str]:
    try:
        container = find_target_container()
        if container is None:
            return False, f"no container found for {COMPOSE_PROJECT}/{COMPOSE_SERVICE}"
        # Match docker-compose.yml's stop_grace_period — the SDK's own
        # default (10s) is shorter and risks SIGKILL before the game
        # finishes saving on shutdown.
        container.stop(timeout=STOP_TIMEOUT_SECONDS)
    except (DockerException, NotFound) as exc:
        return False, str(exc)
    return True, current_status()


ACTION_HANDLERS = {
    "start": do_start,
    "stop": do_stop,
}


class AdapterHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/arcade/info":
            self._send_json(
                200,
                {
                    "id": SERVER_ID,
                    "name": SERVER_NAME,
                    "description": SERVER_DESCRIPTION,
                    "actions": ACTIONS,
                    "status": current_status(),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parts = self.path.rstrip("/").split("/")
        # expect /arcade/actions/<action>
        if len(parts) == 4 and parts[1] == "arcade" and parts[2] == "actions":
            action = parts[3]
            handler = ACTION_HANDLERS.get(action)
            if handler is None:
                self._send_json(404, {"ok": False, "error": f"unknown action: {action}"})
                return
            ok, status_or_error = handler()
            if ok:
                self._send_json(200, {"ok": True, "status": status_or_error})
            else:
                self._send_json(500, {"ok": False, "error": status_or_error})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def log_message(self, format: str, *args) -> None:  # quieter default logging
        print(f"[adapter] {self.address_string()} - {format % args}")


def heartbeat_loop() -> None:
    register_url = f"{ARCADE_BASE_URL}/api/register"
    base_url = adapter_base_url()
    while True:
        payload = {
            "id": SERVER_ID,
            "name": SERVER_NAME,
            "description": SERVER_DESCRIPTION,
            "base_url": base_url,
            "actions": ACTIONS,
            "status": current_status(),
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            register_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5, context=_ssl_context):
                pass
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"[heartbeat] failed to register with {register_url}: {exc}")
        time.sleep(HEARTBEAT_SECONDS)


def main() -> None:
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", ADAPTER_PORT), AdapterHandler)
    print(f"Palworld arcade adapter listening on http://0.0.0.0:{ADAPTER_PORT}")
    print(f"Controlling {COMPOSE_PROJECT}/{COMPOSE_SERVICE} via the Docker socket")
    print(f"Registering with {ARCADE_BASE_URL} every {HEARTBEAT_SECONDS}s as '{SERVER_ID}'")
    server.serve_forever()


if __name__ == "__main__":
    main()
