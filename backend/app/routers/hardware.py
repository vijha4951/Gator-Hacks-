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


class RGBRequest(BaseModel):
    r: bool = False
    g: bool = False
    b: bool = False


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


@router.post("/rgb")
def set_rgb(req: RGBRequest, device: ArduinoLED = Depends(get_arduino)):
    try:
        return device.set_rgb(req.r, req.g, req.b)
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/switch/follow")
def follow_switch(device: ArduinoLED = Depends(get_arduino)):
    """Make the pin 8 LED follow the physical switch on pin 2."""
    try:
        return device.follow_switch()
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/switch")
def read_switch(device: ArduinoLED = Depends(get_arduino)):
    try:
        return device.read_switch()
    except HardwareError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
