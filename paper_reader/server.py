"""Loopback-only HTTP reader for locally cached PDF snapshots and citations."""

from __future__ import annotations

import hmac
import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core import PaperStore
from .sources import PaperError

WEB_DIR = Path(__file__).with_name("web")


def reader_server(store: PaperStore) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            # Stdio belongs to MCP; do not log capability-bearing URLs either.
            pass

        def reply(self, status: int, body: bytes, content_type: str, *, cache=False, attachment=False):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "private, max-age=3600" if cache else "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            if attachment:
                self.send_header("Content-Disposition", 'attachment; filename="paper.pdf"')
            self.end_headers()
            self.wfile.write(body)

        def json_reply(self, status, data):
            self.reply(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            parts = parsed.path.strip("/").split("/")
            if len(parts) < 3 or parts[0] != "r" or not parts[1].isascii() or not hmac.compare_digest(parts[1], store.token):
                self.json_reply(404, {"error": "Use the reader URL returned by a paper-reading tool."})
                return
            # Prevent a hostile page from reading this service through DNS rebinding.
            if self.headers.get("Host") not in (f"127.0.0.1:{store.port}", f"localhost:{store.port}"):
                self.json_reply(403, {"error": "Invalid reader host."})
                return
            route = parts[2:]
            query = urllib.parse.parse_qs(parsed.query)
            try:
                if route == ["health"]:
                    self.json_reply(200, {"service": "paper-critical-reading", "schema_version": 1})
                elif len(route) == 2 and route[0] == "assets" and route[1] in ("reader.js", "reader.css"):
                    content_type = "text/javascript" if route[1].endswith(".js") else "text/css"
                    self.reply(200, (WEB_DIR / route[1]).read_bytes(), content_type + "; charset=utf-8", cache=True)
                elif len(route) == 2 and route[0] == "paper":
                    store.metadata(route[1])
                    self.reply(200, (WEB_DIR / "reader.html").read_bytes(), "text/html; charset=utf-8")
                elif len(route) >= 3 and route[:2] == ["api", "papers"]:
                    paper_id = route[2]
                    if len(route) == 3:
                        self.json_reply(200, store.metadata(paper_id))
                    elif route[3:] == ["source.pdf"]:
                        self.reply(200, (store.paper_dir(paper_id) / "source.pdf").read_bytes(), "application/pdf", attachment=True)
                    elif len(route) == 5 and route[3] == "citations":
                        self.json_reply(200, store.citation(paper_id, route[4]))
                    elif len(route) == 5 and route[3] == "passages":
                        self.json_reply(200, store.passage_target(paper_id, route[4]))
                    elif len(route) == 5 and route[3] == "pages" and route[4].endswith(".png"):
                        number = int(route[4][:-4])
                        scale = float(query.get("scale", ["1.5"])[0])
                        self.reply(200, store.page_png(paper_id, number, scale), "image/png", cache=True)
                    else:
                        self.json_reply(404, {"error": "Unknown reader route."})
                else:
                    self.json_reply(404, {"error": "Unknown reader route."})
            except (PaperError, ValueError, FileNotFoundError) as exc:
                self.json_reply(400, {"error": str(exc)})
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", store.port), Handler)
    server.daemon_threads = True
    store.port = server.server_port
    return server


def start_reader(store: PaperStore) -> ThreadingHTTPServer | None:
    try:
        server = reader_server(store)
    except OSError as exc:
        # A standalone reader or another MCP client may already serve the same store.
        try:
            with urllib.request.urlopen(store.base_url + "/health", timeout=2) as response:
                data = json.load(response)
            if data.get("service") == "paper-critical-reading":
                return None
        except Exception:
            pass
        raise PaperError(f"Reader port {store.port} is unavailable. Choose another --port or stop the conflicting service.") from exc
    threading.Thread(target=server.serve_forever, daemon=True, name="paper-reader-http").start()
    return server
