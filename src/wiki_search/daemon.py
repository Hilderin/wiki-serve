import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from .config import WikiSearchConfig

logger = logging.getLogger("wiki-serve.daemon")

PID_DIR = Path(".wiki-index")
PID_FILE = PID_DIR / "http.pid"
LOG_FILE = PID_DIR / "http.log"
POLL_INTERVAL = 0.2
MAX_WAIT = 10.0


def _get_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def _save_pid(pid: int) -> None:
    PID_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


async def _wait_for_health(config: WikiSearchConfig, timeout: float = MAX_WAIT) -> bool:
    url = f"http://{config.host}:{config.port}/health"
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(url, timeout=2)
                if r.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(POLL_INTERVAL)
    return False


def cmd_start(config: WikiSearchConfig) -> None:
    existing = _get_pid()
    if existing and _is_running(existing):
        print(f"Server already running (PID {existing})")
        return

    print(f"Starting wiki-serve on {config.host}:{config.port}...")
    PID_DIR.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "--host", config.host,
         "--port", str(config.port),
         "--factory",
         "wiki_search.http_server:create_app",
         "--log-level", "info"],
        env=env,
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
    )
    _save_pid(proc.pid)

    if asyncio.run(_wait_for_health(config)):
        print(f"Server started (PID {proc.pid}) — http://{config.host}:{config.port}")
    else:
        print("Server failed to start within timeout")
        proc.kill()
        _remove_pid()
        sys.exit(1)


def cmd_stop(config: WikiSearchConfig) -> None:
    pid = _get_pid()
    if not pid:
        print("No PID file found")
        return
    if not _is_running(pid):
        print(f"Server not running (stale PID {pid})")
        _remove_pid()
        return
    print(f"Stopping server (PID {pid})...")
    os.kill(pid, signal.SIGTERM)
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass
    _remove_pid()
    print("Server stopped")


def cmd_restart(config: WikiSearchConfig) -> None:
    cmd_stop(config)
    time.sleep(0.5)
    cmd_start(config)


def cmd_status(config: WikiSearchConfig) -> None:
    pid = _get_pid()
    if pid and _is_running(pid):
        alive = asyncio.run(_wait_for_health(config, timeout=3.0))
        if alive:
            print(f"Server is running (PID {pid}) — http://{config.host}:{config.port}")
        else:
            print(f"Process exists (PID {pid}) but not responding")
    else:
        if pid:
            _remove_pid()
        print("Server is not running")


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    config = WikiSearchConfig.from_env()

    if len(sys.argv) < 2:
        print("Usage: wiki-serve daemon <start|stop|restart|status>")
        sys.exit(1)

    command = sys.argv[1]
    if command == "start":
        cmd_start(config)
    elif command == "stop":
        cmd_stop(config)
    elif command == "restart":
        cmd_restart(config)
    elif command == "status":
        cmd_status(config)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
