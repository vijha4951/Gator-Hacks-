"""Tests for the LLM-driven agent loop — no real API calls are made.

Gemini's create_interaction is faked to simulate a two-turn tool-calling loop:
turn 1 the model requests the simulate_circuit tool, turn 2 it returns a final
answer. The mock simulator provides deterministic currents.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.schemas import CircuitRequest
from app.services.agent import run_agent_analysis
from app.services.simulator import MockSimulator


def _req(resistance=0.0) -> CircuitRequest:
    return CircuitRequest(voltage=5.0, resistance=resistance, led_forward_voltage=2.0)


class _FakeInteraction:
    def __init__(self, *, status, outputs=None, output_text="", id="i1"):
        self.status = status
        self.outputs = outputs or []
        self.output_text = output_text
        self.id = id


class _FakeGemini:
    """Configured Gemini stub driving a scripted tool-calling loop."""

    def __init__(self, responses):
        self.configured = True
        self._responses = list(responses)
        self.calls = []

    async def create_interaction(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)

    # run_agent_analysis also calls explain() via analyze_circuit (deterministic core)
    explain = AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_agent_runs_tool_then_answers():
    """Model requests a tool, we execute it, model returns a final explanation."""
    turn1 = _FakeInteraction(
        status="requires_action",
        outputs=[{
            "type": "function_call",
            "name": "simulate_circuit",
            "id": "fc_1",
            "arguments": {"voltage": 5.0, "resistance": 0.0, "led_forward_voltage": 2.0},
        }],
        id="i1",
    )
    turn2 = _FakeInteraction(
        status="completed",
        output_text="The simulated current is dangerously high; add a resistor.",
    )
    gemini = _FakeGemini([turn1, turn2])

    result = await run_agent_analysis(_req(resistance=0.0), MockSimulator(), gemini)

    assert result.fell_back is False
    assert result.iterations == 2  # turn 1 ran the tool, turn 2 returned the answer
    assert "resistor" in result.agent_explanation
    # The transcript recorded the tool the agent chose and its real result.
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool == "simulate_circuit"
    assert result.tool_calls[0].result["status"] == "danger"
    # The deterministic backbone is still attached.
    assert result.analysis.status == "danger"


@pytest.mark.asyncio
async def test_agent_falls_back_when_unconfigured():
    """An unconfigured Gemini yields the deterministic result with fell_back=True."""
    class _Unconfigured:
        configured = False
        explain = AsyncMock(return_value=None)

    result = await run_agent_analysis(_req(resistance=0.0), MockSimulator(), _Unconfigured())

    assert result.fell_back is True
    assert result.tool_calls == []
    assert result.agent_explanation == result.analysis.recommendation


@pytest.mark.asyncio
async def test_agent_falls_back_on_api_error():
    """If the interaction call raises, we fall back to the deterministic result."""
    class _Boom:
        configured = True
        explain = AsyncMock(return_value=None)

        async def create_interaction(self, **kwargs):
            raise RuntimeError("network down")

    result = await run_agent_analysis(_req(resistance=220.0), MockSimulator(), _Boom())

    assert result.fell_back is True
    assert result.analysis.status == "safe"
