from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["safe", "warning", "danger"]
ExplanationSource = Literal["gemini", "rules"]


class CircuitRequest(BaseModel):
    voltage: float = Field(gt=0, le=50, description="Source voltage (V)")
    # 0 = no resistor. Needed for the "forgot the resistor" demo case.
    resistance: float = Field(ge=0, description="Series resistance (ohms)")
    led_forward_voltage: float = Field(default=2.0, gt=0, le=5)


class Scenario(BaseModel):
    resistance: float
    current_ma: float | None  # None when the simulator could not produce a reading
    status: Status


class AnalyzeResponse(BaseModel): # this is what the frontend gets back after backend does its thing
    # Fields from the original contract (unchanged, so the frontend works)
    status: Status
    current_ma: float | None  # None when the simulator could not produce a reading
    warnings: list[str]
    recommendation: str
    # Additions for before/after + provenance
    simulated_with: str
    explanation_source: ExplanationSource  # "gemini" if the LLM wrote it, else "rules"
    original: Scenario
    corrected: Scenario | None = None


class ToolCall(BaseModel):
    """One step the agent took: a tool it chose, its arguments, and the result."""
    tool: str
    arguments: dict
    result: dict


class AgentAnalyzeResponse(BaseModel):
    """Result of the LLM-driven (agentic) analysis.

    `analysis` is the same deterministic result the /api/analyze pipeline
    produces, kept as the trustworthy backbone. `agent_explanation` is the
    model's own conclusion after it drove the tools. `tool_calls` is the
    transcript of what the agent did, so the agentic behaviour is visible.
    """
    agent_explanation: str
    tool_calls: list[ToolCall]
    iterations: int
    fell_back: bool  # True if the agent loop failed and we used the deterministic result
    analysis: AnalyzeResponse