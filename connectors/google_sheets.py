"""Google Sheets connector — user registry + client sheet operations."""

import json
import logging
from typing import Any

from google.oauth2.service_account import Credentials
import gspread

from connectors.secrets import get_secret

log = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column order in the users registry sheet (must match actual sheet header row)
_COLS = ["telegram_id", "role", "subscription_status", "expires_at", "requests_used", "fop_profile", "sheet_id"]
_COL_IDX = {name: i + 1 for i, name in enumerate(_COLS)}

# Module-level singletons — initialized on first use
_gc_client: gspread.Client | None = None
_users_worksheet: gspread.Worksheet | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _gc() -> gspread.Client:
    global _gc_client
    if _gc_client is None:
        sa_json = get_secret("google-service-account")
        creds = Credentials.from_service_account_info(json.loads(sa_json), scopes=_SCOPES)
        _gc_client = gspread.Client(auth=creds)
    return _gc_client


def _users_ws() -> gspread.Worksheet:
    global _users_worksheet
    if _users_worksheet is None:
        sheet_id = get_secret("users-sheet-id")
        _users_worksheet = _gc().open_by_key(sheet_id).sheet1
    return _users_worksheet


def _find_row(telegram_id: int) -> int | None:
    """Return 1-indexed row number for telegram_id, or None if not found."""
    ids = _users_ws().col_values(1)  # col 1 = telegram_id
    try:
        return ids.index(str(telegram_id)) + 1
    except ValueError:
        return None


def _row_to_dict(row: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for i, key in enumerate(_COLS):
        val: Any = row[i] if i < len(row) else ""
        if not val:
            val = None
        elif key == "fop_profile":
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        elif key == "requests_used":
            val = int(val)
        result[key] = val
    return result


def _serialize(key: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


# ---------------------------------------------------------------------------
# User registry — public API
# ---------------------------------------------------------------------------

def get_all_user_records() -> list[dict[str, Any]]:
    """Return all user rows, skipping the header row."""
    rows = _users_ws().get_all_values()
    return [_row_to_dict(row) for row in rows[1:] if row and row[0]]


def get_user_record(telegram_id: int) -> dict[str, Any] | None:
    row_num = _find_row(telegram_id)
    if row_num is None:
        return None
    return _row_to_dict(_users_ws().row_values(row_num))


def create_user_record(telegram_id: int, data: dict[str, Any]) -> None:
    data["telegram_id"] = telegram_id
    row = [_serialize(key, data.get(key)) for key in _COLS]
    _users_ws().append_row(row, value_input_option="RAW")


def update_user_record(telegram_id: int, updates: dict[str, Any]) -> None:
    row_num = _find_row(telegram_id)
    if row_num is None:
        raise ValueError(f"User {telegram_id} not found in registry")
    cells = []
    for key, value in updates.items():
        if key not in _COL_IDX:
            log.warning("update_user_record: unknown field '%s' — skipped", key)
            continue
        cells.append(gspread.Cell(row_num, _COL_IDX[key], _serialize(key, value)))
    if cells:
        _users_ws().update_cells(cells)


# ---------------------------------------------------------------------------
# Client sheet operations — used by accounting / document agents
# ---------------------------------------------------------------------------

def get_client_spreadsheet(sheet_id: str) -> gspread.Spreadsheet:
    return _gc().open_by_key(sheet_id)


def read_worksheet(sheet_id: str, worksheet_name: str) -> list[list[str]]:
    return get_client_spreadsheet(sheet_id).worksheet(worksheet_name).get_all_values()


def append_to_worksheet(sheet_id: str, worksheet_name: str, row: list[Any]) -> None:
    ws = get_client_spreadsheet(sheet_id).worksheet(worksheet_name)
    ws.append_row([str(v) if v is not None else "" for v in row], value_input_option="USER_ENTERED")


def copy_template_to_drive(template_sheet_id: str, title: str, owner_email: str) -> str:
    """Copy a template spreadsheet to the user's Drive. Returns new sheet_id."""
    new_sheet = _gc().copy(template_sheet_id, title=title, copy_permissions=False)
    new_sheet.share(owner_email, perm_type="user", role="owner", notify=False)
    return new_sheet.id
