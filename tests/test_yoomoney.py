import hashlib
import hmac
from urllib.parse import quote

from services import yoomoney


def test_build_payment_label() -> None:
    assert yoomoney.build_payment_label(123, 456).endswith("-123-456")


def test_verify_notification_with_sign(monkeypatch) -> None:
    monkeypatch.setattr(yoomoney, "YOOMONEY_NOTIFICATION_SECRET", "secret-key")
    payload = {
        "notification_type": "p2p-incoming",
        "operation_id": "op-1",
        "amount": "100.00",
        "currency": "643",
        "datetime": "2026-05-03T10:00:00Z",
        "sender": "4100111111111111",
        "codepro": "false",
        "label": "onehunt-1-2",
    }
    prepared = "&".join(
        f"{key}={quote(str(value), safe='-._~')}"
        for key, value in sorted(payload.items())
    )
    payload["sign"] = hmac.new(b"secret-key", prepared.encode("utf-8"), hashlib.sha256).hexdigest()
    assert yoomoney.verify_notification(payload) is True


def test_verify_notification_with_legacy_sha1(monkeypatch) -> None:
    monkeypatch.setattr(yoomoney, "YOOMONEY_NOTIFICATION_SECRET", "legacy-secret")
    payload = {
        "notification_type": "card-incoming",
        "operation_id": "753525659460074104",
        "amount": "9.70",
        "currency": "643",
        "datetime": "2023-11-17T12:40:00Z",
        "sender": "",
        "codepro": "false",
        "label": "onehunt-77-15",
    }
    raw = "&".join(
        [
            payload["notification_type"],
            payload["operation_id"],
            payload["amount"],
            payload["currency"],
            payload["datetime"],
            payload["sender"],
            payload["codepro"],
            "legacy-secret",
            payload["label"],
        ]
    )
    payload["sha1_hash"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    assert yoomoney.verify_notification(payload) is True


def test_matches_requested_amount_without_withdraw_amount() -> None:
    assert yoomoney.matches_requested_amount({"amount": "970.00"}, 990) is True


def test_matches_requested_amount_with_withdraw_amount() -> None:
    assert yoomoney.matches_requested_amount({"withdraw_amount": "990.00"}, 990) is True
    assert yoomoney.matches_requested_amount({"withdraw_amount": "980.00"}, 990) is False
