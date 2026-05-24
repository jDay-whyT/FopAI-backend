"""Tests for agents/orchestrator.py — intent detection, model routing, delegation."""

from unittest.mock import AsyncMock, patch

import pytest

from agents.orchestrator import _detect_agent, _detect_intent, _select_model, handle_message
from middleware.rate_limiter import TokenLimitExceeded


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    # accounting — explicit record verb + financial object
    ("запиши дохід 50000", "accounting"),
    ("внеси витрати за оренду", "accounting"),
    ("зафіксуй надходження від клієнта", "accounting"),
    # accounting NOT triggered — no record verb
    ("скільки в мене доходу за квартал", "consultant"),
    ("який ліміт доходу для 3 групи", "consultant"),
    # documents — verb + type
    ("склади акт виконаних робіт", "documents"),
    ("зроби рахунок для клієнта", "documents"),
    ("напиши пояснення для банку", "documents"),
    # documents NOT triggered — verb without type
    ("склади план дій при перевірці", "consultant"),
    # analytics
    ("проаналізуй мої витрати", "analytics"),
    ("звіт за квартал по доходах", "analytics"),
    ("скільки заробив за місяць", "analytics"),
    # reminders
    ("нагадай мені сплатити єсв", "reminders"),
    ("постав нагадування на 20 число", "reminders"),
    # consultant default
    ("що таке фоп", "consultant"),
    ("який ліміт третьої групи", "consultant"),
    ("мені прийшов штраф від дпс", "consultant"),
])
def test_agent_detection(text, expected):
    assert _detect_agent(text) == expected


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("коли платити єсв за квартал", "simple"),
    ("який ліміт для третьої групи", "simple"),
    ("що таке фоп", "simple"),
    ("скільки платити ставка єп", "simple"),
    ("мені прийшов штраф від ДПС", "critical"),
    ("заблокували рахунок у банку", "critical"),
    ("перевірка дпс що робити", "critical"),
    ("кримінальна відповідальність за несплату", "critical"),
    ("як правильно оформити акт виконаних робіт", "complex"),
    ("що таке фінансовий моніторинг для фоп", "complex"),
    ("розкажи про валютне регулювання", "complex"),
])
def test_intent_detection(text, expected):
    assert _detect_intent(text) == expected


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def test_model_simple():
    assert _select_model("simple") == "claude-haiku-4-5-20251001"


def test_model_complex():
    assert _select_model("complex") == "claude-sonnet-4-6"


def test_model_critical():
    assert _select_model("critical") == "claude-opus-4-7"


# ---------------------------------------------------------------------------
# FAQ tier — no Claude call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("agents.orchestrator.check_token_limit")
async def test_faq_hit_skips_consultant(mock_limit):
    result = await handle_message("скільки єсв у 2026", history=[], user=None)
    assert "1 902" in result


@pytest.mark.asyncio
@patch("agents.orchestrator.check_token_limit")
async def test_faq_limit_group3(mock_limit):
    result = await handle_message("який ліміт третьої групи", history=[], user=None)
    assert "10 091" in result


@pytest.mark.asyncio
@patch("agents.orchestrator.check_token_limit")
async def test_faq_vz(mock_limit):
    result = await handle_message("скільки військовий збір для фоп", history=[], user=None)
    assert "864" in result


# ---------------------------------------------------------------------------
# Cache tier
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value="кешована відповідь")
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_cache_hit_skips_consultant(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    result = await handle_message("що таке фоп", history=[], user=None)
    assert result == "кешована відповідь"
    mock_consultant.assert_not_awaited()


@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value=None)
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_simple_query_writes_cache(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    mock_consultant.return_value = "відповідь"
    await handle_message("що таке фоп", history=[], user=None)
    mock_cache_set.assert_called_once()


# ---------------------------------------------------------------------------
# handle_message — delegation and token guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value=None)
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_delegates_to_consultant(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    mock_consultant.return_value = "відповідь консультанта"
    result = await handle_message("що таке єсв", history=[], user=None)
    assert result == "відповідь консультанта"
    mock_consultant.assert_awaited_once()


@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value=None)
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_simple_query_uses_haiku(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    mock_consultant.return_value = "ok"
    await handle_message("що таке фоп", history=[], user=None)
    _, kwargs = mock_consultant.call_args
    assert kwargs["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value=None)
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_critical_query_uses_opus(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    mock_consultant.return_value = "ok"
    await handle_message("заблокували рахунок що робити", history=[], user=None)
    _, kwargs = mock_consultant.call_args
    assert kwargs["model"] == "claude-opus-4-7"


@pytest.mark.asyncio
@patch("agents.orchestrator.check_token_limit", side_effect=TokenLimitExceeded("too long"))
async def test_token_limit_blocks_call(mock_limit):
    with pytest.raises(TokenLimitExceeded):
        await handle_message("x" * 30_000, history=[], user=None)


@pytest.mark.asyncio
@patch("agents.orchestrator.response_cache.set")
@patch("agents.orchestrator.response_cache.get", return_value=None)
@patch("agents.orchestrator.faq.lookup", return_value=None)
@patch("agents.orchestrator.consultant.handle", new_callable=AsyncMock)
@patch("agents.orchestrator.check_token_limit")
async def test_history_passed_to_consultant(mock_limit, mock_consultant, mock_faq, mock_cache_get, mock_cache_set):
    mock_consultant.return_value = "ok"
    history = [{"role": "user", "content": "привіт"}, {"role": "assistant", "content": "привіт"}]
    await handle_message("питання", history=history, user=None)
    _, kwargs = mock_consultant.call_args
    assert kwargs["history"] == history
