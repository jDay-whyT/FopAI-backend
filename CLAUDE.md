# FopAI — CLAUDE.md

## Project Overview

FopAI is a Telegram bot — "smart accountant in your pocket" — for Ukrainian sole proprietors (FOP) and self-employed individuals.

Solves real problems: missed tax deadlines, exceeding simplified tax limits, bank financial monitoring requests, confusion about Tax Code of Ukraine (PKU), missing primary documents during audits.

**Core rule:** FopAI consults and helps with legal accounting only. No gray schemes, no tax evasion advice. Hard limit enforced in every system prompt.

---

## Tech Stack

- **Telegram Bot** — python-telegram-bot, primary user interface
- **Backend** — FastAPI (Python), Google Cloud Run (serverless)
- **AI** — Anthropic Claude API (Haiku for simple queries, Sonnet for complex, Advisor Opus for critical)
- **User DB** — Google Sheets (one file per client, bot reads/writes via API)
- **Files** — Google Drive (documents, acts, invoices, templates)
- **OCR** — Google Document AI (receipts and document recognition)
- **Payments** — LiqPay
- **Secrets** — Google Secret Manager (no keys in code or .env in repo)
- **Regulatory monitoring** — separate NBU/DPS parser module (exists, integrate in V3)

---

## Agent Architecture

```
User (Telegram)
        ↓
Main agent — orchestrator (Sonnet)
detects intent, delegates to subagent
        ↓
┌────────────┬────────────┬────────────┬────────────┬────────────┐
│ Consultant │ Accounting │  Document  │ Analytics  │  Reminder  │
│   agent    │   agent    │   agent    │   agent    │   agent    │
│ (Sonnet+   │  (Haiku)   │  (Sonnet)  │  (Sonnet)  │ (Haiku,    │
│   Opus)    │            │            │            │   cron)    │
└────────────┴────────────┴────────────┴────────────┴────────────┘
```

- **Consultant** — PKU, NBU, financial monitoring, risks, PRRO. Answers with reference to legal norm.
- **Accounting** — records income/expenses in Sheets, calculates EP limits, auto-payment details.
- **Document** — generates acts, invoices, bank explanation letters.
- **Analytics** — analyzes bank statements, bank vs RRO reconciliation, Monobank transaction categorization.
- **Reminder** — cron job, checks payment calendar, sends deadline notifications.

---

## Project Structure

```
fopAI-backend/
├── agents/
│   ├── orchestrator.py        # Main agent, intent routing
│   ├── consultant.py          # PKU/NBU consultant
│   ├── accounting.py          # Income/expense tracking
│   ├── documents.py           # Document generation
│   ├── analytics.py           # Statement analysis
│   └── reminders.py           # Notifications (cron)
├── skills/
│   ├── pku-rules.md           # Tax Code rules for agents
│   ├── nbu-finmon.md          # NBU financial monitoring rules
│   ├── ep-groups.md           # EP groups, limits, rates
│   ├── kved-guide.md          # KVED codes by activity type
│   └── payment-details.md     # Tax payment details (auto-updated)
├── connectors/
│   ├── google_sheets.py       # Google Sheets API
│   ├── google_drive.py        # Google Drive API
│   ├── google_vision.py       # Document AI for OCR
│   ├── monobank.py            # Monobank API (V2)
│   └── liqpay.py              # LiqPay payments
├── templates/
│   ├── sheets/
│   │   ├── fop_group_1_2.json # Template for FOP group 1-2
│   │   ├── fop_group_3.json   # Template for FOP group 3
│   │   └── fop_employee.json  # Template for FOP with employee
│   └── docs/
│       ├── act.md             # Act of completion template
│       ├── invoice_ua.md      # Invoice in Ukrainian
│       ├── invoice_en.md      # Invoice in English
│       └── bank_letter.md     # Bank explanation letter template
├── handlers/
│   ├── telegram.py            # Telegram webhook handlers
│   ├── payments.py            # LiqPay webhooks
│   └── scheduler.py           # Cron jobs for reminders
├── middleware/
│   ├── auth.py                # Whitelist/subscription/limit check
│   ├── rate_limiter.py        # Rate limiting by tokens and requests
│   └── context.py             # Conversation context management
├── models/
│   └── user.py                # User profile (minimum data)
├── main.py                    # FastAPI app entry point
├── requirements.txt
├── Dockerfile
└── CLAUDE.md                  # This file
```

---

## Security — Critical

**What we store in DB (minimum only):**
- `telegram_id` — user identifier
- `role` — admin / tester / subscriber / free
- `subscription_status` — active / expired / free
- `expires_at` — subscription expiry date
- `requests_used` — free tier request counter
- `fop_profile` — EP group, KVEDs, registration date, bank

**What we NEVER store:**
- Financial document contents
- Bank statements
- Transaction amounts
- Personal data beyond Telegram ID

**All financial data lives only in client's Google Sheets. We read and write, never store.**

**Code rules:**
- All secrets via Secret Manager only — never in code or .env
- Logs — technical only (errors, latency, token count). Never request/response content
- Rate limit: max 10 requests per minute per Telegram ID
- Token limit per request: max 8k input tokens
- Conversation context: max 10 last messages, then summarize

---

## Access Control & Monetization

```python
# Check order on every request
def check_access(telegram_id):
    if is_whitelist(telegram_id):         # Admin/testers — always access
        return True
    if has_active_subscription():         # Paid subscription — access
        return True
    if free_requests_remaining() > 0:     # Free tier — 10 requests
        decrement_counter()
        return True
    return False                          # Offer subscription
```

- Free tier: 10 requests
- Subscription: $10-15/month via LiqPay
- Whitelist: admin + testers (including accountant jr)

---

## Model Selection

```python
SIMPLE_QUERIES = ["when to pay", "how much ESV", "what is the limit"]  # → Haiku
COMPLEX_QUERIES = ["analyze statement", "finmon risk", "generate document"]  # → Sonnet
CRITICAL_QUERIES = ["legal situation", "fine", "DPS audit"]  # → Sonnet + Advisor Opus
```

---

## OCR Pipeline

```
User photo (Telegram)
        ↓
Google Document AI (recognition)
        ↓
Structured JSON (amount, date, vendor)
        ↓
Claude API (expense category, business vs personal)
        ↓
Google Sheets (write to correct sheet)
```

---

## Transaction Categorization (Monobank, V2)

Hybrid system:
1. Auto-categorize with confidence score
2. If confidence < 70% → ask user (inline buttons)
3. User confirmed 3+ times → remember counterparty
4. System learns from each user's history over time

---

## Google Sheets Templates (MVP)

Each template has sheets:
1. **Dashboard** — quarterly income, limit remaining, next payment due
2. **Income book** — bot writes automatically (range protected from user)
3. **Expenses & receipts** — OCR writes here
4. **Payment calendar** — dates and amounts for ESV, EP, VZ
5. **Service sheet** — bot internal, protected range (user cannot edit)

On registration: bot copies template to client's Drive → sends link in chat.

---

## Roadmap

**MVP (now):**
- Registration & onboarding (3-4 questions, detect profile)
- PKU/NBU/finmon consultant
- ESV, EP, VZ, reporting deadline reminders
- EP limit control with alerts at 70%, 90%, 100%
- Tax payment details with auto-payment generation
- Google Sheets templates (3 variants)
- Free tier + LiqPay subscription
- Whitelist system

**V2:**
- Monobank API integration
- PrivatBank API (Autoclient)
- Receipt OCR via Google Document AI
- Full accounting in Google Sheets
- Bank vs RRO reconciliation
- Vchasno.Kasa integration
- Document generation (acts, invoices, bank letters)

**V3:**
- Report submission (partnership with Vchasno.Zvit)
- KEP / Diia.Sign integration
- Multi-client mode for accountants
- Onboarding for Bolt/Glovo/Uklon drivers (law effective 2027)
- Open Banking (all banks via NBU standard)
- Regulatory monitoring module integration (NBU/DPS parser)

---

## Legal

- Disclaimer on registration (once): "FopAI provides informational consultations based on PKU and NBU practice. This is not individual legal or tax advice. User makes decisions independently."
- Public offer agreement on subscription payment
- Logs contain no personal data or request content
- Claude API does not use API data for model training

---

## Hard Limits — Never Do This

- Do not advise on tax evasion
- Do not help with gray schemes (drops, undeclared P2P)
- Do not store user financial data on our side
- Do not log request or response content
- Do not mix data between users
- Do not guarantee accuracy — always include disclaimer
- Do not use personal card instead of FOP account

---

## Coding Guidelines (Karpathy)

These behavioral rules apply to every coding task. Bias toward caution over speed.

### 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

---

## Team Context

- Developer: 3 projects experience, uses Claude Code agent for development
- Tester & accounting consultant: jr (practicing accountant, first tester)
- Existing module: NBU/DPS regulatory change parser (integrate in V3)
- Repo: https://github.com/jDay-whyT/fopAI-backend.git
