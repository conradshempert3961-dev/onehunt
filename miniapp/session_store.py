from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

from config import MINIAPP_SESSION_TTL_MINUTES

MiniAppMode = Literal[
    "trail",
    "training",
    "blitz",
    "exam",
    "mistakes",
    "starred",
    "duel",
    "repetition",
    "quick",
]


@dataclass(slots=True)
class WebQuizSession:
    session_id: str
    user_id: int
    mode: MiniAppMode
    title: str
    question_ids: list[int]
    current: int = 0
    correct: int = 0
    wrong: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    question_started_at: datetime = field(default_factory=datetime.utcnow)
    answers_detail: list[dict[str, Any]] = field(default_factory=list)
    current_streak: int = 0
    max_streak: int = 0
    total_timer_seconds: int | None = None
    block_id: int | None = None
    pending_question_id: int | None = None
    last_touched_at: datetime = field(default_factory=datetime.utcnow)


_sessions: dict[str, WebQuizSession] = {}


def cleanup_sessions() -> None:
    cutoff = datetime.utcnow() - timedelta(minutes=MINIAPP_SESSION_TTL_MINUTES)
    stale = [
        session_id
        for session_id, session in _sessions.items()
        if session.last_touched_at < cutoff
    ]
    for session_id in stale:
        _sessions.pop(session_id, None)


def create_session(
    user_id: int,
    mode: MiniAppMode,
    title: str,
    question_ids: list[int],
    total_timer_seconds: int | None = None,
    block_id: int | None = None,
) -> WebQuizSession:
    cleanup_sessions()
    session = WebQuizSession(
        session_id=uuid4().hex,
        user_id=user_id,
        mode=mode,
        title=title,
        question_ids=question_ids,
        total_timer_seconds=total_timer_seconds,
        block_id=block_id,
    )
    _sessions[session.session_id] = session
    return session


def get_session(session_id: str, user_id: int) -> WebQuizSession | None:
    cleanup_sessions()
    session = _sessions.get(session_id)
    if session is None or session.user_id != user_id:
        return None
    session.last_touched_at = datetime.utcnow()
    return session


def drop_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
