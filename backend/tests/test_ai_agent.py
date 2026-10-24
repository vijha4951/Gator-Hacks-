"""Tests for ai_agent.explain() — no real API calls are made."""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import CircuitRequest, Scenario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(**kw) -> CircuitRequest:
    defaults = dict(voltage=5.0, resistance=220.0, led_forward_voltage=2.0)
    return CircuitRequest(**(defaults | kw))


def _scenario(r=220.0, i=13.29, s="safe") -> Scenario:
    return Scenario(resistance=r, current_ma=i, status=s)


# ---------------------------------------------------------------------------
# Fallback when GEMINI_API_KEY is absent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_none_when_no_api_key():
    """explain() must return None (triggering rule-based text) if key is unset."""
    from app.services import ai_agent

    with patch("app.config.settings") as mock_settings:
        mock_settings.gemini_api_key = None
        result = await ai_agent.explain(_req(), _scenario(), None)

    assert result is None


# ---------------------------------------------------------------------------
# Fallback on API error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_none_on_api_error():
    """Any exception from the Gemini client must be caught; return None."""
    from app.services import ai_agent

    mock_client = MagicMock()
    mock_client.aio.interactions.create = AsyncMock(
        side_effect=RuntimeError("quota exceeded")
    )

    with patch("app.config.settings") as mock_settings, \
         patch("google.genai.Client", return_value=mock_client):
        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model = "gemini-3.5-flash"
        result = await ai_agent.explain(_req(), _scenario(), None)

    assert result is None


# ---------------------------------------------------------------------------
# Happy path: populated response forwarded as-is
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_text_on_success():
    """explain() must return the model's text when the API succeeds."""
    from app.services import ai_agent

    expected = "Simulated current looks fine for this LED."

    mock_interaction = MagicMock()
    mock_interaction.output_text = expected

    mock_client = MagicMock()
    mock_client.aio.interactions.create = AsyncMock(return_value=mock_interaction)

    with patch("app.config.settings") as mock_settings, \
         patch("google.genai.Client", return_value=mock_client):
        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model = "gemini-3.5-flash"
        result = await ai_agent.explain(_req(), _scenario(), None)

    assert result == expected


# ---------------------------------------------------------------------------
# Empty response falls back to None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_returns_none_on_empty_response():
    """If the model returns an empty string, fall back to rule-based text."""
    from app.services import ai_agent

    mock_interaction = MagicMock()
    mock_interaction.output_text = "   "  # whitespace only

    mock_client = MagicMock()
    mock_client.aio.interactions.create = AsyncMock(return_value=mock_interaction)

    with patch("app.config.settings") as mock_settings, \
         patch("google.genai.Client", return_value=mock_client):
        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model = "gemini-3.5-flash"
        result = await ai_agent.explain(_req(), _scenario(), None)

    assert result is None


# ---------------------------------------------------------------------------
# Corrected scenario is passed to the model
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_corrected_scenario_included_in_prompt():
    """When corrected is provided, the prompt must mention the recommended resistor."""
    from app.services import ai_agent
    from app.services.ai_agent import _build_user_message

    corrected = _scenario(r=330.0, i=9.09, s="safe")
    msg = _build_user_message(_req(), _scenario(r=0, i=600, s="danger"), corrected)

    assert "330" in msg
    assert "9.09" in msg
