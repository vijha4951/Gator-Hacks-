"""AI-powered circuit explanation using the Gemini API.

The FastAPI application owns a single GeminiClient, built once at startup from
the configured credentials and reused for every request (mirroring how the
PhysBox MCP client is owned by the app). This avoids rebuilding a client and a
fresh HTTP connection pool on every call.

Explanations fail safe: GeminiClient.explain() returns None (triggering the
rule-based text in analysis.py) if:
  - the google-genai package is not installed
  - GEMINI_API_KEY is not set (the client is never configured)
  - the API call fails for any reason (network, quota, bad response)

Never claims simulated results are physical bench measurements.
"""

from __future__ import annotations

import logging
from typing import Any

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
    def _ma(value: float | None) -> str:
        # A missing reading is reported as "Unavailable" so the model never
        # invents a number (and we never crash formatting None).
        return "Unavailable" if value is None else f"{value:.2f} mA"

    lines = [
        "Circuit simulation data:",
        f"  Source voltage          : {circuit.voltage} V",
        f"  LED forward voltage     : {circuit.led_forward_voltage} V",
        f"  Series resistor         : {original.resistance} Ω",
        f"  Simulated LED current   : {_ma(original.current_ma)}",
        f"  Circuit status          : {original.status}",  # safe / warning / danger
    ]

    if corrected is not None:
        lines += [
            "",
            "Suggested correction:",
            f"  Recommended resistor    : {corrected.resistance:.0f} Ω",
            f"  Corrected simulated current: {_ma(corrected.current_ma)}",
            f"  Corrected status        : {corrected.status}",
        ]
    else:
        lines.append("  No resistor change required.")

    return "\n".join(lines)


class GeminiClient:
    """Application-owned Gemini client, built once at startup.

    If the package is missing or no API key is configured, the client stays
    unconfigured and explain() always returns None so the caller uses the
    rule-based fallback. This never prevents the app from starting.
    """

    def __init__(self) -> None:
        self._client: Any | None = None
        self._model: str = ""
        self.last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._client is not None

    def start(self) -> None:
        """Create the underlying genai client from the configured credentials.

        Safe to call at startup. Any failure is recorded in last_error and
        leaves the client unconfigured (fail-safe).
        """
        if self.configured:
            return

        # Imported here so the module loads fine without the package / key.
        try:
            from google import genai
        except ImportError:
            self.last_error = "google-genai is not installed."
            logger.warning("%s Using rule-based fallback.", self.last_error)
            return

        from app.config import settings

        if not settings.gemini_api_key:
            self.last_error = "GEMINI_API_KEY is not set."
            logger.info("%s Using rule-based fallback.", self.last_error)
            return

        try:
            self._client = genai.Client(api_key=settings.gemini_api_key)
            self._model = settings.gemini_model
            self.last_error = None
            logger.info("Gemini client ready (model: %s).", self._model)
        except Exception as exc:  # noqa: BLE001 - startup must not kill the app
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._client = None
            logger.warning("Could not build Gemini client: %s", self.last_error)

    def status(self) -> dict[str, Any]:
        """Report whether the Gemini client is configured and ready."""
        data: dict[str, Any] = {"configured": self.configured}
        if self.configured:
            data["model"] = self._model
        else:
            data["error"] = self.last_error or "Gemini client is not configured."
        return data

    async def create_interaction(
        self,
        *,
        input: Any,
        tools: list[dict] | None = None,
        system_instruction: str | None = None,
        previous_interaction_id: str | None = None,
    ) -> Any:
        """Low-level Interactions API call used by the agent tool-calling loop.

        Returns the raw interaction object. Raises if the client is not
        configured or the API call fails — the agent layer handles fallback.
        """
        if not self.configured:
            raise RuntimeError("Gemini client is not configured.")

        kwargs: dict[str, Any] = {
            "model": self._model,
            "input": input,
            "store": True,  # needed so previous_interaction_id chains the loop
        }
        if tools is not None:
            kwargs["tools"] = tools
        if system_instruction is not None:
            kwargs["system_instruction"] = system_instruction
        if previous_interaction_id is not None:
            kwargs["previous_interaction_id"] = previous_interaction_id

        return await self._client.aio.interactions.create(**kwargs)

    async def explain(
        self,
        circuit: CircuitRequest,
        original: Scenario,
        corrected: Scenario | None,
    ) -> str | None:
        """Return a Gemini-generated explanation, or None to use the fallback."""
        if not self.configured:
            logger.debug("Gemini not configured; using rule-based fallback.")
            return None

        try:
            # Use generate_content rather than the interactions API: for this
            # single-shot explanation the interactions (agentic/reasoning)
            # endpoint added large, variable latency (routinely 45-70s) that
            # blew the request timeout, while generate_content returns the same
            # text far more consistently (~9-34s in testing). The agent
            # tool-calling loop still uses interactions via create_interaction.
            from google.genai import types

            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=_build_user_message(circuit, original, corrected),
                config=types.GenerateContentConfig(system_instruction=_SYSTEM_PROMPT),
            )

            text = (response.text or "").strip()
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
