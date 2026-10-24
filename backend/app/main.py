from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import analyze, physbox
from app.services.physbox_client import PhysBoxMCPClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep one MCP subprocess for the life of the API. If PhysBox is offline,
    # mock mode remains usable and /api/physbox/status reports the problem.
    app.state.physbox = PhysBoxMCPClient()
    await app.state.physbox.start()
    try:
        yield
    finally:
        await app.state.physbox.stop()

app = FastAPI(title="CircuitGuard AI", lifespan=lifespan)
# Volt has one active circuit; keep each request's original and corrected runs
# together so concurrent API requests cannot overwrite one another.
app.state.circuit_analysis_lock = asyncio.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analyze.router)
app.include_router(physbox.router)


@app.get("/health")
def health():
    return {"ok": True}
