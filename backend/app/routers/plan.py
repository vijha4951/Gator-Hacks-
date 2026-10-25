"""API route for beginner project planning."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.schemas import PlanRequest, PlanResponse
from app.services.ai_agent import GeminiClient
from app.services.planner import PlanningError, create_project_plan

router = APIRouter(prefix="/api", tags=["Project planning"])


@router.post("/plan", response_model=PlanResponse)
async def plan_project(body: PlanRequest, request: Request) -> PlanResponse:
    """Return a structured project plan, or a clear 503 without a fake plan."""
    gemini: GeminiClient = request.app.state.gemini
    try:
        return await asyncio.wait_for(
            create_project_plan(body, gemini),
            timeout=settings.plan_timeout_seconds,
        )
    except asyncio.TimeoutError:
        duration = f"{settings.plan_timeout_seconds:g} seconds"
        raise HTTPException(
            status_code=503,
            detail=f"Planning timed out after {duration}.",
        ) from None
    except PlanningError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
