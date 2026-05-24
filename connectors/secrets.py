"""Shared Secret Manager helper — fetch secrets by name."""

import os

from google.cloud import secretmanager

_sm: secretmanager.SecretManagerServiceClient | None = None


def _client() -> secretmanager.SecretManagerServiceClient:
    global _sm
    if _sm is None:
        _sm = secretmanager.SecretManagerServiceClient()
    return _sm


def get_secret(name: str) -> str:
    project = os.environ["GCP_PROJECT_ID"]
    resp = _client().access_secret_version(
        request={"name": f"projects/{project}/secrets/{name}/versions/latest"}
    )
    return resp.payload.data.decode("utf-8")
