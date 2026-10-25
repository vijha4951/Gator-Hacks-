from pathlib import Path
import os
import shutil
import sys
import sysconfig

from fastapi import Request
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.simulator import MockSimulator, PhysBoxSimulator, Simulator

# Resolve .env relative to the project, not the current working directory.
# Without this, the key only loads when the app happens to be launched from the
# directory containing .env. We look in backend/ first, then the repo root
# (config.py is at backend/app/config.py, so parents are app/ -> backend/ -> repo/).
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_FILES = (_BACKEND_DIR / ".env", _REPO_ROOT / ".env")


def _physbox_command_defaults() -> tuple[str, list[str]]:
    """Find the installed console script even when its Scripts folder is off PATH."""
    command = shutil.which("physbox-mcp")
    if command:
        return command, ["--stdio"]

    scheme = "nt_user" if os.name == "nt" else "posix_user"
    script_name = "physbox-mcp.exe" if os.name == "nt" else "physbox-mcp"
    installed_script = Path(sysconfig.get_path("scripts", scheme=scheme)) / script_name
    if installed_script.is_file():
        return str(installed_script), ["--stdio"]

    return sys.executable, ["-m", "physbox_mcp.server", "--stdio"]


_PHYSBOX_COMMAND, _PHYSBOX_ARGS = _physbox_command_defaults()


class Settings(BaseSettings):
    # pydantic-settings accepts multiple files; later entries win on conflict.
    model_config = SettingsConfigDict(env_file=[str(p) for p in _ENV_FILES])

    simulator: str = "physbox"  # set SIMULATOR=mock to use the offline estimate
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite default

    # The FastAPI process launches its own MCP client connection. PhysBox MCP
    # then joins the local relay already used by the coding assistant.
    physbox_mcp_command: str = _PHYSBOX_COMMAND
    physbox_mcp_args: list[str] = _PHYSBOX_ARGS

    # Gemini API – optional; falls back to rule-based explanation if absent
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"

    # Timeouts (seconds)
    ai_timeout_seconds: float = 10.0   # Gemini explanation; falls back to rule-based text
    sim_timeout_seconds: float = 20.0  # per simulator call; failure -> HTTP 502
    plan_timeout_seconds: float = 45.0 # project planning; failure -> HTTP 503


settings = Settings()


def get_simulator(request: Request) -> Simulator:
    if settings.simulator.lower() == "physbox":
        return PhysBoxSimulator(request.app.state.physbox)
    return MockSimulator()
