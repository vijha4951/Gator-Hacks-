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


async def create_project_plan(
    request: PlanRequest, gemini: GeminiClient
) -> PlanResponse:
    """Generate and validate a project plan using the app-owned Gemini client."""
    if not gemini.configured:
        raise PlanningError("Gemini is not configured. Planning is unavailable.")

    try:
        # Load separately here to report missing or malformed reference data
        # distinctly before making a paid model request.
        reference = load_verified_references()
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.error("Planner reference data unavailable: %s", exc)
        raise PlanningError("Planner reference data is unavailable.") from exc

    clarification = confirmation_response_for_request(request, reference)
    if clarification is not None:
        return clarification

    try:
        user_message = build_planning_input(request)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        logger.error("Planner request could not be prepared: %s", exc)
        raise PlanningError("Planner reference data is unavailable.") from exc

    try:
        raw_plan = await gemini.generate_json_plan(
            system_instruction=PROJECT_PLANNING_SYSTEM_PROMPT,
            user_message=user_message,
        )
        if not raw_plan:
            raise ValueError("Gemini returned an empty plan.")
        parsed_plan = PlanResponse.model_validate_json(raw_plan)
        return validate_generated_plan(request, parsed_plan, reference)
    except (ValidationError, ValueError, TypeError) as exc:
        logger.warning("Gemini returned an invalid project plan: %s", exc)
        raise PlanningError("No plan was produced.") from exc
    except Exception as exc:  # noqa: BLE001 - never substitute a fabricated plan
        logger.warning("Gemini project planning failed (%s).", type(exc).__name__)
        raise PlanningError("No plan was produced.") from exc
