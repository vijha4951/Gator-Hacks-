from fastapi import APIRouter, HTTPException, Request

from app.services.physbox_client import PhysBoxMCPClient

router = APIRouter(prefix="/api/physbox", tags=["PhysBox"])


@router.get("/status")
async def physbox_status(request: Request, check_volt: bool = True):
    """Check the app-owned MCP connection and, by default, query Volt read-only."""
    client: PhysBoxMCPClient = request.app.state.physbox
    status = await client.status(check_volt=check_volt)
    if not status["connected"] or (check_volt and not status.get("volt_reachable")):
        raise HTTPException(status_code=503, detail=status)
    return status


@router.get("/tool-schemas")
async def physbox_tool_schemas(request: Request):
    """Expose the circuit tool input contracts for backend integration work."""
    client: PhysBoxMCPClient = request.app.state.physbox
    if not client.connected:
        raise HTTPException(status_code=503, detail=client.last_error)
    allowed = {
        "circuit_get_state",
        "circuit_get_schema",
        "circuit_get_summary",
        "circuit_get_waveforms",
        "circuit_run_sim",
        "circuit_set_circuit",
        "circuit_validate_circuit",
    }
    return {"tools": client.tool_schemas(allowed)}


@router.get("/circuit-schema")
async def physbox_circuit_schema(request: Request):
    """Read the active Volt component schema without changing the circuit."""
    client: PhysBoxMCPClient = request.app.state.physbox
    try:
        return await client.call_tool("circuit_get_schema")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
