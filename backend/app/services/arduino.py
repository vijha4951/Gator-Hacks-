"""Single-process USB serial control for the Uno sketch in hardware/led_serial.

Commands (one per line, 9600 baud). The Uno echoes the command to acknowledge it:
  LED_ON / LED_OFF       pin 8 (LED circuit)
  MODE_SWITCH            pin 8 LED follows the switch on pin 2 (echoes MODE_SWITCH)
  SWITCH?                replies SWITCH_CLOSED or SWITCH_OPEN
  RGB r g b              pins 9/10/11, each 0 or 1 (echoes the command)
"""
import threading
import time
from typing import Callable, Literal

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

    def _exchange(self, command: str, accepts: Callable[[str], bool]) -> str:
        """Send one command and return the first reply that `accepts` approves."""
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
                    if accepts(reply):
                        return reply
                    if reply and reply != "READY":
                        hint = " (re-upload hardware/led_serial/led_serial.ino)" if reply.startswith("ERROR") else ""
                        raise HardwareError(f"Unexpected Arduino reply: {reply[:100]}{hint}")
                raise HardwareError("No matching Arduino acknowledgement; physical LED state is unconfirmed")
            except (OSError, serial.SerialException, HardwareError) as exc:
                self._disconnect()
                raise HardwareError(
                    f"Arduino communication failed: {exc}. Close Serial Monitor, check USB and ARDUINO_PORT, then retry."
                ) from exc

    def set_led(self, state: Literal["on", "off"]):
        if state not in ("on", "off"):
            raise HardwareError("LED state must be on or off")
        command = "LED_ON" if state == "on" else "LED_OFF"
        reply = self._exchange(command, lambda r: r == command)
        return {
            "state": state, "acknowledged": True,
            "reply": reply, "port": self.port,
            "note": "Arduino acknowledged the output command; LED light and current are not measured.",
        }

    def set_rgb(self, r: bool, g: bool, b: bool):
        command = f"RGB {int(bool(r))} {int(bool(g))} {int(bool(b))}"
        reply = self._exchange(command, lambda x: x == command)
        return {
            "r": bool(r), "g": bool(g), "b": bool(b), "acknowledged": True,
            "reply": reply, "port": self.port,
            "note": "Arduino acknowledged the output command; LED light and current are not measured.",
        }

    def follow_switch(self):
        """Pin 8 LED follows the switch on pin 2 until LED_ON/LED_OFF is sent."""
        reply = self._exchange("MODE_SWITCH", lambda r: r == "MODE_SWITCH")
        return {"mode": "switch", "acknowledged": True, "reply": reply, "port": self.port}

    def read_switch(self):
        reply = self._exchange("SWITCH?", lambda r: r in ("SWITCH_OPEN", "SWITCH_CLOSED"))
        return {"closed": reply == "SWITCH_CLOSED", "reply": reply, "port": self.port}
