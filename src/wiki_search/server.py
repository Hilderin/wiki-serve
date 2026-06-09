import asyncio
import sys
import threading
import traceback

from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

from .config import WikiSearchConfig
from .db.connection import DatabaseManager
from .db.schema import initialize_database
from .index.indexer import Indexer
from .index.watcher import start_watcher
from .search.hybrid_search import HybridSearcher
from .search.exact_search import ExactSearcher
from .mcp_tools.search_wiki import (
    SEARCH_WIKI_TOOL,
    SEARCH_EXACT_TOOL,
    handle_search,
    handle_search_exact,
)
from .mcp_tools.read_section import READ_SECTION_TOOL, handle_read_section
from .mcp_tools.read_document import READ_DOCUMENT_TOOL, handle_read_document


async def main_stdio() -> None:
    config = WikiSearchConfig.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    db = DatabaseManager(config.index_path)
    initialize_database(db)

    indexer = Indexer(db, config)

    if config.reindex_on_start:
        reindex_done = asyncio.Event()

        def _bg_reindex():
            try:
                count = indexer.reindex_changed_only()
                print(f"[wiki-serve] Indexed {count} files on startup", file=sys.stderr)
            except Exception:
                print(f"[wiki-serve] Reindexing failed:\n{traceback.format_exc()}", file=sys.stderr)
            finally:
                reindex_done.set()

        threading.Thread(target=_bg_reindex, daemon=True).start()

    if config.watch:
        observer = await start_watcher(config, indexer)
        _ = asyncio.create_task(_keep_watcher_alive(observer))
        print(f"[wiki-serve] File watcher started on {len(config.include_paths)} path(s)", file=sys.stderr)

    hybrid = HybridSearcher(db)
    exact = ExactSearcher(db)
    server = Server("wiki-serve")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        return [
            SEARCH_WIKI_TOOL,
            SEARCH_EXACT_TOOL,
            READ_SECTION_TOOL,
            READ_DOCUMENT_TOOL,
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name == "search":
            return await handle_search(hybrid, arguments)
        if name == "search_exact":
            return await handle_search_exact(exact, arguments)
        if name == "read_section":
            return await handle_read_section(config, db, arguments)
        if name == "read_document":
            return await handle_read_document(config, arguments)
        raise ValueError(f"Unknown tool: {name}")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="wiki-serve",
                server_version="0.2.0",
                capabilities=types.ServerCapabilities(),
            ),
        )


async def _keep_watcher_alive(observer) -> None:
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        observer.stop()
        observer.join()
