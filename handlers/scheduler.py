"""Cron job endpoints — called by Google Cloud Scheduler.

Cloud Scheduler hits POST /cron/reminders daily.
Auth: Authorization: Bearer {cron-secret} header, verified against Secret Manager.
IAM-level restriction (Cloud Scheduler SA → Cloud Run invoker) should also be configured.
"""

import logging
import os
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.cloud import secretmanager
from telegram import Bot

from connectors.google_sheets import get_all_user_records
from models.user import User

log = logging.getLogger(__name__)
router = APIRouter()
_bearer = HTTPBearer()

_REMINDER_DAYS = 7   # notify this many days before deadline

# (month, day, label, applicable EP groups)
_CALENDAR: list[tuple[int, int, str, frozenset[int]]] = [
    (1,  19, "ЄСВ за 4 квартал",                          frozenset({1, 2, 3})),
    (1,  19, "аванс ЄП за 4 квартал",                     frozenset({1, 2})),
    (2,   1, "річна декларація",                           frozenset({1, 2})),
    (2,  10, "ЄП за 4 квартал (декларація + оплата)",     frozenset({3})),
    (4,  19, "ЄСВ за 1 квартал",                          frozenset({1, 2, 3})),
    (4,  19, "аванс ЄП за 1 квартал",                     frozenset({1, 2})),
    (5,  10, "ЄП за 1 квартал (декларація + оплата)",     frozenset({3})),
    (7,  19, "ЄСВ за 2 квартал",                          frozenset({1, 2, 3})),
    (7,  19, "аванс ЄП за 2 квартал",                     frozenset({1, 2})),
    (8,  10, "ЄП за 2 квартал (декларація + оплата)",     frozenset({3})),
    (10, 19, "ЄСВ за 3 квартал",                          frozenset({1, 2, 3})),
    (10, 19, "аванс ЄП за 3 квартал",                     frozenset({1, 2})),
    (11, 10, "ЄП за 3 квартал (декларація + оплата)",     frozenset({3})),
]

_bot: Bot | None = None
_cron_secret: str | None = None


def _secret(name: str) -> str:
    project = os.environ["GCP_PROJECT_ID"]
    sm = secretmanager.SecretManagerServiceClient()
    resp = sm.access_secret_version(
        request={"name": f"projects/{project}/secrets/{name}/versions/latest"}
    )
    return resp.payload.data.decode("utf-8")


def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=_secret("telegram-bot-token"))
    return _bot


def _get_cron_secret() -> str:
    global _cron_secret
    if _cron_secret is None:
        _cron_secret = _secret("cron-secret")
    return _cron_secret


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _verify_cron(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if creds.credentials != _get_cron_secret():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")


# ---------------------------------------------------------------------------
# Deadline logic
# ---------------------------------------------------------------------------

def _upcoming_deadlines(ep_group: int, today: date) -> list[tuple[date, str]]:
    """Return (deadline_date, label) pairs due within REMINDER_DAYS from today."""
    results = []
    for month, day, label, groups in _CALENDAR:
        if ep_group not in groups:
            continue
        # Try this year and next year (handles Jan deadlines when today is Dec)
        for year in (today.year, today.year + 1):
            try:
                deadline = date(year, month, day)
            except ValueError:
                continue
            days_left = (deadline - today).days
            if 0 <= days_left <= _REMINDER_DAYS:
                results.append((deadline, label))
    return results


def _build_reminder(deadlines: list[tuple[date, str]]) -> str:
    lines = ["Нагадування про найближчі дедлайни:\n"]
    for d, label in deadlines:
        days_left = (d - date.today()).days
        when = "сьогодні" if days_left == 0 else f"через {days_left} дн. ({d.strftime('%d.%m')})"
        lines.append(f"• {label} — {when}")
    lines.append(
        "\nⓘ Перевірте актуальні реквізити перед оплатою: /pay_details"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cron endpoint
# ---------------------------------------------------------------------------

@router.post("/reminders", dependencies=[Depends(_verify_cron)], status_code=status.HTTP_200_OK)
async def run_reminders() -> dict:
    today = date.today()
    bot = _get_bot()
    records = get_all_user_records()

    notified = 0
    skipped = 0

    for record in records:
        try:
            user = User.from_record(record)
        except Exception:
            skipped += 1
            continue

        if not user.fop_profile:
            skipped += 1
            continue

        # Only notify active users (subscribers + free tier with requests left)
        if not (user.subscription_active or user.free_requests_remaining > 0):
            skipped += 1
            continue

        deadlines = _upcoming_deadlines(user.fop_profile.ep_group, today)
        if not deadlines:
            continue

        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=_build_reminder(deadlines),
            )
            notified += 1
        except Exception:
            log.exception("Failed to notify user=%s", user.telegram_id)

    log.info("reminders: notified=%s skipped=%s", notified, skipped)
    return {"notified": notified, "skipped": skipped}
