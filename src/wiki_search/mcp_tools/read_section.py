from mcp.types import Tool, TextContent

from ..db.repository import ChunkRepository

READ_SECTION_TOOL = Tool(
    name="wiki_read_section",
    description="Read a specific section from a wiki file by path and heading path.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to wiki root"},
            "heading": {"type": "string", "description": "Heading path, e.g. 'Architecture > Agents > Handoff'"},
        },
        "required": ["path", "heading"],
    },
)


async def handle_read_section(db, arguments: dict) -> list[TextContent]:
    repo = ChunkRepository(db)
    chunks = repo.get_chunks_by_heading(arguments["path"], arguments["heading"])

    if not chunks:
        return [TextContent(
            type="text",
            text=f"Section not found: '{arguments['heading']}' in '{arguments['path']}'",
        )]

    content = "\n".join(c["content"] for c in chunks)
    text = (
        f"File: {arguments['path']}\n"
        f"Heading: {arguments['heading']}\n"
        f"Lines: {chunks[0]['start_line']}-{chunks[-1]['end_line']}\n\n"
        f"{content}"
    )
    return [TextContent(type="text", text=text)]
