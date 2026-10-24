from fastapi import APIRouter, Depends, HTTPException
from app.config import get_simulator
from app.schemas import AnalyzeResponse, CircuitRequest
from app.services.analysis import analyze_circuit
from app.services.simulator import SimulationError, Simulator

router = APIRouter(prefix="/api")


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: CircuitRequest, sim: Simulator = Depends(get_simulator)):
    try:
        return await analyze_circuit(req, sim)
    except SimulationError as e:
        raise HTTPException(status_code=502, detail=f"Simulation failed: {e}")