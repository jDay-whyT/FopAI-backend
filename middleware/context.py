"""Conversation context management.

Persists per-user message history in Firestore.
Keeps last 10 messages. When overflow occurs, add_message signals
the caller to summarize — context.py never calls Claude directly.
"""

from typing import TypedDict

from google.cloud import firestore

_COLLECTION = "contexts"
_MAX_MESSAGES = 10
_TRIM_TO = 5  # messages kept after summarization

_db: firestore.Client | None = None


class Message(TypedDict):
    role: str     # "user" | "assistant"
    content: str


def _fs() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def _ref(telegram_id: int) -> firestore.DocumentReference:
    return _fs().collection(_COLLECTION).document(str(telegram_id))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_context(telegram_id: int) -> list[Message]:
    """
    Return messages ready to pass to Claude as the conversation history.
    If a summary exists it is prepended as a system-style user/assistant exchange
    so older context survives the trim window.
    """
    doc = _ref(telegram_id).get()
    if not doc.exists:
        return []

    data = doc.to_dict()
    messages: list[Message] = data.get("messages", [])
    summary: str | None = data.get("summary")

    if summary:
        # Inject summary as a synthetic exchange before live messages
        prefix: list[Message] = [
            {"role": "user", "content": "Підсумуй попередній контекст нашої розмови."},
            {"role": "assistant", "content": summary},
        ]
        return prefix + messages

    return messages


def add_message(telegram_id: int, role: str, content: str) -> bool:
    """
    Append a message to history.
    Returns True when message count exceeds MAX_MESSAGES — caller must
    call set_summary() with a Claude-generated summary to trim history.
    """
    ref = _ref(telegram_id)
    doc = ref.get()
    data = doc.to_dict() if doc.exists else {}
    messages: list[Message] = data.get("messages", [])
    messages.append({"role": role, "content": content})
    ref.set({"messages": messages, "summary": data.get("summary")}, merge=True)
    return len(messages) > _MAX_MESSAGES


def set_summary(telegram_id: int, summary: str) -> None:
    """
    Store summary and trim messages to the most recent TRIM_TO entries.
    Called by orchestrator after it generates a summary via Claude.
    """
    ref = _ref(telegram_id)
    doc = ref.get()
    messages: list[Message] = doc.to_dict().get("messages", []) if doc.exists else []
    ref.set({
        "summary": summary,
        "messages": messages[-_TRIM_TO:],
    })


def clear_context(telegram_id: int) -> None:
    """Wipe history and summary. Used on /reset or re-registration."""
    _ref(telegram_id).set({"messages": [], "summary": None})
