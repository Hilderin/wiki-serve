# ADR-001: Use SQLite for local search index

## Status

Accepted

## Context

We need a local search index for the wiki that is fast, reliable, and requires zero external services or network access.

## Decision

Use SQLite with the FTS5 extension as the search backend.

## Consequences

- **Fast**: FTS5 provides BM25-ranked full-text search with sub-millisecond queries
- **Zero configuration**: No external database server needed
- **Portable**: Single file database, easy to backup and move
- **Limited**: FTS5 is text-only, no vector search (planned for V2)
