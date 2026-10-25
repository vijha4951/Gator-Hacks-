from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.services import ai_agent
from app.routers import analyze, hardware, buttons, agent

@asynccontextmanager
async def lifespan(app: FastAPI):
    ai_agent.client.start()
    try:
        yield
    finally:
        hardware.arduino.close()
        await ai_agent.close()


app = FastAPI(title="CircuitGuard AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analyze.router)
app.include_router(hardware.router)
app.include_router(buttons.router)
app.include_router(agent.router)


@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/gemini/status")
def gemini_status():
    return {"provider": "gemini", **ai_agent.client.status(),
            "note": "Configured does not confirm a successful API response."}
