from mcp.types import Tool, TextContent

from ..db.repository import DocumentRepository

STATUS_TOOL = Tool(
    name="status",
    description="Return the status of the wiki index.",
    inputSchema={
        "type": "object",
        "properties": {},
    },
)


async def handle_status(config, db) -> list[TextContent]:
    doc_repo = DocumentRepository(db)

    row = db.conn.execute("SELECT MAX(indexed_at) as last_indexed FROM documents").fetchone()
    last_indexed = row["last_indexed"] if row else None

    log_path = config.data_dir / "wiki.indexation.log"

    text = (
        f"Include paths ({len(config.include_paths)}):\n"
        + "\n".join(f"  {p}" for p in config.include_paths)
        + f"\nDatabase: {config.index_path}\n"
        f"Log: {log_path}\n"
        f"Documents: {doc_repo.count_documents()}\n"
        f"Chunks: {doc_repo.count_chunks()}\n"
        f"Watcher: {'enabled' if config.watch else 'disabled'}\n"
        f"Last Indexed: {last_indexed or 'never'}"
    )
    return [TextContent(type="text", text=text)]
