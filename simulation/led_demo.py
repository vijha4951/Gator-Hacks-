"""Run the LED demo through a running PhysBox MCP server and Volt tab."""
import argparse
import asyncio
import json
import math
from pathlib import Path

from fastmcp import Client


def build_led_circuit(supply_voltage=5.0, resistance_ohms=220.0):
    """Build a fresh circuit; reject invalid inputs before contacting Volt."""
    for name, value in (("supply_voltage", supply_voltage),
                        ("resistance_ohms", resistance_ohms)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be finite; voltage must be positive and resistance nonnegative")
        if not math.isfinite(value) or value < 0 or (name == "supply_voltage" and value == 0):
            raise ValueError(f"{name} must be finite; voltage must be positive and resistance nonnegative")
    circuit = json.loads(Path(__file__).with_name("led_220.json").read_text())
    nodes = {node["id"]: node for node in circuit["nodes"]}
    nodes["sg1"]["data"].update(value=supply_voltage, label=f"{supply_voltage:g}V")
    nodes["r1"]["data"].update(value=resistance_ohms, label=f"{resistance_ohms:g}")
    if resistance_ohms == 0:
        # Missing resistor means a direct wire, not an artificial resistance floor.
        circuit["nodes"] = [node for node in circuit["nodes"] if node["id"] != "r1"]
        circuit["edges"] = [edge for edge in circuit["edges"]
                            if "r1" not in (edge["source"], edge["target"])]
        circuit["edges"].append({
            "id": "direct-source-led", "source": "sg1", "sourceHandle": "pos",
            "target": "led1", "targetHandle": "anode", "type": "smoothstep",
        })
    return circuit


async def run_led_demo(supply_voltage=5.0, resistance_ohms=220.0):
    """Run one circuit and return actual PhysBox measurements in mA and V."""
    circuit = build_led_circuit(supply_voltage, resistance_ohms)
    async with Client("http://localhost:3141/mcp", timeout=60) as client:
        tools = {tool.name for tool in await client.list_tools()}
        required = {"detect_apps", "circuit_validate_circuit", "circuit_set_circuit",
                    "circuit_run_sim", "circuit_get_waveforms"}
        if missing := required - tools:
            raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")

        async def call(name, arguments=None):
            result = await client.call_tool(name, arguments or {})
            if result.is_error:
                raise RuntimeError(f"{name}: {result}")
            return result.data

        apps = await call("detect_apps")
        volt = next((app for app in apps if app["id"] == "circuit"), None)
        if not volt or not volt["wsConnected"]:
            raise RuntimeError("Open https://volt.physbox.io on this computer and allow local access.")
        if volt.get("sessionCount") != 1:
            raise RuntimeError("Keep exactly one Volt tab open to avoid changing the wrong circuit.")
        validation = await call("circuit_validate_circuit", circuit)
        if not validation.get("ok"):
            raise RuntimeError(f"Circuit validation failed: {validation}")
        await call("circuit_set_circuit", {**circuit, "runSim": False})
        simulation = await call("circuit_run_sim")
        if not simulation.get("ok"):
            raise RuntimeError(f"Simulation failed: {str(simulation)[:500]}")
        # Volt may acknowledge Run before waveform data reaches the canvas.
        started = asyncio.get_running_loop().time()
        previous_measurement = None
        stable_reads = 0
        for attempt in range(40):
            waveforms = await call("circuit_get_waveforms")
            nodes = {node["id"]: node for node in waveforms.get("nodes", [])}
            led = nodes.get("led1", {})
            samples = led.get("current_array", [])
            if samples and "voltage" in nodes.get("vm_led", {}):
                measurement = (len(samples), samples[-1], nodes["vm_led"]["voltage"])
                stable_reads = stable_reads + 1 if measurement == previous_measurement else 1
                previous_measurement = measurement
                # Volt can publish initial values before its damaged-LED state settles.
                if stable_reads >= 3 and asyncio.get_running_loop().time() - started >= 2:
                    break
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError(
                "Volt did not publish stable LED current and meter voltage within the polling window. "
                "Keep the Volt tab visible, check for simulation errors, and try again."
            )
        return {
            "led_current_mA": samples[-1] * 1000 if resistance_ohms else None,
            "measurement_status": "available" if resistance_ohms else "unavailable",
            "measurement_note": (None if resistance_ohms else
                                 "No reliable current: Volt LED readings vary with the damaged model state."),
            "led_voltage_V": nodes["vm_led"]["voltage"],
            "sample_count": len(samples),
            "supply_voltage_V": supply_voltage,
            "resistance_ohms": resistance_ohms,
            # A fixed 2 V estimate, not a PhysBox measurement or safety verdict.
            "simplified_expected_current_mA": (max(supply_voltage - 2, 0) / resistance_ohms * 1000
                                              if resistance_ohms else None),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voltage", type=float, default=5.0, help="DC supply in volts (default: 5)")
    parser.add_argument("--resistance", type=float, default=220.0, help="Resistance in ohms (default: 220)")
    args = parser.parse_args()
    try:
        result = asyncio.run(run_led_demo(args.voltage, args.resistance))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
