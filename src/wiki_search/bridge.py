import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import anyio
import httpx

logger = logging.getLogger("wiki-serve.bridge")

BRIDGE_POLL_INTERVAL = 0.2
BRIDGE_MAX_WAIT = 10.0


async def _wait_for_health(url: str, timeout: float = BRIDGE_MAX_WAIT) -> bool:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient() as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(f"{url}/health", timeout=2)
                if r.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await anyio.sleep(BRIDGE_POLL_INTERVAL)
    return False


def _start_daemon(config_module: str = "wiki_search.http_server") -> subprocess.Popen:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "--host", env.get("WIKI_HOST", "127.0.0.1"),
         "--port", env.get("WIKI_PORT", "8765"),
         "--factory",
         f"{config_module}:create_app",
         "--log-level", "info"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc


async def _relay(read_stream, write_stream):
    try:
        async for msg in read_stream:
            await write_stream.send(msg)
    except anyio.EndOfStream:
        pass
    except Exception:
        pass


async def _get_server_paths(url: str) -> list[Path] | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{url}/api/status", timeout=3)
            if r.status_code == 200:
                return sorted(Path(p).resolve() for p in r.json().get("include_paths", []))
    except Exception:
        pass
    return None


async def bridge_main() -> None:
    from .config import WikiSearchConfig
    cfg = WikiSearchConfig.from_env()
    base_url = f"http://{cfg.host}:{cfg.port}"
    mcp_url = f"{base_url}/mcp/sse"

    configured_paths = sorted(Path(p).resolve() for p in cfg.include_paths)

    alive = await _wait_for_health(base_url, timeout=2.0)
    if alive:
        server_paths = await _get_server_paths(base_url)
        if server_paths is not None and server_paths != configured_paths:
            logger.error(
                "Server on %s already has different include paths:\n"
                "  Server: %s\n"
                "  Wanted: %s\n"
                "Use a different WIKI_PORT or stop the existing server.",
                base_url,
                [str(p) for p in server_paths],
                [str(p) for p in configured_paths],
            )
            sys.exit(1)
        logger.info("Connected to existing server on %s", base_url)
    else:
        logger.info("Starting daemon on %s...", base_url)
        proc = _start_daemon()
        if not await _wait_for_health(base_url):
            logger.error("Failed to start HTTP server")
            proc.kill()
            sys.exit(1)
        logger.info("Daemon started on %s", base_url)

    from mcp.client.sse import sse_client
    import mcp.server.stdio

    try:
        async with sse_client(mcp_url) as (sse_read, sse_write):
            async with mcp.server.stdio.stdio_server() as (stdio_read, stdio_write):
                async with anyio.create_task_group() as tg:
                    tg.start_soon(_relay, stdio_read, sse_write)
                    tg.start_soon(_relay, sse_read, stdio_write)
    except Exception as e:
        logger.error("Bridge error: %s", e)
        sys.exit(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        anyio.run(bridge_main)
    except KeyboardInterrupt:
        pass
