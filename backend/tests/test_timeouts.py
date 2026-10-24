import asyncio
from unittest.mock import patch

import pytest

from app.config import settings
from app.schemas import CircuitRequest
from app.services import ai_agent
from app.services.analysis import analyze_circuit
from app.services.simulator import MockSimulator, SimulationError


class SlowSimulator(MockSimulator):
    name = "slow"

    async def measure_led_current_ma(self, circuit):
        await asyncio.sleep(5)
        return 0.0


def _req(**kw) -> CircuitRequest:
    return CircuitRequest(**({"voltage": 5.0, "resistance": 220.0} | kw))


async def test_slow_ai_falls_back_to_rules():
    async def slow_explain(*args, **kwargs):
        await asyncio.sleep(5)
        return "this should never be returned"

    with patch.object(settings, "ai_timeout_seconds", 0.05), \
         patch.object(ai_agent, "explain", new=slow_explain):
        result = await analyze_circuit(_req(), MockSimulator())

    assert "this should never" not in result.recommendation
    assert "mA" in result.recommendation          # rule-based text was used
    assert result.status == "safe"


async def test_slow_simulator_raises_simulation_error():
    with patch.object(settings, "sim_timeout_seconds", 0.05):
        with pytest.raises(SimulationError, match="did not respond"):
            await analyze_circuit(_req(), SlowSimulator())


async def test_fast_ai_still_used():
    async def fast_explain(*args, **kwargs):
        return "AI text"

    with patch.object(ai_agent, "explain", new=fast_explain):
        result = await analyze_circuit(_req(), MockSimulator())

    assert result.recommendation == "AI text"