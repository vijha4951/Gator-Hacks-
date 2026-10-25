# Uno USB LED control

Wiring: Uno digital pin 8 -> 220 ohm resistor -> red LED anode; LED cathode -> GND.
Unplug USB before rewiring. Keep the resistor physically installed.
Upload `led_serial/led_serial.ino` in Arduino IDE, board Arduino Uno.
The sketch uses 9600 baud and newline-terminated LED_ON / LED_OFF commands.
It starts with pin 8 LOW. Test in Serial Monitor, then close Serial Monitor before
starting the backend. Only one program can own the port.

From the repository root, install `backend/requirements.txt` in your virtual environment.
Find the port with `python -m serial.tools.list_ports` (use your virtual environment's Python).
Set your own ARDUINO_PORT; the example below is this Mac's current port, not a universal value.

macOS:
```bash
SIMULATOR=physbox ARDUINO_PORT=/dev/cu.usbmodem11201 simulation/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

Windows PowerShell (replace COM3 with your actual port):
```powershell
$env:SIMULATOR = "physbox"
$env:ARDUINO_PORT = "COM3"
.\simulation\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

In http://127.0.0.1:8000/docs use POST /api/hardware/led with:
```json
{"state":"on"}
```
Send `{"state":"off"}` to turn it off. GET /api/hardware/ports lists available ports
without opening them. Hardware does not depend on a Volt tab; simulation still does.

Frontend example (same-origin or configured API base URL):
```javascript
const response = await fetch(`${API_BASE_URL}/api/hardware/led`, {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({state: 'on'})
});
const result = await response.json();
if (!response.ok) throw new Error(result.detail || 'Hardware request failed');
// Display the acknowledged state. This is not a current measurement.
```

The connection opens lazily on the first command, waits two seconds for Uno reset,
and stays open between commands. Calls are serialized; use one backend worker and
one backend instance per Uno. Missing configuration, USB errors, or missing replies
return HTTP 503, never a simulated success. Reconnect USB and retry after an error;
restart with the new port if it changes. Close the backend before uploading sketches.
Do not assume shutdown switches the output off: send OFF and confirm it first.

This is local demo control with no authentication, intended for a loopback backend.
Keep this endpoint local until access control is added for any public deployment.
The API confirms sketch acknowledgements, not measured LED illumination or current.
No physical resistor switching, current sensing, or website deployment is included.
