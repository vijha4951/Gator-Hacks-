"""Trusted reference loading and separate Gemini instructions for planning.

This module does not create a circuit, assign Arduino pins, generate firmware,
or claim that a physical build has been checked.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.schemas import PlanRequest


_REFERENCE_FILE = (
    Path(__file__).resolve().parents[1] / "data" / "verified_references.json"
)


@lru_cache(maxsize=1)
def load_verified_references() -> dict[str, Any]:
    """Load the reviewed JSON reference used by project planning."""
    with _REFERENCE_FILE.open("r", encoding="utf-8") as reference_file:
        data = json.load(reference_file)
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("project_scope"), dict)
        or not isinstance(data.get("verified"), dict)
        or not isinstance(data.get("verified", {}).get("components"), list)
        or not isinstance(data.get("verified", {}).get("board"), dict)
        or not isinstance(data.get("unknown"), list)
        or not isinstance(data.get("unsupported"), list)
        or not isinstance(data.get("pricing"), dict)
        or not isinstance(data.get("project_scope", {}).get("board"), str)
        or not isinstance(data.get("verified", {}).get("board", {}).get("name"), str)
        or not all(
            isinstance(component, dict)
            and isinstance(component.get("id"), str)
            and isinstance(component.get("name"), str)
            and isinstance(component.get("facts", {}), dict)
            for component in data.get("verified", {}).get("components", [])
        )
    ):
        raise ValueError(f"Invalid planner reference structure: {_REFERENCE_FILE}")
    return data


PROJECT_PLANNING_SYSTEM_PROMPT = """\
You are CircuitGuard AI's project planner. Help a complete beginner plan only
within the verified reference supplied with each request. Treat that reference
as the sole source for technical facts; do not rely on general memory to fill
gaps.

If the user asks for a color-changing LED, explain that the supplied v1
reference supports only one red LED and cannot make it change color. Do not
suggest RGB, WS2812/NeoPixel, or another multi-color substitute. If the user
has not accepted the single-red-LED scope, set status to needs_confirmation
and ask whether that simpler project is acceptable.

For every item in the reference's unknown list, either ask a relevant question
or mark the affected detail with the exact phrase "Needs confirmation" and
briefly explain why. Do not invent pin assignments, board limits, resistor
ratings or values, compatibility, code, prices, or part numbers. Do not provide
wire-by-wire directions, diagrams, firmware, or complete Arduino sketches.
Do not give advice for unsupported items listed in the reference.
The 220 Ω and 330 Ω resistor examples are demo values only; never present them
as the correct value for an unconfirmed physical supply and LED.

Return a beginner-friendly summary, scope, questions, assumptions, required
and optional parts, a few broad stages, safety notes, simulator checks, and
limitations. Each stage must include its goal, what to observe, and what to
check before continuing. Describe the simulator only within its documented
scope. A simulated result never proves a physical build is safe.

Use needs_confirmation when a missing or unsupported fact blocks a responsible
plan, such as a request for a color-changing LED when only one red LED is
verified. Ask the user a concise question and do not present the plan as
complete. Use ready only when the plan fits the verified scope; non-blocking
questions may remain. Set a part's obtain flag to true only when the user
explicitly says they need it, false when they say they own it, and null when
ownership is not known.

Return only a JSON object matching PlanResponse. Questions must each have an
id, question, and why_it_matters. scope must have included and not_included
lists. simulator_checks must have can_verify and cannot_verify lists. Each
part must include name, quantity, purpose, verified_ratings, obtain, and notes.
Do not treat a part as owned merely because the user did not mention it;
unknown ownership should be null.
Do not include prices or simulated-current measurements in this planning
response. Circuit measurements are returned by the separate circuit-analysis
feature.
"""


def build_planning_input(request: PlanRequest) -> str:
    """Build the user/reference payload for a future Gemini planning call."""
    data = {
        "user_request": request.model_dump(mode="json"),
        "verified_reference": load_verified_references(),
    }
    return json.dumps(data, ensure_ascii=False)


