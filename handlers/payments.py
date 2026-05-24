"""LiqPay payment webhook and subscription utilities."""

import base64
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Form, status

from connectors.secrets import get_secret
from connectors.google_sheets import get_user_record, update_user_record

log = logging.getLogger(__name__)
router = APIRouter()

_SUBSCRIPTION_DAYS = 30
PRICE_USD = 15
_CURRENCY = "USD"

# Cached per container instance — keys don't change at runtime
_liqpay_keys: tuple[str, str] | None = None


def _keys() -> tuple[str, str]:
    """Return (public_key, private_key), fetched once from Secret Manager."""
    global _liqpay_keys
    if _liqpay_keys is None:
        _liqpay_keys = (get_secret("liqpay-public-key"), get_secret("liqpay-private-key"))
    return _liqpay_keys


def _sign(data: str, private_key: str) -> str:
    raw = (private_key + data + private_key).encode("utf-8")
    return base64.b64encode(hashlib.sha1(raw).digest()).decode("utf-8")


def _verify(data: str, signature: str, private_key: str) -> bool:
    return _sign(data, private_key) == signature


# ---------------------------------------------------------------------------
# Public utilities — used by telegram.py /subscribe command
# ---------------------------------------------------------------------------

def generate_payment_link(telegram_id: int) -> str:
    public_key, private_key = _keys()
    order_id = f"fopai_{telegram_id}_{int(datetime.now(timezone.utc).timestamp())}"

    payload = {
        "version": 3,
        "public_key": public_key,
        "action": "pay",
        "amount": PRICE_USD,
        "currency": _CURRENCY,
        "description": "FopAI — підписка на 30 днів",
        "order_id": order_id,
        "language": "uk",
    }

    data = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode()).decode()
    signature = _sign(data, private_key)
    return f"https://www.liqpay.ua/api/3/checkout?data={data}&signature={signature}"


def activate_subscription(telegram_id: int) -> None:
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=_SUBSCRIPTION_DAYS)
    ).isoformat()
    update_user_record(telegram_id, {
        "role": "subscriber",
        "subscription_status": "active",
        "expires_at": expires_at,
    })
    log.info("subscription activated: user=%s expires=%s", telegram_id, expires_at)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@router.post("/liqpay", status_code=status.HTTP_200_OK)
async def liqpay_webhook(
    data: str = Form(...),
    signature: str = Form(...),
) -> dict:
    """
    LiqPay POSTs application/x-www-form-urlencoded with `data` and `signature`.
    Always return 200 — LiqPay retries on any non-2xx.
    Only activate on status == "success".
    """
    _, private_key = _keys()

    if not _verify(data, signature, private_key):
        log.warning("liqpay_webhook: invalid signature")
        return {"status": "rejected"}

    payload = json.loads(base64.b64decode(data).decode("utf-8"))
    order_id: str = payload.get("order_id", "")
    payment_status: str = payload.get("status", "")

    log.info("liqpay_webhook: order=%s status=%s", order_id, payment_status)

    if payment_status != "success":
        return {"status": "ignored"}

    # order_id format: "fopai_{telegram_id}_{unix_timestamp}"
    parts = order_id.split("_")
    if len(parts) != 3 or parts[0] != "fopai":
        log.error("liqpay_webhook: malformed order_id=%s", order_id)
        return {"status": "ignored"}  # our bug, don't trigger LiqPay retry

    try:
        telegram_id = int(parts[1])
    except ValueError:
        log.error("liqpay_webhook: non-integer telegram_id in order_id=%s", order_id)
        return {"status": "ignored"}

    if get_user_record(telegram_id) is None:
        log.error("liqpay_webhook: payment for unregistered user=%s", telegram_id)
        return {"status": "ignored"}

    activate_subscription(telegram_id)
    return {"status": "ok"}
