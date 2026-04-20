from __future__ import annotations

from typing import Any

from aiohttp import ClientSession

from config import (
    CRYPTO_PAY_ACCEPTED_ASSETS,
    CRYPTO_PAY_API_BASE_URL,
    CRYPTO_PAY_API_TOKEN,
    CRYPTO_PAY_EXPIRES_IN,
    CRYPTO_PAY_RETURN_URL,
    MINIAPP_URL,
)
from utils.constants import PREMIUM_PRICES


class CryptoPayError(RuntimeError):
    pass


def crypto_pay_configured() -> bool:
    return bool(CRYPTO_PAY_API_TOKEN)


async def _request(method: str, payload: dict[str, Any] | None = None) -> Any:
    if not crypto_pay_configured():
        raise CryptoPayError("Crypto Bot payment is not configured yet.")

    url = f"{CRYPTO_PAY_API_BASE_URL}/{method}"
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_API_TOKEN}

    async with ClientSession(headers=headers) as session:
        async with session.post(url, json=payload or {}) as response:
            data = await response.json(content_type=None)

    if response.status >= 400:
        error_text = data.get("error") if isinstance(data, dict) else None
        raise CryptoPayError(error_text or f"Crypto Bot API returned HTTP {response.status}.")

    if not isinstance(data, dict) or not data.get("ok"):
        error_text = data.get("error") if isinstance(data, dict) else None
        raise CryptoPayError(error_text or "Crypto Bot API request failed.")

    return data.get("result")


def invoice_checkout_url(invoice: dict[str, Any], prefer: str = "miniapp") -> str | None:
    fields_by_preference = {
        "miniapp": ["mini_app_invoice_url", "bot_invoice_url", "web_app_invoice_url", "pay_url"],
        "bot": ["bot_invoice_url", "mini_app_invoice_url", "web_app_invoice_url", "pay_url"],
        "web": ["web_app_invoice_url", "mini_app_invoice_url", "bot_invoice_url", "pay_url"],
    }
    for field in fields_by_preference.get(prefer, fields_by_preference["miniapp"]):
        value = str(invoice.get(field, "") or "").strip()
        if value:
            return value
    return None


async def create_premium_invoice(user_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "currency_type": "fiat",
        "fiat": "RUB",
        "amount": str(PREMIUM_PRICES["rub"]),
        "description": "ONEHUNT PREMIUM - полный доступ, гайд и 12 чек-листов.",
        "hidden_message": "После оплаты вернитесь в ONEHUNT и нажмите проверку, чтобы активировать PREMIUM.",
        "payload": f"premium:{user_id}",
        "expires_in": CRYPTO_PAY_EXPIRES_IN,
        "allow_anonymous": False,
        "allow_comments": False,
    }

    accepted_assets = CRYPTO_PAY_ACCEPTED_ASSETS.strip()
    if accepted_assets:
        payload["accepted_assets"] = accepted_assets

    return_url = (CRYPTO_PAY_RETURN_URL or MINIAPP_URL).strip()
    if return_url.startswith(("https://", "http://")):
        payload["paid_btn_name"] = "callback"
        payload["paid_btn_url"] = return_url

    result = await _request("createInvoice", payload)
    if not isinstance(result, dict):
        raise CryptoPayError("Crypto Bot invoice response is invalid.")
    return result


async def get_invoice(invoice_id: int) -> dict[str, Any]:
    result = await _request("getInvoices", {"invoice_ids": str(invoice_id)})
    if not isinstance(result, dict):
        raise CryptoPayError("Crypto Bot invoice list response is invalid.")

    items = result.get("items") or []
    if not items:
        raise CryptoPayError("Crypto Bot invoice was not found.")
    if not isinstance(items[0], dict):
        raise CryptoPayError("Crypto Bot invoice payload is invalid.")
    return items[0]


def invoice_status_label(status: str) -> str:
    mapping = {
        "active": "Ожидает оплату",
        "paid": "Оплачен",
        "expired": "Счет истек",
    }
    return mapping.get(status, status)
