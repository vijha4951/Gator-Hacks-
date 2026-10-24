# CircuitGuard web (figma-ui)

Web version of the Figma "Web Hi-fi / NEW" screens (W01–W10).

## Run
```
npm install
cp .env.example .env.local   # VITE_USE_MOCK=true works without the backend
npm run dev                  # http://localhost:5173
```

## Connect the backend
Set in `.env.local`:
```
VITE_USE_MOCK=false
VITE_API_URL=http://localhost:8000
```
Start the backend from `sim-hardware` (see hardware/README.md). CORS already allows http://localhost:5173.

| Screen | Endpoint |
|---|---|
| CHECK → SCANNING → FOUND/RESULT | `POST /api/analyze` |
| CONNECT UNO (TURN ON / OFF) | `POST /api/hardware/led` (503 → NO UNO screen) |

Notes
- `current_ma` can be `null`; it is shown as "—", never 0.
- "CHECK AGAIN" returns to CHECK with the suggested resistor filled in.
- Plan chat is UI only for now (no plan endpoint yet).

## v6 design update
- Progress segments move yellow → light blue → blue, then green only after a successful API response. This is processing progress, not a safety rating; intermediate stages are illustrative because the API does not stream progress.
- Supply, resistor and LED values sit in a separate caption row below the circuit drawing.
- The physical next steps have a larger, highlighted panel on the result screen.
- Home card headings have more padding and wrap without the moving selection arrow.
- The plan and conversation scroll inside their own bounded panels, including keyboard access.
- Read-only measurements have no input-like border; real inputs keep theirs.
- Reduced-motion preferences disable animations.

Build verified with `npm run build`. Real backend and Uno hardware require your existing server; plan chat remains a UI demo.

## v7 alignment update
- Button labels are centered independently from decorative lightning icons.
- The logo is centered in the header panel.
- The left result/issue card is the primary panel (650px); the right next-step panel is secondary (554px).
- PROJECT NIGHT LIGHT expands 62px to the left and scrolls within its 544px-tall frame. The conversation column is not an independent scroll area.
- Read-only numeric frames means the former small LCD-style borders around 30 mA and 30 → 13.6 mA, not the enclosing information cards or editable inputs.
