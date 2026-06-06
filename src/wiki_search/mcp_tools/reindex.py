from mcp.types import Tool, TextContent

REINDEX_TOOL = Tool(
    name="wiki_reindex",
    description="Force reindexing of the wiki.",
    inputSchema={
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "Reindex mode: 'changed-only' or 'rebuild'",
                "default": "changed-only",
            },
        },
    },
)


async def handle_reindex(indexer, arguments: dict) -> list[TextContent]:
    mode = arguments.get("mode", "changed-only")
    if mode == "rebuild":
        count = indexer.rebuild()
        return [TextContent(type="text", text=f"Rebuild complete. Reindexed {count} files")]
    count = indexer.reindex_changed_only()
    return [TextContent(type="text", text=f"Changed-only reindex complete. Processed {count} files.")]
