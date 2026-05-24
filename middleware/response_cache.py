"""Response cache — Firestore-backed, 24h TTL. Only for simple-intent queries."""

import hashlib
import logging
import time

from google.cloud import firestore

log = logging.getLogger(__name__)

_TTL = 86_400  # 24 hours
_COLLECTION = "response_cache"

_db: firestore.Client | None = None


def _fs() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def _key(text: str, ep_group: str | None) -> str:
    raw = (text.lower().strip() + "|" + (ep_group or "")).encode()
    return hashlib.sha256(raw).hexdigest()[:20]


def get(text: str, ep_group: str | None) -> str | None:
    try:
        doc = _fs().collection(_COLLECTION).document(_key(text, ep_group)).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        if time.time() - data.get("cached_at", 0) > _TTL:
            return None
        return data.get("response")
    except Exception:
        log.warning("response_cache.get failed", exc_info=True)
        return None


def set(text: str, ep_group: str | None, response: str) -> None:
    try:
        _fs().collection(_COLLECTION).document(_key(text, ep_group)).set({
            "response": response,
            "cached_at": time.time(),
        })
    except Exception:
        log.warning("response_cache.set failed", exc_info=True)
