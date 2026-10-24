"""AI-powered circuit explanation using the Gemini API.

Falls back to None (triggering the rule-based text in analysis.py) if:
  - GEMINI_API_KEY is not set
  - The API call fails for any reason (network, quota, bad response)

Never claims simulated results are physical bench measurements.
"""

from __future__ import annotations

import logging

from app.schemas import CircuitRequest, Scenario

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — injected once per call, not stored across requests.
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an expert electronics lab tutor helping a beginner understand \
a simulated LED circuit.

Rules you must follow — no exceptions:
1. Every current or voltage figure you mention must be explicitly labelled \
as a "simulated" value (e.g. "the simulation shows …", "SPICE reports …"). \
Never present them as physical bench or multimeter measurements.
2. Do not invent numbers. Use only the values provided in the user message.
3. Be concise: 3-5 plain-English sentences, no bullet lists, no markdown.
4. Always cover these four points in order:
   a) What is wrong (or confirm the circuit is safe).
   b) What the simulated current means for the LED.
   c) Why the recommended resistor helps (skip if no correction is needed).
   d) One concrete thing the user should check or do next.
"""


def _build_user_message(
    circuit: CircuitRequest,
    original: Scenario,
    corrected: Scenario | None,
) -> str:
    """Render the circuit data as a structured plain-text block for the model."""
    lines = [
        "Circuit simulation data:",
        f"  Source voltage          : {circuit.voltage} V",
        f"  LED forward voltage     : {circuit.led_forward_voltage} V",
        f"  Series resistor         : {original.resistance} Ω",
        f"  Simulated LED current   : {original.current_ma:.2f} mA",
        f"  Circuit status          : {original.status}",  # safe / warning / danger
    ]

    if corrected is not None:
        lines += [
            "",
            "Suggested correction:",
            f"  Recommended resistor    : {corrected.resistance:.0f} Ω",
            f"  Corrected simulated current: {corrected.current_ma:.2f} mA",
            f"  Corrected status        : {corrected.status}",
        ]
    else:
        lines.append("  No resistor change required.")

    return "\n".join(lines)


async def explain(
    circuit: CircuitRequest,
    original: Scenario,
    corrected: Scenario | None,
) -> str | None:
    """Return a Gemini-generated explanation, or None to use the rule-based fallback."""
    # Lazy import so the module loads fine even without the key / package.
    try:
        from app.config import settings
        from google import genai
    except ImportError:
        logger.warning("google-genai not installed; using rule-based fallback.")
        return None

    if not settings.gemini_api_key:
        logger.debug("GEMINI_API_KEY not set; using rule-based fallback.")
        return None

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        interaction = await client.aio.interactions.create(
            model=settings.gemini_model,
            system_instruction=_SYSTEM_PROMPT,
            input=_build_user_message(circuit, original, corrected),
            store=False,  # no conversation history needed between requests
        )

        text = (interaction.output_text or "").strip()
        if not text:
            logger.warning("Gemini returned an empty response; using rule-based fallback.")
            return None

        return text

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Gemini explanation failed (%s: %s); using rule-based fallback.",
            type(exc).__name__,
            exc,
        )
        return None
