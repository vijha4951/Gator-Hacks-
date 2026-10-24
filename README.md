# CircuitGuard (Gator Hacks)

Merged project: React front end + FastAPI backend.

- `frontend/`   React + Vite UI (Figma "Web Hi-Fi" screens W01-W10)
- `backend/`    FastAPI: POST /api/analyze, POST /api/hardware/led, GET /api/hardware/ports, GET /health
- `hardware/`   Arduino Uno LED sketch
- `simulation/` PhysBox demo (only needed with SIMULATOR=physbox)

Merged from the sim-hardware branch (hardware + PhysBox + nullable current) and the
agent branch (Gemini explanations + .env lookup). The Backend and agent branches were
identical code-wise.

## Run (mock simulator, no hardware)
Terminal 1:
    cd backend
    pip install -r requirements.txt   # (physbox-mcp/fastmcp only needed for SIMULATOR=physbox)
    cp .env.example .env
    uvicorn app.main:app --reload     # http://localhost:8000/docs

Terminal 2:
    cd frontend
    npm install
    npm run dev                       # http://localhost:5173  (.env.local points at :8000)

Offline UI only: set VITE_USE_MOCK=true in frontend/.env.local.

## Circuit types
The Check and Connect Uno screens have a **Circuit** dropdown:
- **LED + resistor**: the original circuit (Uno pin 8 -> 220 ohm -> LED).
- **LED with switch**: Check analyses it with the switch closed (the switch doesn't change the current).
  On the Uno the LED on pin 8 follows a switch between pin 2 and GND; the screen shows its live state.
- **RGB LED**: Check analyses each color on its own (red 2 V, green/blue 3 V) with the same resistor value, and
  suggests a resistor per color. On the Uno, pins 9/10/11 drive R/G/B (220 ohm each, common-cathode LED to GND).

**Re-upload `hardware/led_serial/led_serial.ino` to the Uno** to get the switch and RGB commands.
New endpoints: `POST /api/hardware/rgb`, `POST /api/hardware/switch/follow`, `GET /api/hardware/switch`.

## Optional
- Gemini explanations: set GEMINI_API_KEY in backend/.env
- Arduino: set ARDUINO_PORT in backend/.env (see hardware/README.md)
- PhysBox: SIMULATOR=physbox, single worker (see backend/PHYSBOX_SETUP.md)

## Known gaps
- Plan chat screen has no backend endpoint yet.
- SIMULATOR=physbox only supports the red LED (Vf=2.0); Green/Blue/White return 502, and so does the RGB check (green/blue are 3 V).
- The switch and RGB Uno commands are tested against a fake serial port, not a real Uno yet.
