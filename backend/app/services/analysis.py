from app.schemas import AnalyzeResponse, CircuitRequest, Scenario, Status
from app.services import ai_agent
from app.services.simulator import Simulator, SimulationError

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


async def analyze_circuit(req: CircuitRequest, sim: Simulator) -> AnalyzeResponse:
    i0 = await sim.measure_led_current_ma(req)
    if i0 is None and req.resistance != 0:
        raise SimulationError("No reliable current was returned for the circuit")
    # Missing-resistor risk is inferred from topology, not an invented current.
    initial_status = ("danger" if req.voltage > req.led_forward_voltage else "warning") if i0 is None else classify(i0)
    original = Scenario(resistance=req.resistance, current_ma=i0, status=initial_status)

    warnings: list[str] = []
    corrected: Scenario | None = None

    if req.resistance == 0:
        warnings.append("No series current-limiting resistor is present. Add a suitable resistor before building this circuit.")
        if sim.name == "physbox":
            warnings.append("Original current is unavailable: PhysBox LED readings vary with the damaged model state. No reliable hardware current or damage prediction is available.")

    if req.voltage <= req.led_forward_voltage:
        warnings.append("Source voltage is below the LED's forward voltage; it won't light.")
    elif original.status == "danger" and i0 is not None:
        warnings.append(
            f"LED current is {i0:.1f} mA, above the {MAX_SAFE_MA:.0f} mA typical limit. "
            "The LED may burn out."
        )
    elif original.status == "warning" and i0 is not None:
        warnings.append(f"LED current is only {i0:.2f} mA; it will be very dim.")

    if original.status != "safe":
        new_r = suggest_resistor(req)
        if new_r is not None:
            fixed = req.model_copy(update={"resistance": new_r})
            i1 = await sim.measure_led_current_ma(fixed)  # re-simulate the fix
            if i1 is None:
                raise SimulationError("No reliable current was returned for the corrected circuit")
            corrected = Scenario(resistance=new_r, current_ma=i1, status=classify(i1))

    if corrected:
        if i0 is None:
            rec = (f"No current-limiting resistor is present; original current is unavailable. "
                   f"Use a {corrected.resistance:.0f} Ω resistor in series. "
                   f"The corrected simulation measured {corrected.current_ma:.2f} mA.")
        else:
            rec = (f"Use a {corrected.resistance:.0f} Ω resistor in series. "
                   f"Simulated current drops from {i0:.1f} mA to {corrected.current_ma:.1f} mA.")
    elif original.status == "safe":
        rec = f"The resistor limits LED current to approximately {i0:.1f} mA."
    else:
        rec = "Increase the source voltage above the LED's forward voltage."

    # The current explanation interface predates nullable measurements.
    # Preserve factual fallback text until the AI owner supports unavailable values.
    if i0 is not None:
        rec = await ai_agent.explain(req, original, corrected) or rec

    return AnalyzeResponse(
        status=original.status, current_ma=i0, warnings=warnings,
        recommendation=rec, simulated_with=sim.name,
        original=original, corrected=corrected,
    )