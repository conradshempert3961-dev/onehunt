from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

from config import BOT_TOKEN, MINIAPP_DEV_USER_ID


@dataclass(slots=True)
class MiniAppIdentity:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    is_telegram: bool = False


def _build_secret_key() -> bytes:
    return hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()


def validate_init_data(init_data: str, max_age: timedelta = timedelta(hours=12)) -> MiniAppIdentity | None:
    if not BOT_TOKEN or not init_data:
        return None

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    calculated_hash = hmac.new(
        _build_secret_key(),
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    auth_date = values.get("auth_date")
    if auth_date and auth_date.isdigit():
        auth_time = datetime.fromtimestamp(int(auth_date), tz=timezone.utc)
        if datetime.now(tz=timezone.utc) - auth_time > max_age:
            return None

    user_payload = values.get("user")
    if not user_payload:
        return None
    try:
        user = json.loads(user_payload)
    except json.JSONDecodeError:
        return None

    telegram_id = int(user.get("id") or 0)
    if not telegram_id:
        return None

    return MiniAppIdentity(
        telegram_id=telegram_id,
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
        is_telegram=True,
    )


def build_dev_identity() -> MiniAppIdentity | None:
    if not MINIAPP_DEV_USER_ID:
        return None
    return MiniAppIdentity(
        telegram_id=MINIAPP_DEV_USER_ID,
        username="dev_user",
        first_name="ONEHUNT",
        last_name="Dev",
        is_telegram=False,
    )
