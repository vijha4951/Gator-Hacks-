# CircuitGuard AI

CircuitGuard combines a React/Vite UI, FastAPI, verified PhysBox Volt LED simulations,
Gemini circuit explanations, and USB Arduino Uno LED control.

## Run the demo

Use Python 3.13 and the simulation virtual environment. Install backend/requirements.txt.
Set SIMULATOR=physbox and ARDUINO_PORT to the connected Uno port. Put optional
GEMINI_API_KEY and GEMINI_MODEL in an ignored backend/.env on the backend host.
Never commit credentials or put them in VITE_ variables.

From the repository root, run PhysBox MCP, keep exactly one https://volt.physbox.io
tab open with local access allowed, then start FastAPI:

```sh
simulation/.venv/bin/physbox-mcp
# separate terminal:
SIMULATOR=physbox simulation/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

See backend/PHYSBOX_SETUP.md and hardware/TWO_BUTTONS.md for full instructions.
The verified two-button sketch uses LED D5, ON D9, OFF D8, and a 220 ohm series
resistor. It accepts both website commands and physical button presses.

## Website deployment

Deploy frontend/ with Vite, build npm run build, output dist. Set VITE_API_URL
to the reachable HTTPS backend, VITE_USE_MOCK=false, and rebuild after changes.
A temporary tunnel can expire; the laptop backend, tunnel, and Volt tab must stay
running. Uploading frontend assets does not host USB hardware or PhysBox.

## AI and feature status

Gemini explains supplied simulated measurements in recommendation. API responses
include explanation_source=gemini or rules. Missing credentials, errors, and
slow requests use labelled deterministic advice. GET /api/gemini/status reports
configuration only. Real Gemini inference still needs validation with the team's key.
There is no Gemma integration in this combined release.

Red, green, and blue LED models are supported. Missing-resistor current is
unavailable, not zero. RGB check mode simulates each channel separately; it is
not a full shared-device RGB model. RGB physical control is not enabled for the
verified two-button sketch. The project-planning screen remains a UI prototype,
not a live AI conversation. Simulated current is not a physical measurement.

## Validate

```sh
simulation/.venv/bin/python -m pytest backend -q
cd frontend
npm ci
npm run build
```

Windows agent setup and validation: [WINDOWS_HANDOFF.md](WINDOWS_HANDOFF.md).
