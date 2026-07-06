#!/usr/bin/env python3
"""Minimal Groq API reverse proxy for datacenter IP bypass."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

GROQ_ORIGIN = "https://api.groq.com"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 18765


class GroqProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_POST(self) -> None:
        auth = self.headers.get("Authorization", "")
        if not auth:
            self._json_response(401, {"error": {"message": "Authorization required"}})
            return

        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else b""
        path = self.path if self.path.startswith("/openai/") else f"/openai/v1{self.path}"
        target = f"{GROQ_ORIGIN}{path}"

        req = Request(
            target,
            data=body,
            method="POST",
            headers={
                "Authorization": auth,
                "Content-Type": self.headers.get("Content-Type", "application/json"),
                "Accept": "application/json",
                "User-Agent": "ONEHUNT-Groq-Proxy/1.0",
            },
        )

        try:
            with urlopen(req, timeout=90) as upstream:
                payload = upstream.read()
                status = upstream.status
                content_type = upstream.headers.get("Content-Type", "application/json")
        except HTTPError as exc:
            payload = exc.read()
            status = exc.code
            content_type = exc.headers.get("Content-Type", "application/json")
        except URLError as exc:
            self._json_response(502, {"error": {"message": f"Upstream error: {exc.reason}"}})
            return

        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), GroqProxyHandler)
    print(f"Groq proxy listening on http://{LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
