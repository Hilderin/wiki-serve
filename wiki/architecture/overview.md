# Architecture Overview

## System Diagram

```
┌─────────────┐     HTTP/SSE     ┌──────────────────────┐
│   opencode   │────────────────►│  wiki-serve (port 8765) │
│  (MCP Client)│◄───────────────│  - MCP Tools (SSE)     │
└─────────────┘                  │  - Web UI (Browser)    │
                                 │  - REST API            │
        ┌────────────────────────┤                        │
        │                        │  SQLite FTS5 Index     │
        ▼                        └──────────────────────┘
┌──────────────┐
│   Browser    │──────► / (Web UI)
│  (User)      │──────► /api/search
└──────────────┘
```

## Service Lifecycle

- **Daemon mode**: Runs persistently, survives opencode restarts
- **Bridge mode**: Used by opencode "local" type, auto-starts daemon if needed
- **Stdio mode**: Backward-compatible direct MCP over stdio
