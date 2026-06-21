#!/usr/bin/env python3
"""Import DeepSeek userToken into the local free-api proxy (VDS or localhost).

Follows the browser-login flow from .env.local.example:
1. Log in at https://chat.deepseek.com
2. DevTools → Application → Local Storage → userToken → copy "value"
3. Run this script with DEEPSEEK_USER_TOKEN or --token
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DS_HEADERS = {
    "content-type": "application/json",
    "origin": "https://chat.deepseek.com",
    "referer": "https://chat.deepseek.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "x-client-version": "2.0.2",
    "x-client-platform": "web",
}


def http_json(method: str, url: str, headers: dict[str, str], body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail[:400]}") from exc
    return json.loads(raw) if raw else {}


def create_chat_session(token: str) -> str:
    headers = {**DS_HEADERS, "authorization": f"Bearer {token}"}
    payload = http_json(
        "POST",
        "https://chat.deepseek.com/api/v0/chat_session/create",
        headers,
        {},
    )
    biz = payload.get("data", {}).get("biz_data", {}) or payload.get("data", {})
    session_id = biz.get("chat_session", {}).get("id", "") or biz.get("id", "")
    if not session_id:
        raise RuntimeError(f"Could not create chat session: {json.dumps(payload, ensure_ascii=False)[:400]}")
    return session_id


def build_import_curl(token: str, session_id: str) -> str:
    return (
        "curl 'https://chat.deepseek.com/api/v0/chat/completion' "
        f"-H 'authorization: Bearer {token}' "
        "-H 'content-type: application/json' "
        "-H 'origin: https://chat.deepseek.com' "
        f"-H 'referer: https://chat.deepseek.com/a/chat/s/{session_id}' "
        "-H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36' "
        "-H 'x-client-version: 2.0.2' "
        "-H 'x-client-platform: web' "
        f"-d '{{\"session_id\":\"{session_id}\"}}'"
    )


def import_to_proxy(proxy_base: str, token: str, session_id: str) -> dict:
    curl = build_import_curl(token, session_id)
    payload = json.dumps({"curl": curl}).encode("utf-8")
    request = urllib.request.Request(
        f"{proxy_base.rstrip('/')}/api/config",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Proxy import failed HTTP {exc.code}: {detail[:400]}") from exc


def verify_proxy(proxy_base: str) -> None:
    request = urllib.request.Request(f"{proxy_base.rstrip('/')}/health", method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not data.get("configured"):
        raise RuntimeError("Proxy health OK but no account configured.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import DeepSeek userToken into free-api proxy")
    parser.add_argument("--token", default=os.getenv("DEEPSEEK_USER_TOKEN", "").strip())
    parser.add_argument("--proxy", default=os.getenv("DEEPSEEK_PROXY_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()

    token = args.token.strip().removeprefix("Bearer ").strip()
    if not token:
        print(
            "Set DEEPSEEK_USER_TOKEN or pass --token.\n"
            "Get it: chat.deepseek.com → F12 → Application → Local Storage → userToken → value",
            file=sys.stderr,
        )
        return 1

    print("Creating DeepSeek chat session from browser token...")
    session_id = create_chat_session(token)
    print(f"Session: {session_id}")

    print(f"Importing into proxy at {args.proxy} ...")
    result = import_to_proxy(args.proxy, token, session_id)
    if not result.get("ok"):
        print(f"Import failed: {result}", file=sys.stderr)
        return 1

    masked = result.get("masked", "***")
    print(f"Imported account {result.get('account_label', '?')} token {masked}")

    time.sleep(1)
    verify_proxy(args.proxy)
    print("Proxy OK — /v1/models reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
