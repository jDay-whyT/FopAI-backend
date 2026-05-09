"""Telegram webhook handlers — /start, /status, /reset, text → Claude."""

import logging

from fastapi import APIRouter
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from connectors.google_sheets import get_user_record, create_user_record
from middleware.auth import check_access, AccessDenied
from middleware.rate_limiter import check_rate_limit, RateLimitExceeded
from middleware.context import get_context, add_message, set_summary, clear_context
from models.user import User
from agents.orchestrator import handle_message, summarize_context
from handlers.payments import generate_payment_link, PRICE_USD

log = logging.getLogger(__name__)
router = APIRouter()

_DISCLAIMER = (
    "FopAI надає інформаційні консультації на основі ПКУ та практики НБУ. "
    "Це не є індивідуальною правовою або податковою порадою. "
    "Рішення ви приймаєте самостійно."
)

_WELCOME = (
    "Привіт! Я FopAI — розумний бухгалтер у вашій кишені.\n\n"
    "{disclaimer}\n\n"
    "Розкажіть про себе, щоб я міг допомагати точніше:\n"
    "- Яка у вас група єдиного податку? (1, 2 або 3)\n"
    "- Які КВЕД-и?\n"
    "- З якого банку працюєте?"
)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tid = update.effective_user.id
    record = get_user_record(tid)

    if record is None:
        create_user_record(tid, {
            "role": "free",
            "subscription_status": "free",
            "requests_used": 0,
        })
        await update.message.reply_text(_WELCOME.format(disclaimer=_DISCLAIMER))
    else:
        user = User.from_record(record)
        if user.fop_profile:
            await update.message.reply_text(
                f"З поверненням! Група ЄП: {user.fop_profile.ep_group}. "
                f"Чим можу допомогти?"
            )
        else:
            await update.message.reply_text(
                "Ви вже зареєстровані. Чим можу допомогти? "
                "Якщо хочете заповнити профіль — розкажіть про свою групу ЄП та КВЕД-и."
            )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tid = update.effective_user.id
    record = get_user_record(tid)

    if record is None:
        await update.message.reply_text("Ви ще не зареєстровані. Введіть /start.")
        return

    user = User.from_record(record)

    if user.role in ("admin", "tester"):
        await update.message.reply_text(f"Роль: {user.role}. Ліміти не діють.")
        return

    if user.subscription_active:
        await update.message.reply_text(
            f"Підписка активна до: {user.expires_at[:10] if user.expires_at else '—'}."
        )
    else:
        remaining = user.free_requests_remaining
        await update.message.reply_text(
            f"Безкоштовний тариф. Залишилось запитів: {remaining}/10.\n"
            + ("Підписка: /subscribe" if remaining == 0 else "")
        )


async def cmd_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tid = update.effective_user.id
    record = get_user_record(tid)

    if record is None:
        await update.message.reply_text("Спочатку введіть /start.")
        return

    user = User.from_record(record)
    if user.subscription_active:
        await update.message.reply_text(
            f"Підписка вже активна до {user.expires_at[:10] if user.expires_at else '—'}."
        )
        return

    link = generate_payment_link(tid)
    await update.message.reply_text(
        f"Підписка FopAI — ${PRICE_USD}/міс (30 днів).\n\n"
        f"Оплата через LiqPay:\n{link}"
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_context(update.effective_user.id)
    await update.message.reply_text("Контекст розмови очищено.")


# ---------------------------------------------------------------------------
# Text message handler
# ---------------------------------------------------------------------------

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tid = update.effective_user.id
    text = update.message.text

    # Access + rate checks
    try:
        check_access(tid)
    except AccessDenied as e:
        code = str(e)
        if code == "not_registered":
            await update.message.reply_text("Спочатку введіть /start.")
        else:
            await update.message.reply_text(
                "Ви вичерпали безкоштовні запити. Оформіть підписку: /subscribe"
            )
        return

    try:
        check_rate_limit(tid)
    except RateLimitExceeded:
        await update.message.reply_text(
            "Забагато запитів. Зачекайте хвилину і спробуйте знову."
        )
        return

    # Build history + call orchestrator
    history = get_context(tid)
    record = get_user_record(tid)
    user = User.from_record(record) if record else None

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    try:
        reply = await handle_message(text, history=history, user=user)
    except Exception:
        log.exception("Orchestrator error for user %s", tid)
        await update.message.reply_text(
            "Сталася помилка. Спробуйте ще раз або напишіть пізніше."
        )
        return

    await update.message.reply_text(reply)

    # Persist exchange; summarize if overflow
    add_message(tid, "user", text)
    needs_summary = add_message(tid, "assistant", reply)
    if needs_summary:
        try:
            full_history = get_context(tid)
            summary = await summarize_context(full_history)
            set_summary(tid, summary)
        except Exception:
            log.exception("Summarization failed for user %s", tid)


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------

async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("PTB error: %s", context.error, exc_info=context.error)


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------

def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("subscribe", cmd_subscribe))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)
    return app
