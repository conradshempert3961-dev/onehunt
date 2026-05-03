from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

from aiohttp import ClientSession

from config import (
    YOOMONEY_ACCESS_TOKEN,
    YOOMONEY_LABEL_PREFIX,
    YOOMONEY_NOTIFICATION_SECRET,
    YOOMONEY_RETURN_URL,
    YOOMONEY_WALLET,
)
from utils.constants import PREMIUM_PRICES

YOOMONEY_API_BASE = "https://yoomoney.ru/api"
YOOMONEY_QUICKPAY_URL = "https://yoomoney.ru/quickpay/confirm"


class YooMoneyError(RuntimeError):
    pass


def yoomoney_configured() -> bool:
    return bool(YOOMONEY_WALLET)


def yoomoney_history_configured() -> bool:
    return bool(YOOMONEY_ACCESS_TOKEN)


def yoomoney_notifications_configured() -> bool:
    return bool(YOOMONEY_NOTIFICATION_SECRET)


def build_payment_label(user_id: int, payment_id: int) -> str:
    return f"{YOOMONEY_LABEL_PREFIX}-{user_id}-{payment_id}"


def build_quickpay_form(label: str, amount_rub: int) -> dict[str, str]:
    if not yoomoney_configured():
        raise YooMoneyError("YooMoney is not configured yet.")

    return {
        "receiver": YOOMONEY_WALLET,
        "label": label,
        "quickpay-form": "button",
        "targets": "ONEHUNT PREMIUM",
        "sum": f"{Decimal(amount_rub):.2f}",
        "successURL": YOOMONEY_RETURN_URL,
    }


def notification_status_label(status: str) -> str:
    labels = {
        "pending": "Waiting for payment confirmation",
        "in_progress": "Payment is still being processed",
        "completed": "Payment confirmed",
        "success": "Payment confirmed",
        "refused": "Payment was cancelled or refused",
    }
    return labels.get(status, status)


def _as_string_map(payload: dict[str, Any]) -> dict[str, str]:
    return {str(key): str(value or "") for key, value in payload.items()}


def _urlencode_value(value: str) -> str:
    return quote(value, safe="-._~")


def verify_notification(payload: dict[str, Any]) -> bool:
    values = _as_string_map(payload)
    sign = values.get("sign", "").strip().lower()
    if sign and yoomoney_notifications_configured():
        unsigned = {
            key: values[key]
            for key in sorted(values.keys())
            if key != "sign"
        }
        prepared = "&".join(f"{key}={_urlencode_value(unsigned[key])}" for key in unsigned)
        digest = hmac.new(
            YOOMONEY_NOTIFICATION_SECRET.encode("utf-8"),
            prepared.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, sign)

    legacy_hash = values.get("sha1_hash", "").strip().lower()
    if not legacy_hash or not yoomoney_notifications_configured():
        return False

    raw = "&".join(
        [
            values.get("notification_type", ""),
            values.get("operation_id", ""),
            values.get("amount", ""),
            values.get("currency", ""),
            values.get("datetime", ""),
            values.get("sender", ""),
            values.get("codepro", ""),
            YOOMONEY_NOTIFICATION_SECRET,
            values.get("label", ""),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, legacy_hash)


async def _api_request(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not yoomoney_history_configured():
        raise YooMoneyError("YooMoney access token is not configured.")

    headers = {
        "Authorization": f"Bearer {YOOMONEY_ACCESS_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    async with ClientSession(headers=headers) as session:
        async with session.post(f"{YOOMONEY_API_BASE}/{method}", data=payload) as response:
            data = await response.json(content_type=None)

    if response.status >= 400:
        raise YooMoneyError(f"YooMoney API returned HTTP {response.status}.")
    if not isinstance(data, dict):
        raise YooMoneyError("YooMoney API returned an invalid payload.")
    if data.get("error"):
        raise YooMoneyError(f"YooMoney API error: {data['error']}")
    return data


async def get_operation_by_label(label: str) -> dict[str, Any] | None:
    data = await _api_request(
        "operation-history",
        {
            "label": label,
            "records": "10",
            "details": "true",
        },
    )
    operations = data.get("operations") or []
    if not operations:
        return None
    operation = operations[0]
    if not isinstance(operation, dict):
        raise YooMoneyError("YooMoney returned an invalid operation payload.")
    return operation


async def get_operation_details(operation_id: str) -> dict[str, Any]:
    data = await _api_request("operation-details", {"operation_id": operation_id})
    if not isinstance(data, dict):
        raise YooMoneyError("YooMoney returned invalid operation details.")
    return data


def is_successful_operation(operation: dict[str, Any], expected_label: str) -> bool:
    status = str(operation.get("status", "")).lower()
    label = str(operation.get("label", "")).strip()
    direction = str(operation.get("direction", "")).lower()
    return status == "success" and label == expected_label and direction == "in"


def extract_paid_amount(operation: dict[str, Any]) -> Decimal | None:
    for key in ("withdraw_amount", "amount"):
        raw_value = operation.get(key)
        if raw_value in (None, ""):
            continue
        try:
            return Decimal(str(raw_value))
        except (InvalidOperation, ValueError):
            continue
    return None


def matches_requested_amount(operation: dict[str, Any], amount_rub: int) -> bool:
    raw_value = operation.get("withdraw_amount")
    if raw_value in (None, ""):
        return True
    try:
        paid = Decimal(str(raw_value))
    except (InvalidOperation, ValueError):
        return True
    return paid.quantize(Decimal("0.01")) >= Decimal(amount_rub).quantize(Decimal("0.01"))


def build_checkout_html(label: str, amount_rub: int) -> str:
    form = build_quickpay_form(label, amount_rub)
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ONEHUNT x YooMoney</title>
    <style>
        :root {{
            color-scheme: light;
            --bg: #f3f7f2;
            --panel: #ffffff;
            --text: #15221a;
            --soft: #617569;
            --line: rgba(21, 34, 26, 0.1);
            --primary: #2f8f53;
            --primary-dark: #216a3c;
            --shadow: 0 30px 80px rgba(34, 71, 55, 0.16);
            --radius: 28px;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 24px;
            font-family: "Segoe UI", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at 10% 10%, rgba(47, 143, 83, 0.18), transparent 24%),
                radial-gradient(circle at 100% 0%, rgba(212, 178, 114, 0.2), transparent 22%),
                linear-gradient(180deg, #f8fcf8, var(--bg));
        }}
        .panel {{
            width: min(100%, 560px);
            padding: 30px;
            border: 1px solid var(--line);
            border-radius: var(--radius);
            background: rgba(255, 255, 255, 0.92);
            box-shadow: var(--shadow);
        }}
        h1 {{
            margin: 0 0 10px;
            font-size: clamp(2rem, 6vw, 3rem);
            line-height: 0.96;
        }}
        p {{
            margin: 0;
            color: var(--soft);
            line-height: 1.6;
        }}
        .price {{
            margin: 18px 0 22px;
            padding: 16px 18px;
            border-radius: 18px;
            background: #f4faf5;
            border: 1px solid rgba(47, 143, 83, 0.12);
            color: var(--primary-dark);
            font-weight: 700;
        }}
        .actions {{
            display: grid;
            gap: 12px;
            margin-top: 22px;
        }}
        button {{
            min-height: 54px;
            border: 0;
            border-radius: 18px;
            font: inherit;
            font-weight: 700;
            cursor: pointer;
        }}
        .primary {{
            background: linear-gradient(135deg, var(--primary), #42a868);
            color: white;
        }}
        .secondary {{
            background: #eff6f0;
            color: var(--text);
            border: 1px solid var(--line);
        }}
        .meta {{
            margin-top: 18px;
            font-size: 0.92rem;
        }}
    </style>
</head>
<body>
    <main class="panel">
        <p>ONEHUNT PREMIUM</p>
        <h1>Оплата через YooMoney</h1>
        <p>Выберите удобный способ оплаты. После подтверждения платежа вернитесь в ONEHUNT и обновите статус.</p>
        <div class="price">Сумма к оплате: {PREMIUM_PRICES["rub"]} RUB</div>
        <form method="POST" action="{YOOMONEY_QUICKPAY_URL}">
            <input type="hidden" name="receiver" value="{form["receiver"]}">
            <input type="hidden" name="label" value="{form["label"]}">
            <input type="hidden" name="quickpay-form" value="{form["quickpay-form"]}">
            <input type="hidden" name="targets" value="{form["targets"]}">
            <input type="hidden" name="sum" value="{form["sum"]}">
            <input type="hidden" name="successURL" value="{form["successURL"]}">
            <div class="actions">
                <button class="primary" type="submit" name="paymentType" value="AC">Оплатить банковской картой</button>
                <button class="secondary" type="submit" name="paymentType" value="PC">Оплатить из кошелька YooMoney</button>
            </div>
        </form>
        <p class="meta">Метка платежа: {label}</p>
    </main>
</body>
</html>"""
