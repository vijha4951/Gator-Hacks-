from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import analyze
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # start/connect the PhysBox MCP session here if Member 5 exposes a connect()
    yield
    # close it here

app = FastAPI(title="CircuitGuard AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analyze.router)


@app.get("/health")
def health():
    return {"ok": True}