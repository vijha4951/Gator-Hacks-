"""Tests for GeminiClient — no real API calls are made."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import CircuitRequest, Scenario
from app.services.ai_agent import GeminiClient, _build_user_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _req(**kw) -> CircuitRequest:
    defaults = dict(voltage=5.0, resistance=220.0, led_forward_voltage=2.0)
    return CircuitRequest(**(defaults | kw))


def _scenario(r=220.0, i=13.29, s="safe") -> Scenario:
    return Scenario(resistance=r, current_ma=i, status=s)


def _started_client(mock_genai_client) -> GeminiClient:
    """Build a GeminiClient whose underlying genai.Client is mocked."""
    client = GeminiClient()
    with patch("app.config.settings") as mock_settings, \
         patch("google.genai.Client", return_value=mock_genai_client):
        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model = "gemini-3.5-flash"
        client.start()
    return client


# ---------------------------------------------------------------------------
# start(): unconfigured when no API key
# ---------------------------------------------------------------------------

def test_not_configured_without_api_key():
    """With no key, start() leaves the client unconfigured (fail-safe)."""
    client = GeminiClient()
    with patch("app.config.settings") as mock_settings:
        mock_settings.gemini_api_key = None
        client.start()

    assert client.configured is False
    assert client.status()["configured"] is False


# ---------------------------------------------------------------------------
# explain(): fallback when unconfigured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_returns_none_when_unconfigured():
    """An unconfigured client must return None (triggering rule-based text)."""
    client = GeminiClient()  # never started
    result = await client.explain(_req(), _scenario(), None)
    assert result is None


# ---------------------------------------------------------------------------
# explain(): fallback on API error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_returns_none_on_api_error():
    """Any exception from the Gemini call must be caught; return None."""
    mock_genai = MagicMock()
    mock_genai.aio.models.generate_content = AsyncMock(
        side_effect=RuntimeError("quota exceeded")
    )
    client = _started_client(mock_genai)
    assert client.configured is True

    result = await client.explain(_req(), _scenario(), None)
    assert result is None


# ---------------------------------------------------------------------------
# explain(): happy path forwards the model text
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_returns_text_on_success():
    """explain() returns the model's text when the API succeeds."""
    expected = "Simulated current looks fine for this LED."
    mock_response = MagicMock()
    mock_response.text = expected

    mock_genai = MagicMock()
    mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)
    client = _started_client(mock_genai)

    result = await client.explain(_req(), _scenario(), None)
    assert result == expected


# ---------------------------------------------------------------------------
# explain(): empty response falls back to None
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_explain_returns_none_on_empty_response():
    """If the model returns an empty string, fall back to rule-based text."""
    mock_response = MagicMock()
    mock_response.text = "   "  # whitespace only

    mock_genai = MagicMock()
    mock_genai.aio.models.generate_content = AsyncMock(return_value=mock_response)
    client = _started_client(mock_genai)

    result = await client.explain(_req(), _scenario(), None)
    assert result is None


# ---------------------------------------------------------------------------
# Prompt building: corrected scenario is included
# ---------------------------------------------------------------------------

def test_corrected_scenario_included_in_prompt():
    """When corrected is provided, the prompt must mention the recommended resistor."""
    corrected = _scenario(r=330.0, i=9.09, s="safe")
    msg = _build_user_message(_req(), _scenario(r=0, i=600, s="danger"), corrected)

    assert "330" in msg
    assert "9.09" in msg
