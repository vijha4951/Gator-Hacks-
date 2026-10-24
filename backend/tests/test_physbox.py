import asyncio

import pytest
from fastapi.testclient import TestClient

from app.config import get_simulator
from app.main import app
from app.schemas import CircuitRequest
from app.services.simulator import PhysBoxSimulator, SimulationError
from simulation import led_demo


def test_physbox_endpoint_passes_inputs_and_returns_milliamps(monkeypatch):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"led_current_mA": 8.9863}

    monkeypatch.setattr(led_demo, "run_led_demo", run)
    app.dependency_overrides[get_simulator] = PhysBoxSimulator
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"voltage": 5, "resistance": 330})
        assert response.status_code == 200
        body = response.json()
        assert body["current_ma"] == 8.9863
        assert body["simulated_with"] == "physbox"
        assert body["corrected"] is None
        assert calls == [{"supply_voltage": 5, "resistance_ohms": 330}]
    finally:
        app.dependency_overrides.clear()


def test_disconnected_simulator_returns_502(monkeypatch):
    async def run(**kwargs):
        raise RuntimeError("Volt disconnected")

    monkeypatch.setattr(led_demo, "run_led_demo", run)
    app.dependency_overrides[get_simulator] = PhysBoxSimulator
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"voltage": 5, "resistance": 220})
        assert response.status_code == 502
        assert "Volt disconnected" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("updates", [{"resistance": -1}, {"led_forward_voltage": 3}])
def test_unsupported_models_are_explicit(updates):
    req = CircuitRequest(voltage=5, resistance=220).model_copy(update=updates)
    with pytest.raises(SimulationError):
        asyncio.run(PhysBoxSimulator().measure_led_current_ma(req))


def test_shared_canvas_is_serialized(monkeypatch):
    from app.services import simulator

    async def scenario():
        monkeypatch.setattr(simulator, "_physbox_lock", asyncio.Lock())
        active = 0

        async def run(**kwargs):
            nonlocal active
            active += 1
            assert active == 1
            await asyncio.sleep(0.01)
            active -= 1
            return {"led_current_mA": 9}

        monkeypatch.setattr(led_demo, "run_led_demo", run)
        req = CircuitRequest(voltage=5, resistance=330)
        results = await asyncio.gather(
            PhysBoxSimulator().measure_led_current_ma(req),
            PhysBoxSimulator().measure_led_current_ma(req),
        )
        assert results == [9, 9]

    asyncio.run(scenario())


def test_missing_resistor_is_direct_wire():
    circuit = led_demo.build_led_circuit(resistance_ohms=0)
    ids = {node["id"] for node in circuit["nodes"]}
    assert "r1" not in ids
    assert all(edge["source"] in ids and edge["target"] in ids for edge in circuit["edges"])
    assert any(edge["source"] == "sg1" and edge["target"] == "led1"
               and edge["sourceHandle"] == "pos" and edge["targetHandle"] == "anode"
               for edge in circuit["edges"])
    assert any(node["id"] == "r1" for node in led_demo.build_led_circuit()["nodes"])


def test_no_resistor_endpoint_runs_original_and_correction(monkeypatch):
    calls = []

    async def run(**kwargs):
        calls.append(kwargs)
        return {"led_current_mA": 50 if kwargs["resistance_ohms"] == 0 else 13.29}

    monkeypatch.setattr(led_demo, "run_led_demo", run)
    app.dependency_overrides[get_simulator] = PhysBoxSimulator
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"voltage": 5, "resistance": 0})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "danger"
        assert body["current_ma"] is None
        assert body["original"]["current_ma"] is None
        assert body["corrected"]["current_ma"] == 13.29
        assert "unavailable" in body["recommendation"]
        assert "50" not in body["recommendation"]
        assert body["corrected"]["resistance"] == 220
        assert body["corrected"]["status"] == "safe"
        assert body["simulated_with"] == "physbox"
        assert any("unavailable" in warning for warning in body["warnings"])
        assert [c["resistance_ohms"] for c in calls] == [0, 220]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("reported_current", [50, 474.73158877, None])
def test_no_resistor_current_is_never_exposed_as_verified(monkeypatch, reported_current):
    async def run(**kwargs):
        return {"led_current_mA": reported_current}
    monkeypatch.setattr(led_demo, "run_led_demo", run)
    req = CircuitRequest(voltage=5, resistance=0)
    assert asyncio.run(PhysBoxSimulator().measure_led_current_ma(req)) is None


def test_unavailable_original_does_not_call_legacy_ai(monkeypatch):
    from app.services import ai_agent
    async def run(**kwargs):
        return {"led_current_mA": None if kwargs["resistance_ohms"] == 0 else 13.29}
    async def explain(*args):
        raise AssertionError("Legacy AI must not format an unavailable measurement")
    monkeypatch.setattr(led_demo, "run_led_demo", run)
    monkeypatch.setattr(ai_agent, "explain", explain)
    app.dependency_overrides[get_simulator] = PhysBoxSimulator
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"voltage": 5, "resistance": 0})
        assert response.status_code == 200
        assert response.json()["current_ma"] is None
    finally:
        app.dependency_overrides.clear()


def test_missing_resistor_failure_is_not_hidden(monkeypatch):
    async def run(**kwargs):
        raise RuntimeError("Volt disconnected")
    monkeypatch.setattr(led_demo, "run_led_demo", run)
    app.dependency_overrides[get_simulator] = PhysBoxSimulator
    try:
        with TestClient(app) as client:
            response = client.post("/api/analyze", json={"voltage": 5, "resistance": 0})
        assert response.status_code == 502
        assert "Volt disconnected" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
