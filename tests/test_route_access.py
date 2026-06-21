from __future__ import annotations

from types import SimpleNamespace

import pytest

from miniapp.app import decorate_route_payload, has_route_access


def make_user(access_level: str = "basic") -> SimpleNamespace:
    return SimpleNamespace(access_level=access_level)


def test_basic_user_gets_first_three_route_days_for_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("miniapp.app.FREE_MODE", False)
    route = {
        "current_day": 3,
        "completed": 1,
        "percent": 7,
        "days": [
            {"day": 1, "task": {"name": "Day 1"}, "status": "done"},
            {"day": 2, "task": {"name": "Day 2"}, "status": "future"},
            {"day": 3, "task": {"name": "Day 3"}, "status": "today"},
            {"day": 4, "task": {"name": "Day 4"}, "status": "future"},
        ],
    }

    payload = decorate_route_payload(route, make_user(), {"day": 3, "task": {"name": "Day 3"}})

    assert payload["free_days"] == 3
    assert payload["current_task_locked"] is False
    assert [day["locked"] for day in payload["days"]] == [False, False, False, True]
    assert has_route_access(make_user(), 3) is True
    assert has_route_access(make_user(), 4) is False


def test_premium_user_gets_full_route_access() -> None:
    payload = decorate_route_payload(
        {
            "current_day": 8,
            "completed": 4,
            "percent": 29,
            "days": [{"day": 8, "task": {"name": "Day 8"}, "status": "today"}],
        },
        make_user("premium"),
        {"day": 8, "task": {"name": "Day 8"}},
    )

    assert payload["has_full_access"] is True
    assert payload["current_task_locked"] is False
    assert payload["days"][0]["locked"] is False
    assert has_route_access(make_user("premium"), 14) is True

