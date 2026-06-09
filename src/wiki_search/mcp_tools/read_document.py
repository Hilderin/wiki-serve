from mcp.types import Tool, TextContent

from .utils import _resolve_file

READ_DOCUMENT_TOOL = Tool(
    name="read_document",
    description="Read the full content of a wiki document by path. Reads the actual file from disk. Returns an error if the document is not found.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to wiki root"},
        },
        "required": ["path"],
    },
)


def read_document_from_disk(config, path: str) -> dict | None:
    filepath = _resolve_file(config, path)
    if not filepath:
        return None

    content = filepath.read_text(encoding="utf-8")
    line_count = content.count("\n") + 1
    return {
        "content": content,
        "line_count": line_count,
    }


async def handle_read_document(config, arguments: dict) -> list[TextContent]:
    path = arguments["path"]

    doc = read_document_from_disk(config, path)
    if not doc:
        return [TextContent(
            type="text",
            text=f"Document not found: '{path}'",
        )]

    text = (
        f"File: {path}\n"
        f"Lines: 1-{doc['line_count']}\n\n"
        f"{doc['content']}"
    )
    return [TextContent(type="text", text=text)]
