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


def test_explanation_source_is_rules_when_gemini_returns_none():
    """With the offline stub (explain -> None), the source must be 'rules'."""
    r = client.post("/api/analyze",
                    json={"voltage": 5, "resistance": 220, "led_forward_voltage": 2.0})
    assert r.status_code == 200
    body = r.json()
    assert body["explanation_source"] == "rules"
    # The recommendation is the deterministic rule-based sentence.
    assert "resistor" in body["recommendation"].lower()


def test_explanation_source_is_gemini_when_model_answers():
    """When explain() returns text, the source is 'gemini' and text is used."""
    text = "The simulation shows a safe current for this LED."
    app.state.gemini = type("G", (), {"explain": AsyncMock(return_value=text)})()
    try:
        r = client.post("/api/analyze",
                        json={"voltage": 5, "resistance": 220, "led_forward_voltage": 2.0})
    finally:
        # Restore the offline stub for the remaining tests.
        app.state.gemini = type("G", (), {"explain": AsyncMock(return_value=None)})()

    body = r.json()
    assert body["explanation_source"] == "gemini"
    assert body["recommendation"] == text


def test_current_ma_none_is_unavailable():
    """A simulator that returns None yields null current and 'Unavailable' text."""
    class _NoReadingSim:
        name = "mock"
        async def measure_led_current_ma(self, circuit):
            return None

    app.dependency_overrides[get_simulator] = lambda: _NoReadingSim()
    try:
        r = client.post("/api/analyze",
                        json={"voltage": 5, "resistance": 0, "led_forward_voltage": 2.0})
    finally:
        app.dependency_overrides[get_simulator] = lambda: MockSimulator()

    assert r.status_code == 200
    body = r.json()
    assert body["current_ma"] is None
    assert body["original"]["current_ma"] is None
    # No corrected run is attempted without a reading.
    assert body["corrected"] is None
    # The rule-based text (source 'rules' since gemini stub returns None) says Unavailable.
    assert body["explanation_source"] == "rules"
    assert "unavailable" in body["recommendation"].lower()
