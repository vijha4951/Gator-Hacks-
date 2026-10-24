from fastapi import APIRouter, Request

from app.services.ai_agent import GeminiClient

router = APIRouter(prefix="/api/gemini", tags=["Gemini"])


@router.get("/status")
async def gemini_status(request: Request):
    """Report whether the app-owned Gemini client is configured and ready.

    Returns 200 in both cases: a configured client is a bonus, and an
    unconfigured one is a supported state (analyze falls back to rule-based
    text). The body makes the missing/invalid-key case visible instead of
    silent.
    """
    client: GeminiClient = request.app.state.gemini
    return client.status()
