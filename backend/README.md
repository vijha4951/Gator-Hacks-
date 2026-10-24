# CircuitGuard AI — Backend

A small web service that checks whether a simple LED circuit is safe and, when it
isn't, suggests a fix and explains it in plain language.

You give it three numbers — source voltage, series resistance, and the LED's
forward voltage — and it tells you whether the circuit is **safe**, a **warning**
(too dim), or **danger** (the LED will burn out). If it's not safe, it recommends
a real resistor value you can actually buy and re-checks that the fix works.

## What's here

| Path | Role |
|---|---|
| `app/main.py` | Starts the web server and wires everything together |
| `app/routers/analyze.py` | The `/api/analyze` endpoint |
| `app/services/analysis.py` | The decision logic: classify, suggest a fix, explain |
| `app/services/simulator.py` | Works out the LED current (mock today, real PhysBox later) |
| `app/services/ai_agent.py` | Optional Gemini-written explanation, with a safe fallback |
| `app/schemas.py` | The shape and validation rules for requests and responses |
| `app/config.py` | Settings loaded from `.env` |
| `tests/` | The test suite |

## Requirements

- Python 3.10+ (the repo pins 3.15 via `.python-version`)
- The packages in `requirements.txt`

Install them:

```powershell
pip install -r requirements.txt
```

## Configuration

Settings are read from a `.env` file. Copy the example and fill it in:

```powershell
copy .env.example .env
```

Keys:

| Key | Default | Meaning |
|---|---|---|
| `SIMULATOR` | `mock` | `mock` uses Ohm's-law math. `physbox` is the real simulator (not implemented yet). |
| `GEMINI_API_KEY` | _(unset)_ | Optional. If set, explanations are written by Gemini. If unset, a built-in rule-based sentence is used instead. |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Optional override for the model name. |

The `.env` file is found whether it sits in `backend/` or at the repo root, so the
app works no matter which folder you launch it from.

## Run the server

From the `backend` folder:

```powershell
uvicorn app.main:app --reload
```

`--reload` restarts the server automatically when you edit a file. When it starts
you'll see `Uvicorn running on http://127.0.0.1:8000`.

> Run this in your own terminal. It's a long-running process and won't stop on its
> own until you press Ctrl+C.

## Try it

Open the interactive API docs in a browser:

```
http://127.0.0.1:8000/docs
```

Click `POST /api/analyze` → **Try it out**, enter a body like:

```json
{ "voltage": 5, "resistance": 0, "led_forward_voltage": 2.0 }
```

and **Execute**. The `resistance: 0` case is the "forgot the resistor" demo — you
should get a **danger** verdict and a suggested resistor to fix it.

Health check:

```
http://127.0.0.1:8000/health
```

returns `{"ok": true}`.

### From the command line instead

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/analyze -H "Content-Type: application/json" -d '{\"voltage\":5,\"resistance\":0,\"led_forward_voltage\":2.0}'
```

## Run the tests

```powershell
python -m pytest
```

The tests run offline and do not make real network or AI calls.

## Notes and current limitations

- **Mock simulator today.** Current is computed with Ohm's law, not a real circuit
  simulation. The real `PhysBoxSimulator` (driving the PhysBox `circuit_*` MCP
  tools) is stubbed out and not implemented yet.
- **No frontend yet.** The server allows a web page served from
  `http://localhost:5173` (the Vite default) to call it, but that page doesn't
  exist in this repo. Use the `/docs` page or curl in the meantime.
- **AI is optional and fails safe.** If the Gemini key is missing or the call
  fails, you still get a sensible rule-based recommendation.
