from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

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


# Project planning has its own contract because a project idea is not a
# configured or simulated circuit.
PlanningStatus = Literal["ready", "needs_confirmation"]


class PlanContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OwnedPart(PlanContractModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    notes: str | None = Field(default=None, max_length=500)


class PlanConstraints(PlanContractModel):
    budget_usd: float | None = Field(default=None, ge=0)
    must_use_board: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


class PlanRequest(PlanContractModel):
    """Frontend input for project planning; only project_description is required."""

    project_description: str = Field(min_length=3, max_length=1200)
    board_model: str | None = Field(default=None, min_length=1, max_length=120)
    parts_owned: list[OwnedPart] = Field(default_factory=list, max_length=30)
    constraints: PlanConstraints = Field(default_factory=PlanConstraints)


class PlanQuestion(PlanContractModel):
    id: str = Field(min_length=1, max_length=80, description="Stable identifier for this follow-up question")
    question: str = Field(min_length=1, max_length=500)
    why_it_matters: str = Field(min_length=1, max_length=700, description="How the answer affects the project parts, plan, or safety")


class PlanScope(PlanContractModel):
    included: list[str] = Field(default_factory=list)
    not_included: list[str] = Field(default_factory=list)


class PlanSimulatorChecks(PlanContractModel):
    can_verify: list[str] = Field(default_factory=list)
    cannot_verify: list[str] = Field(default_factory=list)


class PlanPart(PlanContractModel):
    name: str = Field(min_length=1, max_length=120)
    quantity: int | None = Field(default=None, ge=1, le=1000)
    purpose: str
    verified_ratings: list[str] = Field(
        default_factory=list,
        description="Only details that exactly match verified reference facts; leave empty when none apply.",
    )
    # None means the planner cannot tell whether the user must obtain it.
    obtain: bool | None = Field(
        default=None,
        description="False only if the user says they own it; true only if they say they need it; otherwise null.",
    )
    notes: list[str] = Field(default_factory=list)


class PlanStage(PlanContractModel):
    title: str
    goal: str
    learn_or_observe: str
    check_before_continuing: str


class PlanResponse(PlanContractModel):
    """Structured project plan returned to the frontend."""

    status: PlanningStatus = Field(
        description="needs_confirmation when a missing or unsupported fact blocks a responsible plan; ready only when offerable within v1 scope."
    )
    project_summary: str
    scope: PlanScope
    questions: list[PlanQuestion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    parts: list[PlanPart] = Field(default_factory=list)
    stages: list[PlanStage] = Field(default_factory=list)
    safety_and_common_problems: list[str] = Field(default_factory=list)
    simulator_checks: PlanSimulatorChecks
    limitations: list[str] = Field(default_factory=list)


def validate_plan_request(payload: dict) -> PlanRequest:
    """Parse and validate a frontend planning request."""
    return PlanRequest.model_validate(payload)


def validate_plan_response(payload: dict) -> PlanResponse:
    """Parse Gemini/backend output into the agreed frontend response shape."""
    return PlanResponse.model_validate(payload)
