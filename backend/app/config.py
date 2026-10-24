from pydantic_settings import BaseSettings, SettingsConfigDict
from app.services.simulator import MockSimulator, PhysBoxSimulator, Simulator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    simulator: str = "mock"  # set SIMULATOR=physbox in .env when ready
    cors_origins: list[str] = ["http://localhost:5173"]  # Vite default


settings = Settings()


def get_simulator() -> Simulator:
    return PhysBoxSimulator() if settings.simulator == "physbox" else MockSimulator()