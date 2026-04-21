from __future__ import annotations

import uuid

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import LabeledPrice

from config import BOT_TOKEN, TELEGRAM_PROXY
from utils.constants import PREMIUM_PRICES


class TelegramStarsError(RuntimeError):
    """Raised when Telegram Stars checkout cannot be created."""


def telegram_stars_configured() -> bool:
    return bool(BOT_TOKEN)


async def create_premium_stars_invoice(user_id: int) -> dict[str, str]:
    if not BOT_TOKEN:
        raise TelegramStarsError("Telegram Stars недоступны: BOT_TOKEN пустой.")

    payload = f"premium_stars_{user_id}_{uuid.uuid4().hex}"
    session_kwargs: dict[str, str] = {}
    if TELEGRAM_PROXY:
        session_kwargs["proxy"] = TELEGRAM_PROXY

    session = AiohttpSession(**session_kwargs)
    bot = Bot(BOT_TOKEN, session=session)

    try:
        invoice_link = await bot.create_invoice_link(
            title="ONEHUNT PREMIUM",
            description=(
                "Полный маршрут подготовки, экзамен, карточки, разбор ошибок, "
                "AI-ассистент и доступ без лимитов."
            ),
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label="ONEHUNT PREMIUM", amount=PREMIUM_PRICES["stars"])],
        )
    except Exception as exc:  # pragma: no cover - depends on Telegram API
        raise TelegramStarsError(f"Не удалось создать счет Telegram Stars: {exc}") from exc
    finally:
        await bot.session.close()

    return {
        "payload": payload,
        "invoice_link": invoice_link,
    }
