"""Offline tests for project planning; no live Gemini calls are made."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.schemas import PlanPart, PlanRequest, PlanResponse, PlanStage
from app.main import app
from app.services.ai_agent import GeminiClient
from app.services.planner import PlanningError, create_project_plan
from app.services.plan_validation import InvalidGeneratedPlan, validate_generated_plan
from app.services.planning import load_verified_references

_SAMPLES = Path(__file__).resolve().parents[1] / "app" / "data" / "plan_contract_samples.json"
_API = TestClient(app)


class _StubGemini:
    configured = True

    def __init__(self, result: str):
        self.result = result
        self.calls = []

    async def generate_json_plan(self, *, user_message: str, system_instruction: str) -> str:
        self.calls.append((user_message, system_instruction))
        return self.result


class _FailedGemini:
    configured = True

    async def generate_json_plan(self, *, user_message: str, system_instruction: str) -> str:
        raise ConnectionError("Gemini is unavailable")


def _sample_objects() -> tuple[dict, dict]:
    samples = json.loads(_SAMPLES.read_text(encoding="utf-8"))
    request = PlanRequest.model_validate(samples["request"])
    response = PlanResponse.model_validate(samples["needs_confirmation_response"])
    return request.model_dump(mode="json"), response.model_dump(mode="json")


@pytest.mark.asyncio
async def test_unconfigured_gemini_fails_without_a_plan():
    request = PlanRequest(project_description="Plan a red LED project")
    with pytest.raises(PlanningError, match="Gemini is not configured"):
        await create_project_plan(request, GeminiClient())


def test_plan_endpoint_returns_503_when_gemini_is_unconfigured():
    previous = getattr(app.state, "gemini", None)
    app.state.gemini = GeminiClient()
    try:
        response = _API.post(
            "/api/plan",
            json={"project_description": "color-changing LED with Arduino Uno R3"},
        )
    finally:
        if previous is None:
            del app.state.gemini
        else:
            app.state.gemini = previous

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini is not configured. Planning is unavailable."


@pytest.mark.parametrize("raw_plan", ["", "This is not JSON", "[]", "{\"status\":\"ready\"}"])
@pytest.mark.asyncio
async def test_empty_non_json_or_invalid_schema_fails_without_a_plan(raw_plan: str):
    request = PlanRequest(project_description="Plan a red LED project")
    gemini = _StubGemini(raw_plan)

    with pytest.raises(PlanningError, match="No plan was produced"):
        await create_project_plan(request, gemini)

    assert len(gemini.calls) == 1


@pytest.mark.asyncio
async def test_valid_json_is_returned_as_plan_response():
    response = {
        "status": "ready",
        "project_summary": "A simple red LED indicator circuit.",
        "scope": {
            "included": ["One red LED, a series resistor, and a positive DC source with ground."],
            "not_included": ["Pin assignments, firmware, and physical safety certification."],
        },
        "questions": [],
        "assumptions": ["The simulator uses the verified red LED model."],
        "parts": [
            {
                "name": "Red LED", "quantity": 1, "purpose": "Visible indicator",
                "verified_ratings": ["color: red", "model forward voltage: 2.0 V", "maximum current: 20 mA"],
                "obtain": None, "notes": [],
            },
            {
                "name": "Series current-limiting resistor", "quantity": 1,
                "purpose": "Limit LED current", "verified_ratings": ["required", "E12 preferred values"],
                "obtain": None, "notes": [],
            },
            {
                "name": "DC voltage source", "quantity": 1,
                "purpose": "Supply the series circuit", "verified_ratings": ["positive DC relative to ground"],
                "obtain": None, "notes": [],
            },
        ],
        "stages": [
            {
                "title": "Review the circuit model", "goal": "Understand the parts in the supported circuit.",
                "learn_or_observe": "Notice how the resistor limits current in the simulated circuit.",
                "check_before_continuing": "Check the simulated current classification.",
            }
        ],
        "safety_and_common_problems": ["The physical resistor rating still needs confirmation."],
        "simulator_checks": {
            "can_verify": ["Simulated current through the modeled red LED circuit."],
            "cannot_verify": ["Physical wiring or Arduino Uno R3 pin behavior."],
        },
        "limitations": ["Simulation does not prove a physical build is safe."],
    }
    request = PlanRequest(
        project_description="Build a red LED indicator",
        board_model="Arduino Uno R3",
    )
    gemini = _StubGemini(json.dumps(response))

    result = await create_project_plan(request, gemini)

    assert isinstance(result, PlanResponse)
    assert result.status == "ready"
    assert len(result.parts) == 3
    assert any("Needs confirmation" in note for note in result.parts[1].notes)
    user_message, system_instruction = gemini.calls[0]
    assert '"verified_reference"' in user_message
    assert request.project_description in user_message
    assert "Do not invent" in system_instruction


@pytest.mark.asyncio
async def test_complete_color_changing_uno_demo_returns_structured_confirmation():
    samples = json.loads(_SAMPLES.read_text(encoding="utf-8"))
    request = PlanRequest.model_validate(samples["request"])
    gemini = _StubGemini("should not be used")

    result = await create_project_plan(request, gemini)

    assert isinstance(result, PlanResponse)
    assert result.status == "needs_confirmation"
    assert result.questions[0].id == "single_red_led_confirmation"
    assert "one red LED" in result.project_summary
    assert result.parts == []
    assert gemini.calls == []


@pytest.mark.asyncio
async def test_unspecified_led_type_prompts_instead_of_assuming_red():
    request = PlanRequest(
        project_description="Help me plan a simple LED project",
        board_model="Arduino Uno R3",
    )
    gemini = _StubGemini("should not be used")

    result = await create_project_plan(request, gemini)

    assert result.status == "needs_confirmation"
    assert result.questions[0].id == "led_type_confirmation"
    assert "red LED" in result.questions[0].question
    assert gemini.calls == []


@pytest.mark.asyncio
async def test_required_but_unspecified_board_prompts_instead_of_assuming_uno():
    request = PlanRequest(
        project_description="Plan a single red LED project",
        constraints={"must_use_board": True},
    )
    gemini = _StubGemini("should not be used")

    result = await create_project_plan(request, gemini)

    assert result.status == "needs_confirmation"
    assert any(question.id == "board_model_confirmation" for question in result.questions)
    assert result.parts == []
    assert gemini.calls == []


@pytest.mark.asyncio
async def test_unsupported_project_request_prompts_without_returning_a_plan():
    request = PlanRequest(
        project_description="Build a battery-powered RGB LED project with a transistor",
    )
    gemini = _StubGemini("should not be used")

    result = await create_project_plan(request, gemini)

    assert result.status == "needs_confirmation"
    assert len(result.questions) >= 1
    assert result.parts == []
    assert result.stages == []
    assert gemini.calls == []


@pytest.mark.asyncio
async def test_gemini_connection_failure_returns_clear_planning_error():
    request = PlanRequest(
        project_description="Plan a single red LED indicator",
        board_model="Arduino Uno R3",
    )

    with pytest.raises(PlanningError, match="No plan was produced"):
        await create_project_plan(request, _FailedGemini())


def test_plan_endpoint_returns_503_when_gemini_connection_fails():
    previous = getattr(app.state, "gemini", None)
    app.state.gemini = _FailedGemini()
    try:
        response = _API.post(
            "/api/plan",
            json={
                "project_description": "Plan a single red LED indicator",
                "board_model": "Arduino Uno R3",
            },
        )
    finally:
        if previous is None:
            del app.state.gemini
        else:
            app.state.gemini = previous

    assert response.status_code == 503
    assert response.json() == {"detail": "No plan was produced."}


def test_plan_endpoint_returns_503_for_malformed_gemini_output():
    previous = getattr(app.state, "gemini", None)
    app.state.gemini = _StubGemini("This is not JSON")
    try:
        response = _API.post(
            "/api/plan",
            json={
                "project_description": "Plan a single red LED indicator",
                "board_model": "Arduino Uno R3",
            },
        )
    finally:
        if previous is None:
            del app.state.gemini
        else:
            app.state.gemini = previous

    assert response.status_code == 503
    assert response.json() == {"detail": "No plan was produced."}


@pytest.mark.asyncio
async def test_color_changing_request_gets_confirmation_without_using_gemini():
    request = PlanRequest(
        project_description="color-changing LED with Arduino Uno R3",
        board_model="Arduino Uno R3",
    )
    gemini = _StubGemini("should not be used")

    result = await create_project_plan(request, gemini)

    assert result.status == "needs_confirmation"
    assert result.questions[0].id == "single_red_led_confirmation"
    assert gemini.calls == []


def test_unsupported_goal_is_never_returned_as_ready():
    _, response = _sample_objects()
    request = PlanRequest(
        project_description="color-changing LED with Arduino Uno R3",
        board_model="Arduino Uno R3",
    )
    plan = PlanResponse.model_validate(response)
    plan.status = "ready"

    checked = validate_generated_plan(request, plan, load_verified_references())

    assert checked.status == "needs_confirmation"
    assert any(question.id == "single_red_led_confirmation" for question in checked.questions)


def test_unverified_part_is_rejected():
    _, response = _sample_objects()
    plan = PlanResponse.model_validate(response)
    plan.parts.append(PlanPart(
        name="RGB LED", quantity=1, purpose="Change colors", obtain=None,
    ))

    with pytest.raises(InvalidGeneratedPlan, match="unverified part"):
        validate_generated_plan(
            PlanRequest(project_description="Plan a red LED project"),
            plan,
            load_verified_references(),
        )


def test_unverified_electrical_rating_is_rejected():
    _, response = _sample_objects()
    plan = PlanResponse.model_validate(response)
    plan.parts.append(PlanPart(
        name="Red LED",
        quantity=1,
        purpose="Visible indicator",
        verified_ratings=["current sourcing limit verified"],
    ))

    with pytest.raises(InvalidGeneratedPlan, match="unverified rating"):
        validate_generated_plan(
            PlanRequest(project_description="Plan a red LED project"),
            plan,
            load_verified_references(),
        )


def test_unverified_electrical_number_is_rejected_even_in_notes():
    _, response = _sample_objects()
    plan = PlanResponse.model_validate(response)
    plan.limitations.append("Use a 3.3 V supply for this project.")

    with pytest.raises(InvalidGeneratedPlan, match="electrical value absent"):
        validate_generated_plan(
            PlanRequest(project_description="Plan a red LED project"),
            plan,
            load_verified_references(),
        )


def test_pin_instructions_are_rejected():
    _, response = _sample_objects()
    plan = PlanResponse.model_validate(response)
    plan.stages.append(PlanStage(
        title="Connect the LED",
        goal="Connect the LED to pin 13.",
        learn_or_observe="Observe the LED.",
        check_before_continuing="Check the LED lights.",
    ))

    with pytest.raises(InvalidGeneratedPlan, match="pin number"):
        validate_generated_plan(
            PlanRequest(project_description="Plan a red LED project"),
            plan,
            load_verified_references(),
        )


@pytest.mark.parametrize(
    ("instruction", "reason"),
    [
        ("void setup() { digitalWrite(13, HIGH); }", "Arduino code"),
        ("Connect the LED anode to 5 V and ground.", "wire-by-wire"),
    ],
)
def test_complete_code_and_wire_by_wire_instructions_are_rejected(instruction, reason):
    _, response = _sample_objects()
    plan = PlanResponse.model_validate(response)
    plan.stages.append(PlanStage(
        title="Build the circuit",
        goal=instruction,
        learn_or_observe="Observe the model.",
        check_before_continuing="Review the result.",
    ))

    with pytest.raises(InvalidGeneratedPlan, match=reason):
        validate_generated_plan(
            PlanRequest(project_description="Plan a red LED project"),
            plan,
            load_verified_references(),
        )
