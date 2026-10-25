"""Tests for the live backend PhysBoxSimulator against a fake MCP client.

These replace an older set of tests that targeted an early prototype
(`simulation/led_demo.py`, a no-arg PhysBoxSimulator). The backend's
PhysBoxSimulator takes an MCP client and drives the circuit_* tools, so the
tests fake that client and assert on the tool calls and parsing.
"""

from __future__ import annotations

import asyncio

import pytest

from app.schemas import CircuitRequest
from app.services.simulator import PhysBoxSimulator, SimulationError


class FakeMCPClient:
    """Minimal stand-in for PhysBoxMCPClient used by PhysBoxSimulator.

    `state_nodes` is what circuit_get_state returns under "nodes". By default
    it reports a healthy LED current_array (amps) that the simulator converts
    to milliamps.
    """

    def __init__(self, *, connected=True, last_error=None, state_nodes=None,
                 validation=None, fail_tool=None, fail_exc=None):
        self.connected = connected
        self.last_error = last_error
        self._state_nodes = state_nodes if state_nodes is not None else [
            {"id": "led1", "data": {"current_array": [0.010, 0.013, 0.01329]}},
        ]
        self._validation = validation if validation is not None else {"valid": True}
        self._fail_tool = fail_tool
        self._fail_exc = fail_exc
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments or {}))
        if self._fail_tool == name and self._fail_exc is not None:
            raise self._fail_exc
        if name == "circuit_validate_circuit":
            return self._validation
        if name == "circuit_set_circuit":
            return {"ok": True}
        if name == "circuit_run_sim":
            return {"ok": True}
        if name == "circuit_get_state":
            return {"nodes": self._state_nodes}
        return {}


def _req(**kw) -> CircuitRequest:
    return CircuitRequest(**({"voltage": 5.0, "resistance": 220.0} | kw))


def test_returns_led_current_in_milliamps():
    """The final current_array sample (amps) is converted to mA."""
    sim = PhysBoxSimulator(FakeMCPClient())
    result = asyncio.run(sim.measure_led_current_ma(_req()))
    assert result == pytest.approx(13.29)  # 0.01329 A -> 13.29 mA


def test_runs_the_expected_tool_sequence():
    """It validates, sets the circuit, runs the sim, then reads state."""
    client = FakeMCPClient()
    sim = PhysBoxSimulator(client)
    asyncio.run(sim.measure_led_current_ma(_req()))
    names = [name for name, _ in client.calls]
    assert names == [
        "circuit_validate_circuit",
        "circuit_set_circuit",
        "circuit_run_sim",
        "circuit_get_state",
    ]


def test_disconnected_client_raises_simulation_error():
    client = FakeMCPClient(connected=False, last_error="Volt disconnected")
    sim = PhysBoxSimulator(client)
    with pytest.raises(SimulationError, match="Volt disconnected"):
        asyncio.run(sim.measure_led_current_ma(_req()))


def test_validation_failure_raises():
    client = FakeMCPClient(validation={"valid": False, "errors": ["bad node"]})
    sim = PhysBoxSimulator(client)
    with pytest.raises(SimulationError, match="rejected"):
        asyncio.run(sim.measure_led_current_ma(_req()))


def test_missing_current_array_raises():
    """A state with no LED current_array is an explicit error, not a silent 0."""
    client = FakeMCPClient(state_nodes=[{"id": "led1", "data": {}}])
    sim = PhysBoxSimulator(client)
    with pytest.raises(SimulationError, match="current_array"):
        asyncio.run(sim.measure_led_current_ma(_req()))


def test_no_resistor_still_builds_and_simulates():
    """A zero-ohm request (forgot the resistor) still runs end to end."""
    client = FakeMCPClient()
    sim = PhysBoxSimulator(client)
    result = asyncio.run(sim.measure_led_current_ma(_req(resistance=0)))
    assert result == pytest.approx(13.29)
    # The built circuit wired the source straight to the LED (no r1 node).
    set_call = next(args for name, args in client.calls if name == "circuit_set_circuit")
    node_ids = {n["id"] for n in set_call["nodes"]}
    assert "r1" not in node_ids
