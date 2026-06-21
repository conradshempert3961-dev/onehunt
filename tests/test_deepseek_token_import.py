from __future__ import annotations

import json
from unittest import mock

import pytest

from scripts import deepseek_token_import as importer


def test_build_import_curl_contains_token_and_session() -> None:
    curl = importer.build_import_curl("abc-token", "11111111-2222-3333-4444-555555555555")
    assert "abc-token" in curl
    assert "11111111-2222-3333-4444-555555555555" in curl
    assert "authorization: Bearer" in curl


def test_create_chat_session_parses_response() -> None:
    payload = {
        "data": {
            "biz_data": {
                "chat_session": {"id": "11111111-2222-3333-4444-555555555555"},
            }
        }
    }

    with mock.patch.object(importer, "http_json", return_value=payload):
        session_id = importer.create_chat_session("token")

    assert session_id == "11111111-2222-3333-4444-555555555555"


def test_import_to_proxy_posts_curl(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"ok": True, "masked": "abc...xyz"}).encode()

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["body"] = request.data.decode()
        return FakeResponse()

    monkeypatch.setattr(importer.urllib.request, "urlopen", fake_urlopen)
    result = importer.import_to_proxy("http://127.0.0.1:8000", "token", "sess-id")
    assert result["ok"] is True
    assert captured["url"].endswith("/api/config")
    assert "token" in captured["body"]
