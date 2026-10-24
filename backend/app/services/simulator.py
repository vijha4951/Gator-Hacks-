from typing import Protocol
from app.schemas import CircuitRequest


class SimulationError(Exception):
    """Raised when the simulator can't produce a result."""


class Simulator(Protocol):
    name: str

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float: ...


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


class PhysBoxSimulator:
    """Member 5 implements this: build the circuit in Volt, call circuit_run_sim
    via MCP, extract the LED current. Verify real tool names first."""
    name = "physbox"

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float:
        raise SimulationError("PhysBox simulator not implemented yet")