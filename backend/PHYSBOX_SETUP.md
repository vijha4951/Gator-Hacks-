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
Supported forward-voltage models: red=2.0 V, green=2.2 V, blue=3.0 V.
Other values remain unsupported until verified.

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


## Red, green, and blue simulation models

The API's existing led_forward_voltage parameter selects red (2.0 V), green
(2.2 V), or blue (3.0 V). Both color and v_drop are set on the Volt LED node.
At 5 V and 220 ohms, real Volt runs returned approximately 13.29 mA red,
12.42 mA green, and 8.98 mA blue. These are representative models, not every
LED's datasheet values. A corrected circuit preserves the selected LED model.
The CLI supports --led-forward-voltage 2.2 or --led-forward-voltage 3.
No Arduino sketch changes are required; simulation color does not change a
physical single-color LED. The current API carries a forward voltage, not a color
field: the frontend's White option also sends 3 V and is indistinguishable from
Blue. A distinct white model needs a separate color input and verification.


## Vercel browser access

Backend defaults allow https://circuitgaurd.vercel.app, local Vite development,
and HTTPS deployment/branch URLs scoped to circuitgaurd in gatorhacks-vivi.
These defaults are committed: no local .env file is required for this project's
CORS support. Override CORS_ORIGINS or CORS_ORIGIN_REGEX for a different project.
Do not replace the origin list with an unrestricted wildcard.

The frontend build still needs VITE_API_URL set to a reachable HTTPS backend and
VITE_USE_MOCK=false. Redeploy after changing build-time variables. A temporary
Cloudflare tunnel can expire or change address: committing CORS does not make the
laptop backend permanently hosted. Keep FastAPI, PhysBox, the tunnel, and one Volt
tab running for the demo. Use a named tunnel with a stable hostname or a persistent
bridge deployment for a durable setup; the Arduino remains attached to its host.
