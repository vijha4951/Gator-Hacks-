"""FastAPI application for gator-hacks."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from gator_hacks import hello


class GreetingResponse(BaseModel):
    message: str


app = FastAPI(
    title="gator-hacks",
    description="FastAPI service with MCP and OpenAI integration",
    version="0.1.0",
)


@app.get("/", response_model=GreetingResponse)
async def root() -> GreetingResponse:
    return GreetingResponse(message=hello())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
