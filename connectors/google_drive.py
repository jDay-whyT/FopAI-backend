"""Google Drive connector — file operations for user document storage."""

import json
import logging
import os
from io import BytesIO

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.cloud import secretmanager

log = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/drive",
]

_drive_service = None


def _secret(name: str) -> str:
    project = os.environ["GCP_PROJECT_ID"]
    sm = secretmanager.SecretManagerServiceClient()
    resp = sm.access_secret_version(
        request={"name": f"projects/{project}/secrets/{name}/versions/latest"}
    )
    return resp.payload.data.decode("utf-8")


def _drive():
    global _drive_service
    if _drive_service is None:
        sa_json = _secret("google-service-account")
        creds = Credentials.from_service_account_info(
            json.loads(sa_json), scopes=_SCOPES
        )
        _drive_service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _drive_service


# ---------------------------------------------------------------------------
# URL helpers — no API call needed
# ---------------------------------------------------------------------------

def get_spreadsheet_url(sheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"


def get_document_url(file_id: str) -> str:
    return f"https://docs.google.com/document/d/{file_id}/edit"


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------

def create_folder(name: str, parent_id: str | None = None) -> str:
    """Create a Drive folder. Returns folder_id."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = _drive().files().create(body=metadata, fields="id").execute()
    return folder["id"]


def share_file(file_id: str, email: str, role: str = "writer") -> None:
    """Share file with a specific Google account."""
    _drive().permissions().create(
        fileId=file_id,
        body={"type": "user", "role": role, "emailAddress": email},
        sendNotificationEmail=False,
    ).execute()


def transfer_ownership(file_id: str, email: str) -> None:
    """Transfer file ownership to the user's Google account."""
    _drive().permissions().create(
        fileId=file_id,
        body={"type": "user", "role": "owner", "emailAddress": email},
        transferOwnership=True,
        sendNotificationEmail=False,
    ).execute()


def upload_file(
    name: str,
    content: bytes,
    mimetype: str,
    parent_id: str | None = None,
) -> str:
    """Upload a file to Drive. Returns file_id."""
    metadata: dict = {"name": name}
    if parent_id:
        metadata["parents"] = [parent_id]
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mimetype, resumable=False)
    file = (
        _drive()
        .files()
        .create(body=metadata, media_body=media, fields="id")
        .execute()
    )
    log.info("uploaded file=%s id=%s", name, file["id"])
    return file["id"]


def delete_file(file_id: str) -> None:
    _drive().files().delete(fileId=file_id).execute()
