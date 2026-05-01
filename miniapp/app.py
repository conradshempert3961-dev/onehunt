from __future__ import annotations

import random
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import (
    APP_TIMEZONE,
    BLOCK_QUESTIONS,
    CRYPTO_PAY_API_TOKEN,
    EXAM_PASS_PERCENT,
    EXAM_QUESTIONS,
    FREE_MODE,
    MINIAPP_BROWSER_DEMO,
    MINIAPP_BROWSER_DEMO_HOSTS,
    TRAINING_FREE_LIMIT,
    TRAIL_FREE_LIMIT,
)
from database.database import init_db
from services.game import (
    answer_daily_question,
    count_achievements,
    count_starred,
    create_payment,
    finish_exam_attempt,
    get_achievement_overview,
    get_answered_question_ids,
    get_card_details,
    get_cards_by_category,
    get_cards_catalog,
    get_daily_question_answer,
    get_daily_question_question,
    get_due_repetition_questions,
    get_exam_history,
    get_journal_stats,
    get_official_exam_questions,
    get_or_create_daily_challenge,
    get_or_create_user,
    get_progress_chart,
    get_question,
    get_question_count,
    get_question_sequence_for_block,
    get_random_questions,
    get_route_overview,
    get_route_task,
    get_starred_questions,
    get_today_stats,
    get_payment_record,
    get_user,
    get_user_block_progress,
    get_wrong_questions,
    mark_user_seen,
    random_quote,
    record_duel,
    record_user_session,
    reset_user_progress,
    save_answer,
    seed_reference_data,
    complete_payment,
    toggle_star,
    update_payment_status,
    update_user,
)
from services.crypto_pay import (
    CryptoPayError,
    create_premium_invoice,
    get_invoice,
    invoice_checkout_url,
)
from services.telegram_stars import (
    TelegramStarsError,
    create_premium_stars_invoice,
    telegram_stars_configured,
)
from miniapp.auth import MiniAppIdentity, build_dev_identity, validate_init_data
from miniapp.session_store import MiniAppMode, WebQuizSession, create_session, drop_session, get_session
from utils.constants import BLOCKS, DAILY_CHALLENGES, PREMIUM_PRICES, ROUTE_TASKS
from utils.helpers import calculate_accuracy, format_duration, get_rank_by_correct, get_xp_level

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
DEMO_COOKIE_NAME = "onehunt_demo_id"


class SessionStartRequest(BaseModel):
    mode: MiniAppMode
    block_id: int | None = None
    weak: bool = False
    timed: bool = False


class SessionAnswerRequest(BaseModel):
    session_id: str
    question_id: int
    answer: str = Field(min_length=1, max_length=2)


class SessionNextRequest(BaseModel):
    session_id: str


class DailyAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=2)


class StarToggleRequest(BaseModel):
    question_id: int


class SettingsUpdateRequest(BaseModel):
    questions_per_session: int | None = None
    timer_seconds: int | None = None
    show_explanations: bool | None = None
    daily_reminder: bool | None = None
    reminder_hour: int | None = None


class AIChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=400)

app = FastAPI(title="ONEHUNT Mini App", version="1.0.0")
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


@app.on_event("startup")
async def startup_event() -> None:
    await init_db()
    await seed_reference_data()


def has_full_access(user: Any) -> bool:
    return FREE_MODE or bool(user and user.access_level == "premium")


def premium_lock_detail(feature: str) -> str:
    messages = {
        "ai": "AI-ассистент доступен только в PREMIUM.",
        "blitz": "Блиц доступен только в PREMIUM.",
        "cards": "Карточки охотника доступны только в PREMIUM.",
        "duel": "Дуэль с Михалычем доступна только в PREMIUM.",
        "exam": "Экзамен доступен только в PREMIUM.",
        "mistakes": "Разбор ошибок доступен только в PREMIUM.",
        "progress": "График прогресса доступен только в PREMIUM.",
        "repetition": "Интервальное повторение доступно только в PREMIUM.",
        "route": "Маршрут на 14 дней открывается только в PREMIUM.",
        "starred": "Избранные вопросы доступны только в PREMIUM.",
        "trail_limit": "Бесплатный лимит по тропе уже исчерпан. Откройте PREMIUM, чтобы идти дальше.",
        "training_limit": "Бесплатный лимит тренировок уже исчерпан. Откройте PREMIUM, чтобы продолжить.",
    }
    return messages.get(feature, "Эта функция доступна только в PREMIUM.")


def resolve_local_image(question) -> str | None:
    image_ref = str(getattr(question, "image_url", "") or "").strip()
    if not image_ref:
        return None
    if image_ref.startswith(("http://", "https://")):
        return image_ref
    return f"/api/media/question/{question.id}"


def serialize_question(question, *, reveal_answer: bool = False) -> dict[str, Any]:
    payload = {
        "id": question.id,
        "source_number": question.source_number,
        "block": question.block,
        "block_name": question.block_name,
        "text": question.question_text,
        "options": [
            {"key": key.lower(), "label": key.upper(), "text": value}
            for key, value in sorted(question.options.items())
        ],
        "image_url": resolve_local_image(question),
        "global_accuracy": question.global_accuracy,
        "times_answered": question.times_answered,
    }
    if reveal_answer:
        payload["correct_answer"] = question.correct_answer
    return payload


def serialize_route_task_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    return {
        "day": payload["day"],
        "task": payload["task"],
    }


def serialize_user(user: Any) -> dict[str, Any]:
    rank = get_rank_by_correct(user.correct_answers)
    current_level, level_name = get_xp_level(user.xp_total)
    access_level = user.access_level
    if access_level != "premium" and FREE_MODE:
        access_level = "open_beta"
    return {
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "questions_completed": user.questions_completed,
        "correct_answers": user.correct_answers,
        "wrong_answers": user.wrong_answers,
        "accuracy": user.accuracy,
        "xp_total": user.xp_total,
        "xp_level": current_level,
        "xp_level_name": level_name,
        "coins": user.coins,
        "streak_days": user.streak_days,
        "best_exam_score": user.best_exam_score,
        "access_level": access_level,
        "has_premium": user.access_level == "premium",
        "theme": user.theme,
        "badge": user.badge,
        "daily_reminder": user.daily_reminder,
        "reminder_hour": user.reminder_hour,
        "settings": dict(user.settings or {}),
        "rank": rank,
    }


def serialize_exam_history_item(attempt: Any) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "score_percent": attempt.score_percent,
        "passed": attempt.passed,
        "correct_count": attempt.correct_count,
        "wrong_count": attempt.wrong_count,
        "time_spent_minutes": attempt.time_spent_minutes,
    }


def serialize_achievement(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": item["code"],
        "name": item["name"],
        "description": item["description"],
        "category": item["category"],
        "xp": item["xp"],
        "coins": item["coins"],
        "secret": item["secret"],
        "unlocked": item["unlocked"],
        "current": item["current"],
        "target": item["target"],
        "percent": item["percent"],
    }


def serialize_card(card: Any) -> dict[str, Any]:
    return {
        "id": card.id,
        "name": card.name,
        "latin_name": card.latin_name,
        "category": card.category,
        "family_name": card.family_name,
        "weight": card.weight,
        "habitat": card.habitat,
        "hunting_season": card.hunting_season,
        "track_description": card.track_description,
        "description": getattr(card, "description", None),
    }


def session_time_left(session: WebQuizSession) -> int | None:
    if session.question_timer_seconds is not None:
        elapsed = int((datetime.utcnow() - session.question_started_at).total_seconds())
        return max(session.question_timer_seconds - elapsed, 0)
    if session.total_timer_seconds is None:
        return None
    elapsed = int((datetime.utcnow() - session.started_at).total_seconds())
    return max(session.total_timer_seconds - elapsed, 0)


def session_timer_meta(session: WebQuizSession) -> dict[str, Any] | None:
    timer_left = session_time_left(session)
    if timer_left is None:
        return None
    if session.question_timer_seconds is not None:
        return {
            "left_seconds": timer_left,
            "kind": "question",
            "label": "на вопрос",
            "limit_seconds": session.question_timer_seconds,
        }
    return {
        "left_seconds": timer_left,
        "kind": "session",
        "label": "на сессию",
        "limit_seconds": session.total_timer_seconds,
    }


def serialize_session_question(session: WebQuizSession, question: Any) -> dict[str, Any]:
    session.pending_question_id = question.id
    return {
        "session_id": session.session_id,
        "mode": session.mode,
        "title": session.title,
        "progress": {
            "current": session.current + 1,
            "total": len(session.question_ids),
            "correct": session.correct,
            "wrong": session.wrong,
            "timer": session_timer_meta(session),
        },
        "question": serialize_question(question),
    }


def build_result_payload(question: Any, selected_answer: str, outcome: Any, show_explanations: bool) -> dict[str, Any]:
    return {
        "is_correct": outcome.is_correct,
        "selected_answer": selected_answer,
        "selected_text": question.options.get(selected_answer, ""),
        "correct_answer": question.correct_answer,
        "correct_text": question.options.get(question.correct_answer, ""),
        "xp_added": outcome.xp_added,
        "coins_added": outcome.coins_added,
        "answer_streak": outcome.answer_streak,
        "rank_up": outcome.rank_up,
        "mistake_fixed": outcome.mistake_fixed,
        "challenge_completed": outcome.challenge_completed,
        "route_day_completed": outcome.route_day_completed,
        "achievements": outcome.achievements,
        "explanation": question.explanation if show_explanations else None,
        "mnemonic": question.mnemonic if show_explanations else None,
    }


async def finalize_session(session: WebQuizSession, timeout: bool = False) -> dict[str, Any]:
    ended_at = datetime.utcnow()
    await record_user_session(
        user_id=session.user_id,
        mode=session.mode,
        questions_count=len(session.question_ids),
        correct_count=session.correct,
        max_streak=session.max_streak,
        started_at=session.started_at,
        ended_at=ended_at,
    )

    if session.mode == "training":
        user = await get_user(session.user_id)
        if user and not has_full_access(user):
            await update_user(user.telegram_id, free_trainings_used=user.free_trainings_used + 1)

    if session.mode == "exam":
        result = await finish_exam_attempt(
            session.user_id,
            session.answers_detail,
            session.started_at,
            ended_at,
        )
        return {
            "type": "exam",
            "title": session.title,
            "passed": result["passed"],
            "score_percent": result["score_percent"],
            "correct_count": result["correct_count"],
            "wrong_count": result["wrong_count"],
            "questions_count": len(session.question_ids),
            "time_spent_minutes": result["time_spent_minutes"],
            "xp_bonus": result["xp_bonus"],
            "achievements": result["achievements"],
            "pass_threshold": EXAM_PASS_PERCENT,
        }

    if session.mode == "duel":
        base = round(len(session.question_ids) * 0.6)
        bot_score = max(0, min(len(session.question_ids), base + random.randint(-2, 2)))
        result = await record_duel(session.user_id, session.correct, bot_score, session.answers_detail)
        return {
            "type": "duel",
            "title": session.title,
            "user_score": session.correct,
            "bot_score": bot_score,
            "user_won": result["user_won"],
            "achievements": result["achievements"],
            "duration": format_duration(int((ended_at - session.started_at).total_seconds())),
        }

    return {
        "type": "generic",
        "title": session.title,
        "timeout": timeout,
        "correct": session.correct,
        "wrong": session.wrong,
        "accuracy": calculate_accuracy(session.correct, max(len(session.answers_detail), 1)),
        "duration": format_duration(int((ended_at - session.started_at).total_seconds())),
        "questions_count": len(session.question_ids),
    }


def route_task_to_session_params(task_callback: str) -> dict[str, Any] | None:
    if task_callback.startswith("trail_block_"):
        return {"mode": "trail", "block_id": int(task_callback.rsplit("_", 1)[-1])}
    if task_callback == "training":
        return {"mode": "training", "weak": False, "timed": False}
    if task_callback == "training_weak":
        return {"mode": "training", "weak": True, "timed": False}
    if task_callback == "training_timed":
        return {"mode": "training", "weak": False, "timed": True}
    if task_callback in {"blitz", "mistakes", "exam"}:
        return {"mode": task_callback}
    return None


def browser_demo_allowed(hostname: str | None) -> bool:
    if not MINIAPP_BROWSER_DEMO:
        return False
    host = (hostname or "").lower()
    return "*" in MINIAPP_BROWSER_DEMO_HOSTS or host in MINIAPP_BROWSER_DEMO_HOSTS


def require_full_access(user: Any, feature: str) -> None:
    if has_full_access(user):
        return
    raise HTTPException(status_code=403, detail=premium_lock_detail(feature))


def build_browser_demo_identity(request: Request, response: Response) -> MiniAppIdentity:
    raw_id = request.cookies.get(DEMO_COOKIE_NAME, "")
    if raw_id.isdigit():
        telegram_id = int(raw_id)
    else:
        telegram_id = 900_000_000_000 + uuid.uuid4().int % 999_999_999
    response.set_cookie(
        DEMO_COOKIE_NAME,
        str(telegram_id),
        max_age=60 * 60 * 24 * 365,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
    )
    return MiniAppIdentity(
        telegram_id=telegram_id,
        username="browser_user",
        first_name="ONEHUNT",
        last_name="Web",
        is_telegram=False,
    )


async def resolve_identity(
    request: Request,
    response: Response,
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
) -> MiniAppIdentity:
    if x_telegram_init_data:
        identity = validate_init_data(x_telegram_init_data)
        if identity:
            return identity
        raise HTTPException(status_code=401, detail="РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґС‚РІРµСЂРґРёС‚СЊ Telegram WebApp.")

    if request.url.hostname in LOCAL_HOSTS:
        identity = build_dev_identity()
        if identity:
            return identity

    if browser_demo_allowed(request.url.hostname):
        return build_browser_demo_identity(request, response)

    raise HTTPException(status_code=401, detail="Mini App РґРѕСЃС‚СѓРїРµРЅ РёР· Telegram РёР»Рё Р»РѕРєР°Р»СЊРЅРѕ РІ СЂРµР¶РёРјРµ СЂР°Р·СЂР°Р±РѕС‚РєРё.")


async def current_user(identity: MiniAppIdentity = Depends(resolve_identity)):
    user = await get_or_create_user(
        telegram_id=identity.telegram_id,
        username=identity.username,
        first_name=identity.first_name,
        last_name=identity.last_name,
    )
    await mark_user_seen(user.telegram_id)
    return user


async def prepare_session(user: Any, payload: SessionStartRequest) -> WebQuizSession:
    mode = payload.mode
    title = ""
    block_id = payload.block_id
    total_timer_seconds: int | None = None
    question_timer_seconds: int | None = None
    questions: list[Any] = []

    if mode == "trail":
        if not block_id or block_id not in BLOCKS:
            raise HTTPException(status_code=400, detail="Для тропы нужен корректный блок.")
        progress = await get_user_block_progress(user.telegram_id, block_id)
        if not has_full_access(user) and progress >= TRAIL_FREE_LIMIT:
            raise HTTPException(status_code=403, detail=premium_lock_detail("trail_limit"))
        answered_ids = await get_answered_question_ids(user.telegram_id, mode="trail", block_id=block_id)
        sequence = await get_question_sequence_for_block(block_id)
        questions = [item for item in sequence if item.id not in answered_ids] or sequence
        if not has_full_access(user):
            questions = questions[:TRAIL_FREE_LIMIT]
        if not questions:
            raise HTTPException(status_code=400, detail="В этом блоке пока нет вопросов.")
        title = f"{BLOCKS[block_id]['icon']} Тропа: {BLOCKS[block_id]['name']}"
    elif mode == "training":
        if not has_full_access(user) and user.free_trainings_used >= TRAINING_FREE_LIMIT:
            raise HTTPException(status_code=403, detail=premium_lock_detail("training_limit"))
        settings = dict(user.settings or {})
        limit = int(settings.get("questions_per_session", 20))
        weak_block = None
        if payload.weak:
            journal = await get_journal_stats(user.telegram_id)
            weak_block = min(
                {1: journal["block1"], 2: journal["block2"], 3: journal["block3"]},
                key=lambda item: {1: journal["block1"], 2: journal["block2"], 3: journal["block3"]}[item],
            )
        questions = await get_random_questions(limit, block_id=weak_block)
        block_id = weak_block
        title = "🎯 Тренировка — слабые темы" if payload.weak else "🎯 Тренировка"
        if payload.timed:
            question_timer_seconds = 60
            title = "🎯 Тренировка с таймером" if not payload.weak else "🎯 Слабые темы + таймер"
    elif mode == "blitz":
        require_full_access(user, "blitz")
        questions = await get_random_questions(20)
        total_timer_seconds = 300
        title = "⚡ Блиц"
    elif mode == "exam":
        require_full_access(user, "exam")
        questions = await get_official_exam_questions(EXAM_QUESTIONS, shuffle=False)
        total_timer_seconds = EXAM_QUESTIONS * 60
        title = f"📝 Экзамен — все {EXAM_QUESTIONS} вопросов"
    elif mode == "mistakes":
        require_full_access(user, "mistakes")
        questions = await get_wrong_questions(user.telegram_id, BLOCK_QUESTIONS)
        title = "🔄 Промахи"
    elif mode == "starred":
        require_full_access(user, "starred")
        questions = await get_starred_questions(user.telegram_id, BLOCK_QUESTIONS)
        title = "⭐ Избранные вопросы"
    elif mode == "repetition":
        require_full_access(user, "repetition")
        questions = await get_due_repetition_questions(user.telegram_id, BLOCK_QUESTIONS)
        title = "🧠 Повторение"
    elif mode == "duel":
        require_full_access(user, "duel")
        questions = await get_random_questions(10)
        title = "⚔️ Дуэль с Михалычем"
    elif mode == "quick":
        questions = await get_random_questions(1)
        title = "🦆 Быстрый вопрос"

    if not questions:
        mode_errors = {
            "mistakes": "Пока нет ошибок для отдельного разбора. Сначала пройдите несколько вопросов.",
            "starred": "В избранном пока пусто. Добавьте вопросы звездочкой во время практики.",
            "repetition": "На повторение пока нечего выносить. Система накопит материал после обычных сессий.",
            "duel": "Для дуэли пока не удалось собрать набор вопросов. Попробуйте обновить экран.",
        }
        raise HTTPException(status_code=400, detail=mode_errors.get(mode, "Для этого режима пока нет вопросов."))

    return create_session(
        user_id=user.telegram_id,
        mode=mode,
        title=title,
        question_ids=[item.id for item in questions],
        total_timer_seconds=total_timer_seconds,
        question_timer_seconds=question_timer_seconds,
        block_id=block_id,
    )



def build_ai_block_snapshot(journal: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"id": 1, "icon": "📜", "name": "Правовые основы", "percent": journal["block1"]},
        {"id": 2, "icon": "🔫", "name": "Оружие и безопасность", "percent": journal["block2"]},
        {"id": 3, "icon": "🦌", "name": "Биология и практика", "percent": journal["block3"]},
    ]


def normalize_ai_prompt(message: str) -> str:
    return re.sub(r"\s+", " ", message.lower()).strip()


def prompt_has_any(prompt: str, *tokens: str) -> bool:
    return any(token in prompt for token in tokens)


async def build_ai_assistant_reply(message: str, user: Any) -> dict[str, Any]:
    journal = await get_journal_stats(user.telegram_id)
    route = await get_route_overview(user.telegram_id)
    route_task = await get_route_task(user.telegram_id)
    today = await get_today_stats(user.telegram_id)
    achievements = await count_achievements(user.telegram_id)
    starred = await count_starred(user.telegram_id)

    blocks = build_ai_block_snapshot(journal)
    weakest = min(blocks, key=lambda item: item["percent"])
    strongest = max(blocks, key=lambda item: item["percent"])
    weak_topics = journal.get("weak_topics") or []
    settings = dict(user.settings or {})

    route_line = (
        f"Сегодня в маршруте день {route['current_day']}: {route_task['task']['icon']} {route_task['task']['name']} — {route_task['task']['goal']}."
        if route_task
        else "Маршрут пока не активирован, поэтому можно начать с тренировки на 10-20 вопросов и вопроса дня."
    )
    weak_topics_line = ", ".join(weak_topics[:4]) if weak_topics else "пока статистики мало, поэтому стоит сделать 15-20 обычных вопросов"
    today_line = (
        f"Сегодня уже дано {today['answers_today']} ответов, вопрос дня {'уже закрыт' if today['daily_answered'] else 'еще ждет вас'}, исправлено ошибок {today['mistakes_fixed_today']}."
    )

    prompt = normalize_ai_prompt(message)

    if prompt_has_any(prompt, "экзамен", "сдать", "257", "порог", "пройду", "завал"):
        reply = "\n".join(
            [
                f"Лучший результат по экзамену сейчас: {user.best_exam_score}% при проходном пороге {EXAM_PASS_PERCENT}%.",
                f"Сильнее всего у вас идет блок «{strongest['icon']} {strongest['name']}» ({strongest['percent']}%), а первым делом стоит дожать «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
                "Быстрый план: 1) короткая тренировка 15-20 вопросов, 2) отдельный проход по слабому блоку, 3) затем пробный экзамен без пауз.",
                route_line,
            ]
        )
        quick = ["Что подтянуть первым?", "Составь план на сегодня", "Как закрыть слабые темы?"]
    elif prompt_has_any(prompt, "ошиб", "слаб", "тема", "просед", "подтянуть", "исправ"):
        reply = "\n".join(
            [
                f"Сейчас самый слабый блок — «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
                f"Слабые темы по журналу: {weak_topics_line}.",
                "Лучше всего работает короткая серия по слабому блоку, затем один смешанный сет для закрепления и только потом экзаменационный режим.",
                today_line,
            ]
        )
        quick = ["Составь план на сегодня", "Как готовиться к экзамену?", "Что у меня с прогрессом?"]
    elif prompt_has_any(prompt, "сегодня", "план", "маршрут", "дальше", "начать", "что делать"):
        reply = "\n".join(
            [
                "Вот спокойный план на текущий день без перегруза:",
                route_line,
                f"После этого добейте 10-20 вопросов по теме «{weakest['icon']} {weakest['name']}», потому что она даст самый заметный прирост.",
                f"Финиш — вопрос дня и короткий разбор ошибок. {today_line}",
            ]
        )
        quick = ["Какая у меня слабая тема?", "Готов ли я к экзамену?", "Что с напоминаниями?"]
    elif prompt_has_any(prompt, "ранг", "xp", "уров", "прогресс", "монет", "серия", "достижен"):
        reply = "\n".join(
            [
                f"Сейчас у вас {user.questions_completed}/257 по прогрессу, точность {user.accuracy}%, серия {user.streak_days} дн., XP {user.xp_total}, монеты {user.coins}.",
                f"Открыто достижений: {achievements}, в избранном сложных вопросов: {starred}.",
                f"Сильный блок — «{strongest['icon']} {strongest['name']}», а главный резерв роста сейчас в «{weakest['icon']} {weakest['name']}».",
                "Если хотите расти быстрее, держите короткие, но регулярные сессии и не пропускайте разбор ошибок после ответа.",
            ]
        )
        quick = ["Что мне подтянуть первым?", "Составь план на сегодня", "Как выйти на экзамен?"]
    elif prompt_has_any(prompt, "напомин", "настрой", "таймер", "объяснен"):
        reminder_state = "включены" if user.daily_reminder else "выключены"
        timer_seconds = int(settings.get("timer_seconds", 0))
        explanations = "включены" if settings.get("show_explanations", True) else "выключены"
        reply = "\n".join(
            [
                f"Напоминания сейчас {reminder_state}, час — {user.reminder_hour}:00.",
                f"В тренировке стоит {int(settings.get('questions_per_session', 20))} вопросов, таймер — {timer_seconds if timer_seconds else 'выкл'}, объяснения — {explanations}.",
                "Если нужен спокойный режим, держите 10-20 вопросов и объяснения включенными. Если нужна боевая подготовка — включайте таймер и идите короткими сетами.",
            ]
        )
        quick = ["Составь план на сегодня", "Что подтянуть первым?", "Как выйти на экзамен?"]
    elif prompt_has_any(prompt, "карточк", "животн", "след", "биолог", "сезон"):
        reply = "\n".join(
            [
                "Карточки лучше использовать как короткий добор после вопросов, а не вместо них.",
                f"Сильнее всего они помогут в блоке «{weakest['icon']} {weakest['name']}», особенно если там есть пробелы по темам: {weak_topics_line}.",
                "Оптимально: 10-15 вопросов, потом 3-5 карточек по близкой теме и финальный быстрый вопрос для самопроверки.",
            ]
        )
        quick = ["Какая у меня слабая тема?", "Составь план на сегодня", "Как лучше разобрать ошибки?"]
    else:
        reply = "\n".join(
            [
                "Я могу помочь по маршруту, ошибкам, экзамену, карточкам и слабым темам.",
                f"Сейчас главный резерв роста — «{weakest['icon']} {weakest['name']}» ({weakest['percent']}%).",
                route_line,
                today_line,
            ]
        )
        quick = ["Что мне подтянуть первым?", "Как лучше разобрать ошибки?", "Готов ли я к экзамену?"]

    return {"reply": reply, "quick_replies": quick[:3]}
@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/bootstrap")
async def bootstrap(user=Depends(current_user)) -> dict[str, Any]:
    questions_count = await get_question_count()
    journal = await get_journal_stats(user.telegram_id)
    today_stats = await get_today_stats(user.telegram_id)
    achievements = await count_achievements(user.telegram_id)
    starred = await count_starred(user.telegram_id)
    route = await get_route_overview(user.telegram_id)
    route_task = await get_route_task(user.telegram_id)
    daily_answer = await get_daily_question_answer(user.telegram_id)
    daily_question = await get_daily_question_question()
    return {
        "user": serialize_user(user),
        "summary": {
            "questions_count": questions_count,
            "achievements": achievements,
            "starred": starred,
            "quote": random_quote(),
        },
        "journal": {
            "rank": journal["rank"],
            "next_rank": journal["next_rank"],
            "level": journal["level"],
            "level_name": journal["level_name"],
            "next_level": journal["next_level"],
            "block1": journal["block1"],
            "block2": journal["block2"],
            "block3": journal["block3"],
            "weak_topics": journal["weak_topics"],
            "achievements": journal["achievements"],
            "starred": journal["starred"],
        },
        "today": today_stats,
        "route": {
            **route,
            "current_task": serialize_route_task_payload(route_task),
        },
        "daily": {
            "answered": daily_answer is not None,
            "question": serialize_question(daily_question) if daily_question else None,
        },
        "blocks": [
            {"id": block_id, **block}
            for block_id, block in BLOCKS.items()
        ],
        "free_mode": FREE_MODE,
        "premium_offer": {
            "title": "Полный путь до первой охоты",
            "subtitle": "Гайд + 12 чек-листов",
            "price_rub": PREMIUM_PRICES["rub"],
            "price_stars": PREMIUM_PRICES["stars"],
            "crypto_enabled": bool(CRYPTO_PAY_API_TOKEN),
            "stars_enabled": telegram_stars_configured(),
        },
        "exam": {
            "questions": EXAM_QUESTIONS,
            "pass_percent": EXAM_PASS_PERCENT,
        },
        "appearance": {
            "timezone": APP_TIMEZONE,
        },
    }


@app.get("/api/daily")
async def daily_view(user=Depends(current_user)) -> dict[str, Any]:
    question = await get_daily_question_question()
    answer = await get_daily_question_answer(user.telegram_id)
    challenge = await get_or_create_daily_challenge(user.telegram_id)
    challenge_cfg = DAILY_CHALLENGES[challenge.challenge_date.weekday()]
    route = await get_route_overview(user.telegram_id)
    route_task = await get_route_task(user.telegram_id)
    return {
        "question": serialize_question(question) if question else None,
        "answered": answer is not None,
        "challenge": {
            "date": challenge.challenge_date.isoformat(),
            "completed": challenge.completed,
            "attempts": challenge.attempts,
            "config": challenge_cfg,
        },
        "route": {
            **route,
            "current_task": serialize_route_task_payload(route_task),
        },
    }


@app.post("/api/daily/answer")
async def submit_daily_answer(payload: DailyAnswerRequest, user=Depends(current_user)) -> dict[str, Any]:
    result = await answer_daily_question(user.telegram_id, payload.answer.lower())
    question = result["question"]
    return {
        "already_answered": result["already_answered"],
        "question": serialize_question(question, reveal_answer=True),
        "result": {
            "is_correct": result.get("is_correct"),
            "correct_answer": question.correct_answer,
            "correct_text": question.options.get(question.correct_answer, ""),
            "correct_percent": result.get("correct_percent"),
            "most_wrong": result.get("most_wrong"),
            "daily_streak": result.get("daily_streak"),
            "explanation": question.explanation,
        },
    }


@app.get("/api/journal")
async def journal_view(user=Depends(current_user)) -> dict[str, Any]:
    stats = await get_journal_stats(user.telegram_id)
    return {
        "user": serialize_user(stats["user"]),
        "rank": stats["rank"],
        "next_rank": stats["next_rank"],
        "level": stats["level"],
        "level_name": stats["level_name"],
        "next_level": stats["next_level"],
        "achievements": stats["achievements"],
        "starred": stats["starred"],
        "block1": stats["block1"],
        "block2": stats["block2"],
        "block3": stats["block3"],
        "weak_topics": stats["weak_topics"],
    }


@app.get("/api/progress")
async def progress_view(user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "progress")
    return await get_progress_chart(user.telegram_id)


@app.get("/api/history")
async def history_view(user=Depends(current_user)) -> dict[str, Any]:
    attempts = await get_exam_history(user.telegram_id)
    return {"items": [serialize_exam_history_item(item) for item in attempts]}


@app.get("/api/achievements")
async def achievements_view(user=Depends(current_user)) -> dict[str, Any]:
    overview = await get_achievement_overview(user.telegram_id)
    return {
        "unlocked": overview["unlocked"],
        "items": [serialize_achievement(item) for item in overview["items"]],
        "nearest": [serialize_achievement(item) for item in overview["nearest"]],
    }


@app.post("/api/premium/crypto/invoice")
async def premium_crypto_invoice(user=Depends(current_user)) -> dict[str, Any]:
    if user.access_level == "premium":
        return {
            "status": "completed",
            "activated": True,
            "already_premium": True,
            "provider": "crypto_bot",
            "user": serialize_user(user),
        }

    try:
        invoice = await create_premium_invoice(user.telegram_id)
    except CryptoPayError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    invoice_id = str(invoice.get("invoice_id") or "").strip()
    if not invoice_id:
        raise HTTPException(status_code=502, detail="Crypto Bot did not return an invoice id.")

    payment = await create_payment(
        user.telegram_id,
        PREMIUM_PRICES["rub"],
        "RUB",
        "crypto_bot",
        invoice_id,
    )

    return {
        "status": "pending",
        "activated": False,
        "payment_id": payment.id,
        "provider": "crypto_bot",
        "invoice_id": invoice_id,
        "pay_url": invoice_checkout_url(invoice, prefer="miniapp"),
        "bot_invoice_url": invoice.get("bot_invoice_url"),
        "mini_app_invoice_url": invoice.get("mini_app_invoice_url"),
        "price_rub": PREMIUM_PRICES["rub"],
    }


@app.get("/api/premium/crypto/status/{payment_id}")
async def premium_crypto_status(payment_id: int, user=Depends(current_user)) -> dict[str, Any]:
    payment = await get_payment_record(payment_id, user.telegram_id)
    if payment is None or payment.provider != "crypto_bot":
        raise HTTPException(status_code=404, detail="Payment was not found.")

    if payment.status == "completed":
        fresh_user = await get_user(user.telegram_id) or user
        return {
            "status": "completed",
            "activated": True,
            "payment_id": payment.id,
            "provider": "crypto_bot",
            "user": serialize_user(fresh_user),
        }

    try:
        invoice = await get_invoice(int(payment.provider_payment_id or 0))
    except (CryptoPayError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    status = str(invoice.get("status") or payment.status or "pending").lower()
    if status == "paid":
        await complete_payment(str(payment.provider_payment_id))
        fresh_user = await get_user(user.telegram_id) or user
        return {
            "status": "completed",
            "activated": True,
            "payment_id": payment.id,
            "provider": "crypto_bot",
            "user": serialize_user(fresh_user),
        }

    if status == "expired":
        await update_payment_status(payment.id, "expired")
    else:
        await update_payment_status(payment.id, "pending")

    return {
        "status": status,
        "activated": False,
        "payment_id": payment.id,
        "provider": "crypto_bot",
        "pay_url": invoice_checkout_url(invoice, prefer="miniapp"),
        "bot_invoice_url": invoice.get("bot_invoice_url"),
        "mini_app_invoice_url": invoice.get("mini_app_invoice_url"),
    }


@app.post("/api/premium/stars/invoice")
async def premium_stars_invoice(user=Depends(current_user)) -> dict[str, Any]:
    if user.access_level == "premium":
        return {
            "status": "completed",
            "activated": True,
            "already_premium": True,
            "provider": "telegram_stars",
            "user": serialize_user(user),
        }

    try:
        invoice = await create_premium_stars_invoice(user.telegram_id)
    except TelegramStarsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    payment = await create_payment(
        user.telegram_id,
        PREMIUM_PRICES["stars"],
        "XTR",
        "telegram_stars",
        invoice["payload"],
    )

    return {
        "status": "pending",
        "activated": False,
        "payment_id": payment.id,
        "provider": "telegram_stars",
        "invoice_link": invoice["invoice_link"],
        "payload": invoice["payload"],
        "price_stars": PREMIUM_PRICES["stars"],
    }


@app.get("/api/premium/stars/status/{payment_id}")
async def premium_stars_status(payment_id: int, user=Depends(current_user)) -> dict[str, Any]:
    payment = await get_payment_record(payment_id, user.telegram_id)
    if payment is None or payment.provider != "telegram_stars":
        raise HTTPException(status_code=404, detail="Payment was not found.")

    if payment.status == "completed":
        fresh_user = await get_user(user.telegram_id) or user
        return {
            "status": "completed",
            "activated": True,
            "payment_id": payment.id,
            "provider": "telegram_stars",
            "user": serialize_user(fresh_user),
        }

    return {
        "status": payment.status or "pending",
        "activated": False,
        "payment_id": payment.id,
        "provider": "telegram_stars",
    }


@app.get("/api/route")
async def route_view(user=Depends(current_user)) -> dict[str, Any]:
    route = await get_route_overview(user.telegram_id)
    route_task = await get_route_task(user.telegram_id)
    return {
        **route,
        "current_task": serialize_route_task_payload(route_task),
    }


@app.post("/api/route/start-task")
async def route_start_task(user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "route")
    payload = await get_route_task(user.telegram_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Текущая задача маршрута не найдена.")
    params = route_task_to_session_params(payload["task"]["callback"])
    if params is None:
        raise HTTPException(status_code=400, detail="Эту задачу пока нельзя открыть в Mini App.")
    session = await prepare_session(
        user,
        SessionStartRequest(
            mode=params["mode"],
            block_id=params.get("block_id"),
            weak=params.get("weak", False),
            timed=params.get("timed", False),
        ),
    )
    question = await get_question(session.question_ids[0])
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден.")
    return serialize_session_question(session, question)


@app.get("/api/cards")
async def cards_catalog(user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "cards")
    return await get_cards_catalog(user.telegram_id)


@app.get("/api/cards/{category}")
async def cards_by_category(category: str, user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "cards")
    cards = await get_cards_by_category(category)
    return {"items": [serialize_card(card) for card in cards]}


@app.get("/api/card/{card_id}")
async def card_details(card_id: int, user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "cards")
    payload = await get_card_details(user.telegram_id, card_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="РљР°СЂС‚РѕС‡РєР° РЅРµ РЅР°Р№РґРµРЅР°.")
    return {
        "card": serialize_card(payload["card"]),
        "question_count": payload["question_count"],
        "correct_count": payload["correct_count"],
        "percent": payload["percent"],
    }


@app.get("/api/settings")
async def settings_view(user=Depends(current_user)) -> dict[str, Any]:
    return {
        "settings": dict(user.settings or {}),
        "daily_reminder": user.daily_reminder,
        "reminder_hour": user.reminder_hour,
        "theme": user.theme,
        "badge": user.badge,
    }


@app.post("/api/settings")
async def settings_update(payload: SettingsUpdateRequest, user=Depends(current_user)) -> dict[str, Any]:
    settings = dict(user.settings or {})
    if payload.questions_per_session is not None:
        settings["questions_per_session"] = max(5, min(int(payload.questions_per_session), 50))
    if payload.timer_seconds is not None:
        settings["timer_seconds"] = max(0, min(int(payload.timer_seconds), 120))
    if payload.show_explanations is not None:
        settings["show_explanations"] = payload.show_explanations

    updated = await update_user(
        user.telegram_id,
        settings=settings,
        daily_reminder=user.daily_reminder if payload.daily_reminder is None else payload.daily_reminder,
        reminder_hour=user.reminder_hour if payload.reminder_hour is None else max(0, min(int(payload.reminder_hour), 23)),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
    return {
        "ok": True,
        "settings": dict(updated.settings or {}),
        "daily_reminder": updated.daily_reminder,
        "reminder_hour": updated.reminder_hour,
    }


@app.post("/api/reset-progress")
async def reset_progress(user=Depends(current_user)) -> dict[str, Any]:
    success = await reset_user_progress(user.telegram_id)
    if not success:
        raise HTTPException(status_code=404, detail="РџСЂРѕС„РёР»СЊ РЅРµ РЅР°Р№РґРµРЅ.")
    return {"ok": True}


@app.post("/api/star/toggle")
async def star_toggle(payload: StarToggleRequest, user=Depends(current_user)) -> dict[str, Any]:
    starred = await toggle_star(user.telegram_id, payload.question_id)
    return {"starred": starred}



@app.post("/api/ai/chat")
async def ai_chat(payload: AIChatRequest, user=Depends(current_user)) -> dict[str, Any]:
    require_full_access(user, "ai")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Введите сообщение для ассистента.")
    return await build_ai_assistant_reply(message, user)
@app.post("/api/session/start")
async def session_start(payload: SessionStartRequest, user=Depends(current_user)) -> dict[str, Any]:
    session = await prepare_session(user, payload)
    question = await get_question(session.question_ids[0])
    if question is None:
        raise HTTPException(status_code=404, detail="Вопрос не найден.")
    return serialize_session_question(session, question)


@app.post("/api/session/answer")
async def session_answer(payload: SessionAnswerRequest, user=Depends(current_user)) -> dict[str, Any]:
    session = get_session(payload.session_id, user.telegram_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия уже завершена или устарела.")
    if session.current >= len(session.question_ids):
        raise HTTPException(status_code=400, detail="Сессия уже завершена.")

    timer_left = session_time_left(session)
    if timer_left is not None and timer_left <= 0:
        summary = await finalize_session(session, timeout=True)
        drop_session(session.session_id)
        return {"status": "finished", "result": None, "next_question": None, "summary": summary}

    expected_question_id = session.question_ids[session.current]
    if expected_question_id != payload.question_id:
        raise HTTPException(status_code=409, detail="Открыт уже другой вопрос. Обновите экран.")

    question = await get_question(payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Р’РѕРїСЂРѕСЃ РЅРµ РЅР°Р№РґРµРЅ.")

    selected_answer = payload.answer.lower()
    time_spent = int((datetime.utcnow() - session.question_started_at).total_seconds())
    outcome = await save_answer(
        user_id=user.telegram_id,
        question_id=question.id,
        selected_answer=selected_answer,
        mode=session.mode,
        time_spent_seconds=time_spent,
    )

    is_correct = selected_answer == question.correct_answer
    session.answers_detail.append(
        {
            "question_id": question.id,
            "block": question.block,
            "selected_answer": selected_answer,
            "correct_answer": question.correct_answer,
            "is_correct": is_correct,
            "time_spent_seconds": time_spent,
        }
    )
    if is_correct:
        session.correct += 1
        session.current_streak += 1
        session.max_streak = max(session.max_streak, session.current_streak)
    else:
        session.wrong += 1
        session.current_streak = 0

    session.current += 1

    result_payload = build_result_payload(
        question,
        selected_answer,
        outcome,
        bool((user.settings or {}).get("show_explanations", True)) and session.mode != "exam",
    )

    if session.current >= len(session.question_ids):
        summary = await finalize_session(session)
        drop_session(session.session_id)
        return {"status": "finished", "result": result_payload, "has_next": False, "summary": summary}

    return {
        "status": "answered",
        "result": result_payload,
        "has_next": True,
        "summary": None,
    }


@app.post("/api/session/next")
async def session_next(payload: SessionNextRequest, user=Depends(current_user)) -> dict[str, Any]:
    session = get_session(payload.session_id, user.telegram_id)
    if session is None:
        raise HTTPException(status_code=404, detail="РЎРµСЃСЃРёСЏ СѓР¶Рµ Р·Р°РІРµСЂС€РµРЅР° РёР»Рё СѓСЃС‚Р°СЂРµР»Р°.")
    if session.current >= len(session.question_ids):
        raise HTTPException(status_code=400, detail="Р’ СЃРµСЃСЃРёРё Р±РѕР»СЊС€Рµ РЅРµС‚ РІРѕРїСЂРѕСЃРѕРІ.")

    question = await get_question(session.question_ids[session.current])
    if question is None:
        raise HTTPException(status_code=404, detail="Р’РѕРїСЂРѕСЃ РЅРµ РЅР°Р№РґРµРЅ.")
    session.question_started_at = datetime.utcnow()
    return serialize_session_question(session, question)


@app.get("/api/media/question/{question_id}")
async def question_media(question_id: int):
    question = await get_question(question_id)
    if question is None or not question.image_url:
        raise HTTPException(status_code=404, detail="РР»Р»СЋСЃС‚СЂР°С†РёСЏ РЅРµ РЅР°Р№РґРµРЅР°.")
    image_ref = str(question.image_url).strip()
    if image_ref.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Р­С‚Рѕ РІРЅРµС€РЅСЏСЏ СЃСЃС‹Р»РєР°, РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РµС‘ РЅР°РїСЂСЏРјСѓСЋ.")

    image_path = Path(image_ref)
    if not image_path.is_absolute():
        image_path = (Path(__file__).resolve().parents[1] / image_ref).resolve()
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Р¤Р°Р№Р» РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РЅРµ РЅР°Р№РґРµРЅ.")
    return FileResponse(image_path)
