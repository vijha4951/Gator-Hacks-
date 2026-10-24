import asyncio
import math
from typing import Protocol
from app.schemas import CircuitRequest


class SimulationError(Exception):
    """Raised when the simulator can't produce a result."""


class Simulator(Protocol):
    name: str

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float | None: ...


class MockSimulator:
    """Plain Ohm's law. For development ONLY. Never present as a real simulation."""
    name = "mock"
    MIN_OHMS = 5.0  # avoids divide-by-zero; stands in for LED internal resistance

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float:
        drop = circuit.voltage - circuit.led_forward_voltage
        if drop <= 0:
            return 0.0
        r = max(circuit.resistance, self.MIN_OHMS)
        return round(drop / r * 1000, 2)


# All requests in this process share the same browser canvas.
# Run FastAPI with a single worker; do not run the CLI concurrently.
_physbox_lock = asyncio.Lock()


class PhysBoxSimulator:
    """Bridge to the verified red-LED demo. No mock fallback."""
    name = "physbox"

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float | None:
        if not math.isfinite(circuit.led_forward_voltage) or circuit.led_forward_voltage != 2.0:
            raise SimulationError("Only the verified red LED model (led_forward_voltage=2.0) is supported")
        if not math.isfinite(circuit.resistance) or circuit.resistance < 0:
            raise SimulationError("Resistance must be finite and nonnegative")
        try:
            from simulation.led_demo import run_led_demo
            async with _physbox_lock:
                result = await run_led_demo(
                    supply_voltage=circuit.voltage,
                    resistance_ohms=circuit.resistance,
                )
            # Volt's missing-resistor LED readings change with its damaged state.
            # Even apparently stable samples are not a verified current measurement.
            if circuit.resistance == 0:
                return None
            current = float(result["led_current_mA"])
            if not math.isfinite(current) or current < 0:
                raise ValueError("PhysBox returned an invalid LED current")
            return current
        except Exception as exc:
            raise SimulationError(f"PhysBox could not measure LED current: {exc}") from exc
