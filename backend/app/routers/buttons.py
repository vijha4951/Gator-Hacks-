import math
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import Field
from app.schemas import CircuitRequest
from app.services.analysis import analyze_circuit
from app.services.simulator import SimulationError, _physbox_lock
from simulation.button_demo import run_button_demo

router = APIRouter(prefix="/api/analyze", tags=["Two-button simulation"])


class ButtonCircuitRequest(CircuitRequest):
    # Uno-style MCU model is powered at 5 V, not arbitrary input voltage.
    voltage: Literal[5] = 5
    resistance: float = Field(default=220, ge=0)
    on_pressed: bool = False
    off_pressed: bool = False
    initial_state: Literal["on", "off"] = "off"


@router.post("/buttons")
async def analyze_buttons(req: ButtonCircuitRequest):
    async def measure(circuit):
        async with _physbox_lock:
            result = await run_button_demo(circuit.resistance, circuit.led_forward_voltage,
                                           req.on_pressed, req.off_pressed, req.initial_state)
        return result
    try:
        original = await measure(req)
        if original['led_state'] == 'off':
            current = original['led_current_mA']
            if current is None or not math.isfinite(current) or abs(current) > .1:
                raise SimulationError('Expected an off output but no valid near-zero current was returned')
            return {**original, 'analysis': None,
                    'recommendation': 'LED is intentionally off. Press ON to test the conducting circuit.'}

        class ButtonSimulator:
            name = 'physbox'
            async def measure_led_current_ma(self, circuit):
                result = original if circuit.resistance == req.resistance else await measure(circuit)
                value = result['led_current_mA']
                if value is not None and (not math.isfinite(value) or value < 0):
                    raise SimulationError('Invalid button-circuit LED current')
                return value
        analysis = await analyze_circuit(req, ButtonSimulator())
        return {**original, 'analysis': analysis.model_dump(),
                'recommendation': analysis.recommendation}
    except (SimulationError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f'Two-button simulation failed: {exc}') from exc
