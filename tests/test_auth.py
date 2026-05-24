"""Tests for middleware/auth.py — access control logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from middleware.auth import check_access, AccessDenied

_NOW = datetime.now(timezone.utc)


def _record(
    role="free",
    sub_status="free",
    expires_at=None,
    requests_used=0,
):
    return {
        "telegram_id": "111",
        "role": role,
        "subscription_status": sub_status,
        "expires_at": expires_at or "",
        "requests_used": requests_used,
        "fop_profile": None,
        "sheet_id": None,
    }


def _future(days=30) -> str:
    return (_NOW + timedelta(days=days)).isoformat()


def _past(days=1) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Not registered
# ---------------------------------------------------------------------------

@patch("middleware.auth.get_user_record", return_value=None)
def test_not_registered_raises(mock_get):
    with pytest.raises(AccessDenied) as exc:
        check_access(111)
    assert str(exc.value) == "not_registered"


# ---------------------------------------------------------------------------
# Pending / rejected
# ---------------------------------------------------------------------------

@patch("middleware.auth.get_user_record", return_value=_record(role="pending"))
def test_pending_raises(mock_get):
    with pytest.raises(AccessDenied) as exc:
        check_access(111)
    assert str(exc.value) == "pending"


@patch("middleware.auth.get_user_record", return_value=_record(role="rejected"))
def test_rejected_raises(mock_get):
    with pytest.raises(AccessDenied) as exc:
        check_access(111)
    assert str(exc.value) == "rejected"


# ---------------------------------------------------------------------------
# Whitelist roles
# ---------------------------------------------------------------------------

@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record", return_value=_record(role="admin"))
def test_admin_always_passes(mock_get, mock_update):
    assert check_access(111) is not None
    mock_update.assert_not_called()


@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record", return_value=_record(role="tester"))
def test_tester_always_passes(mock_get, mock_update):
    assert check_access(111) is not None
    mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# Active subscription
# ---------------------------------------------------------------------------

@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record")
def test_active_subscriber_passes(mock_get, mock_update):
    mock_get.return_value = _record(
        role="subscriber", sub_status="active", expires_at=_future(30)
    )
    assert check_access(111) is not None
    mock_update.assert_not_called()


# ---------------------------------------------------------------------------
# Expired subscription → downgrade → use free counter
# ---------------------------------------------------------------------------

@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record")
def test_expired_subscriber_downgrades_and_uses_free_counter(mock_get, mock_update):
    mock_get.return_value = _record(
        role="subscriber", sub_status="active", expires_at=_past(1), requests_used=0
    )
    assert check_access(111) is not None
    # First call: downgrade write
    assert mock_update.call_count == 2
    first_call_updates = mock_update.call_args_list[0][0][1]
    assert first_call_updates["role"] == "free"
    assert first_call_updates["subscription_status"] == "expired"
    # Second call: increment free counter
    second_call_updates = mock_update.call_args_list[1][0][1]
    assert second_call_updates["requests_used"] == 1


# ---------------------------------------------------------------------------
# Free tier
# ---------------------------------------------------------------------------

@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record")
def test_free_tier_with_requests_remaining(mock_get, mock_update):
    mock_get.return_value = _record(requests_used=5)
    assert check_access(111) is not None
    mock_update.assert_called_once_with(111, {"requests_used": 6})


@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record")
def test_free_tier_exhausted_raises(mock_get, mock_update):
    mock_get.return_value = _record(requests_used=10)
    with pytest.raises(AccessDenied) as exc:
        check_access(111)
    assert str(exc.value) == "limit_reached"
    mock_update.assert_not_called()


@patch("middleware.auth.update_user_record")
@patch("middleware.auth.get_user_record")
def test_free_tier_last_request_passes(mock_get, mock_update):
    mock_get.return_value = _record(requests_used=9)
    assert check_access(111) is not None
    mock_update.assert_called_once_with(111, {"requests_used": 10})
