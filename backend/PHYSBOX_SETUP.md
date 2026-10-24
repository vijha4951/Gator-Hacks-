# Run the backend with PhysBox

Run these commands from the repository root (not inside backend/).
Use the existing simulation virtual environment:

```bash
simulation/.venv/bin/python -m pip install -r backend/requirements.txt
```

Leave the PhysBox MCP server running in a separate terminal:

```bash
simulation/.venv/bin/physbox-mcp
```

Keep exactly one https://volt.physbox.io tab open on this Mac and allow local
access. Save other circuit work: requests replace the Volt canvas.

Start FastAPI from the repository root:

```bash
SIMULATOR=physbox simulation/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Then send a real request:

```bash
curl http://127.0.0.1:8000/api/analyze -H 'Content-Type: application/json' -d '{"voltage":5,"resistance":330,"led_forward_voltage":2}'
```

Expect `simulated_with: "physbox"`, `status: "safe"`, and about 8.99 mA
(model versions can affect results). This is a local browser-backed integration.
The bridge returns actual LED current in mA and converts simulation failures to
HTTP 502, without silently using the mock. Zero resistance builds a direct source-to-LED connection, but its current is
unavailable: readings changed between about 474.7 mA and 50 mA with the LED's
model state. Timing or matching samples cannot establish validity. Both the CLI
and PhysBox adapter return null for this original current. The backend flags the
missing-resistor risk from topology and separately simulates a resistor correction.
Non-2.0 LED forward-voltage requests remain unsupported.

## API contract change for frontend and AI developers

`current_ma` and `original.current_ma` can be null. Display "Unavailable", not
0 mA. Use the warnings and corrected scenario; do not calculate current reduction
when the original measurement is absent. At 5 V and 0 ohms, expect danger,
original current null, recommended 220 ohms, and about 13.29 mA corrected current.
A simulated corrected result is not a physical measurement or full safety assessment.
`simulated_with: "physbox"` identifies the simulation provider, not a guarantee that
every current is available. Connection/solver failures still return HTTP 502.
The legacy AI explanation function is skipped for unavailable original currents;
rule-based advice is used until the AI owner supports nullable measurements.

Calls are serialized within this process. Use one worker, one server instance,
and do not run the CLI during API requests. Multiple workers do not share this lock.
Keep Volt visible. `SIMULATOR=mock` remains available for development tests.

Run tests from the repository root:

```bash
SIMULATOR=mock PYTHONPATH=backend:. simulation/.venv/bin/python -m pytest backend/tests
```
