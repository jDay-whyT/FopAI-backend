"""User profile model — minimum data as specified in CLAUDE.md."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class FopProfile(BaseModel):
    ep_group: Literal[1, 2, 3]
    kveds: list[str] = Field(default_factory=list)
    registration_date: str | None = None   # ISO date string "YYYY-MM-DD"
    bank: str | None = None


class User(BaseModel):
    telegram_id: int
    role: Literal["admin", "tester", "subscriber", "free", "pending", "rejected"] = "pending"
    subscription_status: Literal["active", "expired", "free"] = "free"
    expires_at: str | None = None          # ISO datetime string, UTC
    requests_used: int = 0
    fop_profile: FopProfile | None = None

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    @property
    def subscription_active(self) -> bool:
        if self.role in ("admin", "tester"):
            return True
        if self.subscription_status != "active" or not self.expires_at:
            return False
        return datetime.fromisoformat(self.expires_at).replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

    @property
    def free_requests_remaining(self) -> int:
        return max(0, 10 - self.requests_used)

    # ------------------------------------------------------------------
    # Sheets serialization — flat dict, fop_profile as JSON string (handled by connector)
    # ------------------------------------------------------------------

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> User:
        fop_raw = record.get("fop_profile")
        fop = FopProfile(**fop_raw) if isinstance(fop_raw, dict) else None
        return cls(
            telegram_id=int(record["telegram_id"]),
            role=record.get("role", "free"),
            subscription_status=record.get("subscription_status", "free"),
            expires_at=record.get("expires_at") or None,
            requests_used=int(record.get("requests_used") or 0),
            fop_profile=fop,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "telegram_id": self.telegram_id,
            "role": self.role,
            "subscription_status": self.subscription_status,
            "expires_at": self.expires_at or "",
            "requests_used": self.requests_used,
            "fop_profile": self.fop_profile.model_dump() if self.fop_profile else None,
        }
