from __future__ import annotations

import asyncio
import html
import logging
import os
import random
import socket
import uuid
from aiohttp import ClientSession
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    MenuButtonWebApp,
    PreCheckoutQuery,
    WebAppInfo,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiohttp.hdrs import USER_AGENT
from aiohttp.http import SERVER_SOFTWARE

from aiogram.__meta__ import __version__

from config import (
    ADMIN_IDS,
    ANSWER_BUTTONS_LAYOUT,
    APP_TIMEZONE,
    BLOCK_QUESTIONS,
    BOT_TOKEN,
    EXAM_PASS_PERCENT,
    EXAM_QUESTIONS,
    FREE_MODE,
    MINIAPP_URL,
    TELEGRAM_PROXY,
    PREMIUM_PRICE_RUB,
    PREMIUM_PRICE_STARS,
    TELEGRAM_STARS_PROVIDER_TOKEN,
    TRAINING_FREE_LIMIT,
    TRAIL_FREE_LIMIT,
    USE_REDIS_FSM,
)
from database.database import init_db
from services.game import (
    answer_daily_question,
    apply_promo_code,
    complete_payment,
    count_achievements,
    count_starred,
    create_payment,
    create_promo_code,
    finish_exam_attempt,
    get_active_users,
    get_admin_dashboard,
    get_achievement_overview,
    get_answered_question_ids,
    get_card_details,
    get_cards_by_category,
    get_cards_catalog,
    get_daily_question_answer,
    get_daily_question_question,
    get_exam_history,
    get_official_exam_questions,
    get_journal_stats,
    get_or_create_daily_challenge,
    get_or_create_daily_question,
    get_or_create_user,
    get_progress_chart,
    get_question,
    get_question_count,
    get_question_sequence_for_block,
    get_questions_stats,
    get_random_questions,
    get_route_overview,
    get_route_task,
    get_starred_questions,
    get_due_repetition_questions,
    get_today_stats,
    get_unlocked_achievement_codes,
    get_user,
    get_user_block_progress,
    get_user_card,
    get_wrong_questions,
    grant_premium,
    is_starred,
    list_promo_codes,
    log_broadcast,
    log_reminder,
    mark_user_seen,
    random_quote,
    record_duel,
    record_user_session,
    reset_user_progress,
    revoke_premium,
    save_answer,
    seed_reference_data,
    should_send_reminder,
    toggle_star,
    update_user,
)
from states.states import AppStates
from utils.constants import (
    ACHIEVEMENTS,
    BLOCKS,
    DAILY_CHALLENGES,
    FREE_LIMITS,
    PREMIUM_PRICES,
    QUOTES,
    ROUTE_TASKS,
)
from utils.helpers import (
    calculate_accuracy,
    format_duration,
    format_streak_message,
    get_next_rank_by_correct,
    get_next_xp_level,
    get_rank_by_correct,
    get_xp_level,
    plural_form,
    progress_bar,
    truncate_text,
)

try:
    if USE_REDIS_FSM:
        from aiogram.fsm.storage.redis import RedisStorage
        from redis.asyncio import Redis
    else:
        RedisStorage = None  # type: ignore[assignment]
        Redis = None  # type: ignore[assignment]
except Exception:  # pragma: no cover
    RedisStorage = None  # type: ignore[assignment]
    Redis = None  # type: ignore[assignment]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("onehunt")

bot: Bot | None = None
scheduler: AsyncIOScheduler | None = None


class SystemProxyAiohttpSession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._should_reset_connector:
            await self.close()

        if self._session is None or self._session.closed:
            self._session = ClientSession(
                connector=self._connector_type(**self._connector_init),
                headers={
                    USER_AGENT: f"{SERVER_SOFTWARE} aiogram/{__version__}",
                },
                trust_env=True,
            )
            self._should_reset_connector = False

        return self._session


class IPv4AiohttpSession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._should_reset_connector:
            await self.close()

        if self._session is None or self._session.closed:
            connector_init = dict(self._connector_init)
            connector_init["family"] = socket.AF_INET
            self._session = ClientSession(
                connector=self._connector_type(**connector_init),
                headers={
                    USER_AGENT: f"{SERVER_SOFTWARE} aiogram/{__version__}",
                },
            )
            self._should_reset_connector = False

        return self._session


def build_bot_session() -> AiohttpSession:
    if TELEGRAM_PROXY:
        return IPv4AiohttpSession(proxy=TELEGRAM_PROXY)
    # On Windows we may need system proxy settings; on Linux servers they often
    # cause unnecessary timeouts or proxy resolution issues.
    if os.name == "nt":
        return SystemProxyAiohttpSession()
    return IPv4AiohttpSession()


def build_storage():
    if USE_REDIS_FSM and RedisStorage and Redis:
        from config import REDIS_URL

        return RedisStorage(Redis.from_url(REDIS_URL))
    return MemoryStorage()


dp = Dispatcher(storage=build_storage())

Mode = Literal[
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
class QuizSession:
    mode: Mode
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
    media_message_id: int | None = None


active_sessions: dict[int, QuizSession] = {}
MODE_VALUES = {"trail", "training", "blitz", "exam", "mistakes", "starred", "duel", "repetition", "quick"}


def escape(value: str | None) -> str:
    return html.escape(value or "")


def has_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def is_premium(user) -> bool:
    return bool(user and user.access_level == "premium")


def has_full_access(user) -> bool:
    return FREE_MODE or is_premium(user)


def get_app_timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except Exception:  # pragma: no cover
        logger.warning("Unknown timezone %s, falling back to UTC.", APP_TIMEZONE)
        return ZoneInfo("UTC")


def section_footer_rows(section_text: str, section_callback: str) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text=section_text, callback_data=section_callback),
            InlineKeyboardButton(text="🏕 Главная", callback_data="camp"),
        ]
    ]


def section_back_markup(section_text: str, section_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=section_footer_rows(section_text, section_callback))


def session_result_markup(mode: Mode) -> InlineKeyboardMarkup:
    if mode in {"training", "exam", "quick"}:
        return start_menu_markup()
    if mode in {"trail", "blitz", "mistakes", "starred", "duel", "repetition"}:
        return practice_menu_markup()
    return main_menu_markup()


def main_menu_markup() -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(text="🚀 Старт", callback_data="menu_start"),
                InlineKeyboardButton(text="📚 Практика", callback_data="menu_practice"),
            ],
            [
                InlineKeyboardButton(text="📅 Ежедневно", callback_data="menu_daily"),
                InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
            ],
        ]
    if MINIAPP_URL:
        rows.append([InlineKeyboardButton(text="📱 Войти в Mini App", web_app=WebAppInfo(url=MINIAPP_URL))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_menu_markup() -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(text="🦆 Быстрый вопрос", callback_data="quick"),
                InlineKeyboardButton(text="🎯 Стрельбище", callback_data="training"),
            ],
            [
                InlineKeyboardButton(text="📝 Экзамен 257", callback_data="exam"),
                InlineKeyboardButton(text="🦆 Вопрос дня", callback_data="daily_question"),
            ],
            [InlineKeyboardButton(text="🏕 Главная", callback_data="camp")],
        ]
    if MINIAPP_URL:
        rows.insert(2, [InlineKeyboardButton(text="📱 Открыть Mini App", web_app=WebAppInfo(url=MINIAPP_URL))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def practice_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗺 Тропа знаний", callback_data="trail_menu"),
                InlineKeyboardButton(text="⚡ Блиц", callback_data="blitz"),
            ],
            [
                InlineKeyboardButton(text="🔄 Промахи", callback_data="mistakes"),
                InlineKeyboardButton(text="⭐ Трудные следы", callback_data="starred"),
            ],
            [
                InlineKeyboardButton(text="🧠 Повторение", callback_data="repetition"),
                InlineKeyboardButton(text="⚔️ Дуэль", callback_data="duel"),
            ],
            [
                InlineKeyboardButton(text="🦌 Карточки", callback_data="cards"),
                InlineKeyboardButton(text="📅 Маршрут", callback_data="route"),
            ],
            [InlineKeyboardButton(text="🏕 Главная", callback_data="camp")],
        ]
    )


def daily_menu_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🦆 Вопрос дня", callback_data="daily_question"),
                InlineKeyboardButton(text="🎯 Вызов дня", callback_data="daily_challenge"),
            ],
            [InlineKeyboardButton(text="📍 Задача маршрута", callback_data="route_task")],
            [InlineKeyboardButton(text="🏕 Главная", callback_data="camp")],
        ]
    )


def profile_menu_markup() -> InlineKeyboardMarkup:
    premium_text = "🆓 Всё открыто" if FREE_MODE else "💎 Premium"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Журнал", callback_data="journal"),
                InlineKeyboardButton(text="🏆 Достижения", callback_data="achievements"),
            ],
            [
                InlineKeyboardButton(text="📝 История", callback_data="exam_history"),
                InlineKeyboardButton(text="📈 График", callback_data="progress_graph"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Снаряжение", callback_data="settings"),
                InlineKeyboardButton(text="❓ Справка", callback_data="help"),
            ],
            [InlineKeyboardButton(text=premium_text, callback_data="premium")],
            [InlineKeyboardButton(text="🏕 Главная", callback_data="camp")],
        ]
    )


def trail_menu_markup() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{block['icon']} {block['name']}",
                callback_data=f"trail_block_{block_id}",
            )
        ]
        for block_id, block in BLOCKS.items()
    ]
    rows.extend(section_footer_rows("↩️ Практика", "menu_practice"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_menu_markup() -> InlineKeyboardMarkup:
    if FREE_MODE:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🆓 Сейчас весь функционал открыт", callback_data="menu_profile")],
                *section_footer_rows("↩️ Профиль", "menu_profile"),
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"⭐ Telegram Stars ({PREMIUM_PRICE_STARS} ⭐)", callback_data="buy_premium_stars")],
            [InlineKeyboardButton(text=f"💳 Банковская карта ({PREMIUM_PRICE_RUB} ₽)", callback_data="buy_premium_card")],
            [InlineKeyboardButton(text="🔑 Ввести промокод", callback_data="promo_code")],
            *section_footer_rows("↩️ Профиль", "menu_profile"),
        ]
    )


def settings_markup(user) -> InlineKeyboardMarkup:
    settings = dict(user.settings or {})
    questions = settings.get("questions_per_session", 20)
    timer = settings.get("timer_seconds", 0)
    explanations = settings.get("show_explanations", True)
    reminder = "вкл" if user.daily_reminder else "выкл"
    timer_text = "выкл" if not timer else f"{timer}с"
    rows = [
        [
            InlineKeyboardButton(text=f"🎯 Мишеней: {questions}", callback_data="settings_count"),
            InlineKeyboardButton(text=f"⏱ Таймер: {timer_text}", callback_data="settings_timer"),
        ],
        [
            InlineKeyboardButton(text=f"💬 Объяснения: {'да' if explanations else 'нет'}", callback_data="settings_explanations"),
            InlineKeyboardButton(text=f"🔔 Сигнал: {reminder}", callback_data="settings_reminder"),
        ],
        [
            InlineKeyboardButton(text=f"⏰ Время: {user.reminder_hour}:00", callback_data="settings_hour"),
            InlineKeyboardButton(text="🔑 Промокод", callback_data="promo_code"),
        ],
        [
            InlineKeyboardButton(text="🗑 Начать путь заново", callback_data="reset_progress"),
            InlineKeyboardButton(text="🆓 Всё бесплатно" if FREE_MODE else "💎 Premium", callback_data="premium"),
        ],
    ]
    rows.extend(section_footer_rows("↩️ Профиль", "menu_profile"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏕 Вернуться в лагерь", callback_data="camp")],
            [
                InlineKeyboardButton(text="😴 Отложить на 3 дня", callback_data="snooze_3d"),
                InlineKeyboardButton(text="🔕 Выключить сигнал", callback_data="disable_reminders"),
            ],
            [InlineKeyboardButton(text="⛔ Выключить всё", callback_data="disable_forever")],
        ]
    )


def reset_progress_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, сбросить", callback_data="reset_progress_confirm")],
            [InlineKeyboardButton(text="↩️ Нет, назад", callback_data="settings")],
        ]
    )


def camp_text(user, questions_count: int) -> str:
    rank = get_rank_by_correct(user.correct_answers)
    unlocked = user.correct_answers
    access_label = "Open Beta" if FREE_MODE else ("Premium" if user.access_level == "premium" else "Free")
    return "\n".join(
        [
            "<b>🏕 Лагерь охотника ONEHUNT</b>",
            "",
            f"🗂 В базе: <b>{questions_count}</b> {plural_form(questions_count, 'вопрос', 'вопроса', 'вопросов')}",
            f"🔓 Статус: <b>{access_label}</b>",
            f"🎖 Звание: {rank['icon']} <b>{escape(rank['name'])}</b>",
            "",
            f"📍 Пройдено: <b>{user.questions_completed}/257</b>",
            f"🎯 Точность: <b>{user.accuracy}%</b>",
            f"✅ Уникально правильно: <b>{unlocked}</b>",
            "",
            f"⚡ XP: <b>{user.xp_total}</b> | 💎 Монеты: <b>{user.coins}</b>",
            format_streak_message(user.streak_days),
            "",
            "Ниже 4 раздела: старт, практика, ежедневно и профиль.",
        ]
    )


def premium_required_text(feature_name: str, user) -> str:
    if FREE_MODE:
        return "🆓 Сейчас этот режим уже открыт бесплатно."
    feature_texts = {
        "exam": "🔒 К Испытанию допускаются только с полным снаряжением.\n\n257 вопросов, 90 минут и реальная проверка уровня.",
        "mistakes": f"🔒 Разбор промахов — Premium.\n\nУ вас {user.wrong_answers} ошибок. Исправьте их — и результат заметно вырастет.",
        "starred": "🔒 Трудные следы доступны только Premium-охотникам.",
        "duel": "🔒 Егерь Михалыч ждёт достойного соперника.\n\nДуэль открывается в Premium.",
        "blitz": "🔒 Блиц-режим входит в Premium-снаряжение.",
        "repetition": "🔒 Интервальное повторение доступно в Premium.",
        "route": "🔒 Маршрут 14 дней открывается только с полным снаряжением.",
        "cards": "🔒 Карточки охотника доступны в Premium.",
        "challenge": "🔒 Вызов дня — Premium-функция.",
        "trail_limit": "🔒 Бесплатная тропа на этом блоке уже исчерпана. Откройте весь маршрут целиком.",
        "training_limit": "🔒 5 бесплатных тренировок уже использованы. В Premium стрельбище безлимитное.",
        "graph": "🔒 График прогресса и недельные отчёты доступны в Premium.",
    }
    return "\n".join(
        [
            feature_texts.get(feature_name, "🔒 Эта функция доступна в Premium."),
            "",
            f"💰 {PREMIUM_PRICE_RUB} ₽ один раз или {PREMIUM_PRICE_STARS} ⭐ через Telegram.",
            "Полное снаряжение открывает все режимы навсегда.",
        ]
    )


async def safe_edit(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc).lower():
            return
        await message.answer(text, reply_markup=reply_markup)


async def respond(
    target: Message | CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if isinstance(target, CallbackQuery):
        await safe_edit(target.message, text, reply_markup)
        try:
            await target.answer()
        except TelegramBadRequest as exc:
            exc_text = str(exc).lower()
            if "query is too old" not in exc_text and "query id is invalid" not in exc_text:
                raise
        return
    await target.answer(text, reply_markup=reply_markup)


async def show_premium_required(target: Message | CallbackQuery, feature_name: str) -> None:
    user = await get_user(target.from_user.id)
    if user is None:
        return
    await respond(target, premium_required_text(feature_name, user), reply_markup=premium_menu_markup())


def build_question_text(question, title: str, index: int, total: int, timer_left: int | None = None) -> str:
    lines = [f"<b>{escape(title)}</b>"]
    if total:
        lines.append(f"{progress_bar(index + 1, total)} {index + 1}/{total}")
    if timer_left is not None:
        lines.append(f"⏱ Осталось: <b>{format_duration(max(timer_left, 0))}</b>")
    lines.extend(["", f"❓ {escape(question.question_text)}", ""])
    for key, value in sorted(question.options.items()):
        lines.append(f"{key.upper()}) {escape(value)}")
    return "\n".join(lines)


def build_result_text(question, selected: str, outcome, show_explanation: bool = True) -> str:
    correct_key = question.correct_answer
    selected_text = question.options.get(selected, "")
    correct_text = question.options.get(correct_key, "")
    lines = [
        f"{'✅' if outcome.is_correct else '❌'} <b>{'Верно' if outcome.is_correct else 'Промах'}</b>",
        f"⚡ +{outcome.xp_added} XP | 💎 +{outcome.coins_added}",
        "",
    ]
    if not outcome.is_correct:
        lines.append(f"Ваш ответ: <b>{selected.upper()}</b>) {escape(selected_text)}")
    lines.append(f"Правильный ответ: <b>{correct_key.upper()}</b>) {escape(correct_text)}")
    if show_explanation and question.explanation:
        lines.extend(["", f"📖 {escape(question.explanation)}"])
    if show_explanation and question.mnemonic:
        lines.extend(["", f"🧠 {escape(question.mnemonic)}"])
    if outcome.rank_up:
        lines.extend(
            [
                "",
                f"🎖 Новое звание: {outcome.rank_up['new']['icon']} <b>{escape(outcome.rank_up['new']['name'])}</b>",
            ]
        )
    for achievement in outcome.achievements[:3]:
        lines.append(f"🏆 Достижение: <b>{escape(achievement['name'])}</b>")
    if outcome.challenge_completed:
        lines.append(f"🎯 Вызов дня выполнен: <b>{escape(outcome.challenge_completed['name'])}</b>")
    if outcome.route_day_completed:
        lines.append(f"📅 День {outcome.route_day_completed} маршрута выполнен.")
    return "\n".join(lines)


def build_answer_rows(option_buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    if ANSWER_BUTTONS_LAYOUT == "stacked":
        return [[button] for button in option_buttons]
    if ANSWER_BUTTONS_LAYOUT == "grid":
        return [option_buttons[index : index + 2] for index in range(0, len(option_buttons), 2)]
    return [option_buttons]


async def build_answer_markup(user_id: int, question, mode: Mode) -> InlineKeyboardMarkup:
    option_buttons = [
        InlineKeyboardButton(
            text=key.upper(),
            callback_data=f"answer_{mode}_{question.id}_{key}",
        )
        for key, _value in sorted(question.options.items())
    ]
    rows = build_answer_rows(option_buttons)
    star_label = "⭐ Убрать" if await is_starred(user_id, question.id) else "⭐ В избранное"
    rows.append(
        [
            InlineKeyboardButton(text=star_label, callback_data=f"star_toggle_{question.id}"),
            InlineKeyboardButton(text="🏕 В лагерь", callback_data="camp"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def build_result_markup(user_id: int, question_id: int, next_callback: str, next_label: str) -> InlineKeyboardMarkup:
    star_label = "⭐ Убрать" if await is_starred(user_id, question_id) else "⭐ В избранное"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=next_label, callback_data=next_callback)],
            [
                InlineKeyboardButton(text=star_label, callback_data=f"star_toggle_{question_id}"),
                InlineKeyboardButton(text="🏕 В лагерь", callback_data="camp"),
            ],
        ]
    )


async def ensure_profile(target: Message | CallbackQuery):
    user = await get_or_create_user(
        telegram_id=target.from_user.id,
        username=target.from_user.username,
        first_name=target.from_user.first_name,
        last_name=target.from_user.last_name,
    )
    await mark_user_seen(target.from_user.id)
    return user


def resolve_question_image(question) -> str | FSInputFile | None:
    image_ref = str(getattr(question, "image_url", "") or "").strip()
    if not image_ref:
        return None
    image_path = Path(image_ref)
    if not image_path.is_absolute():
        image_path = (Path(__file__).resolve().parent / image_ref).resolve()
    if image_path.exists():
        return FSInputFile(str(image_path))
    return image_ref


async def clear_session_media(chat_id: int, session: QuizSession) -> None:
    if bot is None or session.media_message_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=session.media_message_id)
    except Exception:
        pass
    session.media_message_id = None


async def show_question_image(chat_id: int, question, session: QuizSession | None = None) -> None:
    if bot is None:
        return
    media = resolve_question_image(question)
    if media is None:
        if session is not None:
            session.media_message_id = None
        return
    try:
        media_message = await bot.send_photo(
            chat_id=chat_id,
            photo=media,
            caption="🖼 Иллюстрация к вопросу",
        )
        if session is not None:
            session.media_message_id = media_message.message_id
    except Exception:
        logger.exception("Failed to send question image for question %s", getattr(question, "id", "?"))
        if session is not None:
            session.media_message_id = None


async def show_camp(target: Message | CallbackQuery) -> None:
    user = await ensure_profile(target)
    await seed_reference_data()
    questions_count = await get_question_count()
    await respond(target, camp_text(user, questions_count), reply_markup=main_menu_markup())


async def show_start_menu(target: Message | CallbackQuery) -> None:
    await respond(
        target,
        "\n".join(
            [
                "<b>🚀 Старт</b>",
                "",
                "Здесь самые быстрые входы в подготовку.",
                "🦆 Быстрый вопрос — один вопрос прямо сейчас.",
                "🎯 Стрельбище — обычная тренировка по вашим настройкам.",
                "📝 Экзамен 257 — полный официальный прогон.",
                "📅 Вопрос дня — короткая ежедневная проверка.",
            ]
        ),
        reply_markup=start_menu_markup(),
    )


async def show_practice_menu(target: Message | CallbackQuery) -> None:
    await respond(
        target,
        "\n".join(
            [
                "<b>📚 Практика</b>",
                "",
                "Здесь собраны все режимы для набивки результата.",
                "🗺 Тропа знаний — прохождение по блокам.",
                "⚡ Блиц, 🔄 Промахи, ⭐ Трудные следы и 🧠 Повторение — для прицельной тренировки.",
                "⚔️ Дуэль, 🦌 Карточки и 📅 Маршрут — дополнительные режимы подготовки.",
            ]
        ),
        reply_markup=practice_menu_markup(),
    )


async def show_daily_menu(target: Message | CallbackQuery) -> None:
    await respond(
        target,
        "\n".join(
            [
                "<b>📅 Ежедневно</b>",
                "",
                "Здесь короткие ежедневные активности.",
                "🦆 Вопрос дня — один обязательный вопрос.",
                "🎯 Вызов дня — мини-цель с наградой.",
                "📍 Задача маршрута — шаг текущего дня в программе подготовки.",
            ]
        ),
        reply_markup=daily_menu_markup(),
    )


async def show_profile_menu(target: Message | CallbackQuery) -> None:
    await respond(
        target,
        "\n".join(
            [
                "<b>👤 Профиль</b>",
                "",
                "Здесь собраны все личные данные и управление ботом.",
                "📊 Журнал и 📈 График показывают ваш прогресс.",
                "🏆 Достижения и 📝 История помогают отслеживать путь.",
                "⚙️ Снаряжение, ❓ Справка и доступ к Premium тоже находятся здесь.",
            ]
        ),
        reply_markup=profile_menu_markup(),
    )


async def show_question(target: Message | CallbackQuery, session: QuizSession) -> None:
    if session.current >= len(session.question_ids):
        await finish_session(target, session)
        return

    question = await get_question(session.question_ids[session.current])
    if question is None:
        await respond(target, "Не удалось открыть вопрос. Попробуйте ещё раз.", reply_markup=main_menu_markup())
        return

    await clear_session_media(target.from_user.id, session)

    session.question_started_at = datetime.utcnow()
    timer_left = None
    if session.total_timer_seconds is not None:
        spent = int((datetime.utcnow() - session.started_at).total_seconds())
        timer_left = session.total_timer_seconds - spent
        if timer_left <= 0:
            await finish_session(target, session, timeout=True)
            return

    await show_question_image(target.from_user.id, question, session)
    text = build_question_text(question, session.title, session.current, len(session.question_ids), timer_left)
    markup = await build_answer_markup(target.from_user.id, question, session.mode)
    await respond(target, text, reply_markup=markup)


async def start_session(target: Message | CallbackQuery, session: QuizSession) -> None:
    active_sessions[target.from_user.id] = session
    await show_question(target, session)


async def require_premium(target: Message | CallbackQuery, feature_name: str) -> bool:
    user = await ensure_profile(target)
    if has_full_access(user):
        return True
    await show_premium_required(target, feature_name)
    return False


async def start_trail(target: Message | CallbackQuery, block_id: int) -> None:
    user = await ensure_profile(target)
    progress = await get_user_block_progress(user.telegram_id, block_id)
    if not has_full_access(user) and progress >= TRAIL_FREE_LIMIT:
        await show_premium_required(target, "trail_limit")
        return

    answered_ids = await get_answered_question_ids(user.telegram_id, mode="trail", block_id=block_id)
    all_questions = await get_question_sequence_for_block(block_id)
    questions = [question for question in all_questions if question.id not in answered_ids]
    if not questions:
        questions = all_questions
    if not has_full_access(user):
        questions = questions[:TRAIL_FREE_LIMIT]
    if not questions:
        await respond(target, "В этом блоке пока нет вопросов.", reply_markup=main_menu_markup())
        return
    block = BLOCKS[block_id]
    await start_session(
        target,
        QuizSession(
            mode="trail",
            title=f"{block['icon']} Тропа: {block['name']}",
            question_ids=[question.id for question in questions],
            block_id=block_id,
        ),
    )


async def start_training(target: Message | CallbackQuery, weak: bool = False, timed: bool = False) -> None:
    user = await ensure_profile(target)
    if not has_full_access(user) and user.free_trainings_used >= TRAINING_FREE_LIMIT:
        await show_premium_required(target, "training_limit")
        return

    settings = dict(user.settings or {})
    limit = int(settings.get("questions_per_session", 20))
    block_id = None
    if weak:
        stats = await get_journal_stats(user.telegram_id)
        block_candidates = {
            1: stats["block1"],
            2: stats["block2"],
            3: stats["block3"],
        }
        block_id = min(block_candidates, key=block_candidates.get)
    questions = await get_random_questions(limit, block_id=block_id)
    title = "🎯 Стрельбище" if not weak else "🎯 Стрельбище — слабые темы"
    await start_session(
        target,
        QuizSession(
            mode="training",
            title=title,
            question_ids=[question.id for question in questions],
            total_timer_seconds=(limit * 60 if timed else None),
            block_id=block_id,
        ),
    )


async def start_blitz(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "blitz"):
        return
    questions = await get_random_questions(20)
    await start_session(
        target,
        QuizSession(
            mode="blitz",
            title="⚡ Блиц-режим",
            question_ids=[question.id for question in questions],
            total_timer_seconds=300,
        ),
    )


async def start_exam(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "exam"):
        return
    questions = await get_official_exam_questions(EXAM_QUESTIONS, shuffle=False)
    await start_session(
        target,
        QuizSession(
            mode="exam",
            title="📝 Экзамен — все 257 вопросов",
            question_ids=[question.id for question in questions],
            total_timer_seconds=90 * 60,
        ),
    )


async def start_mistakes(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "mistakes"):
        return
    questions = await get_wrong_questions(target.from_user.id, 20)
    if not questions:
        await respond(target, "Промахов пока нет. Отлично идёте! 🎉", reply_markup=main_menu_markup())
        return
    await start_session(
        target,
        QuizSession(
            mode="mistakes",
            title="🔄 Разбор промахов",
            question_ids=[question.id for question in questions],
        ),
    )


async def start_starred(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "starred"):
        return
    questions = await get_starred_questions(target.from_user.id, 20)
    if not questions:
        await respond(target, "Трудных следов пока нет. Добавляйте вопросы звёздочкой.", reply_markup=main_menu_markup())
        return
    await start_session(
        target,
        QuizSession(
            mode="starred",
            title="⭐ Трудные следы",
            question_ids=[question.id for question in questions],
        ),
    )


async def start_repetition(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "repetition"):
        return
    questions = await get_due_repetition_questions(target.from_user.id, 20)
    if not questions:
        await respond(target, "Сейчас нет вопросов, готовых к повторению. Возвращайтесь позже.", reply_markup=main_menu_markup())
        return
    await start_session(
        target,
        QuizSession(
            mode="repetition",
            title="🧠 Интервальное повторение",
            question_ids=[question.id for question in questions],
        ),
    )


async def start_duel(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "duel"):
        return
    questions = await get_random_questions(10)
    await start_session(
        target,
        QuizSession(
            mode="duel",
            title="⚔️ Дуэль с Михалычем",
            question_ids=[question.id for question in questions],
            total_timer_seconds=180,
        ),
    )


async def start_quick(target: Message | CallbackQuery) -> None:
    questions = await get_random_questions(1)
    if not questions:
        await respond(target, "База вопросов пока пуста.", reply_markup=main_menu_markup())
        return
    await start_session(
        target,
        QuizSession(
            mode="quick",
            title="🦆 Быстрый вопрос",
            question_ids=[questions[0].id],
        ),
    )


async def finish_session(target: Message | CallbackQuery, session: QuizSession, timeout: bool = False) -> None:
    active_sessions.pop(target.from_user.id, None)
    ended_at = datetime.utcnow()
    await clear_session_media(target.from_user.id, session)
    await record_user_session(
        user_id=target.from_user.id,
        mode=session.mode,
        questions_count=len(session.question_ids),
        correct_count=session.correct,
        max_streak=session.max_streak,
        started_at=session.started_at,
        ended_at=ended_at,
    )

    if session.mode == "training":
        user = await get_user(target.from_user.id)
        if user and not has_full_access(user):
            await update_user(user.telegram_id, free_trainings_used=user.free_trainings_used + 1)

    if session.mode == "exam":
        result = await finish_exam_attempt(
            target.from_user.id,
            session.answers_detail,
            session.started_at,
            ended_at,
        )
        lines = [
            f"{'🏆' if result['passed'] else '📘'} <b>{'Испытание пройдено!' if result['passed'] else 'Испытание завершено'}</b>",
            "",
            f"Результат: <b>{result['correct_count']}/{len(session.question_ids)}</b> ({result['score_percent']}%)",
            f"Проходной порог: <b>{EXAM_PASS_PERCENT}%</b>",
            f"Время: <b>{result['time_spent_minutes']} мин</b>",
            f"Бонус: <b>+{result['xp_bonus']} XP</b>",
        ]
        for achievement in result["achievements"][:3]:
            lines.append(f"🏆 Достижение: <b>{escape(achievement['name'])}</b>")
        await respond(target, "\n".join(lines), reply_markup=session_result_markup(session.mode))
        return

    if session.mode == "duel":
        user_score = session.correct
        base = round(len(session.question_ids) * 0.6)
        bot_score = max(0, min(len(session.question_ids), base + random.randint(-2, 2)))
        result = await record_duel(target.from_user.id, user_score, bot_score, session.answers_detail)
        text = "\n".join(
            [
                f"{'🏆' if result['user_won'] else '🦌'} <b>{'Вы победили Михалыча!' if result['user_won'] else 'Михалыч оказался сильнее.'}</b>",
                "",
                f"Ваш счёт: <b>{user_score}</b>",
                f"Михалыч: <b>{bot_score}</b>",
                f"Время: <b>{format_duration(int((ended_at - session.started_at).total_seconds()))}</b>",
            ]
        )
        await respond(target, text, reply_markup=session_result_markup(session.mode))
        return

    if session.mode == "quick":
        await start_quick(target)
        return

    text = "\n".join(
        [
            f"<b>{escape(session.title)}</b>",
            "Сессия завершена." if not timeout else "Время вышло. Сессия завершена.",
            "",
            f"Верно: <b>{session.correct}</b>",
            f"Ошибок: <b>{session.wrong}</b>",
            f"Точность: <b>{calculate_accuracy(session.correct, max(len(session.answers_detail), 1))}%</b>",
            f"Время: <b>{format_duration(int((ended_at - session.started_at).total_seconds()))}</b>",
        ]
    )
    await respond(target, text, reply_markup=session_result_markup(session.mode))


async def handle_session_answer(callback: CallbackQuery, mode: Mode, question_id: int, selected_answer: str) -> None:
    session = active_sessions.get(callback.from_user.id)
    if session is None or session.mode != mode:
        await callback.answer("Сессия уже завершена или устарела.", show_alert=True)
        return

    if session.current >= len(session.question_ids):
        await finish_session(callback, session)
        return

    expected_question_id = session.question_ids[session.current]
    if expected_question_id != question_id:
        await callback.answer("Сообщение устарело. Откройте следующий вопрос заново.", show_alert=True)
        return

    total_elapsed = int((datetime.utcnow() - session.started_at).total_seconds())
    if session.total_timer_seconds is not None and total_elapsed > session.total_timer_seconds:
        await finish_session(callback, session, timeout=True)
        return

    question = await get_question(question_id)
    if question is None:
        await callback.answer("Вопрос не найден.", show_alert=True)
        return

    time_spent = int((datetime.utcnow() - session.question_started_at).total_seconds())
    outcome = await save_answer(
        user_id=callback.from_user.id,
        question_id=question_id,
        selected_answer=selected_answer,
        mode=mode,
        time_spent_seconds=time_spent,
    )

    if outcome.is_correct:
        session.correct += 1
        session.current_streak += 1
        session.max_streak = max(session.max_streak, session.current_streak)
    else:
        session.wrong += 1
        session.current_streak = 0
    session.answers_detail.append(
        {
            "question_id": question.id,
            "block": question.block,
            "selected": selected_answer,
            "is_correct": outcome.is_correct,
        }
    )
    session.current += 1

    user = await get_user(callback.from_user.id)
    show_explanation = bool((user.settings or {}).get("show_explanations", True)) and session.mode != "exam"
    text = build_result_text(question, selected_answer, outcome, show_explanation=show_explanation)
    next_callback = f"next_{mode}" if session.current < len(session.question_ids) else f"finish_{mode}"
    next_label = "➡️ Следующий вопрос" if session.current < len(session.question_ids) else "🏁 Итог"
    markup = await build_result_markup(callback.from_user.id, question.id, next_callback, next_label)
    await safe_edit(callback.message, text, reply_markup=markup)
    await callback.answer()


async def show_daily_question(target: Message | CallbackQuery) -> None:
    question = await get_daily_question_question()
    if question is None:
        await respond(target, "Не удалось подготовить вопрос дня.", reply_markup=daily_menu_markup())
        return
    existing_answer = await get_daily_question_answer(target.from_user.id)
    header = f"🦆 Вопрос дня | {datetime.now().strftime('%d.%m.%Y')}"
    if existing_answer:
        await respond(target, f"<b>{header}</b>\n\nВы уже ответили на вопрос дня сегодня.", reply_markup=daily_menu_markup())
        return
    await show_question_image(target.from_user.id, question)
    text = build_question_text(question, header, 0, 1)
    option_buttons = [
        InlineKeyboardButton(text=key.upper(), callback_data=f"daily_answer_{question.id}_{key}")
        for key, _value in sorted(question.options.items())
    ]
    rows = build_answer_rows(option_buttons)
    rows.extend(section_footer_rows("↩️ Ежедневно", "menu_daily"))
    await respond(target, text + "\n\n+20 XP за правильный ответ!", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def show_daily_challenge(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "challenge"):
        return
    challenge = await get_or_create_daily_challenge(target.from_user.id)
    cfg = DAILY_CHALLENGES[challenge.challenge_date.weekday()]
    text = "\n".join(
        [
            f"<b>🎯 Вызов дня | {challenge.challenge_date.strftime('%d.%m')}</b>",
            "",
            f"{cfg['icon']} <b>{escape(cfg['name'])}</b>",
            escape(cfg["description"]),
            f"Награда: ⚡ +{cfg['xp']} XP | 💎 +{cfg['coins']}",
            f"Статус: <b>{'выполнен' if challenge.completed else 'в процессе'}</b>",
        ]
    )
    await respond(target, text, reply_markup=section_back_markup("↩️ Ежедневно", "menu_daily"))


async def show_route(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "route"):
        return
    overview = await get_route_overview(target.from_user.id)
    lines = ["<b>📅 Маршрут охотника — 14 дней</b>", ""]
    for item in overview["days"]:
        status_icon = "✅" if item["status"] == "done" else "👉" if item["status"] == "today" else "⬜"
        suffix = "✓" if item["status"] == "done" else "← сегодня" if item["status"] == "today" else ""
        lines.append(f"{status_icon} День {item['day']}: {item['task']['icon']} {item['task']['name']} {suffix}".rstrip())
    lines.extend(
        [
            "",
            f"Прогресс: <b>{overview['completed']}/14</b> ({overview['percent']}%)",
            progress_bar(overview["completed"], 14),
        ]
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ К задаче дня", callback_data="route_task")],
            *section_footer_rows("↩️ Ежедневно", "menu_daily"),
        ]
    )
    await respond(target, "\n".join(lines), reply_markup=keyboard)


async def show_route_task(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "route"):
        return
    payload = await get_route_task(target.from_user.id)
    if payload is None:
        await respond(target, "Маршрут завершён или ещё не начат.", reply_markup=daily_menu_markup())
        return
    day_number = payload["day"]
    task = payload["task"]
    text = "\n".join(
        [
            f"<b>👉 День {day_number} | Задача</b>",
            "",
            f"{task['icon']} <b>{escape(task['name'])}</b>",
            f"Цель: {escape(task['goal'])}",
            f"Время: ~{task['minutes']} минут",
            "Награда: ⚡ +100 XP | 💎 +15",
        ]
    )
    await respond(
        target,
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Начать задачу дня", callback_data=f"route_start_{day_number}")],
                *section_footer_rows("↩️ Ежедневно", "menu_daily"),
            ]
        ),
    )


async def show_journal(target: Message | CallbackQuery) -> None:
    stats = await get_journal_stats(target.from_user.id)
    user = stats["user"]
    rank = stats["rank"]
    next_rank = stats["next_rank"]
    next_level = stats["next_level"]
    lines = [
        "<b>📊 Журнал охотника</b>",
        "",
        f"🎖 Звание: {rank['icon']} <b>{escape(rank['name'])}</b>",
        f"⚡ Уровень: <b>{stats['level']}</b> | XP: <b>{user.xp_total}</b>",
        f"💎 Монеты: <b>{user.coins}</b>",
        f"🏆 Достижения: <b>{stats['achievements']}/{len(ACHIEVEMENTS)}</b>",
        f"📍 Прогресс: <b>{user.questions_completed}/257</b>",
        f"✅ Правильно: <b>{user.correct_answers}</b> ({user.accuracy}%)",
        f"❌ Ошибки: <b>{user.wrong_answers}</b>",
        f"📚 Право: <b>{stats['block1']}%</b>",
        f"🔫 Безопасность: <b>{stats['block2']}%</b>",
        f"🦌 Природа: <b>{stats['block3']}%</b>",
        f"🔥 Серия: <b>{user.streak_days}</b> дней | рекорд <b>{user.streak_best}</b>",
        f"📝 Испытания: <b>{user.exams_taken}</b> | лучший <b>{user.best_exam_score}%</b>",
    ]
    if next_rank:
        lines.append(f"До звания {next_rank['icon']} {escape(next_rank['name'])}: <b>{int(next_rank['min_correct']) - user.correct_answers}</b>")
    if next_level:
        lines.append(f"До уровня {next_level[0]}: <b>{next_level[1] - user.xp_total} XP</b>")
    lines.extend(["", "⚠️ Слабые следы:"])
    lines.extend(stats["weak_topics"])
    rows = [
        [InlineKeyboardButton(text="📝 История испытаний", callback_data="exam_history")],
        [InlineKeyboardButton(text="📈 График прогресса", callback_data="progress_graph")],
    ]
    rows.extend(section_footer_rows("↩️ Профиль", "menu_profile"))
    await respond(target, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def show_exam_history(target: Message | CallbackQuery) -> None:
    history = await get_exam_history(target.from_user.id)
    if not history:
        await respond(target, "История испытаний пока пуста.", reply_markup=profile_menu_markup())
        return
    lines = ["<b>📝 История испытаний</b>", ""]
    for index, attempt in enumerate(history, 1):
        status = "✅" if attempt.passed else "❌"
        lines.append(
            f"#{index} | {attempt.started_at.strftime('%d.%m.%Y')} | {attempt.score_percent}% {status} | ⏱ {attempt.time_spent_minutes or 0} мин"
        )
    await respond(target, "\n".join(lines), reply_markup=section_back_markup("↩️ Профиль", "menu_profile"))


async def show_progress_graph(target: Message | CallbackQuery) -> None:
    user = await get_user(target.from_user.id)
    if user is None:
        return
    if not has_full_access(user):
        await show_premium_required(target, "graph")
        return
    graph = await get_progress_chart(target.from_user.id)
    text = "\n".join(
        [
            "<b>📈 Прогресс за 14 дней</b>",
            "",
            f"<pre>{escape(graph['chart'])}</pre>",
            f"Тренд: {'📈' if graph['diff'] >= 0 else '📉'} {graph['diff']}%",
            f"Прогноз до 80%+: {graph['estimate_days']} дн." if graph["estimate_days"] else "Цель 80% уже достигнута.",
        ]
    )
    await respond(target, text, reply_markup=section_back_markup("↩️ Профиль", "menu_profile"))


async def show_achievements(target: Message | CallbackQuery) -> None:
    overview = await get_achievement_overview(target.from_user.id)
    lines = [
        "<b>🏆 Достижения охотника</b>",
        "",
        f"Разблокировано: <b>{overview['unlocked']}/{len(ACHIEVEMENTS)}</b>",
        progress_bar(overview["unlocked"], len(ACHIEVEMENTS)),
        "",
    ]
    for item in overview["items"][:12]:
        if item["unlocked"]:
            lines.append(f"{'🏆' if not item['secret'] else '🔓'} <b>{escape(item['name'])}</b> — {escape(item['description'])}")
        elif item["secret"]:
            lines.append("🔒 ??? — Секретное достижение")
        else:
            lines.append(f"🔒 {escape(item['name'])} — {escape(item['description'])}")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Ближайшие к получению", callback_data="achievements_near")],
            *section_footer_rows("↩️ Профиль", "menu_profile"),
        ]
    )
    await respond(target, "\n".join(lines), reply_markup=keyboard)


async def show_nearest_achievements(target: Message | CallbackQuery) -> None:
    overview = await get_achievement_overview(target.from_user.id)
    lines = ["<b>🎯 Ближайшие достижения</b>", ""]
    for index, item in enumerate(overview["nearest"], 1):
        lines.append(f"{index}. <b>{escape(item['name'])}</b> — {escape(item['description'])}")
        lines.append(f"Прогресс: {item['current']}/{item['target']} ({item['percent']}%)")
        lines.append(progress_bar(int(item["current"]), int(item["target"])))
        lines.append("")
    await respond(target, "\n".join(lines).strip(), reply_markup=section_back_markup("↩️ Профиль", "menu_profile"))


async def show_cards(target: Message | CallbackQuery) -> None:
    if not await require_premium(target, "cards"):
        return
    catalog = await get_cards_catalog(target.from_user.id)
    lines = [
        "<b>🦌 Карточки охотника</b>",
        "",
        f"Изучено: <b>{catalog['viewed']}/{catalog['total']}</b> ({catalog['percent']}%)",
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for item in catalog["categories"]:
        rows.append([InlineKeyboardButton(text=f"{item['name']} ({item['count']})", callback_data=f"cards_cat_{item['name']}")])
    rows.extend(section_footer_rows("↩️ Практика", "menu_practice"))
    await respond(target, "\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def show_cards_category(target: Message | CallbackQuery, category: str) -> None:
    if not await require_premium(target, "cards"):
        return
    cards = await get_cards_by_category(category)
    rows = [[InlineKeyboardButton(text=card.name, callback_data=f"card_{card.id}")] for card in cards]
    rows.extend(section_footer_rows("↩️ Практика", "menu_practice"))
    await respond(target, f"<b>{escape(category)}</b>\n\nВыберите карточку:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def show_card(target: Message | CallbackQuery, card_id: int) -> None:
    if not await require_premium(target, "cards"):
        return
    details = await get_card_details(target.from_user.id, card_id)
    if details is None:
        await respond(target, "Карточка не найдена.", reply_markup=practice_menu_markup())
        return
    card = details["card"]
    lines = [
        f"<b>🦌 {escape(card.name)}</b>",
        f"<i>{escape(card.latin_name)}</i>" if card.latin_name else "",
        "",
        f"Категория: <b>{escape(card.category)}</b>",
        f"Семейство: {escape(card.family_name)}" if card.family_name else "",
        f"Вес: {escape(card.weight)}" if card.weight else "",
        f"Среда: {escape(card.habitat)}" if card.habitat else "",
        f"Охота: {escape(card.hunting_season)}" if card.hunting_season else "",
        f"След: {escape(card.track_description)}" if card.track_description else "",
        f"Вопросы по теме: <b>{details['question_count']}</b>",
        f"Правильно: <b>{details['correct_count']}</b> ({details['percent']}%)",
    ]
    await respond(target, "\n".join([line for line in lines if line]), reply_markup=section_back_markup("↩️ Практика", "menu_practice"))


async def show_settings(target: Message | CallbackQuery) -> None:
    user = await ensure_profile(target)
    settings = dict(user.settings or {})
    timer = settings.get("timer_seconds", 0)
    timer_text = "выкл" if not timer else f"{timer} сек"
    text = "\n".join(
        [
            "<b>⚙️ Снаряжение</b>",
            "",
            f"🎯 Мишеней в сессии: <b>{settings.get('questions_per_session', 20)}</b>",
            f"⏱ Таймер: <b>{timer_text}</b>",
            f"💬 Объяснения: <b>{'да' if settings.get('show_explanations', True) else 'нет'}</b>",
            f"🔔 Утренний сигнал: <b>{'вкл' if user.daily_reminder else 'выкл'}</b>",
            f"⏰ Время сигнала: <b>{user.reminder_hour}:00</b>",
            f"🎨 Тема: <b>{escape(user.theme)}</b>",
            f"🏷 Значок: <b>{escape(user.badge or 'нет')}</b>",
            f"📊 Статус: <b>{'Open Beta' if FREE_MODE else ('Premium' if user.access_level == 'premium' else 'Free')}</b>",
        ]
    )
    await respond(target, text, reply_markup=settings_markup(user))


async def show_help(target: Message | CallbackQuery) -> None:
    premium_line = (
        "Сейчас весь функционал открыт бесплатно, позже платный доступ можно вернуть одним флагом в .env."
        if FREE_MODE
        else "Вопрос дня доступен всем, а маршрут, вызовы, карточки и продвинутые режимы — в Premium."
    )
    text = "\n".join(
        [
            "<b>❓ Справка охотника</b>",
            "",
            "ONEHUNT — бот-тренажёр для подготовки к охотничьему минимуму.",
            "Режимы: быстрый вопрос, тренировки, блиц, ошибки, избранное, экзамен, маршрут и карточки.",
            "Также доступен Telegram Mini App с теми же ключевыми сценариями в отдельном интерфейсе.",
            premium_line,
            "Рекомендация: 14 дней по 15–20 минут дают устойчивый рост до 80%+.",
            "",
            "Команды: /start, /help, /admin",
            "Поддержка: @onehunt_support",
        ]
    )
    await respond(target, text, reply_markup=section_back_markup("↩️ Профиль", "menu_profile"))


async def show_premium(target: Message | CallbackQuery) -> None:
    if FREE_MODE:
        await respond(
            target,
            "<b>🆓 Сейчас весь функционал открыт бесплатно</b>\n\nКогда будет нужно, платный доступ можно вернуть одним флагом `FREE_MODE=false` в .env.",
            reply_markup=section_back_markup("↩️ Профиль", "menu_profile"),
        )
        return
    text = "\n".join(
        [
            "<b>💎 Полное снаряжение</b>",
            "",
            "Все 257 вопросов, 9 режимов, маршрут 14 дней, дуэли, интервальное повторение, карточки животных, вызов дня и расширенная аналитика.",
            f"Цена: <b>{PREMIUM_PRICE_RUB} ₽</b> или <b>{PREMIUM_PRICE_STARS} ⭐</b>.",
        ]
    )
    await respond(target, text, reply_markup=premium_menu_markup())


async def show_admin_panel(message: Message) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    dashboard = await get_admin_dashboard()
    text = "\n".join(
        [
            "<b>🔐 Админ-панель ONEHUNT</b>",
            "",
            f"👥 Пользователей: <b>{dashboard['total_users']}</b>",
            f"💎 Premium: <b>{dashboard['premium_users']}</b> ({dashboard['premium_percent']}%)",
            f"📊 Активных 24ч: <b>{dashboard['dau']}</b>",
            f"📊 Активных 7д: <b>{dashboard['wau']}</b>",
            f"💰 Доход 30д: <b>{dashboard['revenue_30d']} ₽</b>",
            f"💰 Доход всего: <b>{dashboard['revenue_total']} ₽</b>",
            f"📝 Испытаний сдано: <b>{dashboard['exams_passed']}</b>",
            f"🎯 Средний результат: <b>{dashboard['avg_exam']}%</b>",
        ]
    )
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏕 В лагерь", callback_data="camp")]]))


@dp.message(CommandStart())
async def command_start(message: Message) -> None:
    if message.from_user.id in active_sessions:
        await message.answer(
            "У вас есть активная сессия. Нажмите нужную кнопку в боте или вернитесь в лагерь через меню.",
            reply_markup=main_menu_markup(),
        )
        return
    await show_camp(message)


@dp.message(Command("help"))
async def command_help(message: Message) -> None:
    await show_help(message)


@dp.message(Command("admin"))
async def command_admin(message: Message) -> None:
    await show_admin_panel(message)


@dp.message(Command("user"))
async def command_user(message: Message, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /user TELEGRAM_ID")
        return
    payload = await get_user_card(int(command.args))
    if payload is None:
        await message.answer("Пользователь не найден.")
        return
    user = payload["user"]
    stats = payload["stats"]
    text = "\n".join(
        [
            "<b>👤 Карточка пользователя</b>",
            "",
            f"ID: <b>{user.telegram_id}</b>",
            f"Username: <b>@{escape(user.username or '—')}</b>",
            f"Имя: <b>{escape((user.first_name or '') + ' ' + (user.last_name or ''))}</b>",
            f"Статус: <b>{escape(user.access_level)}</b>",
            f"Звание: {stats['rank']['icon']} <b>{escape(stats['rank']['name'])}</b>",
            f"XP: <b>{user.xp_total}</b> | 💎 <b>{user.coins}</b>",
            f"Прогресс: <b>{user.questions_completed}/257</b>",
            f"Точность: <b>{user.accuracy}%</b>",
            f"Испытаний: <b>{user.exams_taken}</b> | лучший <b>{user.best_exam_score}%</b>",
            f"Оплачено: <b>{payload['payment_amount']} ₽</b>",
            f"Промокод: <b>{escape(user.promo_code_used or '—')}</b>",
        ]
    )
    await message.answer(text)


@dp.message(Command("grant_premium"))
async def command_grant_premium(message: Message, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /grant_premium TELEGRAM_ID")
        return
    user = await grant_premium(int(command.args))
    await message.answer("Premium активирован." if user else "Пользователь не найден.")


@dp.message(Command("revoke_premium"))
async def command_revoke_premium(message: Message, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    if not command.args or not command.args.isdigit():
        await message.answer("Использование: /revoke_premium TELEGRAM_ID")
        return
    user = await revoke_premium(int(command.args))
    await message.answer("Premium отозван." if user else "Пользователь не найден.")


@dp.message(Command("promo_create"))
async def command_promo_create(message: Message, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    args = (command.args or "").split()
    if len(args) < 3:
        await message.answer("Использование: /promo_create CODE DISCOUNT MAX_USES [DAYS]")
        return
    code, discount, max_uses, *tail = args
    days_valid = int(tail[0]) if tail else None
    promo = await create_promo_code(code, int(discount), int(max_uses), days_valid, message.from_user.id)
    await message.answer(f"Промокод {promo.code} создан.")


@dp.message(Command("promo_list"))
async def command_promo_list(message: Message) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    promos = await list_promo_codes()
    if not promos:
        await message.answer("Промокодов пока нет.")
        return
    lines = ["<b>🔑 Промокоды</b>", ""]
    for promo in promos[:20]:
        lines.append(
            f"{promo.code} | {promo.discount_percent}% | {promo.used_count}/{promo.max_uses} | до {promo.valid_until.strftime('%d.%m.%Y') if promo.valid_until else '∞'}"
        )
    await message.answer("\n".join(lines))


@dp.message(Command("questions_stats"))
async def command_questions_stats(message: Message) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    stats = await get_questions_stats()
    lines = ["<b>📝 Вопросы с низкой точностью</b>", ""]
    for item in stats:
        lines.append(f"#{item['id']} — {item['accuracy']}% — «{escape(truncate_text(item['text'], 50))}»")
    await message.answer("\n".join(lines))


@dp.message(Command("broadcast"))
async def command_broadcast(message: Message, state: FSMContext, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    text = command.args or ""
    if not text:
        await state.set_state(AppStates.waiting_broadcast_text)
        await message.answer("Введите текст для общей рассылки.")
        return
    await state.update_data(broadcast_text=text, premium_only=False)
    await message.answer("Подтвердить общую рассылку?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")], [InlineKeyboardButton(text="❌ Отмена", callback_data="camp")]]))


@dp.message(Command("broadcast_premium"))
async def command_broadcast_premium(message: Message, state: FSMContext, command: CommandObject) -> None:
    if not has_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    text = command.args or ""
    if not text:
        await state.set_state(AppStates.waiting_broadcast_premium_text)
        await message.answer("Введите текст для Premium-рассылки.")
        return
    await state.update_data(broadcast_text=text, premium_only=True)
    await message.answer("Подтвердить Premium-рассылку?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")], [InlineKeyboardButton(text="❌ Отмена", callback_data="camp")]]))


@dp.message(AppStates.waiting_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext) -> None:
    await state.update_data(broadcast_text=message.text, premium_only=False)
    await state.set_state(None)
    await message.answer("Подтвердить общую рассылку?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")], [InlineKeyboardButton(text="❌ Отмена", callback_data="camp")]]))


@dp.message(AppStates.waiting_broadcast_premium_text)
async def process_broadcast_premium_text(message: Message, state: FSMContext) -> None:
    await state.update_data(broadcast_text=message.text, premium_only=True)
    await state.set_state(None)
    await message.answer("Подтвердить Premium-рассылку?", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Отправить", callback_data="broadcast_confirm")], [InlineKeyboardButton(text="❌ Отмена", callback_data="camp")]]))


@dp.message(AppStates.waiting_promo_code)
async def process_promo(message: Message, state: FSMContext) -> None:
    result = await apply_promo_code(message.from_user.id, message.text.strip())
    await state.clear()
    if not result["ok"]:
        await message.answer(result["error"], reply_markup=premium_menu_markup())
        return
    if result["activated"]:
        await message.answer("🎉 Промокод принят. Premium активирован!", reply_markup=main_menu_markup())
        return
    await message.answer(
        f"🎉 Промокод принят. Скидка {result['discount_percent']}%.\nЦена: {result['discounted_price']} ₽",
        reply_markup=premium_menu_markup(),
    )


@dp.callback_query(F.data == "camp")
async def callback_camp(callback: CallbackQuery) -> None:
    await show_camp(callback)


@dp.callback_query(F.data == "menu_start")
async def callback_menu_start(callback: CallbackQuery) -> None:
    await show_start_menu(callback)


@dp.callback_query(F.data == "menu_practice")
async def callback_menu_practice(callback: CallbackQuery) -> None:
    await show_practice_menu(callback)


@dp.callback_query(F.data == "menu_daily")
async def callback_menu_daily(callback: CallbackQuery) -> None:
    await show_daily_menu(callback)


@dp.callback_query(F.data == "menu_profile")
async def callback_menu_profile(callback: CallbackQuery) -> None:
    await show_profile_menu(callback)


@dp.callback_query(F.data == "trail_menu")
async def callback_trail_menu(callback: CallbackQuery) -> None:
    await respond(callback, "<b>🗺 Тропа знаний</b>\n\nВыберите блок для последовательного прохождения.", reply_markup=trail_menu_markup())


@dp.callback_query(F.data.startswith("trail_block_"))
async def callback_trail_block(callback: CallbackQuery) -> None:
    block_id = int(callback.data.rsplit("_", 1)[-1])
    await start_trail(callback, block_id)


@dp.callback_query(F.data == "training")
async def callback_training(callback: CallbackQuery) -> None:
    await start_training(callback)


@dp.callback_query(F.data == "training_weak")
async def callback_training_weak(callback: CallbackQuery) -> None:
    await start_training(callback, weak=True)


@dp.callback_query(F.data == "training_timed")
async def callback_training_timed(callback: CallbackQuery) -> None:
    await start_training(callback, timed=True)


@dp.callback_query(F.data == "blitz")
async def callback_blitz(callback: CallbackQuery) -> None:
    await start_blitz(callback)


@dp.callback_query(F.data == "exam")
async def callback_exam(callback: CallbackQuery) -> None:
    await start_exam(callback)


@dp.callback_query(F.data == "mistakes")
async def callback_mistakes(callback: CallbackQuery) -> None:
    await start_mistakes(callback)


@dp.callback_query(F.data == "starred")
async def callback_starred(callback: CallbackQuery) -> None:
    await start_starred(callback)


@dp.callback_query(F.data == "repetition")
async def callback_repetition(callback: CallbackQuery) -> None:
    await start_repetition(callback)


@dp.callback_query(F.data == "duel")
async def callback_duel(callback: CallbackQuery) -> None:
    await start_duel(callback)


@dp.callback_query(F.data == "quick")
async def callback_quick(callback: CallbackQuery) -> None:
    await start_quick(callback)


@dp.callback_query(F.data == "daily_question")
async def callback_daily_question(callback: CallbackQuery) -> None:
    await show_daily_question(callback)


@dp.callback_query(F.data == "daily_challenge")
async def callback_daily_challenge(callback: CallbackQuery) -> None:
    await show_daily_challenge(callback)


@dp.callback_query(F.data == "route")
async def callback_route(callback: CallbackQuery) -> None:
    await show_route(callback)


@dp.callback_query(F.data == "route_task")
async def callback_route_task(callback: CallbackQuery) -> None:
    await show_route_task(callback)


@dp.callback_query(F.data.startswith("route_start_"))
async def callback_route_start(callback: CallbackQuery) -> None:
    day_number = int(callback.data.rsplit("_", 1)[-1])
    task = ROUTE_TASKS.get(day_number)
    if not task:
        await callback.answer("Задача не найдена.", show_alert=True)
        return
    action = task["callback"]
    if action.startswith("trail_block_"):
        await start_trail(callback, int(action.rsplit("_", 1)[-1]))
    elif action == "training":
        await start_training(callback)
    elif action == "training_weak":
        await start_training(callback, weak=True)
    elif action == "training_timed":
        await start_training(callback, timed=True)
    elif action == "blitz":
        await start_blitz(callback)
    elif action == "mistakes":
        await start_mistakes(callback)
    elif action == "exam":
        await start_exam(callback)
    else:
        await callback.answer("Пока не удалось открыть задачу.", show_alert=True)


@dp.callback_query(F.data == "journal")
async def callback_journal(callback: CallbackQuery) -> None:
    await show_journal(callback)


@dp.callback_query(F.data == "exam_history")
async def callback_exam_history(callback: CallbackQuery) -> None:
    await show_exam_history(callback)


@dp.callback_query(F.data == "progress_graph")
async def callback_progress_graph(callback: CallbackQuery) -> None:
    await show_progress_graph(callback)


@dp.callback_query(F.data == "achievements")
async def callback_achievements(callback: CallbackQuery) -> None:
    await show_achievements(callback)


@dp.callback_query(F.data == "achievements_near")
async def callback_near_achievements(callback: CallbackQuery) -> None:
    await show_nearest_achievements(callback)


@dp.callback_query(F.data == "cards")
async def callback_cards(callback: CallbackQuery) -> None:
    await show_cards(callback)


@dp.callback_query(F.data.startswith("cards_cat_"))
async def callback_cards_category(callback: CallbackQuery) -> None:
    category = callback.data.replace("cards_cat_", "", 1)
    await show_cards_category(callback, category)


@dp.callback_query(F.data.startswith("card_"))
async def callback_card(callback: CallbackQuery) -> None:
    card_id = int(callback.data.split("_", 1)[1])
    await show_card(callback, card_id)


@dp.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery) -> None:
    await show_settings(callback)


@dp.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery) -> None:
    await show_help(callback)


@dp.callback_query(F.data == "settings_explanations")
async def callback_settings_explanations(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    settings = dict(user.settings or {})
    settings["show_explanations"] = not settings.get("show_explanations", True)
    await update_user(user.telegram_id, settings=settings)
    await show_settings(callback)


@dp.callback_query(F.data == "settings_reminder")
async def callback_settings_reminder(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    await update_user(user.telegram_id, daily_reminder=not user.daily_reminder)
    await show_settings(callback)


@dp.callback_query(F.data == "settings_count")
async def callback_settings_count(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    settings = dict(user.settings or {})
    current = int(settings.get("questions_per_session", 20))
    choices = [10, 20, 30, 50]
    index = choices.index(current) if current in choices else 1
    settings["questions_per_session"] = choices[(index + 1) % len(choices)]
    await update_user(user.telegram_id, settings=settings)
    await show_settings(callback)


@dp.callback_query(F.data == "settings_timer")
async def callback_settings_timer(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    settings = dict(user.settings or {})
    current = int(settings.get("timer_seconds", 0))
    choices = [0, 30, 45, 60]
    index = choices.index(current) if current in choices else 0
    settings["timer_seconds"] = choices[(index + 1) % len(choices)]
    await update_user(user.telegram_id, settings=settings)
    await show_settings(callback)


@dp.callback_query(F.data == "settings_hour")
async def callback_settings_hour(callback: CallbackQuery) -> None:
    user = await get_user(callback.from_user.id)
    next_hour = 8 if user.reminder_hour >= 22 else user.reminder_hour + 1
    await update_user(user.telegram_id, reminder_hour=next_hour)
    await show_settings(callback)


@dp.callback_query(F.data == "premium")
async def callback_premium(callback: CallbackQuery) -> None:
    await show_premium(callback)


@dp.callback_query(F.data == "promo_code")
async def callback_promo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AppStates.waiting_promo_code)
    await respond(callback, "🔑 Введите промокод:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏕 В лагерь", callback_data="camp")]]))


@dp.callback_query(F.data == "buy_premium_card")
async def callback_buy_card(callback: CallbackQuery) -> None:
    payment_id = str(uuid.uuid4())
    await create_payment(callback.from_user.id, PREMIUM_PRICE_RUB, "RUB", "manual_card", payment_id)
    await respond(
        callback,
        "💳 Платёж для банковской карты подготовлен.\n\nПодключите реальные реквизиты ЮKassa в .env, чтобы активировать этот сценарий автоматически.",
        reply_markup=premium_menu_markup(),
    )


@dp.callback_query(F.data == "buy_premium_stars")
async def callback_buy_stars(callback: CallbackQuery) -> None:
    if bot is None:
        await callback.answer("Бот ещё не готов.", show_alert=True)
        return
    if not TELEGRAM_STARS_PROVIDER_TOKEN:
        await respond(
            callback,
            "Telegram Stars пока не настроены. Заполните TELEGRAM_STARS_PROVIDER_TOKEN в .env.",
            reply_markup=premium_menu_markup(),
        )
        return
    payload = f"premium_{callback.from_user.id}_{uuid.uuid4().hex}"
    await create_payment(callback.from_user.id, PREMIUM_PRICE_STARS, "XTR", "telegram_stars", payload)
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="ONEHUNT Premium — Полное снаряжение",
        description="Все режимы, маршрут 14 дней, карточки, дуэли, повторение и журнал без ограничений.",
        payload=payload,
        currency="XTR",
        provider_token=TELEGRAM_STARS_PROVIDER_TOKEN,
        prices=[LabeledPrice(label="Premium", amount=PREMIUM_PRICE_STARS)],
    )
    await callback.answer()


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    await complete_payment(payment.invoice_payload)
    await grant_premium(message.from_user.id)
    await message.answer("🎉 Оплата прошла успешно. Premium активирован!", reply_markup=main_menu_markup())


@dp.callback_query(F.data.startswith("star_toggle_"))
async def callback_star_toggle(callback: CallbackQuery) -> None:
    question_id = int(callback.data.rsplit("_", 1)[-1])
    starred = await toggle_star(callback.from_user.id, question_id)
    await callback.answer("⭐ Добавлено в избранное" if starred else "✖️ Убрано из избранного")


@dp.callback_query(F.data.startswith("daily_answer_"))
async def callback_daily_answer(callback: CallbackQuery) -> None:
    _, _, question_id, selected = callback.data.split("_", 3)
    result = await answer_daily_question(callback.from_user.id, selected)
    if result["already_answered"]:
        await callback.answer("Сегодня вы уже отвечали.", show_alert=True)
        return
    question = result["question"]
    lines = [
        f"{'✅' if result['is_correct'] else '❌'} <b>{'Вы ответили правильно!' if result['is_correct'] else 'Промах'}</b>",
        f"Ответ: <b>{question.correct_answer.upper()}</b>",
    ]
    if question.explanation:
        lines.extend(["", f"📖 {escape(question.explanation)}"])
    lines.extend(["", f"📊 Правильно ответили: <b>{result['correct_percent']}%</b>"])
    if result["most_wrong"]:
        wrong_key, wrong_count = result["most_wrong"]
        lines.append(f"Самый частый промах: <b>{wrong_key.upper()}</b> ({wrong_count})")
    await respond(callback, "\n".join(lines), reply_markup=daily_menu_markup())


@dp.callback_query(F.data == "broadcast_confirm")
async def callback_broadcast_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not has_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    data = await state.get_data()
    text = data.get("broadcast_text")
    premium_only = bool(data.get("premium_only"))
    if not text:
        await callback.answer("Нет текста для рассылки.", show_alert=True)
        return
    users = await get_active_users(days=90, premium_only=premium_only)
    sent = 0
    failed = 0
    blocked = 0
    if bot is None:
        await callback.answer("Бот не инициализирован.", show_alert=True)
        return
    for user in users:
        try:
            await bot.send_message(user.telegram_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            blocked += 1
        except Exception:
            failed += 1
    await log_broadcast("premium" if premium_only else "all", text, sent, failed, blocked, callback.from_user.id)
    await state.clear()
    await respond(callback, f"📢 Рассылка завершена.\n✅ Отправлено: {sent}\n🚫 Заблокировали: {blocked}\n❌ Ошибки: {failed}", reply_markup=main_menu_markup())


@dp.callback_query(F.data.startswith("answer_"))
async def callback_answer_router(callback: CallbackQuery) -> None:
    try:
        _, mode, question_id, selected_answer = callback.data.split("_", 3)
        if mode not in MODE_VALUES:
            raise ValueError
        await handle_session_answer(callback, mode, int(question_id), selected_answer)
    except ValueError:
        await callback.answer("Не удалось обработать ответ.", show_alert=True)


@dp.callback_query(F.data.startswith("next_"))
async def callback_next_router(callback: CallbackQuery) -> None:
    mode = callback.data.split("_", 1)[1]
    if mode not in MODE_VALUES:
        await callback.answer("Неизвестный режим.", show_alert=True)
        return
    session = active_sessions.get(callback.from_user.id)
    if session is None or session.mode != mode:
        await callback.answer("Сессия уже завершена.", show_alert=True)
        return
    await show_question(callback, session)


@dp.callback_query(F.data.startswith("finish_"))
async def callback_finish_router(callback: CallbackQuery) -> None:
    mode = callback.data.split("_", 1)[1]
    if mode not in MODE_VALUES:
        await callback.answer("Неизвестный режим.", show_alert=True)
        return
    session = active_sessions.get(callback.from_user.id)
    if session is None or session.mode != mode:
        await callback.answer("Сессия уже завершена.", show_alert=True)
        return
    await finish_session(callback, session)


@dp.callback_query(F.data == "reset_progress")
async def callback_reset_progress(callback: CallbackQuery) -> None:
    text = "\n".join(
        [
            "<b>🗑 Сбросить прогресс?</b>",
            "",
            "Будут очищены ответы, экзамены, достижения, дуэли, маршрут и внутренняя статистика.",
            "Premium, настройки, промокоды и профиль сохранятся.",
        ]
    )
    await respond(callback, text, reply_markup=reset_progress_markup())


@dp.callback_query(F.data == "reset_progress_confirm")
async def callback_reset_progress_confirm(callback: CallbackQuery) -> None:
    active_sessions.pop(callback.from_user.id, None)
    success = await reset_user_progress(callback.from_user.id)
    if not success:
        await callback.answer("Профиль не найден.", show_alert=True)
        return
    await respond(callback, "Прогресс сброшен. Можно начинать путь заново.", reply_markup=profile_menu_markup())


@dp.callback_query(F.data == "snooze_3d")
async def callback_snooze_reminders(callback: CallbackQuery) -> None:
    await update_user(
        callback.from_user.id,
        reminder_snoozed_until=datetime.utcnow() + timedelta(days=3),
    )
    await respond(callback, "Напоминания отложены на 3 дня.", reply_markup=profile_menu_markup())


@dp.callback_query(F.data == "disable_reminders")
async def callback_disable_reminders(callback: CallbackQuery) -> None:
    await update_user(
        callback.from_user.id,
        daily_reminder=False,
        reminder_snoozed_until=None,
    )
    await respond(callback, "Утренние сигналы выключены.", reply_markup=profile_menu_markup())


@dp.callback_query(F.data == "disable_forever")
async def callback_disable_forever(callback: CallbackQuery) -> None:
    await update_user(
        callback.from_user.id,
        daily_reminder=False,
        all_notifications_off=True,
        reminder_snoozed_until=None,
    )
    await respond(callback, "Все уведомления отключены.", reply_markup=profile_menu_markup())


@dp.message(F.text)
async def fallback_message(message: Message, state: FSMContext) -> None:
    if await state.get_state():
        return
    if message.text and message.text.startswith("/"):
        await message.answer("Команда не распознана. Используйте /start или меню ниже.", reply_markup=main_menu_markup())
        return
    if message.from_user.id in active_sessions:
        await message.answer("Во время сессии отвечайте кнопками под вопросом или вернитесь в лагерь.", reply_markup=main_menu_markup())
        return
    await show_camp(message)


def build_reminder_text(user, reminder_type: str) -> str:
    quote = random_quote()
    if reminder_type == "gentle_reminder":
        return "\n".join(
            [
                "<b>🔔 Утренний сигнал ONEHUNT</b>",
                "",
                quote,
                "Откройте лагерь и сделайте хотя бы 5 вопросов, чтобы сохранить темп.",
            ]
        )
    if reminder_type == "streak_warning":
        return "\n".join(
            [
                "<b>🔥 Серия под угрозой</b>",
                "",
                f"У вас уже {user.streak_days} дней подряд. Один короткий заход сегодня сохранит серию.",
                quote,
            ]
        )
    if reminder_type == "week_away":
        return "\n".join(
            [
                "<b>🧭 Лагерь ждёт вас</b>",
                "",
                "Неделя без практики заметно замедляет рост точности. Вернитесь на 10 минут и снова поймайте ритм.",
                quote,
            ]
        )
    if reminder_type == "two_weeks_away":
        return "\n".join(
            [
                "<b>📅 Пора вернуться на маршрут</b>",
                "",
                "Две недели паузы уже ощущаются. Начните с Быстрого вопроса или Вопроса дня и мягко войдите обратно.",
                quote,
            ]
        )
    return "\n".join(
        [
            "<b>🏕 ONEHUNT напоминает о себе</b>",
            "",
            "Вы давно не заходили. Пара коротких сессий поможет снова выйти к цели 75%+.",
            quote,
        ]
    )


async def detect_reminder_type(user) -> str | None:
    now_utc = datetime.utcnow()
    last_seen = user.last_seen_at or user.created_at
    inactivity = now_utc - last_seen
    local_now = datetime.now(get_app_timezone())

    if user.all_notifications_off:
        return None
    if user.reminder_snoozed_until and user.reminder_snoozed_until > now_utc:
        return None
    if user.daily_reminder and local_now.hour == user.reminder_hour:
        if await should_send_reminder(user.telegram_id, "gentle_reminder"):
            return "gentle_reminder"
    if inactivity >= timedelta(days=30) and await should_send_reminder(user.telegram_id, "month_away"):
        return "month_away"
    if inactivity >= timedelta(days=14) and await should_send_reminder(user.telegram_id, "two_weeks_away"):
        return "two_weeks_away"
    if inactivity >= timedelta(days=7) and await should_send_reminder(user.telegram_id, "week_away"):
        return "week_away"
    if inactivity >= timedelta(hours=24) and user.streak_days > 0:
        if await should_send_reminder(user.telegram_id, "streak_warning"):
            return "streak_warning"
    return None


async def send_reminders_job() -> None:
    if bot is None:
        return
    users = await get_active_users(days=3650)
    for user in users:
        reminder_type = await detect_reminder_type(user)
        if reminder_type is None:
            continue
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=build_reminder_text(user, reminder_type),
                reply_markup=reminder_markup(),
            )
            await log_reminder(user.telegram_id, reminder_type)
            await asyncio.sleep(0.05)
        except TelegramForbiddenError:
            continue
        except Exception:
            logger.exception("Failed to send reminder to %s", user.telegram_id)


async def cleanup_sessions_job() -> None:
    now = datetime.utcnow()
    stale_users = [
        user_id
        for user_id, session in active_sessions.items()
        if now - session.started_at > timedelta(hours=4)
    ]
    for user_id in stale_users:
        active_sessions.pop(user_id, None)


async def register_bot_commands() -> None:
    if bot is None:
        return
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Открыть лагерь"),
                BotCommand(command="help", description="Показать справку"),
                BotCommand(command="admin", description="Открыть админ-панель"),
            ],
            request_timeout=30,
        )
    except Exception:
        logger.exception("Failed to set bot commands, continuing startup.")
    if MINIAPP_URL and MINIAPP_URL.lower().startswith("https://"):
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="ONEHUNT App",
                    web_app=WebAppInfo(url=MINIAPP_URL),
                ),
                request_timeout=30,
            )
        except Exception:
            logger.exception("Failed to configure Mini App menu button.")


def setup_scheduler() -> AsyncIOScheduler:
    instance = AsyncIOScheduler(timezone=get_app_timezone())
    instance.add_job(send_reminders_job, "interval", hours=1, id="reminders", replace_existing=True)
    instance.add_job(cleanup_sessions_job, "interval", minutes=15, id="cleanup_sessions", replace_existing=True)
    return instance


async def main() -> None:
    global bot, scheduler

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is empty. Fill it in .env before запуском бота.")

    await init_db()
    await seed_reference_data()

    bot = Bot(
        token=BOT_TOKEN,
        session=build_bot_session(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    scheduler = setup_scheduler()
    scheduler.start()

    logger.info("ONEHUNT bot is starting.")
    await register_bot_commands()
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if scheduler and scheduler.running:
            scheduler.shutdown(wait=False)
        if bot:
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
