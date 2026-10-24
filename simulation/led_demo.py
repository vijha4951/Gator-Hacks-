"""Run the LED demo through a running PhysBox MCP server and Volt tab."""
import asyncio
import json
from pathlib import Path

from fastmcp import Client


async def run_led_demo():
    circuit = json.loads(Path(__file__).with_name("led_220.json").read_text())
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
            raise RuntimeError("Open https://volt.physbox.io on this Mac and allow local access.")
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
        for attempt in range(40):
            waveforms = await call("circuit_get_waveforms")
            nodes = {node["id"]: node for node in waveforms.get("nodes", [])}
            led = nodes.get("led1", {})
            samples = led.get("current_array", [])
            if samples and "voltage" in nodes.get("vm_led", {}):
                break
            await asyncio.sleep(0.25)
        else:
            raise RuntimeError(
                "Volt did not publish LED current and meter voltage within 10 seconds. "
                "Keep the Volt tab visible, check for simulation errors, and try again."
            )
        return {
            "led_current_mA": samples[-1] * 1000,
            "led_voltage_V": nodes["vm_led"]["voltage"],
            "sample_count": len(samples),
            "simplified_expected_current_mA": (5 - 2) / 220 * 1000,
        }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_led_demo()), indent=2))
