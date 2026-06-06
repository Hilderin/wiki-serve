# Agents

## Overview

The wiki-search service provides tools for AI agents to search and read project documentation.

## Recommended Usage

- Use `wiki_search` for conceptual or fuzzy questions about the project
- Use `wiki_search_exact` when you know specific terms, file names, or class names
- Always cite the file path, heading path, and line range when referencing search results
- If a search result excerpt is insufficient, use `wiki_read_section` to get the full section content
- Before modifying specifications or ADRs, search the wiki first

## Development

To add a new MCP tool:

1. Create a new module in `src/wiki_search/mcp_tools/`
2. Define the Tool schema and handler function
3. Register it in both `server.py` and `http_server.py`
