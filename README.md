# CircuitGuard AI

CircuitGuard helps beginners plan a small electronics project and check one modeled LED circuit. The planning scope is one red LED, one series current-limiting resistor, and a positive 5 V DC source with ground. Arduino Uno R3 is accepted as a named board for planning, but the simulator does not model the board's pins or firmware.

The app has two separate jobs:

1. **Plan a project:** Gemini creates a structured plan using the reviewed reference file. Unsupported requests, such as RGB LEDs, need confirmation instead of being silently converted into a supported build.
2. **Check a circuit:** FastAPI sends the entered resistor value to the configured simulator and returns the modeled LED current with warnings. This check covers the modeled circuit only; it does not prove a physical build is safe.

## Run locally

Use Python 3.13 or newer and Node.js. From the repository root, open two terminals.

Terminal 1, start FastAPI:

```powershell
uv sync --dev
uv run uvicorn app.main:app --app-dir backend --reload
```

Terminal 2, start the frontend:

```powershell
npm install
npm run dev
```

Open the local address printed by Vite, normally `http://localhost:5173`. The frontend calls `http://127.0.0.1:8000` by default. Set `VITE_API_BASE_URL` if your backend uses another address.

## Configure services

Project planning needs `GEMINI_API_KEY` in a private `.env` file at the repository root or in `backend/`. Keep the key out of frontend variables and source files. If it is missing, circuit analysis can still work, but planning is unavailable.

The default circuit simulator is PhysBox. For a real Volt simulation, install `physbox-mcp` in the Python environment used by FastAPI, keep the PhysBox relay running, and open Volt in a browser. FastAPI starts its own MCP client; a connection established only by a coding assistant is not used by the running app. Check the backend-owned connection at `http://127.0.0.1:8000/api/physbox/status`. The response should report `connected: true` and `volt_reachable: true`.

For development without Volt, set `SIMULATOR=mock` in the private `.env`. This computes an Ohm's-law estimate. The interface labels this result as an offline estimate, not as a PhysBox simulation. Restart FastAPI after changing `.env`.

Useful endpoints:

- `GET http://127.0.0.1:8000/health` — backend process check.
- `GET http://127.0.0.1:8000/api/gemini/status` — Gemini configuration status.
- `GET http://127.0.0.1:8000/api/physbox/status` — PhysBox and Volt status.
- `POST http://127.0.0.1:8000/api/plan` — project planning.
- `POST http://127.0.0.1:8000/api/analyze` — modeled LED circuit check.
- `http://127.0.0.1:8000/docs` — interactive API reference.

## Supported limits

The planner uses only `backend/app/data/verified_references.json`. Unknown part details are called out for confirmation. Version one does not generate pin assignments, wiring instructions, complete Arduino programs, prices, or shopping links. It does not support RGB or addressable LEDs, and it does not model Arduino pins, PWM, firmware, or a physical breadboard. Review `backend/app/data/VERIFIED_REFERENCES.md` and `backend/app/data/PLAN_CONTRACT.md` for the exact boundaries and API fields.

Use [DEMO_GUIDE.md](DEMO_GUIDE.md) for the presentation flow and recovery steps.
