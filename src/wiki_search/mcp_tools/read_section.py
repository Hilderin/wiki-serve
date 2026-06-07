from pathlib import Path

from mcp.types import Tool, TextContent

from ..db.repository import ChunkRepository

READ_SECTION_TOOL = Tool(
    name="read_section",
    description="Read a specific section from a wiki file by path and heading path. Reads the actual file from disk for the complete section content, with fallback to indexed chunks.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path relative to wiki root"},
            "heading": {"type": "string", "description": "Heading path, e.g. 'Architecture > Agents > Handoff'"},
        },
        "required": ["path", "heading"],
    },
)


def _parse_heading(line: str) -> tuple[int, str] | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None
    level = 0
    for ch in stripped:
        if ch == "#":
            level += 1
        else:
            break
    if level < 1 or level > 6:
        return None
    title = stripped[level:].strip()
    if not title:
        return None
    return level, title


def _find_section_range(lines: list[str], heading_path: str) -> tuple[int, int] | None:
    parts = [p.strip() for p in heading_path.split(">")]

    stack: list[tuple[int, str]] = []
    target_start = None
    target_level = None

    for i, line in enumerate(lines):
        parsed = _parse_heading(line)
        if parsed:
            level, title = parsed
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))

            if " > ".join(t for _, t in stack) == heading_path:
                target_start = i
                target_level = level
                break

    if target_start is None:
        return None

    target_end = len(lines)
    for i in range(target_start + 1, len(lines)):
        parsed = _parse_heading(lines[i])
        if parsed and parsed[0] <= target_level:
            target_end = i
            break

    return target_start, target_end


def _resolve_file(config, path: str) -> Path | None:
    p = Path(path)
    if p.is_absolute():
        return p if p.exists() else None

    candidate = (Path.cwd() / p).resolve()
    if candidate.exists():
        return candidate

    for inc in config.include_paths:
        inc = inc.resolve()
        base = inc if inc.is_dir() else inc.parent
        candidate = (base / p).resolve()
        if candidate.exists():
            return candidate

    return None


def read_section_from_disk(config, path: str, heading: str) -> dict | None:
    filepath = _resolve_file(config, path)
    if not filepath:
        return None

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    section_range = _find_section_range(lines, heading)
    if not section_range:
        return None

    start, end = section_range
    return {
        "content": "\n".join(lines[start:end]),
        "start_line": start + 1,
        "end_line": end,
    }


async def handle_read_section(config, db, arguments: dict) -> list[TextContent]:
    path = arguments["path"]
    heading = arguments["heading"]

    section = read_section_from_disk(config, path, heading)
    if section:
        text = (
            f"File: {path}\n"
            f"Heading: {heading}\n"
            f"Lines: {section['start_line']}-{section['end_line']}\n\n"
            f"{section['content']}"
        )
        return [TextContent(type="text", text=text)]

    repo = ChunkRepository(db)
    chunks = repo.get_chunks_by_heading(path, heading)
    if not chunks:
        return [TextContent(
            type="text",
            text=f"Section not found: '{heading}' in '{path}'",
        )]

    content = "\n".join(c["content"] for c in chunks)
    text = (
        f"File: {path}\n"
        f"Heading: {heading}\n"
        f"Lines: {chunks[0]['start_line']}-{chunks[-1]['end_line']}\n"
        f"(partial content — file not available on disk)\n\n"
        f"{content}"
    )
    return [TextContent(type="text", text=text)]
