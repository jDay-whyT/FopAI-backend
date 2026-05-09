"""Rate limiter — per-user request rate and token budget enforcement.

Uses Firestore for atomic sliding-window counters so limits hold across
Cloud Run instances. Token limit is a stateless local check.
"""

import logging
import time

from google.cloud import firestore

log = logging.getLogger(__name__)

_RATE_LIMIT = 10        # max requests per window per user
_WINDOW_SEC = 60        # sliding window in seconds
_TOKEN_LIMIT = 8_000    # max input tokens per request

_db: firestore.Client | None = None


class RateLimitExceeded(Exception):
    pass


class TokenLimitExceeded(Exception):
    pass


def _firestore() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def check_rate_limit(telegram_id: int) -> None:
    """Raises RateLimitExceeded if user has hit 10 requests in the last 60 seconds."""
    now = time.time()
    cutoff = now - _WINDOW_SEC
    ref = _firestore().collection("rate_limits").document(str(telegram_id))

    @firestore.transactional
    def _apply(transaction: firestore.Transaction, doc_ref: firestore.DocumentReference) -> None:
        snapshot = doc_ref.get(transaction=transaction)
        timestamps: list[float] = snapshot.get("ts") if snapshot.exists else []
        timestamps = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= _RATE_LIMIT:
            raise RateLimitExceeded(str(telegram_id))
        timestamps.append(now)
        transaction.set(doc_ref, {"ts": timestamps})

    _apply(_firestore().transaction(), ref)


def check_token_limit(token_count: int) -> None:
    """Raises TokenLimitExceeded if input token count exceeds 8k."""
    if token_count > _TOKEN_LIMIT:
        raise TokenLimitExceeded(f"{token_count} > {_TOKEN_LIMIT}")
