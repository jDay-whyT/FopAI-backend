"""Main orchestrator — intent detection, model selection, agent delegation.

MVP: all queries → consultant agent.
V2: route accounting/documents/analytics to their own agents.
"""

import logging

import anthropic

from agents import consultant, faq
from middleware import response_cache
from middleware.context import Message
from middleware.rate_limiter import check_token_limit
from models.user import User

log = logging.getLogger(__name__)

_MODEL_HAIKU = "claude-haiku-4-5-20251001"
_MODEL_SONNET = "claude-sonnet-4-6"
_MODEL_OPUS = "claude-opus-4-7"

_SIMPLE = {
    "коли платити", "скільки єсв", "який ліміт", "коли звітувати",
    "ставка єп", "розмір єсв", "скільки платити", "коли здавати звіт",
    "перша група", "друга група", "третя група", "що таке фоп",
}
_CRITICAL = {
    "штраф", "перевірка дпс", "перевірка податков", "кримінальна",
    "заблокували рахунок", "блокування рахунку", "арешт коштів",
    "санкція", "порушення", "ухилення від податків",
}

# Agent routing — imperative recording verbs required for accounting
# to avoid false positives on questions that mention the same objects.
_RECORD_VERBS = ("запиши", "внеси", "зафіксуй")
_ACCOUNT_OBJECTS = ("дохід", "доходу", "витрат", "надходжен", "виплат")
_DOC_VERBS = ("склади", "створи", "зроби", "сформуй", "підготуй", "напиши")
_DOC_TYPES = ("акт", "рахунок", "інвойс", "накладн", "договір", "лист до банку", "пояснення для банку")
_ANALYTICS_KW = (
    "проаналізуй", "перевір виписк", "звіт за", "статистик",
    "підсумок за", "скільки заробив за", "скільки витратив за",
)
_REMINDER_KW = ("нагадай мені", "постав нагадування", "нагадування на")

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _detect_agent(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _REMINDER_KW):
        return "reminders"
    if any(v in lower for v in _DOC_VERBS) and any(t in lower for t in _DOC_TYPES):
        return "documents"
    if any(kw in lower for kw in _ANALYTICS_KW):
        return "analytics"
    if any(v in lower for v in _RECORD_VERBS) and any(o in lower for o in _ACCOUNT_OBJECTS):
        return "accounting"
    return "consultant"


def _detect_intent(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _CRITICAL):
        return "critical"
    if any(kw in lower for kw in _SIMPLE):
        return "simple"
    return "complex"


def _select_model(intent: str) -> str:
    return {
        "simple": _MODEL_HAIKU,
        "complex": _MODEL_SONNET,
        "critical": _MODEL_OPUS,
    }[intent]


async def handle_message(
    text: str,
    history: list[Message],
    user: User | None,
) -> str:
    check_token_limit(len(text) // 2)

    # Tier 1: FAQ — zero API cost
    answer = faq.lookup(text)
    if answer is not None:
        log.info("faq.hit user=%s", user.telegram_id if user else None)
        return answer

    intent = _detect_intent(text)
    model = _select_model(intent)
    agent = _detect_agent(text)
    ep_group = str(user.fop_profile.ep_group) if user and user.fop_profile else None

    # Tier 2: Response cache — simple consultant queries only
    if intent == "simple" and agent == "consultant":
        cached = response_cache.get(text, ep_group)
        if cached is not None:
            log.info("cache.hit user=%s", user.telegram_id if user else None)
            return cached

    log.info("intent=%s agent=%s model=%s user=%s", intent, agent, model, user.telegram_id if user else None)
    if agent != "consultant":
        log.warning("agent=%s not implemented, routing to consultant", agent)

    reply = await consultant.handle(text, history=history, user=user, model=model)

    if intent == "simple":
        response_cache.set(text, ep_group, reply)

    return reply


async def summarize_context(history: list[Message]) -> str:
    prompt = (
        "Стисло підсумуй цю розмову в 3-5 реченнях. "
        "Збережи: групу ЄП, КВЕДи, конкретні цифри, ключові висновки. "
        "Відповідай лише підсумком, без вступу."
    )
    response = await _get_client().messages.create(
        model=_MODEL_HAIKU,
        max_tokens=512,
        messages=[*history, {"role": "user", "content": prompt}],
    )
    return response.content[0].text
