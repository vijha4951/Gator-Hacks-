"""Single-process USB serial control for the verified Uno LED sketch."""
import json
import threading
import time
from typing import Literal

import serial


class HardwareError(Exception):
    pass


class ArduinoLED:
    def __init__(self, port: str | None, *, serial_factory=serial.Serial, boot_delay=2.0):
        self.port = port
        self._factory = serial_factory
        self._boot_delay = boot_delay
        self._serial = None
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            self._disconnect()

    def _disconnect(self):
        connection, self._serial = self._serial, None
        if connection is not None:
            try:
                connection.close()
            except (OSError, serial.SerialException):
                pass

    def set_led(self, state: Literal["on", "off"]):
        if state not in ("on", "off"):
            raise HardwareError("LED state must be on or off")
        command = "LED_ON" if state == "on" else "LED_OFF"
        self._exchange(command, command)
        return {"state": state, "acknowledged": True, "reply": command, "port": self.port,
                "note": "Arduino acknowledged the output command; LED light and current are not measured."}

    def read_state(self):
        reply = self._exchange("STATE", "STATE ")
        try:
            state = json.loads(reply[len("STATE "):])
            if (state.get("state") not in ("on", "off")
                    or type(state.get("button_on_pressed")) is not bool
                    or type(state.get("button_off_pressed")) is not bool
                    or (state.get("led_pin"), state.get("on_pin"), state.get("off_pin")) != (5, 9, 8)):
                raise ValueError("Unexpected two-button state fields")
        except (ValueError, TypeError, AttributeError) as exc:
            raise HardwareError("Invalid state response; upload the two_button_led sketch") from exc
        return {**state, "connected": True, "source": "arduino", "port": self.port,
                "note": "Sketch-reported state and button inputs, not a current or light measurement."}

    def _exchange(self, command, expected):
        if not self.port:
            raise HardwareError("Set ARDUINO_PORT to the Uno USB port and restart the backend")
        with self._lock:
            try:
                if self._serial is None:
                    self._serial = self._factory(
                        self.port, baudrate=9600, timeout=0.25, write_timeout=2,
                    )
                    # Opening the Uno serial port normally resets its sketch.
                    time.sleep(self._boot_delay)
                connection = self._serial
                connection.reset_input_buffer()
                connection.write((command + "\n").encode("ascii"))
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    reply = connection.readline().decode("ascii", errors="replace").strip()
                    if (reply == expected if command != "STATE" else reply.startswith(expected)):
                        return reply
                    if reply and reply != "READY":
                        raise HardwareError(f"Unexpected Arduino reply: {reply[:100]}")
                raise HardwareError("No matching Arduino acknowledgement; physical LED state is unconfirmed")
            except (OSError, serial.SerialException, HardwareError) as exc:
                self._disconnect()
                raise HardwareError(
                    f"Arduino communication failed: {exc}. Close Serial Monitor, check USB and ARDUINO_PORT, then retry."
                ) from exc
