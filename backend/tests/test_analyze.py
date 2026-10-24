from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app.config import get_simulator
from app.main import app
from app.services.simulator import MockSimulator

app.dependency_overrides[get_simulator] = lambda: MockSimulator()
client = TestClient(app)


@pytest.fixture(autouse=True)
def _offline_gemini():
    """Keep these endpoint tests offline and deterministic.

    The analyze endpoint reads the app-owned Gemini client from app.state and
    calls its explain(). TestClient does not run the lifespan that normally
    builds that client, so we install a stub whose explain() returns None,
    exercising the rule-based recommendation path with no network calls.
    """
    stub = type("StubGemini", (), {"explain": AsyncMock(return_value=None)})()
    app.state.gemini = stub
    yield
    del app.state.gemini


def test_safe_circuit():
    r = client.post("/api/analyze",
                    json={"voltage": 5, "resistance": 220, "led_forward_voltage": 2.0})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "safe"
    assert body["corrected"] is None


def test_no_resistor_is_danger_and_gets_fix():
    r = client.post("/api/analyze",
                    json={"voltage": 5, "resistance": 0, "led_forward_voltage": 2.0})
    body = r.json()
    assert body["status"] == "danger"
    assert body["corrected"]["status"] == "safe"


def test_invalid_input_rejected():
    r = client.post("/api/analyze", json={"voltage": -5, "resistance": 220})
    assert r.status_code == 422
