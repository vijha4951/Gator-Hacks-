// Backend client for CircuitGuard (FastAPI).
// VITE_API_URL  — backend base URL (default http://localhost:8000)
// VITE_USE_MOCK — "true" to run without the backend (same math as the backend's MockSimulator)

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind; // "INVALID" | "SIM_FAILED" | "HARDWARE" | "NETWORK" | "UNKNOWN"
  }
}

async function send(method, path, body) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("NETWORK", "Couldn't reach the server.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.ok) return data;
  if (res.status === 422) throw new ApiError("INVALID", "Check the values.");
  if (res.status === 502) throw new ApiError("SIM_FAILED", "The simulation failed.");
  if (res.status === 503) throw new ApiError("HARDWARE", data.detail || "Uno not responding.");
  throw new ApiError("UNKNOWN", `Server error (${res.status}).`);
}

const post = (path, body) => send("POST", path, body);
const get = (path) => send("GET", path);

// POST /api/analyze → { status, current_ma (may be null), warnings, recommendation,
//                       simulated_with, original:{resistance,current_ma,status}, corrected|null }
export function analyzeCircuit({ voltage, resistance, led_forward_voltage }) {
  const body = {
    voltage: Number(voltage),
    resistance: Number(resistance),
    led_forward_voltage: Number(led_forward_voltage),
  };
  return USE_MOCK ? mockAnalyze(body) : post("/api/analyze", body);
}

// POST /api/hardware/led {state:"on"|"off"} → acknowledged command (not a measurement)
export function setLed(state) {
  if (USE_MOCK) return new Promise((ok) => setTimeout(() => ok({ state, acknowledged: true }), 300));
  return post("/api/hardware/led", { state });
}

// POST /api/hardware/rgb {r,g,b: bool} → pins 9/10/11 (RGB LED circuit)
export function setRgb({ r, g, b }) {
  if (USE_MOCK) return new Promise((ok) => setTimeout(() => ok({ r, g, b, acknowledged: true }), 300));
  return post("/api/hardware/rgb", { r: !!r, g: !!g, b: !!b });
}

// POST /api/hardware/switch/follow → command D5 ON; D9/D8 buttons retain control.
export function followSwitch() {
  if (USE_MOCK) return new Promise((ok) => setTimeout(() => ok({ mode: "switch", acknowledged: true }), 300));
  return post("/api/hardware/switch/follow", {});
}

// GET /api/hardware/switch → { closed: bool }  (mock mode flips every 2 s so the demo moves)
export function getSwitch() {
  if (USE_MOCK) return Promise.resolve({ closed: Math.floor(Date.now() / 2000) % 2 === 0 });
  return get("/api/hardware/switch");
}

// ---- Mock: mirrors backend/app/services/analysis.py + MockSimulator ----
const MIN_OHMS = 5, TARGET_MA = 15, MAX_SAFE_MA = 20, MIN_VISIBLE_MA = 1;
const E12 = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82];
const round2 = (n) => Math.round(n * 100) / 100;
const currentMa = (v, r, vf) => (v <= vf ? 0 : round2(((v - vf) / Math.max(r, MIN_OHMS)) * 1000));
const classify = (i) => (i > MAX_SAFE_MA ? "danger" : i < MIN_VISIBLE_MA ? "warning" : "safe");

function suggestResistor(v, vf) {
  if (v <= vf) return null;
  const ideal = (v - vf) / (TARGET_MA / 1000);
  for (let d = 1; d <= 10000; d *= 10) for (const b of E12) if (b * d >= ideal) return b * d;
  return null;
}

async function mockAnalyze({ voltage: v, resistance: r, led_forward_voltage: vf }) {
  const i0 = currentMa(v, r, vf);
  const status = classify(i0);
  const warnings = [];
  if (v <= vf) warnings.push("Voltage is below the LED's forward voltage. It won't light.");
  else if (i0 > MAX_SAFE_MA) warnings.push("Current is over 20 mA. The LED may burn out.");
  else if (i0 < MIN_VISIBLE_MA) warnings.push("Current is under 1 mA. The LED will be very dim.");
  let corrected = null;
  if (status !== "safe") {
    const rFix = suggestResistor(v, vf);
    if (rFix !== null) {
      const i1 = currentMa(v, rFix, vf);
      corrected = { resistance: rFix, current_ma: i1, status: classify(i1) };
    }
  }
  return {
    status,
    current_ma: i0,
    warnings,
    recommendation: corrected ? `Use a ${corrected.resistance} Ω resistor.` : v <= vf ? "Raise the supply voltage." : "Looks good.",
    simulated_with: "mock",
    original: { resistance: r, current_ma: i0, status },
    corrected,
  };
}
