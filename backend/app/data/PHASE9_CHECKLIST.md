# Phase 9: Planner example checks

This checklist records what is covered and what has actually been run. Test cases were added or confirmed in `backend/tests/test_planner.py`; because the repository's Python environment is currently unavailable, those tests are **not yet confirmed passing**.

## Example coverage

- **Demo request: color-changing LED with Arduino Uno R3** — Covered. Expected result is a structured `needs_confirmation` response explaining that v1 only supports one red LED. This request is stopped before Gemini is called, so the planner does not disguise it as a color-changing build.
- **Supported red LED project with Arduino Uno R3** — Covered by the valid-response test. It checks for a structured `ready` response, the three supported parts, verified-reference content in Gemini's input, and explicit confirmation notes for unknown physical details.
- **LED type omitted** — Correction made in Phase 9. A generic LED request now asks whether one red LED is acceptable instead of silently choosing a color. A frontend action offers that supported scope.
- **Board required but omitted** — Covered. When the request says the board must be used but gives no model, the planner asks which board; it does not assume Uno R3.
- **Unsupported request** — Covered with an RGB, battery, and transistor example. Expected result is `needs_confirmation` with no parts or build stages presented as a complete plan.
- **Malformed Gemini response or failed Gemini connection** — Covered at the service level and with endpoint checks. Malformed output returns HTTP 503 with `No plan was produced.` A Gemini service failure returns HTTP 503 with a safe message pointing to status, model, key, quota, and connection checks. Neither case returns a partial plan.
- **Forbidden detail** — Covered for pin numbers, complete Arduino code, and wire-by-wire connection directions. The validator should reject these rather than return them as plan instructions.

## Execution and reader review

- **Automated planner tests:** Not run. `uv` cannot use the repository `.venv` because its `pyvenv.cfg` is missing; the available system Python also points to a missing installation. Restore a working project Python environment, then run `python -m pytest backend/tests/test_planner.py -q` from the repository root.
- **Python syntax check:** Passed for the changed planner validator and planner tests.
- **Frontend build:** Not run successfully. `npm run build` could not find Vite, which means frontend dependencies are not installed in this workspace. Install the project's npm dependencies, then run the build.
- **Live API/Gemini request:** Not checked. The local backend could not be reached from this session; offline tests use a stub and do not prove API key, network, or model availability.
- **Beginner read-through:** Not done. Ask a beginner to read a ready plan and explain (1) which parts they need, (2) what each broad stage is for, and (3) what they should do when a warning appears. Record any confusing phrase and revise it before calling the result beginner-checked.

## Corrections still needed before sign-off

1. Restore Python and frontend dependencies, then run the planner tests and frontend build.
2. Check the supported red LED prompt against the live Gemini service and record the actual response status.
3. Complete the beginner read-through and update the plan language from their feedback.
