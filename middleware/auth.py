from datetime import datetime, timezone
from connectors.google_sheets import get_user_record, update_user_record


FREE_TIER_LIMIT = 10


class AccessDenied(Exception):
    pass


def check_access(telegram_id: int) -> bool:
    """
    Returns True if user can proceed.
    Raises AccessDenied with a user-facing message if not.
    """
    user = get_user_record(telegram_id)

    if user is None:
        raise AccessDenied("not_registered")

    role = user.get("role", "free")

    if role in ("admin", "tester"):
        return True

    if role == "subscriber":
        expires_at = user.get("expires_at")
        if expires_at and _parse_dt(expires_at) > datetime.now(timezone.utc):
            return True
        # Subscription expired — downgrade gracefully, don't block outright
        update_user_record(telegram_id, {"role": "free", "subscription_status": "expired"})

    requests_used = int(user.get("requests_used", 0))
    if requests_used < FREE_TIER_LIMIT:
        update_user_record(telegram_id, {"requests_used": requests_used + 1})
        return True

    raise AccessDenied("limit_reached")


def _parse_dt(value: str) -> datetime:
    # ISO 8601, always UTC
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
