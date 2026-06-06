import hashlib
from pathlib import Path

CHUNK_MAX_LINES = 50


def chunk_file(filepath: Path) -> list[dict]:
    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    return chunk_content(str(filepath), lines)


def chunk_content(filepath: str, lines: list[str]) -> list[dict]:
    sections = _split_by_headings(lines)
    chunks = []
    for section in sections:
        subchunks = _split_large_section(section)
        chunks.extend(subchunks)
    return chunks


def _split_by_headings(lines: list[str]) -> list[dict]:
    sections = []
    heading_stack: list[dict] = []

    current = {
        "heading_path": [],
        "heading_level": 0,
        "start_line": 0,
        "end_line": 0,
        "lines": [],
    }

    for i, line in enumerate(lines):
        parsed = _parse_heading(line)
        if parsed:
            if current["lines"] or current["heading_level"] > 0:
                current["end_line"] = i - 1
                sections.append(dict(current))

            level, title = parsed
            while heading_stack and heading_stack[-1]["level"] >= level:
                heading_stack.pop()
            heading_stack.append({"level": level, "title": title})

            current = {
                "heading_path": [h["title"] for h in heading_stack],
                "heading_level": level,
                "start_line": i,
                "end_line": i,
                "lines": [line],
            }
        else:
            current["lines"].append(line)
            current["end_line"] = i

    if current["lines"]:
        sections.append(dict(current))

    return sections


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


def _split_large_section(section: dict) -> list[dict]:
    lines = section["lines"]
    if len(lines) <= CHUNK_MAX_LINES:
        content = "\n".join(lines)
        heading_path_str = " > ".join(section["heading_path"]) if section["heading_path"] else None
        return [
            {
                "path": "",
                "heading_path": heading_path_str,
                "heading_level": section["heading_level"],
                "content": content,
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                "start_line": section["start_line"],
                "end_line": section["end_line"],
            }
        ]

    chunks = []
    heading_base = " > ".join(section["heading_path"]) if section["heading_path"] else None

    for i in range(0, len(lines), CHUNK_MAX_LINES):
        chunk_lines = lines[i : i + CHUNK_MAX_LINES]
        hp = heading_base
        if i > 0 and hp:
            hp = f"{hp} (cont.)"
        elif i > 0:
            hp = "(cont.)"

        content = "\n".join(chunk_lines)
        chunks.append(
            {
                "path": "",
                "heading_path": hp,
                "heading_level": section["heading_level"],
                "content": content,
                "content_hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                "start_line": section["start_line"] + i,
                "end_line": section["start_line"] + min(i + CHUNK_MAX_LINES - 1, len(lines) - 1),
            }
        )
    return chunks
