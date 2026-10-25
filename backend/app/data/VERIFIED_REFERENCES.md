# Verified references (v1.1)

This file summarizes [`verified_references.json`](verified_references.json), the
backend reference that the planner should load. The JSON is the source used by
the application; update this summary whenever that reference changes.

## Supported planning example

- The accepted board name is **Arduino Uno R3**. This is a scope decision, not
  verification of its electrical limits or compatibility with a particular
  physical build.
- The modeled circuit is **one red LED**, **one series current-limiting
  resistor**, and a positive DC source with ground. The verified demo uses a
  5 V source.
- The LED model has a 2.0 V forward voltage and a 20 mA maximum current. The
  simulated-current band is 1–20 mA inclusive, with a target near 15 mA.
- The resistor is required. Zero ohms is classified as danger. E12 values are
  preferred by the existing analysis code; 220 Ω and 330 Ω have been exercised
  in the 5 V demo. These demo facts do not establish the right resistor for
  every user's supply or physical LED.
- The simulator can report current for the modeled LED circuit. It does not
  verify the physical build or model Arduino pin behavior.

## Unknown: ask or label “Needs confirmation”

The planner must not guess any of the following:

- Arduino Uno R3 pin current limits, 5 V regulator rating, recommended pins,
  USB versus external supply limits, or ability of its 5 V pin to supply the
  intended current.
- The user's physical LED part number or measured forward voltage.
- The resistor's wattage rating or exact value for the user's actual supply and
  LED.
- Whether direct LED drive without the series resistor is appropriate. The
  supported circuit requires the resistor; do not recommend removing it.

Each unknown in the JSON includes why it matters and what the planner should
do. Treat the LED's 2.0 V as a model value, not a measurement of the user's
part. Never claim simulation proves that a physical circuit is safe.

## Excluded in v1

RGB, WS2812/NeoPixel, other multi-color or addressable LEDs, pin assignments,
wire-by-wire diagrams, complete sketches, PWM or digital output modeling,
multiple LEDs, transistors, drivers, level shifting, battery advice, USB details
beyond the 5 V rail assumption, unverified breadboard layout advice, prices,
part numbers, and shopping lists are unsupported. They are not typical values
or recommendations.

Pricing is omitted (`pricing.status` is `omitted`) until the team supplies a
current, dated, approved source.

## Planner rule

Load `verified_references.json`. Use only its `verified` facts. For every item
under `unknown`, ask a relevant question or label it **Needs confirmation**.
Never invent pin maps, programs, ratings, or prices.
