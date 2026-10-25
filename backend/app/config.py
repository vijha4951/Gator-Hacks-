from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.simulator import MockSimulator, PhysBoxSimulator, Simulator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    arduino_port: str | None = None  # e.g. /dev/cu.usbmodem11201 or COM3
    simulator: str = "mock"  # set SIMULATOR=physbox in .env when ready
    # Match this project's Vercel preview/branch hosts, not arbitrary Vercel sites.
    cors_origin_regex: str | None = (
        r"^https://circuitgaurd-[a-z0-9-]+-gatorhacks-vivi\.vercel\.app$"
    )
    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "https://circuitgaurd.vercel.app",
    ]


settings = Settings()


def get_simulator() -> Simulator:
    return PhysBoxSimulator() if settings.simulator == "physbox" else MockSimulator()