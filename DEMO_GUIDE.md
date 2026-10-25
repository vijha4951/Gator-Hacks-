# CircuitGuard AI demo guide

This guide shows the planned-project flow and then checks one supported LED model. Allow about three minutes. Keep the backend terminal visible so the team can tell when requests arrive.

## Before presenting

1. Start FastAPI and the Vite frontend using the commands in the root `README.md`.
2. Open the Volt app in a browser and confirm that the PhysBox relay is connected.
3. Open `http://127.0.0.1:8000/api/physbox/status`. For a real PhysBox demo, confirm both `connected` and `volt_reachable` are `true`.
4. Open the Vite page and confirm it loads. Planning needs a working Gemini key in the backend's private `.env` file.
5. Keep the hardware demo separate from the simulation result. The simulation covers its model; it cannot confirm the physical wiring or Arduino pin behavior.

## Presentation flow

1. Enter: **“Can you help me plan a color-changing LED with an Arduino Uno R3?”**
2. Show the `needs_confirmation` response. Explain that version one has verified information for one red LED, not RGB or addressable LEDs; it asks rather than pretending that the unsupported feature is covered.
3. Choose **Use the supported single-red-LED project** and submit the supported idea. Review the parts, broad stages, open questions, and limits. Point out that the plan does not invent pin numbers, a complete sketch, prices, or an exact resistor for unknown physical parts.
4. Select **Check a circuit**. The plan summary travels with the user to this screen. Enter the value of the resistor being modeled. The page fixes the model at one red LED, about 2 V forward drop, and a 5 V DC source.
5. To demonstrate the missing-resistor case, enter `0` and analyze. The backend omits the resistor from its circuit model; the simulator result should flag excessive current and may include a proposed resistor that can be simulated again. Explain that a suggested value is for the modeled setup and must not be treated as proof about someone's physical components.
6. If time allows, enter a nonzero resistor value and analyze again to show how the simulated current changes.

## Confirm which simulator answered

The result screen names its source:

- **PhysBox simulated LED current** means the backend used its PhysBox simulator. The backend status endpoint should also report Volt reachable.
- **Offline estimate using Ohm's law (not a PhysBox simulation)** means `SIMULATOR=mock` is active. It is useful for a software walkthrough, but does not demonstrate PhysBox integration.

Do not present the offline estimate as a simulator run. If PhysBox is unavailable, state that clearly or restore the relay/Volt connection before claiming the PhysBox portion worked.

## Recovery notes

- **Planning unavailable:** check `GET /api/gemini/status`, confirm `GEMINI_API_KEY` is set in a private backend or root `.env`, then restart FastAPI.
- **Circuit check unavailable:** check `GET /api/physbox/status`; open Volt, confirm the relay, and restart FastAPI if needed. For a UI-only walkthrough, set `SIMULATOR=mock` and restart, then identify the result as an estimate.
- **Frontend cannot reach backend:** confirm FastAPI is on port 8000 or set `VITE_API_BASE_URL` to its address. Restart Vite after changing that frontend setting.

## Claims the demo can support

- The planner can produce a scoped plan using its checked reference data.
- The application can submit the supported LED circuit to the configured simulator and display a measured current when the simulator supplies one.
- The result describes a circuit model. It does not certify a real build or verify Arduino pins, firmware, breadboard placement, component wattage, or a user's exact LED.
