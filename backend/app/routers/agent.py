from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_simulator
from app.schemas import AgentAnalyzeResponse, CircuitRequest
from app.services.agent import run_agent_analysis
from app.services.simulator import SimulationError, Simulator

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.post("/analyze", response_model=AgentAnalyzeResponse)
async def agent_analyze(
    req: CircuitRequest,
    request: Request,
    sim: Simulator = Depends(get_simulator),
):
    """LLM-driven analysis: Gemini drives the simulation tools itself.

    This is the optional 'agentic' counterpart to POST /api/analyze. It returns
    the agent's explanation, a transcript of the tools it called, and the same
    deterministic analysis as a trustworthy backbone. If the agent loop fails,
    it falls back to the deterministic result (fell_back=true).
    """
    try:
        gemini = request.app.state.gemini
        # Volt has one shared active circuit and the agent runs several sims,
        # so hold the lock for the whole agent run.
        async with request.app.state.circuit_analysis_lock:
            return await run_agent_analysis(req, sim, gemini)
    except SimulationError as e:
        raise HTTPException(status_code=502, detail=f"Simulation failed: {e}")
