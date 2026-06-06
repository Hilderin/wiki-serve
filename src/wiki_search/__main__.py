import sys
import asyncio


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: wiki-serve <serve|stdio|bridge|daemon> [args...]")
        print()
        print("Commands:")
        print("  serve              Start HTTP server (foreground)")
        print("  stdio              Start stdio MCP server (for backward compat)")
        print("  bridge             Start MCP bridge (stdio↔SSE, auto-starts daemon)")
        print("  daemon <cmd>       Manage daemon: start|stop|restart|status")
        sys.exit(1)

    cmd = sys.argv[1]
    sys.argv = [sys.argv[0]] + sys.argv[2:]

    if cmd == "serve":
        from .http_server import run
        run()
    elif cmd == "stdio":
        from .server import main_stdio
        asyncio.run(main_stdio())
    elif cmd == "bridge":
        from .bridge import main as bridge_main
        bridge_main()
    elif cmd == "daemon":
        from . import daemon
        daemon.main()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
