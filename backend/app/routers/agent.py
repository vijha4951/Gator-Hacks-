from fastapi import APIRouter, Depends, HTTPException
from app.config import get_simulator
from app.schemas import AgentAnalyzeResponse, CircuitRequest
from app.services.ai_agent import client
from app.services.agent import run_agent_analysis
from app.services.simulator import SimulationError, Simulator

router = APIRouter(prefix="/api/agent", tags=["Agent"])

@router.post("/analyze", response_model=AgentAnalyzeResponse)
async def agent_analyze(req: CircuitRequest, sim: Simulator = Depends(get_simulator)):
    try:
        return await run_agent_analysis(req, sim, client)
    except SimulationError as exc:
        raise HTTPException(status_code=502, detail=f"Simulation failed: {exc}") from exc
