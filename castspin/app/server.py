"""Initial CastSpin Home Assistant Ingress shell.

This intentionally does not claim to implement the Cast receiver or Sendspin
transport yet. It is a working setup/status surface for iterative development.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

PORT = int(os.environ.get("CASTSPIN_PORT", "8099"))
CONFIG = Path(os.environ.get("CASTSPIN_CONFIG", "/data/mappings.json"))


def read_mappings():
    try:
        value = json.loads(CONFIG.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (FileNotFoundError, ValueError, OSError):
        return []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/health", "/healthz"):
            self.respond(200, '{"status":"ok","cast_receiver":"not_implemented","sendspin":"not_implemented"}', "application/json")
            return
        if path == "/api/mappings":
            self.respond(200, json.dumps({"mappings": read_mappings(), "operational": False}), "application/json")
            return
        if path not in ("/", "/index.html"):
            self.respond(404, "Not found", "text/plain")
            return
        rows = "".join(
            "<li><strong>" + escape(str(item.get("name", "Unnamed"))) + "</strong> → " +
            escape(str(item.get("sendspin_id", "unassigned"))) + "</li>"
            for item in read_mappings() if isinstance(item, dict)
        )
        body = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>CastSpin</title><style>body{font:16px system-ui,sans-serif;max-width:740px;margin:3rem auto;padding:0 1.5rem;color:#ddd;background:#111827}
        h1{font-size:2rem}section{padding:1.4rem;background:#1f2937;border-radius:12px;margin:1rem 0}
        small{color:#a5b4fc}code{color:#93c5fd}</style></head><body>
        <h1>CastSpin</h1><small>Home Assistant App · foundation preview</small>
        <section><h2>Gateway status</h2><p>App started successfully.</p>
        <p>Google Cast receiver: <strong>Not yet implemented</strong></p>
        <p>Sendspin server: <strong>Not yet implemented</strong></p>
        <p>No audio playback is available in this release.</p></section>
        <section><h2>Planned mappings</h2><ul>""" + (rows or "<li>No mappings configured</li>") + """</ul>
        <p>Mapping configuration and discovery UI are planned.</p></section></body></html>"""
        self.respond(200, body, "text/html; charset=utf-8")

    def respond(self, status, body, content_type):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
