from unittest.mock import Mock

from fastapi.testclient import TestClient
import pytest
import serial

from app.main import app
from app.routers.hardware import get_arduino
from app.services.arduino import ArduinoLED, HardwareError


class FakeSerial:
    def __init__(self):
        self.writes = []
        self.replies = []
        self.closed = False

    def reset_input_buffer(self):
        pass

    def write(self, payload):
        self.writes.append(payload)
        self.replies.extend([b"READY\n", payload])
        return len(payload)

    def readline(self):
        return self.replies.pop(0) if self.replies else b""

    def close(self):
        self.closed = True


def test_usb_commands_reuse_connection_and_require_ack():
    connection = FakeSerial()
    factory = Mock(return_value=connection)
    device = ArduinoLED("TEST", serial_factory=factory, boot_delay=0)
    assert device.set_led("on")["acknowledged"] is True
    assert device.set_led("off")["state"] == "off"
    assert connection.writes == [b"LED_ON\n", b"LED_OFF\n"]
    factory.assert_called_once_with("TEST", baudrate=9600, timeout=0.25, write_timeout=2)
    device.close()
    assert connection.closed


def test_missing_port_does_not_open_usb():
    factory = Mock()
    with pytest.raises(HardwareError, match="ARDUINO_PORT"):
        ArduinoLED(None, serial_factory=factory).set_led("on")
    factory.assert_not_called()


def test_timeout_does_not_claim_success(monkeypatch):
    from app.services import arduino
    connection = FakeSerial()
    connection.readline = lambda: b""
    clock = iter([0, 1, 4])
    monkeypatch.setattr(arduino.time, "monotonic", lambda: next(clock))
    device = ArduinoLED("TEST", serial_factory=lambda *a, **k: connection, boot_delay=0)
    with pytest.raises(HardwareError, match="unconfirmed"):
        device.set_led("on")
    assert connection.closed


def test_disconnect_clears_connection_and_allows_reconnect():
    first, second = FakeSerial(), FakeSerial()
    first.write = Mock(side_effect=serial.SerialException("USB removed"))
    factory = Mock(side_effect=[first, second])
    device = ArduinoLED("TEST", serial_factory=factory, boot_delay=0)
    with pytest.raises(HardwareError, match="USB removed"):
        device.set_led("on")
    assert first.closed
    assert device.set_led("off")["acknowledged"] is True
    assert factory.call_count == 2
    device.close()


def test_hardware_endpoint_and_invalid_commands():
    connection = FakeSerial()
    device = ArduinoLED("TEST", serial_factory=lambda *a, **k: connection, boot_delay=0)
    app.dependency_overrides[get_arduino] = lambda: device
    try:
        with TestClient(app) as client:
            r = client.post("/api/hardware/led", json={"state": "on"})
            assert r.status_code == 200 and r.json()["reply"] == "LED_ON"
            r = client.post("/api/hardware/led", json={"state": "blink"})
            assert r.status_code == 422
        assert connection.writes == [b"LED_ON\n"]
    finally:
        app.dependency_overrides.clear()
        device.close()


def test_hardware_endpoint_unconfigured_returns_503():
    app.dependency_overrides[get_arduino] = lambda: ArduinoLED(None)
    try:
        with TestClient(app) as client:
            r = client.post("/api/hardware/led", json={"state": "off"})
            assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("state,closed", [("on", True), ("off", False)])
def test_deployed_switch_routes_report_real_latch(state, closed):
    device = Mock()
    device.set_led.return_value = {"acknowledged": True}
    device.read_state.return_value = {
        "state": state, "connected": True, "source": "arduino",
        "button_on_pressed": False, "button_off_pressed": False,
    }
    app.dependency_overrides[get_arduino] = lambda: device
    try:
        with TestClient(app) as client:
            read = client.get("/api/hardware/switch")
            follow = client.post("/api/hardware/switch/follow", json={})
        assert read.status_code == follow.status_code == 200
        assert read.json()["closed"] is closed
        assert follow.json()["closed"] is closed
        assert follow.json()["acknowledged"] is True
        device.set_led.assert_called_once_with("on")
    finally:
        app.dependency_overrides.clear()


def test_switch_connection_failure_is_not_reported_as_closed():
    device = Mock()
    device.read_state.side_effect = HardwareError("USB disconnected")
    app.dependency_overrides[get_arduino] = lambda: device
    try:
        with TestClient(app) as client:
            for method, path in [("GET", "/api/hardware/switch"),
                                 ("POST", "/api/hardware/switch/follow")]:
                response = client.request(method, path)
                assert response.status_code == 503
                assert response.json()["detail"] == "USB disconnected"
    finally:
        app.dependency_overrides.clear()
