"""Command-line access and client configuration for the paper reader."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from .core import PaperStore
from .sources import PaperError


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read papers with verified, clickable PDF citations.")
    root.add_argument("--data-dir", help="PDF and citation storage (or PAPER_READER_DATA_DIR)")
    root.add_argument("--port", type=int, default=int(os.environ.get("PAPER_READER_PORT", "8765")))
    commands = root.add_subparsers(dest="command", required=True)
    imp = commands.add_parser("import", help="Import a local PDF or a paper URL")
    imp.add_argument("source")
    imp.add_argument("--title")
    imp.add_argument("--refresh", action="store_true")
    commands.add_parser("list", help="List imported papers")
    for name in ("info", "read", "search", "cite", "page"):
        command = commands.add_parser(name)
        command.add_argument("--paper", required=True, help="paper_id returned by import")
        if name in ("read", "page"):
            command.add_argument("--page", type=int, required=name == "page")
        if name == "read":
            command.add_argument("--start", type=int, default=0)
            command.add_argument("--limit", type=int, default=12)
        if name == "search":
            command.add_argument("--query", required=True)
            command.add_argument("--limit", type=int, default=5)
        if name == "cite":
            command.add_argument("--quote", required=True)
            command.add_argument("--passage", action="append", required=True, help="Repeat for adjacent passages")
            command.add_argument("--occurrence", type=int)
        if name == "page":
            command.add_argument("--output", required=True)
    commands.add_parser("serve", help="Keep the local PDF reader running")
    commands.add_parser("mcp", help="Start MCP stdio tools and the local reader")
    config = commands.add_parser("config", help="Print MCP client configuration; does not change client settings")
    config.add_argument("--client", choices=("claude-desktop", "codex"), required=True)
    return root


def main():
    args = parser().parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Choose a port between 1 and 65535.")
    try:
        store = PaperStore(args.data_dir, args.port)
        if args.command == "import":
            result = store.import_paper(args.source, args.title, args.refresh)
        elif args.command == "list":
            result = store.list_papers()
        elif args.command == "info":
            result = store.metadata(args.paper)
        elif args.command == "read":
            result = store.read_passages(args.paper, args.page, args.start, args.limit)
        elif args.command == "search":
            result = store.search(args.paper, args.query, args.limit)
        elif args.command == "cite":
            result = store.make_citation(args.paper, args.quote, args.passage, args.occurrence)
        elif args.command == "page":
            output = Path(args.output).expanduser()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(store.page_png(args.paper, args.page))
            result = {"output": str(output.resolve())}
        elif args.command == "config":
            command = [sys.executable, "-m", "paper_reader", "--data-dir", str(store.root), "--port", str(store.port), "mcp"]
            if args.client == "codex":
                print(shlex.join(["codex", "mcp", "add", "paper-reader", "--", *command]))
                return
            result = {"mcpServers": {"paper-reader": {"command": command[0], "args": command[1:]}}}
        elif args.command == "serve":
            from .server import reader_server
            with reader_server(store) as server:
                print(f"Local paper reader listening on 127.0.0.1:{store.port}. Open a reader_url or citation URL from a tool result.", file=sys.stderr)
                server.serve_forever()
            return
        else:
            from .mcp_server import run_mcp
            run_mcp(store)
            return
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        return
    except (PaperError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
