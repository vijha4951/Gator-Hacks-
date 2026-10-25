from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import agent, analyze, gemini, physbox
from app.services.ai_agent import GeminiClient
from app.services.physbox_client import PhysBoxMCPClient


def _configure_app_logging() -> None:
    """Route the `app` package loggers through uvicorn's handler at INFO.

    uvicorn attaches handlers only to its own `uvicorn*` loggers and leaves the
    root at WARNING, so application `logger.info(...)` calls (e.g. the per-phase
    request timings in analysis.py) are otherwise dropped. Borrow uvicorn's
    handlers when present so timing lines share the server's log format and
    stream; fall back to a basic handler when running outside uvicorn (tests,
    scripts).
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    uvicorn_logger = logging.getLogger("uvicorn")
    if uvicorn_logger.handlers:
        app_logger.handlers = uvicorn_logger.handlers
        app_logger.propagate = False
    elif not app_logger.handlers:
        app_logger.addHandler(logging.StreamHandler())
        app_logger.propagate = False


_configure_app_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Re-run now that uvicorn's handlers are installed, so app INFO logs (the
    # per-phase request timings) share the server's log stream and format.
    _configure_app_logging()

    # Build one Gemini client for the life of the API. If no key is configured,
    # it stays unconfigured and analyze falls back to rule-based text;
    # /api/gemini/status reports the state.
    app.state.gemini = GeminiClient()
    app.state.gemini.start()

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
app.include_router(gemini.router)
app.include_router(agent.router)


@app.get("/health")
def health():
    return {"ok": True}
