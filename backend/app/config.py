from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.simulator import MockSimulator, PhysBoxSimulator, Simulator

# Resolve .env relative to the project, not the current working directory:
# backend/ first, then the repo root (later entries win on conflict).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (_BACKEND_DIR / ".env", _REPO_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=[str(p) for p in _ENV_FILES])

    arduino_port: str | None = None  # e.g. /dev/cu.usbmodem11201 or COM3
    simulator: str = "mock"  # set SIMULATOR=physbox in .env when ready
    # Vite dev server; both hostnames, since the browser may use either.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Gemini API - optional; falls back to rule-based explanation if absent
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"


settings = Settings()


def get_simulator() -> Simulator:
    return PhysBoxSimulator() if settings.simulator == "physbox" else MockSimulator()
