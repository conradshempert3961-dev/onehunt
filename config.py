from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from utils.constants import BLOCKS, FREE_LIMITS, PREMIUM_PRICES, RANKS, XP_LEVELS, XP_RULES

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{(BASE_DIR / 'onehunt.db').as_posix()}",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ADMIN_IDS = [
    int(item.strip())
    for item in os.getenv("ADMIN_IDS", "").split(",")
    if item.strip().isdigit()
]

QUESTIONS_FILE = os.getenv("QUESTIONS_FILE", str(BASE_DIR / "questions.json"))
EXPORT_DIR = os.getenv("EXPORT_DIR", str(BASE_DIR / "data"))
ANIMAL_CARDS_FILE = os.getenv("ANIMAL_CARDS_FILE", str(BASE_DIR / "data" / "animal_cards.json"))
QUOTES_FILE = os.getenv("QUOTES_FILE", str(BASE_DIR / "data" / "quotes.json"))

USE_REDIS_FSM = os.getenv("USE_REDIS_FSM", "false").lower() == "true"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Moscow")
FREE_MODE = os.getenv("FREE_MODE", "true").lower() == "true"
ANSWER_BUTTONS_LAYOUT = os.getenv("ANSWER_BUTTONS_LAYOUT", "single_row")
MINIAPP_URL = os.getenv("MINIAPP_URL", "")
MINIAPP_DEV_USER_ID = int(os.getenv("MINIAPP_DEV_USER_ID", "0") or 0)
MINIAPP_PORT = int(os.getenv("MINIAPP_PORT", "8080"))
MINIAPP_SESSION_TTL_MINUTES = int(os.getenv("MINIAPP_SESSION_TTL_MINUTES", "240"))
MINIAPP_BROWSER_DEMO = os.getenv("MINIAPP_BROWSER_DEMO", "false").lower() == "true"
MINIAPP_BROWSER_DEMO_HOSTS = {
    item.strip().lower()
    for item in os.getenv("MINIAPP_BROWSER_DEMO_HOSTS", "localhost,127.0.0.1,::1").split(",")
    if item.strip()
}
TELEGRAM_PROXY = os.getenv("TELEGRAM_PROXY", "").strip()

TELEGRAM_STARS_PROVIDER_TOKEN = os.getenv("TELEGRAM_STARS_PROVIDER_TOKEN", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://t.me/onehunt_exam_bot")
PAYMENTS_WEBHOOK_SECRET = os.getenv("PAYMENTS_WEBHOOK_SECRET", "")

EXAM_QUESTIONS = int(os.getenv("EXAM_QUESTIONS", "257"))
EXAM_PASS_PERCENT = int(os.getenv("EXAM_PASS_PERCENT", "75"))
BLOCK_QUESTIONS = int(os.getenv("BLOCK_QUESTIONS", "10"))
TRAIL_FREE_LIMIT = FREE_LIMITS["trail_per_block"]
TRAINING_FREE_LIMIT = FREE_LIMITS["trainings"]
PREMIUM_PRICE_RUB = PREMIUM_PRICES["rub"]
PREMIUM_PRICE_STARS = PREMIUM_PRICES["stars"]

XP_TABLE = XP_RULES
