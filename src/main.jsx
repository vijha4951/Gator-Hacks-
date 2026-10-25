import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

function Section({ title, children, className = "" }) {
  return (
    <section className={`result-section ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function TextList({ items, empty = "Nothing to show yet." }) {
  if (!items?.length) return <p className="muted">{empty}</p>;
  return (
    <ul className="plain-list">
      {items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
    </ul>
  );
}

function PlanResult({ plan, onEdit, onNew, onUseRedLed, onCheckCircuit }) {
  const needsConfirmation = plan.status === "needs_confirmation";
  return (
    <div className="plan-result" aria-live="polite">
      <div className={`status-banner ${needsConfirmation ? "status-pending" : "status-ready"}`}>
        <div className="status-icon" aria-hidden="true">{needsConfirmation ? "?" : "✓"}</div>
        <div>
          <p className="eyebrow">{needsConfirmation ? "A choice is needed" : "Project plan"}</p>
          <h2>{needsConfirmation ? "Let’s confirm the project scope" : "Your project plan"}</h2>
          <p>{needsConfirmation
            ? "This is a clarification, not a complete plan. Answer the question below before treating it as ready."
            : "This plan follows CircuitGuard’s verified first-version scope. Read the checks and limits before building."}</p>
        </div>
      </div>

      {plan.project_summary && (
        <Section title="Project summary">
          <p>{plan.project_summary}</p>
        </Section>
      )}

      {needsConfirmation && plan.questions?.length > 0 && (
        <Section title="Please confirm">
          <div className="question-list">
            {plan.questions.map((question) => (
              <article className="question-card" key={question.id}>
                <h3>{question.question}</h3>
                <p>{question.why_it_matters}</p>
                {["single_red_led_confirmation", "led_type_confirmation"].includes(question.id) && (
                  <button className="inline-action" type="button" onClick={onUseRedLed}>
                    Use the supported single-red-LED project
                  </button>
                )}
              </article>
            ))}
          </div>
          <p className="small-note">To continue, edit your project description to reflect your answer, then submit it again.</p>
        </Section>
      )}

      {!needsConfirmation && plan.questions?.length > 0 && (
        <Section title="Optional questions">
          <div className="question-list">
            {plan.questions.map((question) => (
              <article className="question-card" key={question.id}>
                <h3>{question.question}</h3>
                <p>{question.why_it_matters}</p>
              </article>
            ))}
          </div>
          <p className="small-note">These answers do not block this first-version plan.</p>
        </Section>
      )}

      {plan.scope && (
        <Section title="What this covers">
          <div className="two-column">
            <div>
              <h3>Included</h3>
              <TextList items={plan.scope.included} empty="No included items listed." />
            </div>
            <div>
              <h3>Not included</h3>
              <TextList items={plan.scope.not_included} empty="No exclusions listed." />
            </div>
          </div>
        </Section>
      )}

      {!needsConfirmation && plan.parts?.length > 0 && (
        <Section title="Parts to consider">
          <div className="part-list">
            {plan.parts.map((part, index) => (
              <article className="part-card" key={`${part.name}-${index}`}>
                <div className="part-heading">
                  <h3>{part.name}</h3>
                  <span className="quantity">{part.quantity ?? "Quantity to confirm"}</span>
                </div>
                <p>{part.purpose}</p>
                {part.verified_ratings?.length > 0 && (
                  <div className="fact-box">
                    <strong>Verified details</strong>
                    <TextList items={part.verified_ratings} />
                  </div>
                )}
                <p className="obtain-note">{part.obtain === true
                  ? "You said you need to get this part."
                  : part.obtain === false
                    ? "You said you already have this part."
                    : "Whether you need to get this part is not known yet."}</p>
                {part.notes?.length > 0 && <TextList items={part.notes} />}
              </article>
            ))}
          </div>
          <p className="small-note">No prices or part numbers are provided. Check every “Needs confirmation” note against your actual components.</p>
        </Section>
      )}

      {!needsConfirmation && plan.stages?.length > 0 && (
        <Section title="Broad build stages">
          <ol className="stage-list">
            {plan.stages.map((stage, index) => (
              <li className="stage-card" key={`${stage.title}-${index}`}>
                <span className="stage-number" aria-hidden="true">{index + 1}</span>
                <div>
                  <h3>{stage.title}</h3>
                  <p><strong>Goal:</strong> {stage.goal}</p>
                  <p><strong>Observe:</strong> {stage.learn_or_observe}</p>
                  <p><strong>Check before continuing:</strong> {stage.check_before_continuing}</p>
                </div>
              </li>
            ))}
          </ol>
          <p className="small-note">These are learning stages, not a wire-by-wire guide or a complete Arduino program.</p>
        </Section>
      )}

      {plan.safety_and_common_problems?.length > 0 && (
        <Section title="Safety and common problems" className="safety-section">
          <TextList items={plan.safety_and_common_problems} />
        </Section>
      )}

      {plan.simulator_checks && (
        <Section title="What the simulator can check">
          <div className="two-column">
            <div><h3>Can check</h3><TextList items={plan.simulator_checks.can_verify} /></div>
            <div><h3>Cannot check</h3><TextList items={plan.simulator_checks.cannot_verify} /></div>
          </div>
          <p className="small-note">A simulated result describes the modeled circuit. It does not prove a physical build is safe or correctly assembled.</p>
        </Section>
      )}

      {plan.assumptions?.length > 0 && (
        <Section title="Assumptions"><TextList items={plan.assumptions} /></Section>
      )}
      {plan.limitations?.length > 0 && (
        <Section title="Limits"><TextList items={plan.limitations} /></Section>
      )}

      <div className="result-actions">
        <button className="button button-secondary" type="button" onClick={needsConfirmation ? onEdit : onNew}>
          {needsConfirmation ? "Edit request and try again" : "Plan another project"}
        </button>
        {!needsConfirmation && <button className="text-link text-button" type="button" onClick={() => onCheckCircuit(plan)}>Check a circuit</button>}
      </div>
    </div>
  );
}

function CircuitCheck({ onBack, plan }) {
  const [resistance, setResistance] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function analyzeCircuit(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ voltage: 5, resistance: Number(resistance), led_forward_voltage: 2.0 }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "Circuit analysis is unavailable. Check that Volt is open and try again.");
      }
      setResult(body);
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? "Could not reach FastAPI. Make sure the backend is running at the configured address, then try again."
        : requestError.message || "Circuit analysis is unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const statusText = result?.status === "safe" ? "Within the simulated current range" : result?.status === "danger" ? "Simulated current is above the LED limit" : "Needs attention";
  return (
    <div className="check-grid">
      <form className="form-card check-card" onSubmit={analyzeCircuit}>
        <div className="form-heading">
          <div className="step-badge">01</div>
          <div><p className="eyebrow">Circuit check</p><h2>Check the supported LED circuit</h2></div>
        </div>
        {plan && <div className="plan-handoff"><strong>Checking from your plan</strong><p>{plan.project_summary}</p><span>The check below covers only the supported red LED circuit. It does not simulate the Arduino board or the full project.</span></div>}
        <p className="check-intro">Enter the series resistor value you used or want to try. This check models one red LED with a 5 V DC source and ground.</p>
        <label className="field-label" htmlFor="check-resistance">Series resistor value</label>
        <div className="unit-input"><input id="check-resistance" type="number" min="0" step="1" value={resistance} onChange={(event) => setResistance(event.target.value)} placeholder="Enter your resistor value" required /><span>Ω</span></div>
        <p className="helper-text">The plan does not choose a resistor for your real parts. Use the value printed on your resistor, or ask for help identifying it.</p>
        <div className="fixed-model">
          <div><span>Source model</span><strong>5 V DC</strong></div>
          <div><span>LED model</span><strong>Red · about 2 V</strong></div>
        </div>
        <p className="helper-text">The LED details are model values. Your physical parts may differ.</p>
        {error && <div className="error-box" role="alert"><strong>We couldn’t check the circuit.</strong><span>{error}</span></div>}
        <button className="button button-primary submit-button" type="submit" disabled={loading || resistance === ""}>
          {loading ? <><span className="spinner" aria-hidden="true" /> Checking the modeled circuit…</> : <>Analyze circuit <span aria-hidden="true">→</span></>}
        </button>
        <button className="back-link" type="button" onClick={onBack}>Back to project planning</button>
        <p className="privacy-note">The backend runs the available simulator and returns its result.</p>
      </form>

      <aside className="check-side">
        {result ? (
          <section className={`result-section check-result check-${result.status}`} aria-live="polite">
            <p className="eyebrow">Simulation result</p>
            <h2>{statusText}</h2>
            <p className="current-reading">{result.current_ma == null ? "Unavailable" : `${Number(result.current_ma).toFixed(2)} mA`}</p>
            <p className="small-note">{result.simulated_with === "physbox" ? "PhysBox simulated LED current" : "Offline estimate using Ohm’s law (not a PhysBox simulation)"}</p>
            <div className="recommendation"><strong>What this means</strong><p>{result.recommendation}</p></div>
            {result.warnings?.length > 0 && <div className="warning-list"><strong>Warnings</strong><ul className="plain-list">{result.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}</ul></div>}
            {result.corrected && (
              <div className="corrected-result">
                <strong>Suggested resistor to simulate next</strong>
                <p>{result.corrected.resistance} Ω · {result.corrected.current_ma == null ? "current unavailable" : `${Number(result.corrected.current_ma).toFixed(2)} mA simulated`}</p>
              </div>
            )}
            <p className="small-note">A simulation checks the modeled circuit only. It does not prove the physical build is safe or correctly assembled.</p>
          </section>
        ) : (
          <section className="side-card side-card-dark check-side-card">
            <p className="eyebrow">What gets checked</p>
            <h2>One simple circuit</h2>
            <p>The simulator reports current through the modeled red LED. It does not model Arduino pins, firmware, or your physical wiring.</p>
            <div className="model-line"><span>5 V source</span><i aria-hidden="true">→</i><span>resistor</span><i aria-hidden="true">→</i><span>red LED</span></div>
          </section>
        )}
      </aside>
    </div>
  );
}

function App() {
  const [view, setView] = useState("plan");
  const [description, setDescription] = useState("");
  const [board, setBoard] = useState("");
  const [partsOwned, setPartsOwned] = useState([]);
  const [partName, setPartName] = useState("");
  const [partQuantity, setPartQuantity] = useState("1");
  const [budget, setBudget] = useState("");
  const [mustUseBoard, setMustUseBoard] = useState(false);
  const [constraintsNotes, setConstraintsNotes] = useState("");
  const [plan, setPlan] = useState(null);
  const [checkPlan, setCheckPlan] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function addOwnedPart(event) {
    event.preventDefault();
    const name = partName.trim();
    if (!name) return;
    setPartsOwned((items) => [...items, { name, quantity: Number(partQuantity) || 1 }]);
    setPartName("");
    setPartQuantity("1");
  }

  async function submitPlan(event) {
    event.preventDefault();
    setError("");
    setPlan(null);
    setLoading(true);

    const request = {
      project_description: description.trim(),
      parts_owned: partsOwned,
      constraints: {
        budget_usd: budget === "" ? null : Number(budget),
        must_use_board: mustUseBoard,
        notes: constraintsNotes.trim() || null,
      },
    };
    if (board) request.board_model = board;

    try {
      const response = await fetch(`${API_BASE}/api/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(request),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof body.detail === "string" ? body.detail : "Planning is unavailable. Please try again.");
      }
      if (!body?.status || !body?.project_summary) {
        throw new Error("The backend response was missing plan details. Restart FastAPI and try again.");
      }
      setPlan(body);
    } catch (requestError) {
      setError(requestError instanceof TypeError
        ? "Could not reach FastAPI. Make sure the backend is running at the configured address, then try again."
        : requestError.message || "Planning is unavailable. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  function resetForm() {
    setPlan(null);
    setError("");
  }

  function startAnotherPlan() {
    resetForm();
    setDescription("");
    setBoard("");
    setPartsOwned([]);
    setPartName("");
    setPartQuantity("1");
    setBudget("");
    setMustUseBoard(false);
    setConstraintsNotes("");
    // Return focus to the (now empty) description so it is clear a new idea is
    // needed; without this the primary button looks stuck because it is
    // disabled until the description has at least 3 characters.
    window.requestAnimationFrame(() => document.getElementById("description")?.focus());
  }

  function editRequest() {
    resetForm();
    window.requestAnimationFrame(() => document.getElementById("description")?.focus());
  }

  function useSupportedRedLedProject() {
    setDescription("Plan a single red LED indicator circuit using an Arduino Uno R3.");
    setBoard("Arduino Uno R3");
    setMustUseBoard(true);
    resetForm();
    window.requestAnimationFrame(() => document.getElementById("description")?.focus());
  }

  function useDemoIdea() {
    setDescription("Can you help me plan a color-changing LED with an Arduino Uno R3? I am new to electronics.");
    setBoard("Arduino Uno R3");
    setPlan(null);
    setError("");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CircuitGuard AI home">
          <span className="brand-mark" aria-hidden="true">CG</span>
          <span>CircuitGuard <b>AI</b></span>
        </a>
        <nav className="mode-nav" aria-label="CircuitGuard tools">
          <button className={view === "plan" ? "mode-button active" : "mode-button"} type="button" onClick={() => setView("plan")}>Plan a project</button>
          <button className={view === "check" ? "mode-button active" : "mode-button"} type="button" onClick={() => { setCheckPlan(null); setView("check"); }}>Check a circuit</button>
        </nav>
      </header>

      <div className="page-content" id="top">
        <section className="intro">
          <p className="eyebrow">{view === "plan" ? "Start with an idea" : "Check as you build"}</p>
          <h1>{view === "plan" ? <>Let’s plan a project<br /><span>you can understand.</span></> : <>Check a circuit<br /><span>before continuing.</span></>}</h1>
          <p className="intro-copy">{view === "plan"
            ? "Describe what you want to make. CircuitGuard will help you think through the parts, broad stages, and what still needs checking before you build."
            : "Enter the resistor value for the supported one-red-LED model. CircuitGuard runs the available simulator and explains its simulated result."}</p>
          <div className="scope-chip"><span aria-hidden="true">●</span> First version: one red LED, one series resistor, and a 5 V DC source with ground</div>
        </section>

        {view === "check" && <CircuitCheck plan={checkPlan} onBack={() => setView("plan")} />}

        {view === "plan" && !plan && (
          <div className="planner-grid">
            <form className="form-card" onSubmit={submitPlan}>
              <div className="form-heading">
                <div className="step-badge">01</div>
                <div><p className="eyebrow">Project idea</p><h2>What would you like to make?</h2></div>
              </div>

              <label className="field-label" htmlFor="description">Describe your project <span className="required">Required</span></label>
              <textarea
                id="description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="For example: I want to make a red LED indicator with an Arduino Uno R3. I’m new to electronics."
                rows={5}
                maxLength={1200}
                required
                minLength={3}
              />
              <div className="field-foot"><span>Use your own words. A short description is enough.</span><span>{description.length}/1200</span></div>
              <button className="demo-link" type="button" onClick={useDemoIdea}>Try the demo idea: color-changing LED <span aria-hidden="true">↗</span></button>

              <div className="form-divider" />
              <div className="form-heading compact">
                <div className="step-badge">02</div>
                <div><p className="eyebrow">Optional details</p><h2>What do you already know?</h2></div>
              </div>

              <label className="field-label" htmlFor="board">Board model</label>
              <select id="board" value={board} onChange={(event) => setBoard(event.target.value)}>
                <option value="">I’m not sure yet</option>
                <option value="Arduino Uno R3">Arduino Uno R3</option>
              </select>
              <label className="checkbox-row" htmlFor="must-use-board">
                <input id="must-use-board" type="checkbox" checked={mustUseBoard} onChange={(event) => setMustUseBoard(event.target.checked)} />
                <span>I need the plan to use this board</span>
              </label>

              <label className="field-label owned-label" htmlFor="part-name">Parts I already have</label>
              <div className="owned-entry">
                <input id="part-name" value={partName} onChange={(event) => setPartName(event.target.value)} placeholder="Part name" maxLength={120} />
                <input aria-label="Quantity owned" type="number" min="1" max="1000" value={partQuantity} onChange={(event) => setPartQuantity(event.target.value)} />
                <button className="add-button" type="button" onClick={addOwnedPart} disabled={!partName.trim()}>Add</button>
              </div>
              {partsOwned.length > 0 && (
                <ul className="owned-list" aria-label="Parts you already have">
                  {partsOwned.map((part, index) => (
                    <li key={`${part.name}-${index}`}>
                      <span>{part.name} <small>× {part.quantity}</small></span>
                      <button type="button" aria-label={`Remove ${part.name}`} onClick={() => setPartsOwned((items) => items.filter((_, itemIndex) => itemIndex !== index))}>Remove</button>
                    </li>
                  ))}
                </ul>
              )}

              <div className="optional-grid">
                <div>
                  <label className="field-label" htmlFor="budget">Budget (optional)</label>
                  <div className="input-prefix"><span>$</span><input id="budget" type="number" min="0" step="0.01" value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="No budget set" /></div>
                  <p className="helper-text">The planner won’t return prices.</p>
                </div>
                <div>
                  <label className="field-label" htmlFor="notes">Other preferences</label>
                  <input id="notes" value={constraintsNotes} onChange={(event) => setConstraintsNotes(event.target.value)} maxLength={1000} placeholder="Keep it simple, for example" />
                </div>
              </div>

              {error && <div className="error-box" role="alert"><strong>We couldn’t make a plan.</strong><span>{error}</span></div>}

              <button className="button button-primary submit-button" type="submit" disabled={loading || description.trim().length < 3}>
                {loading ? <><span className="spinner" aria-hidden="true" /> Making your plan…</> : <>Create my project plan <span aria-hidden="true">→</span></>}
              </button>
              <p className="privacy-note">Your project description is sent to CircuitGuard’s backend to create the plan.</p>
            </form>

            <aside className="side-column">
              <section className="side-card side-card-dark">
                <p className="eyebrow">How it works</p>
                <div className="mini-flow">
                  <div><span>1</span><p><b>Describe</b><small>Tell us what you hope to make.</small></p></div>
                  <div><span>2</span><p><b>Plan</b><small>Review parts, broad stages, and open questions.</small></p></div>
                  <div><span>3</span><p><b>Build & check</b><small>Check a supported circuit before continuing.</small></p></div>
                </div>
              </section>
              <section className="side-card boundary-card">
                <div className="boundary-icon" aria-hidden="true">!</div>
                <div><h2>Small, checked scope</h2><p>V1 plans a single red LED, a current-limiting resistor, and a 5 V DC source with ground. It does not provide pin numbers, wiring diagrams, full code, or prices.</p></div>
              </section>
              <section className="side-card learning-card">
                <p className="eyebrow">Good to know</p>
                <p>The plan uses verified reference facts where available. Unknown details are marked <b>Needs confirmation</b>. A simulation checks a model, not your physical build.</p>
              </section>
            </aside>
          </div>
        )}

        {view === "plan" && plan && <PlanResult plan={plan} onEdit={editRequest} onNew={startAnotherPlan} onUseRedLed={useSupportedRedLedProject} onCheckCircuit={(approvedPlan) => { setCheckPlan(approvedPlan); setView("check"); }} />}

        <footer className="page-footer">
          <span>CircuitGuard AI · Learn by planning, building, and checking</span>
          <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">Backend docs</a>
        </footer>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
