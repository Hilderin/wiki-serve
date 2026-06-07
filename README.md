# wiki-serve

Local wiki search service with MCP over HTTP/SSE and a web UI. Indexes markdown files from multiple paths, serves them via MCP tools for AI agents (OpenCode) and a searchable web interface.

## Features

- **MCP over SSE** — AI agents (OpenCode) connect via HTTP SSE, no stdio subprocess
- **Persistent daemon** — survives OpenCode restarts, single instance across projects
- **Multi-path indexing** — index any number of files and directories via `WIKI_INCLUDE`
- **Web UI** — search, browse sections, open files in VS Code directly from your browser
- **FTS5 full-text search** — fast, ranked results with BM25 scoring and heading boost
- **Hybrid vector search** — RRF fusion between FTS5 and embedding-based semantic search (384-dim, `all-MiniLM-L6-v2`)
- **File watching** — automatic reindex on file changes (via watchdog)
- **Backward compatible** — stdio MCP server still available

## Quick start

```bash
uv sync
WIKI_INCLUDE="./wiki" uv run wiki-serve serve
```

Open **http://127.0.0.1:8765** in your browser.

## Web UI

The web interface is available at **http://localhost:8765** (or the port you configure).

### Search

Type a query in the search bar and press Enter. Results show:

- **File path** — click to open the file at the exact line in VS Code
- **Heading path** — hierarchical section location (e.g. `Architecture > Overview > System Diagram`)
- **Score** — relevance score (0–1)
- **Excerpt** — surrounding context with the match highlighted
- **View section** — click to see the full section content

### Section viewer

Click "View section" on any result to see the full content of that section, including VS Code links and line ranges.

### Status page

Visit `/status` to see:
- Document and chunk counts
- Currently indexed paths
- Database and log file locations
- Last indexed timestamp
- Reindex button

---

## Indexing multiple paths

`WIKI_INCLUDE` accepts a colon-separated (`:`) list of file and directory paths.

### Examples

```bash
# Multiple directories
WIKI_INCLUDE="./wiki:./docs:./adr"

# Directory + single file
WIKI_INCLUDE="./docs:/home/user/project/README.md"

# Absolute paths
WIKI_INCLUDE="/home/user/project-a/docs:/home/user/project-b/docs"

# Single file only
WIKI_INCLUDE="/home/user/project/CONTRIBUTING.md"

# Mix of files and directories from different projects
WIKI_INCLUDE="/project-a/docs:/project-a/CHANGELOG.md:/project-b/README.md"
```

### How it works

- **Directory** → scanned recursively for all `*.md` files
- **File** → indexed directly (must have `.md` extension)
- **Non-existent paths** → silently skipped
- **All paths are resolved** to absolute paths at startup

---

## Usage

### CLI

```bash
wiki-serve serve              # HTTP server (foreground)
wiki-serve daemon start       # HTTP server (background daemon)
wiki-serve daemon stop        # Stop the daemon
wiki-serve daemon status      # Check if running
wiki-serve bridge             # Stdio↔SSE bridge (auto-starts daemon)
wiki-serve stdio              # Legacy stdio MCP server
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WIKI_INCLUDE` | `./wiki` | Colon-separated paths (files + dirs) to index |
| `WIKI_DATA_DIR` | `./.wiki-index` | Root directory for data files (database, logs, PID) |
| `WIKI_HOST` | `127.0.0.1` | HTTP bind address |
| `WIKI_PORT` | `8765` | HTTP port |
| `WIKI_WATCH` | `true` | Enable file watching |
| `WIKI_REINDEX_ON_START` | `true` | Reindex on startup |
| `WIKI_EMBEDDING_ENABLED` | `true` | Enable vector search (requires model download on first run) |
| `WIKI_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model name |
| `WIKI_EMBEDDING_DEVICE` | `cpu` | Device for embedding model (`cpu` or `cuda`) |

---

## OpenCode integration

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "wiki-serve": {
      "type": "local",
      "command": ["uv", "run", "wiki-serve", "bridge"],
      "enabled": true,
      "environment": {
        "WIKI_INCLUDE": "./wiki",
        "WIKI_PORT": "8765"
      }
    }
  }
}
```

The bridge auto-starts a persistent daemon if not running. If a daemon is already running on the same port with **different** include paths, the bridge refuses to connect and shows an error — preventing accidental index contamination.

### Multiple projects

Each project gets its own daemon on a different port:

```json
// Project A — opencode.json
{ "WIKI_PORT": "8765", "WIKI_INCLUDE": "/project-a/docs" }

// Project B — opencode.json
{ "WIKI_PORT": "8766", "WIKI_INCLUDE": "/project-b/docs" }
```

---

## Architecture

```
opencode ──HTTP/SSE──► wiki-serve daemon (:8765)
                            ├── MCP tools (search, read_section, …)
                            ├── Web UI (search, section viewer)
                            └── REST API (/api/search, /api/status, …)

browser ──► http://localhost:8765
```

## Search

### Hybrid vector search

When `WIKI_EMBEDDING_ENABLED=true` (default), `search` combines:
- **FTS5 (BM25)** — keyword/lexical matching
- **Vector search** — semantic similarity via `all-MiniLM-L6-v2` embeddings, stored in SQLite via `sqlite-vec`

Results are fused using **Reciprocal Rank Fusion (RRF)**. On first run, the embedding model (~80MB) is downloaded automatically from Hugging Face.

Set `WIKI_EMBEDDING_ENABLED=false` to fall back to pure FTS5 (no model download, no GPU memory).

### Exact search

`search_exact` uses pure FTS5 — useful for specific terms, identifiers, class names, or file paths.

## MCP tools

| Tool | Description |
|------|-------------|
| `search` | Hybrid (FTS5 + vector) search for fuzzy/conceptual queries |
| `search_exact` | Exact lexical search for specific terms, IDs, file names |
| `read_section` | Read a full section by heading path |

## Development

```bash
uv sync
uv run pytest -v
```

## License

MIT

---

*Built with curiosity, Python and a lot of AI.*
