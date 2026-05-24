from datetime import datetime, timezone
from typing import Any

from connectors.google_sheets import get_user_record, update_user_record


FREE_TIER_LIMIT = 10


class AccessDenied(Exception):
    pass


def check_access(telegram_id: int) -> dict[str, Any]:
    """
    Returns the user record if access is granted.
    Raises AccessDenied with a reason code if not.
    """
    user = get_user_record(telegram_id)

    if user is None:
        raise AccessDenied("not_registered")

    role = user.get("role", "free")

    if role in ("admin", "tester"):
        return user

    if role == "pending":
        raise AccessDenied("pending")

    if role == "rejected":
        raise AccessDenied("rejected")

    if role == "subscriber":
        expires_at = user.get("expires_at")
        if expires_at and _parse_dt(expires_at) > datetime.now(timezone.utc):
            return user
        # Subscription expired — downgrade gracefully, don't block outright
        update_user_record(telegram_id, {"role": "free", "subscription_status": "expired"})
        user["role"] = "free"
        user["subscription_status"] = "expired"

    requests_used = int(user.get("requests_used", 0))
    if requests_used < FREE_TIER_LIMIT:
        update_user_record(telegram_id, {"requests_used": requests_used + 1})
        return user

    raise AccessDenied("limit_reached")


def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
