from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from database.database import async_session
from database.models import User, WebAccount, WebSession
from utils.constants import DEFAULT_SETTINGS


WEB_SESSION_DAYS = 30
WEB_USER_ID_BASE = 700_000_000_000


class WebAuthError(ValueError):
    """Raised when web authentication validation fails."""


@dataclass(slots=True)
class WebAuthIdentity:
    user: User
    account: WebAccount


def utcnow() -> datetime:
    return datetime.utcnow()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected = password_hash.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return hmac.compare_digest(actual, expected)


async def _generate_web_user_id(session) -> int:
    while True:
        candidate = WEB_USER_ID_BASE + uuid.uuid4().int % 999_999_999
        existing = await session.scalar(select(User.telegram_id).where(User.telegram_id == candidate))
        if existing is None:
            return candidate


async def create_web_account(email: str, password: str, display_name: str | None = None) -> User:
    normalized_email = normalize_email(email)
    clean_name = (display_name or "").strip() or normalized_email.split("@", 1)[0]

    if len(password) < 8:
        raise WebAuthError("Пароль должен быть не короче 8 символов.")

    async with async_session() as session:
        existing_account = await session.scalar(select(WebAccount).where(WebAccount.email == normalized_email))
        if existing_account is not None:
            raise WebAuthError("Аккаунт с таким email уже существует.")

        user_id = await _generate_web_user_id(session)
        user = User(
            telegram_id=user_id,
            username=normalized_email.split("@", 1)[0],
            first_name=clean_name,
            last_name=None,
            settings=dict(DEFAULT_SETTINGS),
            daily_reminder=False,
            access_level="free",
        )
        session.add(user)
        session.add(
            WebAccount(
                user_id=user_id,
                email=normalized_email,
                password_hash=hash_password(password),
                display_name=clean_name,
            )
        )
        await session.commit()
        await session.refresh(user)
        return user


async def authenticate_web_account(email: str, password: str) -> WebAuthIdentity:
    normalized_email = normalize_email(email)
    async with async_session() as session:
        account = await session.scalar(select(WebAccount).where(WebAccount.email == normalized_email))
        if account is None or not verify_password(password, account.password_hash):
            raise WebAuthError("Неверный email или пароль.")

        user = await session.scalar(select(User).where(User.telegram_id == account.user_id))
        if user is None:
            raise WebAuthError("Профиль не найден. Попробуйте зарегистрироваться заново.")

        return WebAuthIdentity(user=user, account=account)


async def create_web_session(user_id: int, user_agent: str | None = None, ip_address: str | None = None) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = utcnow() + timedelta(days=WEB_SESSION_DAYS)
    async with async_session() as session:
        await session.execute(delete(WebSession).where(WebSession.user_id == user_id))
        session.add(
            WebSession(
                session_token=token,
                user_id=user_id,
                user_agent=(user_agent or "")[:255] or None,
                ip_address=(ip_address or "")[:64] or None,
                expires_at=expires_at,
            )
        )
        await session.commit()
    return token


async def get_user_by_session(token: str | None) -> User | None:
    if not token:
        return None

    async with async_session() as session:
        web_session = await session.scalar(select(WebSession).where(WebSession.session_token == token))
        if web_session is None:
            return None
        if web_session.expires_at <= utcnow():
            await session.delete(web_session)
            await session.commit()
            return None

        web_session.last_seen_at = utcnow()
        user = await session.scalar(select(User).where(User.telegram_id == web_session.user_id))
        await session.commit()
        return user


async def delete_web_session(token: str | None) -> None:
    if not token:
        return
    async with async_session() as session:
        await session.execute(delete(WebSession).where(WebSession.session_token == token))
        await session.commit()
