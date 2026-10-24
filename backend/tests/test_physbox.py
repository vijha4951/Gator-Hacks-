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


@pytest.mark.parametrize("updates", [{"resistance": 0}, {"led_forward_voltage": 3}])
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
