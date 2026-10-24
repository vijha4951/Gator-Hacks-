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

## Optional
- Gemini explanations: set GEMINI_API_KEY in backend/.env
- Arduino: set ARDUINO_PORT in backend/.env (see hardware/README.md)
- PhysBox: SIMULATOR=physbox, single worker (see backend/PHYSBOX_SETUP.md)

## Known gaps
- Plan chat screen has no backend endpoint yet.
- SIMULATOR=physbox only supports the red LED (Vf=2.0); Green/Blue/White return 502.
