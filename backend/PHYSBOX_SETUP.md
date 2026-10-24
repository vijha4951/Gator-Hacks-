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
HTTP 502, without silently using the mock. Zero resistance and non-2.0 LED
forward-voltage requests are explicitly unsupported until their models are verified.
The fixed 2 V parameter describes the selected model; the measured LED voltage
can differ. It is not an ideal fixed-drop diode.

Calls are serialized within this process. Use one worker, one server instance,
and do not run the CLI demo during API requests. Multiple workers/machines do
not share this lock. Keep Volt visible while running simulations.
`SIMULATOR=mock` remains available for existing development tests.

Run tests from the repository root:

```bash
SIMULATOR=mock PYTHONPATH=backend:. simulation/.venv/bin/python -m pytest backend/tests
```
