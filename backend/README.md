# CircuitGuard AI — Backend

FastAPI service for CircuitGuard's structured project planner and simulated LED circuit check.

## Start the backend

From the repository root:

```powershell
uv sync --dev
uv run uvicorn app.main:app --app-dir backend --reload
```

Or, after activating the project's Python environment, from `backend/`:

```powershell
uvicorn app.main:app --reload
```

The API docs are at `http://127.0.0.1:8000/docs`; `GET /health` returns `{"ok": true}`.

## Configuration

Settings load from a private `.env` file in `backend/` or the repository root. Keep secrets out of the frontend and Git.

| Setting | Default | Use |
|---|---|---|
| `GEMINI_API_KEY` | unset | Required for model-generated `POST /api/plan` results; scope clarifications work without it. Optional for circuit explanations. |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model name. This default is chosen for lower response time; set it explicitly in `.env` to use a different supported model. |
| `SIMULATOR` | `physbox` | Use `physbox` for Volt or `mock` for an offline Ohm's-law estimate. |
| `PHYSBOX_MCP_COMMAND` | detected launcher or Python module | Optional override for the MCP process. |
| `PHYSBOX_MCP_ARGS` | detected defaults | Optional arguments for the MCP process. |

## PhysBox / Volt connection

The FastAPI application starts its own PhysBox MCP client. Install PhysBox MCP in the same Python environment and keep the relay running; open Volt in a browser so it can connect to that relay. The coding assistant's MCP connection alone does not connect the backend.

Check `GET /api/physbox/status`. A working connection reports `connected: true` and `volt_reachable: true`. The endpoint runs a read-only circuit-state request to confirm that Volt responds.

`POST /api/analyze` replaces the active Volt circuit with a voltage source, optional resistor, red LED, and ground; validates it; runs the simulator; and reads the LED's current measurement. Volt reports amperes, which the API converts to milliamps. Requests are serialized because Volt has one active circuit. A resistor value of zero is supported for the missing-resistor demonstration.

When `SIMULATOR=mock`, the backend calculates an estimate using Ohm's law. Its response reports `simulated_with: "mock"`; do not describe it as a PhysBox result. The frontend labels it accordingly.

## Planning endpoint

`POST /api/plan` accepts `PlanRequest` and returns a validated `PlanResponse`. The planner loads the trusted reference JSON, sends rules separately from the request/reference contents, asks Gemini for JSON, then checks the response against the supported scope. Missing configuration, model errors, missing reference data, or invalid output produce an error response; the backend does not substitute a made-up plan.

Planning accepts Arduino Uno R3 as the named board, but does not claim board pin limits or model board behavior. See `app/data/PLAN_CONTRACT.md`, `app/data/VERIFIED_REFERENCES.md`, and `app/data/PHASE4_PLANNER_GEMINI.md` for the contract, verified information, and planning service notes.

## API routes

- `GET /health`
- `GET /api/gemini/status`
- `GET /api/physbox/status`
- `POST /api/plan`
- `POST /api/analyze`

For the end-to-end demo, see the repository's `DEMO_GUIDE.md`.
