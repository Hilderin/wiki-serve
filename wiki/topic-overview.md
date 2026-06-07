# Wiki Search

A local full-text search engine for markdown wikis.

## Overview

Wiki Search indexes markdown files using SQLite FTS5 for fast, ranked search results. It supports automatic file watching for real-time index updates.

## Architecture

The system is built with a modular architecture:

### Core Components

- **Indexer** processes markdown files and builds a searchable index
- **Chunker** splits markdown files into sections by headings
- **FTS Engine** provides full-text search with BM25 ranking
- **File Watcher** monitors the wiki directory for changes

### MCP Tools

- `wiki_search` - Hybrid search for fuzzy/conceptual queries
- `wiki_search_exact` - Exact term search
- `wiki_read_section` - Read a full section by heading path
- `wiki_reindex` - Force reindexing
- `wiki_status` - Index health and statistics

### HTTP Service

The service runs as an HTTP daemon on port 8765, providing MCP over SSE and a web UI.

## Data Flow

1. Markdown files are read from the wiki directory
2. Files are split into sections by markdown headings
3. Each section becomes a searchable chunk in SQLite
4. FTS5 indexes enable fast full-text search
5. Results are ranked by BM25 with heading-boost reranking

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| WIKI_ROOT | ./wiki | Path to markdown files |
| WIKI_DATA_DIR | ./.wiki-index | Root directory for data files (DB, logs, PID) |
| WIKI_HOST | 127.0.0.1 | HTTP bind address |
| WIKI_PORT | 8765 | HTTP port |
| WIKI_WATCH | true | Enable file watching |
| WIKI_REINDEX_ON_START | true | Reindex on startup |
