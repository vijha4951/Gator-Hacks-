# Two-button LED: Check my circuit + Connect Uno

## Wiring and physical behavior

Upload the separate `hardware/two_button_led/two_button_led.ino` sketch only after
rewiring with USB unplugged. The original pin-8 `led_serial` sketch is unchanged.

- D5 -> 220 ohm resistor -> LED anode. LED cathode -> GND.
- Button A / ON: one switched contact to D9, other to GND.
- Button B / OFF: one switched contact to D8, other to GND.
- Inputs use INPUT_PULLUP; pressed reads LOW. Do not wire a button to 5V.
- Four-legged tactile switches have internally joined pairs: choose contacts
  that are disconnected when released. Place them across the breadboard gap.

ON latches the LED on; OFF latches it off. Releasing buttons preserves state.
OFF wins when physical buttons are pressed together. Website actions also set
the same latched output. A website action can change the state after a physical
press; a new physical press changes it again. There is 30 ms input debounce.
The MCU starts OFF on reset. USB opening can reset it. Serial remains 9600 baud.

Close the backend/Serial Monitor before upload. Do not upload automatically:
the LED wire must move from D8 to D5 because D8 is now an input.

## Frontend: Connect Uno

Existing POST /api/hardware/led with {"state":"on"|"off"} still works.
The uploaded sketch determines the output pin (old sketch D8, new sketch D5).

New POST /api/hardware/buttons:
```json
{"button":"on"}
```
Use "off" for the other button. This sends a website command; it does not
physically press a switch. Wait for acknowledged=true before claiming success.

New GET /api/hardware/state queries the real sketch:
```json
{
  "connected":true,"source":"arduino","state":"on",
  "button_on_pressed":false,"button_off_pressed":false,
  "led_pin":5,"on_pin":9,"off_pin":8
}
```
Poll about once per second while the hardware tab is visible, with at most one
request in flight; cancel/stop polling when leaving the tab. Use reported state
for the LED display so physical presses are reflected. On 503 show unavailable;
do not keep claiming a confirmed current state. The old sketch does not support
STATE and returns an error; upload the new sketch first. No current is measured.

## Frontend: Check my circuit

New POST /api/analyze/buttons builds an actual Volt circuit with a programmable
MCU, two SPST switches and 20k pullups representing the MCU's internal pullups.
The controller uses D5 output, D9 ON input and D8 OFF input.

```json
{
  "voltage":5,"resistance":220,"led_forward_voltage":2,
  "on_pressed":true,"off_pressed":false,"initial_state":"off"
}
```
The Uno-style model is fixed at 5V; other voltages return 422. Supported LED model
values are 2 (red), 2.2 (green), 3 (blue). Button booleans describe whether switches
are pressed for this run. `initial_state` lets the frontend carry the prior latched
state into the next run. Requests do not share a hidden global latch.

Response has `led_state`, `led_current_mA`, `led_voltage_V`, `simulated_with`,
`controller_model`, `recommendation`, and `analysis`. When ON, analysis contains
the usual original/corrected troubleshooting response. When intentionally OFF,
analysis is null: near-zero current is expected, not a dim-LED fault requiring a
new resistor. No-resistor current remains unavailable when ON.

Volt runs JavaScript MCU behavior + SPICE, not compiled AVR firmware. At 5V,
220 ohms, red LED: ON was about 12.22 mA; OFF and both pressed were 0 mA. The MCU
output model differs from an ideal 5V source, so results differ from the simple
LED demo. Simulation requests use the existing shared canvas lock.

The hardware tab uses real USB communication; the check tab uses Volt. Neither
simulated current nor sketch-reported state is a physical current measurement.

Keep this as a distinct two-button option. Existing single-LED controls retain
their contract. RGB is a separate pending feature, not included in this change.

Deployed frontend compatibility: GET /api/hardware/switch returns the same real
state plus `closed` (true when the LED latch is ON). POST
/api/hardware/switch/follow implements the screen's Turn on action: it sends
LED_ON and then reads the real latch. Physical buttons can change it afterward. This does not turn the momentary
buttons into a maintained single switch.
