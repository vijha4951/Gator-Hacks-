from fastapi import APIRouter, Depends, HTTPException, Request
from app.config import get_simulator
from app.schemas import AnalyzeResponse, CircuitRequest
from app.services.analysis import analyze_circuit
from app.services.simulator import SimulationError, Simulator

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: CircuitRequest, request: Request, sim: Simulator = Depends(get_simulator)):
    try:
        async with request.app.state.circuit_analysis_lock:
            return await analyze_circuit(req, sim)
    except SimulationError as e:
        raise HTTPException(status_code=502, detail=f"Simulation failed: {e}")
