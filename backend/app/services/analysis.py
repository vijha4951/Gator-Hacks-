from app.schemas import AnalyzeResponse, CircuitRequest, Scenario, Status
from app.services.ai_agent import GeminiClient
from app.services.simulator import Simulator

TARGET_MA = 15.0
MAX_SAFE_MA = 20.0
MIN_VISIBLE_MA = 1.0
E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]


def classify(current_ma: float) -> Status:
    if current_ma > MAX_SAFE_MA:
        return "danger"
    if current_ma < MIN_VISIBLE_MA:
        return "warning"
    return "safe"


def suggest_resistor(c: CircuitRequest) -> float | None:
    drop = c.voltage - c.led_forward_voltage
    if drop <= 0:
        return None
    ideal = drop / (TARGET_MA / 1000)
    values = [b * 10**d for d in range(0, 5) for b in E12]
    return float(min(v for v in values if v >= ideal))


async def analyze_circuit(
    req: CircuitRequest, sim: Simulator, gemini: GeminiClient
) -> AnalyzeResponse:
    i0 = await sim.measure_led_current_ma(req)
    original = Scenario(resistance=req.resistance, current_ma=i0, status=classify(i0))

    warnings: list[str] = []
    corrected: Scenario | None = None

    if req.voltage <= req.led_forward_voltage:
        warnings.append("Source voltage is below the LED's forward voltage; it won't light.")
    elif original.status == "danger":
        warnings.append(
            f"LED current is {i0:.1f} mA, above the {MAX_SAFE_MA:.0f} mA typical limit. "
            "The LED may burn out."
        )
    elif original.status == "warning":
        warnings.append(f"LED current is only {i0:.2f} mA; it will be very dim.")

    if original.status != "safe":
        new_r = suggest_resistor(req)
        if new_r is not None:
            fixed = req.model_copy(update={"resistance": new_r})
            i1 = await sim.measure_led_current_ma(fixed)  # re-simulate the fix
            corrected = Scenario(resistance=new_r, current_ma=i1, status=classify(i1))

    if corrected:
        rec = (f"Use a {corrected.resistance:.0f} Ω resistor in series. "
               f"Simulated current drops from {i0:.1f} mA to {corrected.current_ma:.1f} mA.")
    elif original.status == "safe":
        rec = f"The resistor limits LED current to approximately {i0:.1f} mA."
    else:
        rec = "Increase the source voltage above the LED's forward voltage."

    rec = await gemini.explain(req, original, corrected) or rec

    return AnalyzeResponse(
        status=original.status, current_ma=i0, warnings=warnings,
        recommendation=rec, simulated_with=sim.name,
        original=original, corrected=corrected,
    )