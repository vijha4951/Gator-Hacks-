"""Gemini-backed project planning with a trusted reference and strict output."""

from __future__ import annotations

import logging

from pydantic import ValidationError

from app.schemas import PlanRequest, PlanResponse
from app.services.ai_agent import GeminiClient
from app.services.planning import (
    PROJECT_PLANNING_SYSTEM_PROMPT,
    build_planning_input,
    load_verified_references,
)
from app.services.plan_validation import (
    confirmation_response_for_request,
    validate_generated_plan,
)

logger = logging.getLogger(__name__)


class PlanningError(Exception):
    """A planning failure that must be returned without a made-up plan."""


GEMINI_FAILURE_DETAIL = (
    "Gemini could not generate a plan. Check the backend Gemini status, "
    "model setting, API key, quota, and connection."
)


async def create_project_plan(
    request: PlanRequest, gemini: GeminiClient
) -> PlanResponse:
    """Generate and validate a project plan using the app-owned Gemini client."""
    try:
        # Load first so a deterministic clarification can be returned without
        # requiring a configured model or a paid request.
        reference = load_verified_references()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.error("Planner reference data unavailable: %s", exc)
        raise PlanningError("Planner reference data is unavailable.") from exc

    # Out-of-scope requests (e.g. color-changing LED) are answered with a
    # clarification before any model call, so this works even if Gemini is
    # unconfigured.
    clarification = confirmation_response_for_request(request, reference)
    if clarification is not None:
        return clarification

    if not gemini.configured:
        raise PlanningError("Gemini is not configured. Planning is unavailable.")

    try:
        user_message = build_planning_input(request)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.error("Planner request could not be prepared: %s", exc)
        raise PlanningError("Planner reference data is unavailable.") from exc

    # Distinguish two failure modes:
    #   - the model call itself failed (network/quota/service) -> actionable msg
    #   - the model returned something unusable (empty/non-JSON/invalid schema
    #     or outside the verified boundary) -> "No plan was produced."
    try:
        raw_plan = await gemini.generate_json_plan(
            system_instruction=PROJECT_PLANNING_SYSTEM_PROMPT,
            user_message=user_message,
        )
    except Exception as exc:  # noqa: BLE001 - surface a safe, actionable message
        logger.warning("Gemini planning request failed (%s): %s", type(exc).__name__, exc)
        raise PlanningError(GEMINI_FAILURE_DETAIL) from exc

    try:
        if not raw_plan:
            raise ValueError("Gemini returned an empty plan.")
        parsed_plan = PlanResponse.model_validate_json(raw_plan)
        return validate_generated_plan(request, parsed_plan, reference)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("Gemini returned an invalid project plan: %s", exc)
        raise PlanningError("No plan was produced.") from exc
