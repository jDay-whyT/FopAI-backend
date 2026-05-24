# FopAI

Telegram-бот — розумний бухгалтер в кишені для українських ФОП та самозайнятих.

## Що вирішує

- Пропущені дедлайни ЄСВ/ЄП/ВЗ → штрафи 20–50%
- Перевищення лімітів єдиного податку
- Фінмон-запити банку — не знають що відповісти
- Плутанина в ПКУ без доступу до бухгалтера
- Відсутність первинних документів при перевірці

## Стек

| Шар | Технологія |
|-----|-----------|
| Інтерфейс | Telegram Bot (python-telegram-bot) |
| Backend | FastAPI + Google Cloud Run |
| AI | Anthropic Claude API (Haiku / Sonnet / Opus) |
| БД користувача | Google Sheets (фінансові дані у клієнта) |
| Файли | Google Drive |
| OCR | Google Document AI |
| Платежі | LiqPay |
| Секрети | Google Secret Manager |

## Архітектура агентів

```
Користувач (Telegram)
        ↓
Orchestrator (Sonnet) — визначає інтент, обирає модель
        ↓
┌─────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ Consultant  │ Accounting  │  Documents  │  Analytics  │  Reminders  │
│ (Sonnet/    │   (Haiku)   │  (Sonnet)   │  (Sonnet)   │ (Haiku,cron)│
│   Opus)     │             │             │             │             │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
```

## Структура проекту

```
fopAI-backend/
├── agents/          # AI-агенти (orchestrator, consultant, ...)
├── connectors/      # Google Sheets, Drive, Vision, LiqPay, secrets
├── handlers/        # Telegram webhook, LiqPay webhook, cron
├── middleware/      # Auth, rate limiter, context
├── models/          # User (Pydantic)
├── skills/          # Знання агентів (ПКУ, НБУ, групи ЄП, КВЕДи)
├── templates/       # Шаблони документів і Sheets
└── tests/
```

## Доступ і монетизація

```
whitelist (admin/tester) → підписка ($15/міс) → free tier (10 запитів) → блок
```

## Roadmap

**MVP** — консультант ПКУ/НБУ, нагадування ЄСВ/ЄП/ВЗ, контроль лімітів, фінмон-аналіз, LiqPay підписка

**V2** — Monobank API, ПриватБанк, OCR чеків, Google Sheets облік, генерація документів

**V3** — онбординг Bolt/Glovo (закон про платформи 2027), мульти-клієнт бухгалтер, Open Banking

## Локальний запуск

```bash
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env  # заповнити змінні
python -m pytest tests/
uvicorn main:app --reload
```

Змінні середовища:

| Змінна | Опис |
|--------|------|
| `GCP_PROJECT_ID` | ID проекту Google Cloud |
| `WEBHOOK_URL` | Публічний URL для Telegram webhook |
| `TELEGRAM_WEBHOOK_SECRET` | Секрет для валідації webhook |
| `ADMIN_TELEGRAM_ID` | Telegram ID адміністратора |
| `ANTHROPIC_API_KEY` | Ключ Anthropic (dev, у prod — Secret Manager) |

Секрети в production зберігаються в Google Secret Manager, не в `.env`.

## Деплой

GitHub Actions → Google Cloud Run (ручний запуск через `workflow_dispatch`).

## Hard limits

- Без порад щодо ухилення від податків
- Без сірих схем (дропи, P2P без декларування)
- Фінансові дані клієнта зберігаються тільки в його Google Sheets
- Логи не містять вміст запитів
