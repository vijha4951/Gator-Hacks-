from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


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