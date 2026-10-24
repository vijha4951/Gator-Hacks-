from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["safe", "warning", "danger"]


class CircuitRequest(BaseModel):
    voltage: float = Field(gt=0, le=50, description="Source voltage (V)")
    # 0 = no resistor. Needed for the "forgot the resistor" demo case.
    resistance: float = Field(ge=0, description="Series resistance (ohms)")
    led_forward_voltage: float = Field(default=2.0, gt=0, le=5)


class Scenario(BaseModel):
    resistance: float
    current_ma: float | None = Field(description="Simulated current in mA; null when no reliable measurement is available")
    status: Status


class AnalyzeResponse(BaseModel): # this is what the frontend gets back after backend does its thing
    # Current may be null; clients must show unavailable, never coerce null to zero.
    status: Status
    current_ma: float | None = Field(description="Simulated current in mA; null when no reliable measurement is available")
    warnings: list[str]
    recommendation: str
    # Additions for before/after + provenance
    simulated_with: str
    original: Scenario
    corrected: Scenario | None = None