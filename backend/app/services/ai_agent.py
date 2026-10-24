from app.schemas import CircuitRequest, Scenario


async def explain(
    circuit: CircuitRequest, original: Scenario, corrected: Scenario | None
) -> str | None:
    """Member 3 replaces this with the LLM agent. Return None to use the
    rule-based text from analysis.py."""
    return None