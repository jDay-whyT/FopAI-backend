"""FastAPI entry point — FopAI backend on Google Cloud Run."""

from dotenv import load_dotenv
load_dotenv()

import logging
import os
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request, Response, status
from telegram import Update
from telegram.ext import Application

from connectors.secrets import get_secret
from handlers.telegram import build_application
from handlers.payments import router as payments_router
from handlers.scheduler import router as scheduler_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

_ptb_app: Application | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ptb_app

    token = get_secret("telegram-bot-token")
    webhook_url = os.environ["WEBHOOK_URL"].rstrip("/") + "/webhook/telegram"
    webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET") or None

    _ptb_app = build_application(token)
    await _ptb_app.initialize()
    await _ptb_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        secret_token=webhook_secret,
    )
    log.info("Telegram webhook set: %s", webhook_url)

    yield

    await _ptb_app.shutdown()
    log.info("PTB application shut down")


app = FastAPI(title="FopAI", lifespan=lifespan)

app.include_router(payments_router, prefix="/webhook")
app.include_router(scheduler_router, prefix="/cron")


@app.get("/health", status_code=status.HTTP_200_OK)
async def health() -> dict:
    return {"status": "ok"}


async def _process_update(data: dict) -> None:
    if _ptb_app is None:
        return
    update = Update.de_json(data, _ptb_app.bot)
    await _ptb_app.process_update(update)


@app.post("/webhook/telegram", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    if _ptb_app is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if expected and request.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != expected:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)
    data = await request.json()
    background_tasks.add_task(_process_update, data)
    return Response()
