#!/usr/bin/env python3
"""Forward Telegram Bot API requests (for VDS blocked from api.telegram.org)."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TELEGRAM_ORIGIN = "https://api.telegram.org"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 18766


class TelegramProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length) if length else None
        target = f"{TELEGRAM_ORIGIN}{self.path}"

        headers = {
            "Accept": "application/json",
            "User-Agent": "ONEHUNT-Telegram-Proxy/1.0",
        }
        content_type = self.headers.get("Content-Type")
        if content_type:
            headers["Content-Type"] = content_type

        req = Request(target, data=body, method=self.command, headers=headers)

        try:
            with urlopen(req, timeout=90) as upstream:
                payload = upstream.read()
                status = upstream.status
                resp_type = upstream.headers.get("Content-Type", "application/json")
        except HTTPError as exc:
            payload = exc.read()
            status = exc.code
            resp_type = exc.headers.get("Content-Type", "application/json")
        except URLError as exc:
            self._json_response(502, {"ok": False, "description": f"Upstream error: {exc.reason}"})
            return

        self.send_response(status)
        self.send_header("Content-Type", resp_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _json_response(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), TelegramProxyHandler)
    print(f"Telegram API proxy on http://{LISTEN_HOST}:{LISTEN_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
