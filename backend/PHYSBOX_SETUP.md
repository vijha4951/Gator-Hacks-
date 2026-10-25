# Run the backend with PhysBox

Run these commands from the repository root (not inside backend/).

Install the backend dependencies (use a virtual environment of your choice):

```bash
pip install -r backend/requirements.txt
```

Leave the PhysBox MCP relay running in a separate terminal:

```bash
physbox-mcp
```

Keep exactly one https://volt.physbox.io tab open and allow local access.
Save other circuit work: requests replace the Volt canvas. Only one process
should start the relay — if your coding assistant already runs physbox-mcp,
free its port first (see the connection troubleshooting below).

Start FastAPI from the repository root:

```bash
SIMULATOR=physbox python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Then send a real request:

```bash
curl http://127.0.0.1:8000/api/analyze -H 'Content-Type: application/json' -d '{"voltage":5,"resistance":330,"led_forward_voltage":2}'
```

Expect `simulated_with: "physbox"`, `status: "safe"`, and about 8.99 mA
(model versions can affect results). This is a local browser-backed integration.
The bridge returns actual LED current in mA and converts simulation failures to
HTTP 502, without silently using the mock.

Check the connection at any time:

```bash
curl http://127.0.0.1:8000/api/physbox/status
```

A healthy response has `connected: true` and `volt_reachable: true`. On failure
it returns HTTP 503 with the cause (relay not running, port in use, or Volt
tab not open).

Calls are serialized within this process. Use one worker and one server
instance. Multiple workers/machines do not share this lock. Keep Volt visible
while running simulations. `SIMULATOR=mock` remains available for offline
development and runs the test suite without Volt.

Run tests from the backend folder:

```bash
python -m pytest
```
