"""LLM-driven (agentic) circuit analysis — the hybrid's agent path.

This is the optional counterpart to the deterministic analyze_circuit pipeline.
Here Gemini genuinely drives the workflow: it is given a set of circuit tools
and decides, turn by turn, to build the circuit, run the simulation, and read
the result, then reasons about whether it is safe.

Design guarantees that keep this a *hybrid*, not a gamble:
  - The model can only call tools this module exposes and executes; it cannot
    invent tool names or reach anything outside the whitelist.
  - A hard iteration cap stops runaway loops and cost.
  - If the agent loop errors or stalls, we fall back to the deterministic
    analyze_circuit() result so the caller always gets a trustworthy answer.
  - The tools run against whatever Simulator is active: real PhysBox when
    available, the mock otherwise, so the agentic behaviour demos either way.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.schemas import (
    AgentAnalyzeResponse,
    AnalyzeResponse,
    CircuitRequest,
    ToolCall,
)
from app.services.ai_agent import GeminiClient
from app.services.analysis import analyze_circuit, classify
from app.services.simulator import Simulator

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 8

_AGENT_SYSTEM_PROMPT = """\
You are an electronics lab agent diagnosing a beginner's simulated LED circuit.
You have tools that build the circuit, run a SPICE simulation, and read the
simulated LED current. Work step by step:
1. Build the circuit from the given parameters.
2. Run the simulation.
3. Read the resulting LED current.
4. If the circuit is unsafe, build a corrected version with the suggested
   resistor and simulate again to confirm the fix.
5. Give a final 3-5 sentence plain-English explanation.

Rules:
- Always label currents and voltages as "simulated" values. Never present them
  as real bench measurements.
- Use only numbers the tools return. Do not invent values.
- A current above 20 mA is dangerous (the LED may burn out); below 1 mA is too
  dim; in between is safe.
"""


def _tool_definitions() -> list[dict]:
    """Function declarations handed to Gemini (Interactions API tool format)."""
    return [
        {
            "type": "function",
            "name": "simulate_circuit",
            "description": (
                "Build the LED circuit with the given values, run the SPICE "
                "simulation, and return the simulated LED current in milliamps "
                "plus a safety classification."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "voltage": {"type": "number", "description": "Source voltage in volts"},
                    "resistance": {"type": "number", "description": "Series resistance in ohms (0 means no resistor)"},
                    "led_forward_voltage": {"type": "number", "description": "LED forward voltage in volts"},
                },
                "required": ["voltage", "resistance", "led_forward_voltage"],
            },
        },
        {
            "type": "function",
            "name": "suggest_resistor_value",
            "description": (
                "Given the source and LED forward voltages, return a recommended "
                "real (E12) series resistor value in ohms that targets a safe LED "
                "current. Returns null if the source voltage is too low."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "voltage": {"type": "number"},
                    "led_forward_voltage": {"type": "number"},
                },
                "required": ["voltage", "led_forward_voltage"],
            },
        },
    ]


class _ToolExecutor:
    """Runs the whitelisted tools against the active simulator."""

    def __init__(self, sim: Simulator) -> None:
        self.sim = sim

    async def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "simulate_circuit":
            return await self._simulate(args)
        if name == "suggest_resistor_value":
            return self._suggest(args)
        # The model asked for a tool we never advertised. Report, don't crash.
        return {"error": f"Unknown tool '{name}'."}

    async def _simulate(self, args: dict[str, Any]) -> dict[str, Any]:
        from app.services.analysis import MAX_SAFE_MA  # local import avoids cycle noise

        req = CircuitRequest(
            voltage=float(args["voltage"]),
            resistance=float(args["resistance"]),
            led_forward_voltage=float(args["led_forward_voltage"]),
        )
        current_ma = await self.sim.measure_led_current_ma(req)
        return {
            "current_ma": current_ma,
            "status": classify(current_ma),
            "max_safe_ma": MAX_SAFE_MA,
            "simulated_with": self.sim.name,
        }

    def _suggest(self, args: dict[str, Any]) -> dict[str, Any]:
        from app.services.analysis import suggest_resistor

        probe = CircuitRequest(
            voltage=float(args["voltage"]),
            resistance=0.0,
            led_forward_voltage=float(args["led_forward_voltage"]),
        )
        value = suggest_resistor(probe)
        return {"recommended_resistance_ohms": value}


# --- Resilient readers for the Interactions API response objects -------------
# The google-genai SDK returns model objects; be tolerant of attribute vs dict
# access and snake_case vs camelCase, mirroring the style in physbox_client.


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _as_dict(obj: Any) -> dict:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json", exclude_none=True)
    return {}


def _function_calls(response: Any) -> list[dict]:
    """Extract function-call outputs from an interaction response."""
    outputs = _get(response, "outputs", default=[]) or []
    calls: list[dict] = []
    for item in outputs:
        if _get(item, "type") == "function_call":
            raw_args = _get(item, "arguments", default={}) or {}
            if isinstance(raw_args, str):
                try:
                    raw_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    raw_args = {}
            calls.append({
                "name": _get(item, "name"),
                "id": _get(item, "id", "call_id"),
                "arguments": raw_args,
            })
    return calls


def _final_text(response: Any) -> str:
    """Pull the final text answer from a completed interaction."""
    text = _get(response, "output_text", "outputText")
    if isinstance(text, str) and text.strip():
        return text.strip()
    # Fall back to scanning outputs/steps for a text item.
    for key in ("outputs", "steps"):
        for item in _get(response, key, default=[]) or []:
            if _get(item, "type") == "text":
                t = _get(item, "text")
                if isinstance(t, str) and t.strip():
                    return t.strip()
    return ""


async def run_agent_analysis(
    req: CircuitRequest, sim: Simulator, gemini: GeminiClient
) -> AgentAnalyzeResponse:
    """Run the LLM-driven loop, always returning a trustworthy deterministic core.

    The deterministic analyze_circuit() runs regardless and is returned as
    `analysis`. The agent loop produces `agent_explanation` and the tool-call
    transcript; on any failure we set `fell_back=True` and reuse the
    deterministic recommendation as the explanation.
    """
    # The trustworthy backbone — computed independently of the agent.
    deterministic: AnalyzeResponse = await analyze_circuit(req, sim, gemini)

    if not gemini.configured:
        return AgentAnalyzeResponse(
            agent_explanation=deterministic.recommendation,
            tool_calls=[],
            iterations=0,
            fell_back=True,
            analysis=deterministic,
        )

    executor = _ToolExecutor(sim)
    tools = _tool_definitions()
    transcript: list[ToolCall] = []

    user_prompt = (
        "Diagnose this LED circuit. "
        f"Source voltage: {req.voltage} V. "
        f"Series resistance: {req.resistance} ohms "
        f"({'no resistor' if req.resistance == 0 else 'resistor present'}). "
        f"LED forward voltage: {req.led_forward_voltage} V."
    )

    try:
        response = await gemini.create_interaction(
            system_instruction=_AGENT_SYSTEM_PROMPT,
            input=user_prompt,
            tools=tools,
        )

        iterations = 0
        while iterations < MAX_ITERATIONS:
            iterations += 1
            status = _get(response, "status")
            calls = _function_calls(response)

            if status != "requires_action" and not calls:
                break  # model produced a final answer

            if not calls:
                break  # nothing actionable; stop

            # Execute each requested tool and gather the results to send back.
            results_input: list[dict] = []
            for call in calls:
                result = await executor.run(call["name"], call["arguments"])
                transcript.append(ToolCall(
                    tool=call["name"] or "unknown",
                    arguments=call["arguments"],
                    result=result,
                ))
                results_input.append({
                    "type": "function_result",
                    "name": call["name"],
                    "call_id": call["id"],
                    "result": [{"type": "text", "text": json.dumps(result)}],
                })

            response = await gemini.create_interaction(
                input=results_input,
                tools=tools,
                previous_interaction_id=_get(response, "id"),
            )

        explanation = _final_text(response)
        if not explanation:
            # Loop ended without a clean final answer; use the reliable text.
            return AgentAnalyzeResponse(
                agent_explanation=deterministic.recommendation,
                tool_calls=transcript,
                iterations=iterations,
                fell_back=True,
                analysis=deterministic,
            )

        return AgentAnalyzeResponse(
            agent_explanation=explanation,
            tool_calls=transcript,
            iterations=iterations,
            fell_back=False,
            analysis=deterministic,
        )

    except Exception as exc:  # noqa: BLE001 - agent must never break the endpoint
        logger.warning("Agent loop failed (%s: %s); using deterministic result.",
                       type(exc).__name__, exc)
        return AgentAnalyzeResponse(
            agent_explanation=deterministic.recommendation,
            tool_calls=transcript,
            iterations=len(transcript),
            fell_back=True,
            analysis=deterministic,
        )
