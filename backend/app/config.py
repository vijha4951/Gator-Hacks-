from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.simulator import MockSimulator, PhysBoxSimulator, Simulator

# Resolve .env relative to the project, not the current working directory.
# Without this, the key only loads when the app happens to be launched from the
# directory containing .env. We look in backend/ first, then the repo root
# (config.py is at backend/app/config.py, so parents are app/ -> backend/ -> repo/).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (_BACKEND_DIR / ".env", _REPO_ROOT / ".env")


class Settings(BaseSettings):
    # pydantic-settings accepts multiple files; later entries win on conflict.
    model_config = SettingsConfigDict(env_file=[str(p) for p in _ENV_FILES])

    simulator: str = "mock"  # set SIMULATOR=physbox in .env when ready
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite default

    # Gemini API – optional; falls back to rule-based explanation if absent
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    # Timeouts (seconds)
    ai_timeout_seconds: float = 10.0   # Gemini explanation; falls back to rule-based text
    sim_timeout_seconds: float = 20.0  # per simulator call; failure -> HTTP 502


settings = Settings()


def get_simulator() -> Simulator:
    return PhysBoxSimulator() if settings.simulator == "physbox" else MockSimulator()
