from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import analyze, hardware

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    hardware.arduino.close()


app = FastAPI(title="CircuitGuard AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analyze.router)
app.include_router(hardware.router)


@app.get("/health")
def health():
    return {"ok": True}