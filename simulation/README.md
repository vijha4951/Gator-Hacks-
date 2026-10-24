# PhysBox LED simulation

A first working example for CircuitGuard AI. This replaces the circuit in the active Volt tab with a 5 V DC supply, 220 ohm resistor, red LED, ground, and a voltage meter across the LED. Save any other circuit before running it.

## Setup on macOS

From the repository root:

```bash
python3 -m venv simulation/.venv
simulation/.venv/bin/python -m pip install -r simulation/requirements.txt
simulation/.venv/bin/physbox-mcp
```

Leave that terminal running. Expected: WebSocket hub on port 3142 and HTTP MCP endpoint at http://localhost:3141/mcp. If the address is already in use, check whether the existing PhysBox server is running; do not start another copy.

Open https://volt.physbox.io in a browser on the same Mac. Allow local network access if requested. Keep exactly one Volt tab open. The Machine Disconnected indicator refers to physical equipment, not MCP connectivity.

In a second terminal, from the repository root:

```bash
simulation/.venv/bin/python simulation/led_demo.py
```

Verified results: approximately 13.29 mA LED current, 2.077 V LED voltage, and 1008 samples for the one-second run. The simplified fixed-2-V estimate is 13.64 mA. Model versions and simulation duration can affect results.

If connection is refused, start the server. If Volt is disconnected, keep its tab open and reload it after the server starts. The script discovers required tools before using them and checks circuit validation before replacing the canvas.

## Files

- `led_demo.py`: small async example with `run_led_demo()`; uses the running HTTP MCP server.
- `led_220.json`: circuit nodes and wires retrieved from the verified example.
- `requirements.txt`: pinned top-level versions used for verification; transitive dependencies are not locked.

Known measurement limitation: the source current array reported 5 mA while the resistor and LED reported approximately 13.29 mA. This demo uses the LED current array and voltage meter reading; do not treat every component current array as a verified measurement.

The simulator remains browser-backed: this is not yet an unattended or multi-user backend service. No physical Arduino connection is implemented here.

Official documentation: https://github.com/physbox-io/physbox-mcp

## Configurable inputs

The original command still defaults to 5 V and 220 ohms. To run 5 V and 330 ohms:

```bash
simulation/.venv/bin/python simulation/led_demo.py --voltage 5 --resistance 330
```

From Python, await `run_led_demo(supply_voltage=5, resistance_ohms=330)`.
The result includes the input values, actual LED current in mA, LED voltage in V,
and a separately labeled simplified estimate using a fixed 2 V LED drop.
The LED model remains the same red LED; this estimate does not change its model.
At 5 V and 330 ohms, the estimate is 9.09 mA; the actual simulation may differ.

Voltage must be finite and positive; resistance must be finite and nonnegative.
Negative resistance, NaN, and infinity are rejected before connecting to Volt.
Zero resistance removes the resistor and directly wires the source to the LED.
The fixed-drop estimate and `led_current_mA` are null for this case.
`measurement_status` is "unavailable" and `measurement_note` explains why.
Volt reported about 474.7 mA and 50 mA at different LED model states; waiting for
matching samples did not establish a reliable current. Neither value is presented
as a verified original measurement. Corrected positive-resistance circuits still
return measured current. The API separately simulates the recommended resistor.
Run one request at a time because Volt is a shared canvas.
