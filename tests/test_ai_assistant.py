from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from services import ai_assistant


def make_user() -> SimpleNamespace:
    return SimpleNamespace(
        telegram_id=42,
        questions_completed=120,
        accuracy=78,
        best_exam_score=65,
        streak_days=3,
        xp_total=1500,
        coins=40,
        daily_reminder=True,
        reminder_hour=9,
        settings={"questions_per_session": 20, "timer_seconds": 0, "show_explanations": True},
    )


def make_context(user: SimpleNamespace | None = None) -> dict:
    user = user or make_user()
    blocks = ai_assistant.build_ai_block_snapshot({"block1": 80, "block2": 55, "block3": 70})
    weakest = min(blocks, key=lambda item: item["percent"])
    strongest = max(blocks, key=lambda item: item["percent"])
    return {
        "journal": {"block1": 80, "block2": 55, "block3": 70, "weak_topics": ["Оружие"]},
        "route": {"current_day": 2},
        "route_task": {
            "task": {"icon": "🎯", "name": "Тренировка", "goal": "15 вопросов"},
        },
        "today": {"answers_today": 5, "daily_answered": False, "mistakes_fixed_today": 1},
        "achievements": 4,
        "starred": 2,
        "blocks": blocks,
        "weakest": weakest,
        "strongest": strongest,
        "weak_topics": ["Оружие"],
        "weak_topics_line": "Оружие",
        "settings": dict(user.settings),
        "route_line": "Сегодня в маршруте день 2: 🎯 Тренировка — 15 вопросов.",
        "today_line": "Сегодня дано 5 ответов, вопрос дня ещё открыт, исправлено ошибок 1.",
        "user": user,
    }


def test_ai_assistant_meta_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "")
    meta = ai_assistant.ai_assistant_meta()
    assert meta["configured"] is False
    assert meta["provider"] == "rules"
    assert meta["model"] is None


def test_ai_assistant_meta_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_assistant, "OPENAI_API_BASE", "https://api.openai.com/v1")
    monkeypatch.setattr(ai_assistant, "OPENAI_MODEL", "gpt-4o-mini")
    meta = ai_assistant.ai_assistant_meta()
    assert meta["configured"] is True
    assert meta["provider"] == "openai_compatible"
    assert meta["model"] == "gpt-4o-mini"


def test_ai_assistant_meta_detects_deepseek_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "sk-dummy")
    monkeypatch.setattr(ai_assistant, "OPENAI_API_BASE", "http://127.0.0.1:18632/v1")
    monkeypatch.setattr(ai_assistant, "OPENAI_MODEL", "deepseek-chat")
    meta = ai_assistant.ai_assistant_meta()
    assert meta["provider"] == "deepseek"
    assert meta["endpoint"] == "http://127.0.0.1:18632/v1"


def test_build_rule_based_reply_mentions_exam() -> None:
    result = ai_assistant.build_rule_based_reply("Готов ли я к экзамену?", make_context())
    assert "экзамен" in result["reply"].lower()
    assert result["source"] == "rules"
    assert len(result["quick_replies"]) == 3


def test_normalize_history_filters_invalid_items() -> None:
    history = ai_assistant._normalize_history(
        [
            {"role": "user", "text": "Привет"},
            {"role": "assistant", "text": "Ответ"},
            {"role": "system", "text": "skip"},
            {"role": "user", "text": ""},
        ]
    )
    assert history == [
        {"role": "user", "text": "Привет"},
        {"role": "assistant", "text": "Ответ"},
    ]


def test_generate_ai_reply_uses_rules_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "")

    async def fake_gather(_user):
        return make_context()

    monkeypatch.setattr(ai_assistant, "gather_user_context", fake_gather)

    result = asyncio.run(ai_assistant.generate_ai_reply("Что делать сегодня?", make_user()))
    assert result["provider"] == "rules"
    assert "план" in result["reply"].lower()


def test_generate_ai_reply_uses_llm_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(ai_assistant, "OPENAI_MODEL", "gpt-4o-mini")

    async def fake_gather(_user):
        return make_context()

    async def fake_call(_messages):
        return "Сфокусируйтесь на блоке «Оружие и безопасность» и сделайте 15 вопросов."

    monkeypatch.setattr(ai_assistant, "gather_user_context", fake_gather)
    monkeypatch.setattr(ai_assistant, "_call_openai_chat", fake_call)

    result = asyncio.run(ai_assistant.generate_ai_reply("Что подтянуть первым?", make_user()))
    assert result["provider"] == "openai_compatible"
    assert result["source"] == "llm"
    assert "Оружие" in result["reply"]


def test_generate_ai_reply_falls_back_when_llm_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai_assistant, "OPENAI_API_KEY", "test-key")

    async def fake_gather(_user):
        return make_context()

    async def failing_call(_messages):
        raise ai_assistant.AIAssistantError("upstream error")

    monkeypatch.setattr(ai_assistant, "gather_user_context", fake_gather)
    monkeypatch.setattr(ai_assistant, "_call_openai_chat", failing_call)

    result = asyncio.run(ai_assistant.generate_ai_reply("Как готовиться к экзамену?", make_user()))
    assert result["provider"] == "rules"
    assert result.get("fallback") is True
    assert "экзамен" in result["reply"].lower()
