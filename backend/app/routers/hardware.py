from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from serial.tools import list_ports

from app.config import settings
from app.services.arduino import ArduinoLED, HardwareError

router = APIRouter(prefix="/api/hardware", tags=["Hardware"])
arduino = ArduinoLED(settings.arduino_port)


def get_arduino() -> ArduinoLED:
    return arduino


class LEDRequest(BaseModel):
    state: Literal["on", "off"]


@router.get("/ports")
def ports():
    """List ports for configuration; does not open a USB connection."""
    return {"ports": [{"device": p.device, "description": p.description}
                      for p in list_ports.comports()]}


@router.post("/led")
def set_led(req: LEDRequest, device: ArduinoLED = Depends(get_arduino)):
    try:
        return device.set_led(req.state)
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


class ButtonRequest(BaseModel):
    button: Literal["on", "off"]


@router.post("/buttons")
def press_button(req: ButtonRequest, device: ArduinoLED = Depends(get_arduino)):
    """Website ON/OFF action; does not physically depress a button."""
    try:
        return device.set_led(req.button)
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/state")
def read_state(device: ArduinoLED = Depends(get_arduino)):
    """Poll this endpoint to reflect physical button presses in the frontend."""
    try:
        return device.read_state()
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _switch_state(device: ArduinoLED):
    # Frontend's switch indicator represents the latched LED output. The two
    # physical momentary button inputs remain available as separate fields.
    state = device.read_state()
    return {**state, "closed": state["state"] == "on", "mode": "two-button-latch"}


@router.get("/switch")
def switch_state(device: ArduinoLED = Depends(get_arduino)):
    """Compatibility route for the deployed switch screen; reads real USB state."""
    try:
        return _switch_state(device)
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/switch/follow")
def follow_switch(device: ArduinoLED = Depends(get_arduino)):
    """Frontend Turn on action: command ON, then read the actual latch.

    Physical buttons continue to control the latch after this command.
    """
    try:
        acknowledgement = device.set_led("on")
        return {**_switch_state(device),
                "acknowledged": acknowledgement["acknowledged"]}
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
