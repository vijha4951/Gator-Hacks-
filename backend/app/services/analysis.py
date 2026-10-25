import asyncio
import logging
import time
from contextlib import asynccontextmanager

from app.config import settings
from app.schemas import AnalyzeResponse, CircuitRequest, Scenario, Status
from app.services.ai_agent import GeminiClient
from app.services.simulator import Simulator
from app.services.simulator import SimulationError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _timed(phase: str):
    """Log how long an await-heavy phase of a request takes.

    Emitted at INFO so each request's Volt/Gemini breakdown shows in the server
    log without debug logging. A phase that raises is still timed and labelled
    'failed' so a slow error is as visible as a slow success.
    """
    start = time.perf_counter()
    status = "ok"
    try:
        yield
    except BaseException:
        status = "failed"
        raise
    finally:
        logger.info("analyze phase %-18s %6.2fs (%s)", phase, time.perf_counter() - start, status)

TARGET_MA = 15.0
MAX_SAFE_MA = 20.0
MIN_VISIBLE_MA = 1.0
E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]


def classify(current_ma: float | None) -> Status:
    # No reading means we cannot confirm the LED is driven safely; warn rather
    # than claim "safe".
    if current_ma is None:
        return "warning"
    if current_ma > MAX_SAFE_MA:
        return "danger"
    if current_ma < MIN_VISIBLE_MA:
        return "warning"
    return "safe"


def _fmt_ma(current_ma: float | None, digits: int = 1) -> str:
    """Render a current reading for human text, or 'Unavailable' when missing."""
    if current_ma is None:
        return "Unavailable"
    return f"{current_ma:.{digits}f} mA"


def suggest_resistor(c: CircuitRequest) -> float | None:
    drop = c.voltage - c.led_forward_voltage
    if drop <= 0:
        return None
    ideal = drop / (TARGET_MA / 1000)
    values = [b * 10**d for d in range(0, 5) for b in E12]
    return float(min(v for v in values if v >= ideal))

async def _measure(sim: Simulator, circuit: CircuitRequest) -> float | None:
    """Run one simulation; convert a hang into a SimulationError (-> HTTP 502).

    Returns None when the simulator ran but could not produce a reading, which
    the caller renders as 'Unavailable'.
    """
    try:
        return await asyncio.wait_for(
            sim.measure_led_current_ma(circuit),
            timeout=settings.sim_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise SimulationError(
            f"simulator did not respond within {settings.sim_timeout_seconds:.0f}s"
        ) from None


async def _explain(
    gemini: GeminiClient,
    req: CircuitRequest,
    original: Scenario,
    corrected: Scenario | None,
) -> str | None:
    """Get the AI explanation, or None if it's slow (caller uses rule-based text)."""
    try:
        return await asyncio.wait_for(
            gemini.explain(req, original, corrected),
            timeout=settings.ai_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "AI explanation timed out after %.0fs; using rule-based fallback.",
            settings.ai_timeout_seconds,
        )
        return None

async def analyze_circuit(
    req: CircuitRequest, sim: Simulator, gemini: GeminiClient
) -> AnalyzeResponse:
    request_start = time.perf_counter()

    async with _timed(f"sim-original[{sim.name}]"):
        i0 = await _measure(sim, req)
    original = Scenario(resistance=req.resistance, current_ma=i0, status=classify(i0))

    warnings: list[str] = []
    corrected: Scenario | None = None

    if i0 is None:
        warnings.append("The simulator did not return an LED current reading; result is Unavailable.")
    elif req.voltage <= req.led_forward_voltage:
        warnings.append("Source voltage is below the LED's forward voltage; it won't light.")
    elif original.status == "danger":
        warnings.append(
            f"LED current is {_fmt_ma(i0)}, above the {MAX_SAFE_MA:.0f} mA typical limit. "
            "The LED may burn out."
        )
    elif original.status == "warning":
        warnings.append(f"LED current is only {_fmt_ma(i0, 2)}; it will be very dim.")

    # Only attempt a corrective resistor when we actually have a reading to fix.
    if original.status != "safe" and i0 is not None:
        new_r = suggest_resistor(req)
        if new_r is not None:
            fixed = req.model_copy(update={"resistance": new_r})
            async with _timed(f"sim-corrected[{sim.name}]"):
                i1 = await _measure(sim, fixed)  # re-simulate the fix
            corrected = Scenario(resistance=new_r, current_ma=i1, status=classify(i1))

    if i0 is None:
        rec = "Simulated LED current is Unavailable; re-run the simulation to get a reading."
    elif corrected:
        rec = (f"Use a {corrected.resistance:.0f} Ω resistor in series. "
               f"Simulated current drops from {_fmt_ma(i0)} to {_fmt_ma(corrected.current_ma)}.")
    elif original.status == "safe":
        rec = f"The resistor limits LED current to approximately {_fmt_ma(i0)}."
    else:
        rec = "Increase the source voltage above the LED's forward voltage."

    async with _timed("gemini-explain"):
        explanation = await _explain(gemini, req, original, corrected)
    rec = explanation or rec
    explanation_source = "gemini" if explanation else "rules"

    logger.info(
        "analyze done status=%s source=%s total=%.2fs",
        original.status, explanation_source, time.perf_counter() - request_start,
    )

    return AnalyzeResponse(
        status=original.status, current_ma=i0, warnings=warnings,
        recommendation=rec, simulated_with=sim.name,
        explanation_source=explanation_source,
        original=original, corrected=corrected,
    )