"""FastAPI entry point — FopAI backend on Google Cloud Run."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from telegram import Update
from telegram.ext import Application

from google.cloud import secretmanager

from handlers.telegram import build_application, router as telegram_router
from handlers.payments import router as payments_router
from handlers.scheduler import router as scheduler_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

_ptb_app: Application | None = None


def _secret(name: str) -> str:
    project = os.environ["GCP_PROJECT_ID"]
    client = secretmanager.SecretManagerServiceClient()
    resp = client.access_secret_version(
        request={"name": f"projects/{project}/secrets/{name}/versions/latest"}
    )
    return resp.payload.data.decode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ptb_app

    token = _secret("telegram-bot-token")
    webhook_url = os.environ["WEBHOOK_URL"].rstrip("/") + "/webhook/telegram"

    _ptb_app = build_application(token)
    await _ptb_app.initialize()
    await _ptb_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    log.info("Telegram webhook set: %s", webhook_url)

    yield

    await _ptb_app.shutdown()
    log.info("PTB application shut down")


app = FastAPI(title="FopAI", lifespan=lifespan)

app.include_router(telegram_router, prefix="/webhook")
app.include_router(payments_router, prefix="/webhook")
app.include_router(scheduler_router, prefix="/cron")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


@app.post("/webhook/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request) -> Response:
    if _ptb_app is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    data = await request.json()
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.process_update(update)
    return Response()
