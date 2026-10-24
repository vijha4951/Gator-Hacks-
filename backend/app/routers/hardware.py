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
