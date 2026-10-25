# Project planning request and response contract

This contract is shared by the React frontend, FastAPI backend, and planning
service. The backend Pydantic models in `app/schemas.py` define the accepted
field names and types. `plan_contract_samples.json` contains a full request and
a response that needs user confirmation.

## Frontend request: `PlanRequest`

Only `project_description` is required. A beginner can submit just that field.
The other fields refine the plan when the user knows the information.

| Field | Type | Meaning |
|---|---|---|
| `project_description` | string, 3–1200 characters | The user's idea in their own words. |
| `board_model` | string or null | Board the user says they have or want to use. Omit or send null when unknown. This does not verify board electrical limits. |
| `parts_owned` | array of `OwnedPart` | Parts the user says they own. Each item has `name`, optional positive `quantity`, and optional `notes`. Empty by default. |
| `constraints` | `PlanConstraints` | Optional preferences. Omit it to use empty defaults. |
| `constraints.budget_usd` | nonnegative number or null | User's budget. It can guide scope, but v1 gives no prices or purchase links. |
| `constraints.must_use_board` | boolean or null | Whether the plan must use the board named by the user. |
| `constraints.notes` | string or null | Other user preferences, up to 1000 characters. |

Minimal request:

```json
{ "project_description": "color-changing LED with Arduino Uno R3" }
```

The backend rejects unknown fields so spelling or contract mismatches are
visible instead of silently ignored.

## Backend response: `PlanResponse`

| Field | Type | Meaning |
|---|---|---|
| `status` | `ready` or `needs_confirmation` | Whether the plan can be offered within the supported scope. |
| `project_summary` | string | What the project would do, in plain language. |
| `scope` | `PlanScope` | `included` and `not_included` lists. |
| `questions` | array of `PlanQuestion` | Each question has a stable `id`, the question text, and `why_it_matters`. |
| `assumptions` | array of strings | Facts the plan is temporarily assuming. Label uncertain technical facts “Needs confirmation.” |
| `parts` | array of `PlanPart` | Name, quantity, purpose, verified ratings, obtain flag, and notes. `obtain` is true if the user needs it, false if they said they own it, or null if unknown. Do not include prices. |
| `stages` | array of `PlanStage` | Each stage has a title, goal, what to learn or observe, and a check before continuing. These are broad stages, not wiring instructions. |
| `safety_and_common_problems` | array of strings | Warning signs grounded in verified data. |
| `simulator_checks` | `PlanSimulatorChecks` | Separate lists of what PhysBox can and cannot verify for the plan. |
| `limitations` | array of strings | Limits of this plan and the product. |

### Status rules

- Use `needs_confirmation` when a missing or unsupported fact prevents a
  responsible plan. For example, the user asks for a color-changing LED while
  v1 only supports one red LED. Include a question that identifies what the
  user must decide. The frontend should show the question and must not present
  the plan as complete.
- Use `ready` when the plan fits the supported scope. Questions may remain if
  their answers do not block offering the plan; explain them as such.
- A `ready` result is not a safety certification. The physical circuit still
  needs appropriate checks, and simulation only covers the modeled circuit.

## Agreed v1 boundaries

The planner loads `verified_references.json` and uses only facts under
`verified`. For every relevant `unknown`, it asks a question or says **Needs
confirmation** and explains why. It must not invent board limits, component
ratings, pin maps, programs, prices, or compatibility.

Before returning a generated plan, the backend checks that:

- every listed part is in the verified component list or is the accepted board;
- each `verified_ratings` entry matches facts approved for that part, and
  electrical numbers elsewhere in the response also occur in the reference;
- a ready plan contains the three required circuit components;
- the response does not give pin numbers, complete code, wire-by-wire
  directions, prices, or claim simulation proves physical safety;
- an unsupported color-changing request or an explicitly unsupported board is
  returned as `needs_confirmation`, even if Gemini labels it `ready`;
- `obtain` is false only for parts declared owned, and remains null when the
  request does not say whether the user owns the part.

Plans that fail these checks are not returned; the API responds with
`{"detail":"No plan was produced."}` and HTTP 503. This avoids showing a
well-formed but out-of-scope answer as a valid plan.

The supported circuit is one red LED, one series current-limiting resistor,
and a positive DC source with ground. V1 does not support RGB or addressable
LEDs, exact pin assignments, wire-by-wire diagrams, complete sketches, PWM or
digital-output modeling, multiple LEDs, drivers, batteries, shopping prices,
or claims that simulation proves a physical build safe.

## Sample objects

See `plan_contract_samples.json` for a full `PlanRequest` and a matching
`needs_confirmation` `PlanResponse` for the color-changing LED example.
