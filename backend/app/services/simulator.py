import asyncio
import math
import json
from typing import Any, Protocol

from app.schemas import CircuitRequest
from app.services.physbox_client import PhysBoxConnectionError, PhysBoxMCPClient


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


# All requests in this process share the same browser canvas.
# Run FastAPI with a single worker; do not run the CLI concurrently.
_physbox_lock = asyncio.Lock()


class PhysBoxSimulator:
    """Build and run the request's LED circuit in PhysBox: Volt."""
    name = "physbox"

    def __init__(self, client: PhysBoxMCPClient) -> None:
        self.client = client

    @staticmethod
    def build_led_circuit(circuit: CircuitRequest) -> tuple[list[dict], list[dict]]:
        """Create the small Volt graph used by the MVP."""
        nodes: list[dict] = [
            {"id": "v1", "type": "voltage", "position": {"x": 80, "y": 140}, "data": {"label": f"{circuit.voltage:g}V"}},
            {"id": "led1", "type": "led", "position": {"x": 500, "y": 140}, "data": {"label": "Red LED", "color": "red", "v_drop": circuit.led_forward_voltage, "max_current": 20}},
            {"id": "g1", "type": "ground", "position": {"x": 500, "y": 290}, "data": {"label": "GND"}},
        ]
        edges: list[dict] = []

        if circuit.resistance > 0:
            nodes.append({"id": "r1", "type": "resistor", "position": {"x": 300, "y": 140}, "data": {"label": f"{circuit.resistance:g}"}})
            edges.extend([
                {"id": "e-v1-r1", "source": "v1", "target": "r1", "sourceHandle": "pos", "targetHandle": "in", "type": "smoothstep"},
                {"id": "e-r1-led1", "source": "r1", "target": "led1", "sourceHandle": "out", "targetHandle": "anode", "type": "smoothstep"},
            ])
        else:
            # A zero-ohm request means the user omitted the current-limiting resistor.
            edges.append({"id": "e-v1-led1", "source": "v1", "target": "led1", "sourceHandle": "pos", "targetHandle": "anode", "type": "smoothstep"})

        edges.extend([
            {"id": "e-led1-g1", "source": "led1", "target": "g1", "sourceHandle": "cathode", "targetHandle": "in", "type": "smoothstep"},
            {"id": "e-v1-g1", "source": "v1", "target": "g1", "sourceHandle": "neg", "targetHandle": "in", "type": "smoothstep"},
        ])
        return nodes, edges

    @staticmethod
    def _payload(result: Any) -> Any:
        """Read structured MCP output, falling back to its JSON text block."""
        if isinstance(result, dict):
            structured = result.get("structured_content")
            if structured is not None:
                return structured
            for block in result.get("content", []):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    try:
                        return json.loads(block["text"])
                    except json.JSONDecodeError:
                        continue
        return result

    @classmethod
    def _led_current_ma(cls, state_result: Any) -> float:
        state = cls._payload(state_result)
        if not isinstance(state, dict):
            raise SimulationError("PhysBox returned circuit state in an unsupported format.")
        nodes = state.get("nodes")
        if not isinstance(nodes, list):
            raise SimulationError("PhysBox circuit state did not contain a nodes array.")
        led = next((node for node in nodes if isinstance(node, dict) and node.get("id") == "led1"), None)
        data = led.get("data") if isinstance(led, dict) else None
        currents = data.get("current_array") if isinstance(data, dict) else None
        if not isinstance(currents, list) or not currents:
            raise SimulationError("PhysBox ran the circuit but returned no LED current_array.")
        samples = [float(value) for value in currents if isinstance(value, (int, float)) and math.isfinite(value)]
        if not samples:
            raise SimulationError("PhysBox returned no finite LED current samples.")
        # Volt's schema documents current_array in amperes; use the final transient sample.
        return round(abs(samples[-1]) * 1000, 2)

    async def measure_led_current_ma(self, circuit: CircuitRequest) -> float:
        if not self.client.connected:
            raise SimulationError(self.client.last_error or "PhysBox MCP is not connected.")
        nodes, edges = self.build_led_circuit(circuit)
        try:
            validation = self._payload(await self.client.call_tool(
                "circuit_validate_circuit", {"nodes": nodes, "edges": edges}
            ))
            if isinstance(validation, dict):
                if validation.get("valid") is False:
                    raise SimulationError(f"PhysBox rejected the LED circuit: {validation}")
                errors = validation.get("errors")
                if isinstance(errors, list) and errors:
                    raise SimulationError(f"PhysBox rejected the LED circuit: {errors}")

            await self.client.call_tool("circuit_set_circuit", {"nodes": nodes, "edges": edges, "runSim": False})
            await self.client.call_tool("circuit_run_sim")
            state = await self.client.call_tool("circuit_get_state")
            return self._led_current_ma(state)
        except PhysBoxConnectionError as exc:
            raise SimulationError(str(exc)) from exc
