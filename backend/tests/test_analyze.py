from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_live_ai():
    """Keep these endpoint tests offline and deterministic.

    Without this, a GEMINI_API_KEY in .env makes analyze_circuit() issue a real
    network call to Gemini, which is slow, flaky, and can hang the suite. Forcing
    explain() to return None exercises the rule-based recommendation path.
    """
    with patch("app.services.ai_agent.explain", new=AsyncMock(return_value=None)):
        yield


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