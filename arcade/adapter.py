#!/usr/bin/env python3
"""arcade.stanley.arpa control adapter for docker-palworld.

Runs as a plain host process (not inside Docker, to avoid Docker-socket
exposure) alongside this repo. Exposes the shared arcade adapter contract
(GET /arcade/info, POST /arcade/actions/<action>) backed by `docker compose`,
and periodically registers itself with the arcade portal so it shows up as
a managed server with start/stop actions.

Zero third-party dependencies on purpose — this only needs to run reliably
as a small systemd unit, not pull in a virtualenv.

See docs/ARCADE_CONTRACT.md for the protocol this implements, and
homelab-arcade's docs/ for the portal side.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent

SERVER_ID = os.environ.get("ARCADE_SERVER_ID", "palworld")
SERVER_NAME = os.environ.get("ARCADE_SERVER_NAME", "Palworld")
SERVER_DESCRIPTION = os.environ.get(
    "ARCADE_SERVER_DESCRIPTION", "Palworld dedicated server (docker-palworld)"
)
ADAPTER_PORT = int(os.environ.get("ARCADE_ADAPTER_PORT", "8300"))
ARCADE_BASE_URL = os.environ.get("ARCADE_BASE_URL", "http://arcade.stanley.arpa").rstrip("/")
HEARTBEAT_SECONDS = float(os.environ.get("ARCADE_HEARTBEAT_SECONDS", "30"))
ADAPTER_BASE_URL_OVERRIDE = os.environ.get("ARCADE_ADAPTER_BASE_URL", "").rstrip("/")

ACTIONS = ["start", "stop"]


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


def run_compose(*args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=REPO_DIR,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def current_status() -> str:
    """running | stopped | unknown"""
    try:
        result = run_compose("ps", "--status", "running", "-q", timeout=15)
    except (subprocess.SubprocessError, OSError):
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    return "running" if result.stdout.strip() else "stopped"


def do_start() -> tuple[bool, str]:
    result = run_compose("up", "-d")
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "docker compose up failed").strip()
    return True, current_status()


def do_stop() -> tuple[bool, str]:
    # `stop`, not `down` — leaves the container/volumes in place so a
    # subsequent `start` is fast and no world data is touched.
    result = run_compose("stop")
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "docker compose stop failed").strip()
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
            try:
                ok, status_or_error = handler()
            except subprocess.TimeoutExpired:
                self._send_json(504, {"ok": False, "error": "docker compose timed out"})
                return
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
            with urllib.request.urlopen(request, timeout=5):
                pass
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            print(f"[heartbeat] failed to register with {register_url}: {exc}")
        time.sleep(HEARTBEAT_SECONDS)


def main() -> None:
    threading.Thread(target=heartbeat_loop, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", ADAPTER_PORT), AdapterHandler)
    print(f"Palworld arcade adapter listening on http://0.0.0.0:{ADAPTER_PORT}")
    print(f"Registering with {ARCADE_BASE_URL} every {HEARTBEAT_SECONDS}s as '{SERVER_ID}'")
    server.serve_forever()


if __name__ == "__main__":
    main()
