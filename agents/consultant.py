"""PKU/NBU consultant agent — experienced accountant for Ukrainian FOPs."""

import logging
from pathlib import Path

import anthropic

from middleware.context import Message
from models.user import User

log = logging.getLogger(__name__)

_SKILLS = Path(__file__).parent.parent / "skills"

_SYSTEM = """\
Ти — досвідчений бухгалтер з 10+ роками практики з українськими ФОП та самозайнятими особами. \
Консультуєш виключно з питань, що стосуються обліку та оподаткування ФОП в Україні.

СФЕРА КОМПЕТЕНЦІЇ:
- Єдиний податок (ЄП): групи 1, 2, 3 — ліміти доходу, ставки, строки авансів, декларації
- ЄСВ: ставки, мінімальна/максимальна база, строки сплати, звільнення
- Військовий збір (ВЗ): ставки для ФОП з 2025 року, строки
- Звітність: форми та строки подання для кожної групи ЄП
- Первинні документи: що обов'язково мати, як правильно оформити акт, накладну, рахунок
- Фінансовий моніторинг: правила НБУ, порогові суми, документи для банку, пояснювальні листи
- Валютне регулювання: рахунки в іноземній валюті, репатріація виручки, правила НБУ для ФОП
- ПРРО: коли обов'язково, як зареєструвати, штрафи за відсутність
- Банківський комплаєнс: фінмон-запити, обґрунтування операцій

МОВА:
Визнач мову повідомлення користувача (українська або російська) і відповідай тією ж мовою.

СТИЛЬ ВІДПОВІДІ:
- Конкретні цифри та дати, не загальні фрази
- Посилання на статтю ПКУ або постанову НБУ, коли це підтверджує відповідь (наприклад, "ст. 291.4 ПКУ")
- Якщо норма могла змінитися — попередь, порекомендуй перевірити актуальну редакцію на zakon.rada.gov.ua
- Якщо питання виходить за межі компетенції — скажи чесно та порекомендуй звернутись до профільного спеціаліста

ЗАБОРОНИ (абсолютні, не обговорюються):
- Поради щодо ухилення від податків
- Допомога з сірими схемами: дропи, незадекларовані P2P, фіктивні витрати
- Будь-які питання не пов'язані з обліком та оподаткуванням ФОП
  Приклад відмови: "Це питання поза моєю спеціалізацією. Для консультації з [тема] зверніться до [спеціаліст]."
"""

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _load_skill(filename: str) -> str:
    path = _SKILLS / filename
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(encoding="utf-8")
    return ""


def _build_system(user: User | None) -> list[dict]:
    pku = _load_skill("pku-rules.md")
    ep = _load_skill("ep-groups.md")
    finmon = _load_skill("nbu-finmon.md")

    static = _SYSTEM
    if pku:
        static += f"\n\n---\n# Правила ПКУ (актуальна редакція)\n{pku}"
    if ep:
        static += f"\n\n---\n# Групи єдиного податку — ліміти та ставки\n{ep}"
    if finmon:
        static += f"\n\n---\n# Правила НБУ — фінансовий моніторинг\n{finmon}"

    blocks: list[dict] = [
        # Static block — cached across requests (same for all users)
        {
            "type": "text",
            "text": static,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    # User profile — not cached, varies per user
    if user and user.fop_profile:
        p = user.fop_profile
        parts = [f"ФОП, {p.ep_group}-а група ЄП"]
        if p.kveds:
            parts.append(f"КВЕДи: {', '.join(p.kveds)}")
        if p.bank:
            parts.append(f"банк: {p.bank}")
        if p.registration_date:
            parts.append(f"дата реєстрації: {p.registration_date}")
        blocks.append({
            "type": "text",
            "text": "Профіль клієнта: " + ", ".join(parts) + ".",
        })

    return blocks


async def handle(
    text: str,
    history: list[Message],
    user: User | None,
    model: str,
) -> str:
    system = _build_system(user)
    log.info("consultant.handle model=%s user=%s", model, user.telegram_id if user else None)

    response = await _get_client().messages.create(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[*history, {"role": "user", "content": text}],
    )

    return response.content[0].text
