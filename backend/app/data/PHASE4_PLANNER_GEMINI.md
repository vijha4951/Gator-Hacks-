# Phase 4: Gemini-backed project planning

- The FastAPI process uses the existing application-owned `GeminiClient`.
- `GEMINI_API_KEY` remains in the backend or repository-root private `.env`;
  never send it to the frontend or commit it.
- `POST /api/plan` accepts `PlanRequest` and returns `PlanResponse`.
- The planner instruction is sent as Gemini's system instruction. The separate
  user message contains the request and `verified_references.json`.
- Gemini is asked for JSON matching the Pydantic `PlanResponse` model. The
  backend validates the response before returning it.
- Missing configuration, timeout, unavailable reference data, or an invalid
  model response returns HTTP 503 with a plain `detail` message. No fallback
  plan is fabricated.
- The shared `GET /api/gemini/status` endpoint reports whether the same client
  is configured.
