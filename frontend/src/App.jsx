import { createContext, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { analyzeCircuit, setLed as sendLed, setRgb, followSwitch, getSwitch } from "./api";

const Go = createContext(() => {});
const Slots = createContext({ head: null, dock: null });

const A = (n) => `/assets/${n}.svg`;
const LEDS = { Red: 2, Green: 2.2, Blue: 3, White: 3 };
const LIMIT = 20;
const CIRCUITS = {
  led: { label: "LED + resistor", art: "circuit" },
  switch: { label: "LED with switch", art: "circuit-switch" },
  rgb: { label: "RGB LED", art: "circuit-rgb" },
};
// Typical RGB LED forward voltages: red ~2 V, green and blue ~3 V.
const RGB = [
  { k: "r", name: "RED", vf: 2, color: "#E5533D" },
  { k: "g", name: "GREEN", vf: 3, color: "#54B06B" },
  { k: "b", name: "BLUE", vf: 3, color: "#4FA9C7" },
];
const SEV = { safe: 0, warning: 1, danger: 2 };
const cap = (t) => t[0] + t.slice(1).toLowerCase();

// Folds three per-colour analyses into one object shaped like a single-LED result,
// so the found/result screens keep working. `corrected.resistance` is the largest
// per-colour fix: a resistor that big is safe on every colour.
function combineRgb(channels) {
  const worst = channels.reduce((a, b) => {
    const d = SEV[b.res.status] - SEV[a.res.status];
    return d > 0 || (d === 0 && (b.res.original.current_ma ?? 0) > (a.res.original.current_ma ?? 0)) ? b : a;
  });
  const fixes = channels.filter((x) => x.res.corrected);
  const after = channels.map((x) => (x.res.corrected ?? x.res.original).status).reduce((a, b) => (SEV[b] > SEV[a] ? b : a));
  return {
    rgb: true, ckt: "rgb", channels,
    status: worst.res.status, current_ma: worst.res.original.current_ma,
    warnings: channels.flatMap((x) => x.res.warnings),
    recommendation: worst.res.recommendation, simulated_with: worst.res.simulated_with,
    original: worst.res.original,
    corrected: fixes.length ? { resistance: Math.max(...fixes.map((x) => x.res.corrected.resistance)), current_ma: null, status: after } : null,
  };
}

const CircuitPick = ({ value, onChange, disabled, title, style }) => (
  <label className="a pick" style={style} title={title}>
    <select aria-label="Circuit type" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)}>
      {Object.entries(CIRCUITS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
    </select>
  </label>
);

const flow = ["VALUES", "CHECK", "RESULT"];
const fmt = (x, d = 0) => (x == null ? "—" : Number(x).toFixed(d));
const ghost = (t) => String(t).replace(/\d/g, "8"); // unlit LCD segments behind the digits
const fmtI = (x) => (x == null ? "—" : Number(x) < 10 ? Number(x).toFixed(1) : Number(x).toFixed(0)); // small currents keep a decimal
const ICON = {
  cam: <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#26332C" strokeWidth="2"><path d="M3 8h4l2-3h6l2 3h4v11H3z" strokeLinejoin="round" /><circle cx="12" cy="13" r="3.5" /></svg>,
  uno: <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#26332C" strokeWidth="2"><rect x="5" y="5" width="14" height="14" rx="1" /><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3" /><path d="M12.8 8.5L10 12.5h2.2l-1 3.5 3-4.2h-2.2z" fill="#26332C" stroke="none" /></svg>,
  chat: <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#26332C" strokeWidth="2"><path d="M4 5h16v11H11l-4 4v-4H4z" strokeLinejoin="round" /><path d="M13 7.5l-3 4h3l-2 3" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>,
  camS: <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#26332C" strokeWidth="2.2"><path d="M3 8h4l2-3h6l2 3h4v11H3z" strokeLinejoin="round" /><circle cx="12" cy="13" r="3.5" /></svg>,
};

function Type({ text, speed = 30 }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    setN(0);
    const t = setInterval(() => setN((x) => (x >= text.length ? (clearInterval(t), x) : x + 1)), 1000 / speed);
    return () => clearInterval(t);
  }, [text, speed]);
  return <span onClick={() => setN(text.length)}>{text.slice(0, n)}{n >= text.length && <span className="caret">▼</span>}</span>;
}

const Page = ({ children, lamp = "", back, title, step, action, onGo, goDisabled, ask = true, bar }) => {
  const go = useContext(Go);
  const { head, dock } = useContext(Slots);
  return (
    <>
      {head && createPortal(
        <>
          <div className="a hd" />
          <div className={"a lamp " + lamp}>{lamp === "issue" ? "!" : lamp === "ok" ? "✓" : lamp === "warn" ? "?" : lamp === "work" || lamp === "on" ? "⚡" : ""}</div>
          <img className="a logo" src={A("logo")} alt="CircuitGuard" />
          <img className="a bolt" src={A("bolt")} />
        </>, head)}
      {dock && createPortal(
        <>
          {!ask && !bar && <img className="a rail" src={A("rail")} />}
          {ask && <button className="a ask click" onClick={() => go("chat")}>⚡<br />ASK</button>}
          {action && <button className="a btn go click" disabled={goDisabled} onClick={onGo}><img src={A("spark")} alt="" aria-hidden="true" /><span className="btn-label">{action}</span></button>}
          {bar}
        </>, dock)}
      {back && <button className="a back click" aria-label="Back" onClick={() => go(back)}><img src={A("back")} /></button>}
      {title && <h2 className="a nav" style={{ left: back ? 160 : 96 }}>{title}</h2>}
      {step != null && (
        <div className="a steps" style={{ left: 544 }}>
          {flow.map((f, i) => (
            <span key={f} style={{ display: "contents" }}>
              <span className={i === step ? "cur" : i > step ? "todo" : ""}>{i < step ? "✓ " : ""}{f}</span>
              {i < 2 && <i />}
            </span>
          ))}
        </div>
      )}
      {children}
    </>
  );
};

const DEFAULT_PARTS = ["Arduino Uno", "Light sensor (LDR)", "LED", "Resistors 220 Ω, 10 kΩ", "Breadboard + wires"];
const DEFAULT_STEPS = ["Light up the LED", "Read the light sensor", "Make the LED react"];
// Each starter idea is linked to a materials text file in /public/materials/.
const PLANS = {
  "Make an LED blink": { file: "led-blink", steps: ["Wire the LED and resistor", "Upload the Blink sketch", "Change the blink speed"] },
  "Night light for the dark": { file: "night-light", steps: DEFAULT_STEPS },
  "Ideas for a starter kit": { file: "starter-kit", steps: ["Sort your parts", "Build a simple LED circuit", "Pick your first project"] },
};
const parseMaterials = (txt) => {
  const lines = txt.split(/\r?\n/);
  const first = (lines[0] || "").replace(/^PROJECT:\s*/i, "").trim();
  let on = false; const parts = [];
  for (const l of lines) {
    if (/^[A-Z][A-Z ]+$/.test(l.trim())) on = l.trim() === "MATERIALS";
    else if (on && l.startsWith("- ")) parts.push(l.slice(2).trim());
  }
  return { title: first, parts };
};

export default function App() {
  const [scr, setScr] = useState("home");
  const [sel, setSel] = useState(0);
  const [volts, setVolts] = useState("5");
  const [ohms, setOhms] = useState("100");
  const [led, setLed] = useState("Red");
  const [tip, setTip] = useState(null);
  const [win, setWin] = useState({ w: 1440, h: 900 });
  const [head, setHead] = useState(null);
  const [dock, setDock] = useState(null);
  const [idea, setIdea] = useState("");
  const [draft, setDraft] = useState("");
  const [have, setHave] = useState([true, false, true, true, true]);
  const [mat, setMat] = useState(null); // materials loaded from the linked .txt file
  const [prog, setProg] = useState(0);
  useEffect(() => {
    const plan = PLANS[idea];
    if (!plan) { setMat(null); setHave([true, false, true, true, true]); return; }
    let alive = true;
    fetch(`${import.meta.env.BASE_URL}materials/${plan.file}.txt`)
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((t) => { if (!alive) return; const m = parseMaterials(t); if (!m.parts.length) throw 0; setMat({ ...m, file: plan.file, steps: plan.steps }); setHave(m.parts.map(() => false)); })
      .catch(() => { if (alive) { setMat(null); setHave([true, false, true, true, true]); } });
    return () => { alive = false; };
  }, [idea]);
  const [scanDone, setScanDone] = useState(false);
  const [ckt, setCkt] = useState("led");                       // led | switch | rgb (shared by Check and Uno)
  const [rgbOn, setRgbOn] = useState({ r: true, g: true, b: true });
  const [sw, setSw] = useState(null);                          // live switch state: true closed, false open
  const [unoErr, setUnoErr] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef();

  const V = parseFloat(volts), R = parseFloat(ohms), Vf = LEDS[led];
  const o = res?.original, c = res?.corrected;
  const mA = o?.current_ma ?? null;
  const fixR = c?.resistance;
  const fixmA = c?.current_ma ?? null;
  const st = res?.status;
  const volErr = !(V > 0);
  const runCheck = async () => {
    const base = { voltage: V, resistance: R };
    if (ckt !== "rgb") return { ...(await analyzeCircuit({ ...base, led_forward_voltage: Vf })), ckt }; // switch is analysed closed
    return combineRgb(await Promise.all(RGB.map((ch) => analyzeCircuit({ ...base, led_forward_voltage: ch.vf }).then((res) => ({ ...ch, res })))));
  };
  const go = (s) => setScr(s);
  const { w, h } = win;
  const scale = Math.max(0.4, Math.min(1.4, (w - 52) / 1388, Math.max(1, (h - 268) / 768)));
  const shellOuter = `M28 12H${w - 180}L${w - 160} 30H${w - 60}L${w - 12} 70V${h - 80}L${w - 68} ${h - 12}H28C17.3 ${h - 12} 12 ${h - 17.3} 12 ${h - 28}V28C12 17.3 17.3 12 28 12Z`;

  useEffect(() => {
    const fit = () => setWin({ w: document.documentElement.clientWidth, h: innerHeight });
    fit(); addEventListener("resize", fit);
    return () => removeEventListener("resize", fit);
  }, []);

  // home: arrow keys + Enter
  useEffect(() => {
    if (scr !== "home") return;
    const k = (e) => {
      if (e.key === "ArrowRight") setSel((s) => Math.min(2, s + 1));
      if (e.key === "ArrowLeft") setSel((s) => Math.max(0, s - 1));
      if (e.key === "Enter") go(["check", "uno_off", "chat"][sel]);
    };
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [scr, sel]);

  // scanning auto-advances
  useEffect(() => {
    clearInterval(timer.current);
    if (scr !== "scanning") return;
    let alive = true, done = null, p = 0, finishTimer;
    setScanDone(false);
    setProg(0);
    runCheck()
      .then((r) => (done = { r }))
      .catch((e) => (done = { e }));
    timer.current = setInterval(() => {
      if (!alive) return;
      p = done ? Math.min(10, p + 1) : Math.min(9, p + 1); // gauge waits at 9/10 until the server answers
      setProg(p);
      if (p >= 10 && done) {
        clearInterval(timer.current);
        if (done.r) { setRes(done.r); setScanDone(true); finishTimer = setTimeout(() => { if (alive) go(done.r.corrected ? "found" : "result"); }, 400); }
        else { setErr(done.e); go("failed"); }
      }
    }, 280);
    return () => { alive = false; clearInterval(timer.current); clearTimeout(finishTimer); };
  }, [scr]);

  // live switch state while the Uno follows it
  useEffect(() => {
    if (scr !== "uno_on" || ckt !== "switch") { setSw(null); return; }
    let alive = true;
    const poll = async () => {
      try { const r = await getSwitch(); if (alive) setSw(r.closed); }
      catch (e) { if (alive) { setUnoErr(e?.message || "Lost contact with the Uno."); go("no_uno"); } }
    };
    poll();
    const t = setInterval(poll, 700);
    return () => { alive = false; clearInterval(t); };
  }, [scr, ckt]);

  const rgbSteps = res?.rgb ? [
    res.channels.filter((x) => x.res.corrected).map((x) => `${cap(x.name)} ${x.res.corrected.resistance} Ω`).join(" · "),
    `Or ${fixR} Ω on all three`, "Check again"] : [];

  const dexRgb = (ok) => (
    <div className="a card rise" style={{ left: 96, top: 256, width: 650, overflow: "hidden" }}>
      <div style={{ height: 51, background: "var(--yellow)", borderBottom: "2px solid var(--ink)", display: "flex", alignItems: "center", gap: 12, padding: "0 18px" }} className="px">
        <span className="num" style={{ background: ok ? "var(--green)" : st === "warning" ? "var(--ink)" : "var(--red)", color: "#fff" }}>1</span><span style={{ fontSize: 13 }}>No.1 RGB LED</span>
      </div>
      <div style={{ padding: 18 }}>
        {ok
          ? <div className="px" style={{ fontSize: 20, margin: "6px 0 12px" }}>{c?.status === "safe" || (!c && st === "safe") ? "✓ WITHIN LIMIT" : "! CHECK NEEDED"}</div>
          : <div style={{ background: "#f3f4f0", borderRadius: 8, height: 150, display: "grid", placeItems: "center", margin: "0 0 12px" }}>
            <img src={A("circuit-rgb")} style={{ height: 130, maxWidth: "100%" }} /></div>}
        {res.channels.map((ch) => {
          const cur = ch.res.original.current_ma, fx = ch.res.corrected;
          return (
            <div className="rgb-row" key={ch.k}>
              <i style={{ background: ch.color }} /><span className="px">{ch.name}</span>
              <b style={{ color: !ok && ch.res.status === "danger" ? "var(--red)" : "var(--ink)" }}>
                {ok && fx ? `${fmtI(cur)} → ${fmt(fx.current_ma, 1)}` : fmtI(cur)} mA</b>
              <span className="fix">{fx ? `→ ${fx.resistance} Ω` : ch.res.status === "safe" ? "OK" : "—"}</span>
            </div>);
        })}
        <p style={{ fontSize: 18, margin: "10px 0 0", color: "var(--mute)" }}>{ok ? "Simulation only · not a physical test" : `Limit ${LIMIT} mA per color`}</p>
      </div>
    </div>
  );

  const Dex = ({ ok }) => res?.rgb ? dexRgb(ok) : (
    <div className="a card rise" style={{ left: 96, top: ok ? 256 : 256, width: 650, overflow: "hidden" }}>
      <div style={{ height: 51, background: "var(--yellow)", borderBottom: "2px solid var(--ink)", display: "flex", alignItems: "center", gap: 12, padding: "0 18px" }} className="px">
        <span className="num" style={{ background: ok ? "var(--green)" : st === "warning" ? "var(--ink)" : "var(--red)", color: "#fff" }}>1</span><span style={{ fontSize: 13 }}>No.1 RESISTOR</span>
      </div>
      {ok ? (
        <div style={{ padding: 19 }}>
          <div className="px" style={{ fontSize: 20, marginTop: 12 }}>{(c || o)?.status === "safe" ? "✓ WITHIN LIMIT" : "! CHECK NEEDED"}</div>
          <div className="lcd big" style={{ margin: "24px 0" }} data-ghost={c ? `${ghost(fmtI(mA))} → ${ghost(fmt(fixmA, 1))}` : ghost(fmt(mA, 1))}><b>{c ? <>{fmtI(mA)} → {fmt(fixmA, 1)}</> : fmt(mA, 1)}</b><span className="u">mA</span></div>
          {c && <p className="px" style={{ fontSize: 20 }}>FIX {fmt(o?.resistance)} Ω → {fixR} Ω</p>}
          {c && <><div className="px" style={{ fontSize: 13, margin: "22px 0 8px", display: "flex", justifyContent: "space-between" }}><span>BEFORE</span><span>{fmtI(mA)} mA</span></div>
          <div className="bar"><b style={{ width: Math.min(100, (mA ?? 0) * 2.5) + "%", background: "#8a9490" }} /><i className="lim" /></div></>}
          <div className="px" style={{ fontSize: 13, margin: "22px 0 8px", display: "flex", justifyContent: "space-between" }}><span>{c ? "AFTER" : "CURRENT"}</span><span>{fmt(c ? fixmA : mA, 1)} mA</span></div>
          <div className="bar"><b style={{ width: Math.min(100, ((c ? fixmA : mA) ?? 0) * 2.5) + "%", background: "var(--ink)" }} /><i className="lim" /></div>
          <p style={{ fontSize: 20, margin: "30px 0 4px", borderTop: "2px solid var(--ink)", paddingTop: 16 }}>Simulation only · not a physical test</p>
        </div>
      ) : (
        <div style={{ padding: 18 }}>
          <div style={{ background: "#f3f4f0", borderRadius: 8, height: 170, display: "grid", placeItems: "center", margin: "0 0 12px" }}>
            <img src={A(CIRCUITS[res?.ckt || "led"].art)} style={{ width: 430, maxWidth: "100%" }} /></div>
          <div style={{ fontSize: 28 }}>{st === "danger" ? "Resistance is too low" : "Resistance is too high"}</div>
          <div className="px" style={{ fontSize: 13, margin: "18px 0 8px", display: "flex", justifyContent: "space-between", alignItems: "center" }}><span>CURRENT</span><div className={"lcd" + (st === "danger" ? " hot" : "")} data-ghost={ghost(fmtI(mA))}><b>{fmtI(mA)}</b><span className="u">mA</span></div></div>
          <div className="bar"><b style={{ width: Math.min(100, (mA ?? 0) * 2.5) + "%", background: st === "danger" ? "var(--red)" : "var(--yellow)" }} /><i className="lim" /></div>
          <div className="px" style={{ fontSize: 13, marginTop: 8 }}>LIMIT {LIMIT} mA{mA != null && mA > LIMIT ? ` · +${Math.round(mA - LIMIT)} OVER` : ""}</div>
          <p className="px" style={{ fontSize: 20, borderTop: "2px solid var(--ink)", paddingTop: 20, marginTop: 20 }}>FIX {fmt(o?.resistance)} Ω → {fixR} Ω</p>
        </div>
      )}
    </div>
  );

  const screens = {
    home: (
      <Page ask={false}>
        <h2 className="a px" style={{ left: 96, top: 170, fontSize: 18, margin: 0 }}>START</h2>
        <p className="a" style={{ left: 96, top: 256, fontSize: 24, margin: 0 }}>Choose your next step.</p>
        {[[ICON.cam, "CHECK MY CIRCUIT", "Check values and find problems.", "check"],
          [ICON.uno, "CONNECT UNO", "Control a real LED from here.", "uno_off"],
          [ICON.chat, "PLAN A PROJECT", "Get parts and a plan from AI.", "chat"]].map(([ic, t, d, to], i) => (
          <button key={t} className={"a choice click" + (sel === i ? " sel" : "")} style={{ left: 96 + i * 429, top: 304 }}
            onMouseEnter={() => setSel(i)} onFocus={() => setSel(i)} onClick={() => go(to)}>
            <div className="tile">{ic}</div>
            <h3>{t}</h3><p>{d}</p>
          </button>
        ))}
        <p className="a" style={{ left: 96, top: 690, fontSize: 20, color: "var(--mute)", margin: 0 }}>No circuit yet? Start with a plan.</p>
        <p className="a" style={{ left: 880, top: 690, width: 464, textAlign: "right", fontSize: 20, color: "var(--mute)", margin: 0 }}>Arrow keys to choose · Enter to start</p>
      </Page>
    ),
    chat: (
      <Page back="home" title="PLAN" ask={false} bar={<form className="a chat" onSubmit={(e) => { e.preventDefault(); if (draft.trim()) { setIdea(draft); setDraft(""); go("plan"); } }}>
          <input placeholder="Describe your idea…" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button className="click" type="submit">➤</button></form>}>
        <div className="a dlg" style={{ left: 78, top: 238, width: 562, height: 117 }}>
          <div><Type text="What do you want to build?" /></div></div>
        <p className="a label" style={{ left: 96, top: 379 }}>TRY ONE</p>
        <div className="a" style={{ left: 96, top: 411 }}>
          {["Make an LED blink", "Night light for the dark", "Ideas for a starter kit"].map((s) => (
            <button key={s} className="sug click" onClick={() => { setIdea(s); go("plan"); }}>{s}<span>›</span></button>))}
        </div>
        <div className="a px" style={{ left: 784, top: 256, width: 560, height: 560, display: "grid", placeItems: "center", fontSize: 13, color: "var(--mute)", border: "2px dashed var(--mute)", borderRadius: 12 }}>YOUR PLAN</div>
        
      </Page>
    ),
    plan: (
      <Page back="chat" title="PLAN" ask={false} bar={<form className="a chat" onSubmit={(e) => { e.preventDefault(); setDraft(""); }}>
          <input placeholder="Ask a follow-up…" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button className="click" type="submit">➤</button></form>}>
        <div className="a plan-conversation"><div className="msg-u">{idea || "A night light that turns on in the dark"}</div>
        <div className="dlg" style={{ height: 100, marginTop: 24 }}>
          <div style={{ padding: "14px 20px" }}><Type text="Here's your plan →" /></div></div></div>
        <div className="a card panel-scroll plan-card" tabIndex={0} aria-label="Project plan, scroll for parts and steps" style={{ left: 760, top: 256, width: 584, height: 544, padding: 24 }}>
          <p className="label">{"PROJECT " + (mat ? mat.title : "NIGHT LIGHT")}</p>
          <div className="row px" style={{ fontSize: 12, color: "var(--mute)", marginTop: 14 }}><span>PARTS</span><span>HAVE IT?</span></div>
          {(mat ? mat.parts : DEFAULT_PARTS).map((p, i) => (
            <div key={p} className="row"><span>{p}</span>
              <button className={"chk click" + (have[i] ? " on" : "")} aria-label={"Have " + p} onClick={() => setHave(have.map((h, j) => (j === i ? !h : h)))}>{have[i] ? "✓" : ""}</button></div>))}
          <p style={{ fontSize: 20, margin: "6px 0 14px", color: "var(--mute)" }}>{have.filter((h) => !h).length} {have.filter((h) => !h).length === 1 ? "part" : "parts"} to buy{mat && <> · <a href={`${import.meta.env.BASE_URL}materials/${mat.file}.txt`} download style={{ color: "inherit" }}>Download list (.txt)</a></>}</p>
          <p className="label" style={{ borderTop: "2px solid var(--ink)", paddingTop: 14 }}>PLAN</p>
          {(mat ? mat.steps : DEFAULT_STEPS).map((s, i) => (
            <div key={s} className="row" style={{ height: 48 }}><span style={{ display: "flex", gap: 14, alignItems: "center" }}><span className="num">{i + 1}</span>{s}</span>
              <button className="click" aria-label="Check this step" style={{ width: 48, height: 44, border: "2px solid var(--ink)", borderRadius: 8, background: "#fff" }} onClick={() => go("check")}>{ICON.camS}</button></div>))}
        </div>
        
      </Page>
    ),
    check: (
      <Page lamp="" back="home" title="CHECK" step={0} action="CHECK CIRCUIT" goDisabled={volErr || !(R > 0)} onGo={() => go("scanning")}>
        <div className="a card" style={{ left: 96, top: 256, width: 600, height: 520 }}>
                    <span className="a" style={{ left: 32, top: 30, fontSize: 28 }}>Circuit</span>
          <CircuitPick value={ckt} onChange={setCkt} style={{ left: 200, top: 20, width: 368 }} />
          {[["Power", "V", 96, <input aria-label="Volts" value={volts} onChange={(e) => setVolts(e.target.value)} inputMode="decimal" />, "Power is the battery or supply voltage. Try 5 V."],
            ["Resistor", "Ω", 224, <input aria-label="Ohms" value={ohms} onChange={(e) => setOhms(e.target.value)} inputMode="decimal" />, "A resistor limits current. Bigger value, less current."]].map(([n, u, top, inp, tx], i) => (
            <div key={n}>
              <span className="a" style={{ left: 32, top: top + 18, fontSize: 28, display: "flex", alignItems: "center", gap: 12 }}>{n}
                <button className="help click" style={{ position: "static" }} aria-label={"About " + n} onMouseEnter={() => setTip(n)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(n)} onBlur={() => setTip(null)}>?</button></span>
              <div className={"a in" + (i === 0 && volErr ? " err" : "")} style={{ left: 328, top }}>{inp}<span style={{ fontSize: 28 }}>{u}</span></div>
              {tip === n && <div className="tip" style={{ left: 120, top: top + 60 }}><p style={{ margin: 0, fontSize: 22 }}>{tx}</p></div>}
              <div className="a" style={{ left: 32, top: top + 100, width: 536, height: 2, background: "var(--ink)", opacity: .25 }} />
            </div>))}
          {volErr && <span className="a err-t" style={{ left: 328, top: 176 }}>Enter more than 0 V</span>}
          <span className="a" style={{ left: 32, top: 370, fontSize: 28, display: "flex", alignItems: "center", gap: 12 }}>LED
            <button className="help click" style={{ position: "static" }} aria-label="About LED" onMouseEnter={() => setTip("LED")} onMouseLeave={() => setTip(null)} onFocus={() => setTip("LED")} onBlur={() => setTip(null)}>?</button></span>
          <div className="a in" style={{ left: 328, top: 352, gap: 12 }}>
            {ckt === "rgb" ? <span style={{ fontSize: 20, whiteSpace: "nowrap" }}>R 2 · G 3 · B 3 V</span> : <>
            <select aria-label="LED color" style={{ fontSize: 26 }} value={led} onChange={(e) => setLed(e.target.value)}>{Object.keys(LEDS).map((c) => <option key={c}>{c}</option>)}</select>
            <span style={{ fontSize: 24, whiteSpace: "nowrap" }}>{Vf} V</span></>}</div>
          {tip === "LED" && <div className="tip" style={{ left: 72, top: 412 }}><p style={{ margin: 0, fontSize: 24 }}>{ckt === "rgb" ? "RGB LED." : "Pick a color."}</p><p style={{ margin: "8px 0 0", fontSize: 18, color: "var(--mute)" }}>{ckt === "rgb" ? "Red 2 V, green and blue 3 V. One resistor value is checked on each color." : "We set the voltage."}</p></div>}
                  </div>
        <div className="a card" style={{ left: 744, top: 256, width: 600, height: 520 }}>
          <p className="label a" style={{ left: 32, top: 32 }}>PREVIEW</p>
          {ckt !== "led" && <p className="a" style={{ left: 32, top: 74, fontSize: 20, margin: 0, color: "var(--mute)" }}>{ckt === "switch" ? "Checked with the switch closed." : "Same resistor value on each color."}</p>}
          <img className="a" src={A(CIRCUITS[ckt].art)} style={{ left: 32, top: 128, width: 536, height: 280, objectFit: "contain" }} />
          <div className="a circuit-values" style={{ left: 32, top: 440, width: 536 }}>
            <span>POWER <b>{volErr ? "—" : V} V</b></span>
            <span>RESISTOR <b>{R || "—"} Ω</b></span>
            <span>LED <b>{ckt === "rgb" ? "2·3·3 V" : Vf + " V"}</b></span>
          </div>
                  </div>
      </Page>
    ),
    scanning: (
      <Page lamp="work" title="CHECKING" back="check" step={1}>
        <div className="a" style={{ left: 427, top: 296, width: 587 }}>
          <div className="scan" style={{ height: 339 }}>
            {["Reading", "Simulating", "Checking"].map((t, i) => <div key={t}>{prog > i * 3 ? "●" : "○"} {t}</div>)}</div>
          <div className={"gauge progress-" + (scanDone ? "complete" : prog < 4 ? "reading" : prog < 7 ? "simulating" : "checking")} role="progressbar" aria-label="Circuit check progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={prog * 10} aria-valuetext={scanDone ? "Check complete" : prog >= 9 ? "Waiting for simulator" : "Checking circuit"} style={{ marginTop: 24 }}>{Array.from({ length: 10 }, (_, i) => <i key={i} className={i < prog ? "on" : ""} />)}</div>
        </div>
        <p className="a" style={{ left: 480, top: 713, width: 481, textAlign: "center", fontSize: 22, margin: 0 }}>{scanDone ? "Check complete" : prog >= 9 ? "Waiting for simulator…" : "Reading → simulating → checking"}</p>
        <button className="a btn sec click" style={{ left: 600, top: 769, width: 240, height: 60 }} onClick={() => go("check")}>CANCEL</button>
      </Page>
    ),
    found: (
      <Page lamp={st === "warning" ? "warn" : "issue"} title="FOUND" back="check" step={1} action="TEST FIX" onGo={() => go("result")}>
        <Dex />
        <div className="a flash" />
        <div className="a dlg" style={{ left: 784, top: 256, width: 560, height: 300 }}>
          <div><p className="label">WHY?</p>
            <p style={{ fontSize: 26, margin: "26px 0 14px" }}>{st === "danger" ? "Too much current." : "Too little current."}</p>
            <p style={{ fontSize: 22, margin: 0 }}>{st === "danger" ? "Bigger resistor → less current." : "Smaller resistor → brighter LED."}</p>
            {res?.ckt === "switch" && <p style={{ fontSize: 18, margin: "12px 0 0", color: "var(--mute)" }}>Checked with the switch closed.</p>}
            {res?.rgb && <p style={{ fontSize: 18, margin: "12px 0 0", color: "var(--mute)" }}>Each color is checked on its own.</p>}
<span className="caret">▼</span></div></div>
      </Page>
    ),
    result: (
      <Page lamp={(c || o)?.status === "safe" ? "ok" : "warn"} title="RESULT" back={c ? "found" : "check"} step={2} action="CHECK AGAIN" onGo={() => { if (c) setOhms(String(c.resistance)); go("check"); }}>
        <Dex ok />
        {c && <div className="a card next-action rise" style={{ left: 790, top: 256, width: 554, minHeight: 300, padding: 24 }}>
          <p className="label">NEXT · ON YOUR BOARD</p><h3 className="next-title">Try the fix</h3><p className="next-note">Power off before changing parts.</p>
          {(res?.rgb ? rgbSteps : ["Swap in a " + fixR + " Ω resistor", "Check again"]).map((t, i) => (
            <div key={t} style={{ display: "flex", gap: 18, alignItems: "center", fontSize: res?.rgb ? 22 : 28, marginTop: 24 }}><span className="num">{i + 1}</span>{t}</div>))}
        </div>}
      </Page>
    ),
    failed: (
      <Page lamp="issue" title="CHECK FAILED" back="check" step={1} action="RETRY" onGo={() => go("scanning")}>
        <h3 className="a px" style={{ left: 96, top: 256, fontSize: 26, margin: 0, lineHeight: 1.5, width: 900 }}>{err?.kind === "NETWORK" ? "Couldn't reach the simulator." : err?.kind === "INVALID" ? "Check your values." : "The check failed."}</h3>
        <p className="a" style={{ left: 96, top: 326, width: 720, fontSize: 26, margin: 0 }}>{err?.kind === "NETWORK" ? "Values saved. Is the server running?" : "Values saved. Try again."}</p>
        <button className="a btn sec click" style={{ left: 96, top: 446, width: 260, height: 60 }} onClick={() => go("check")}>EDIT VALUES</button>
      </Page>
    ),
    uno_off: <Uno on={false} />, uno_on: <Uno on />, no_uno: <NoUno />,
  };

  function Uno({ on }) {
    const press = async () => {
      if (busy) return;
      setBusy(true);
      try {
        if (ckt === "rgb") await setRgb(on ? { r: false, g: false, b: false } : rgbOn);
        else if (ckt === "switch" && !on) await followSwitch();
        else await sendLed(on ? "off" : "on");
        setUnoErr(""); go(on ? "uno_off" : "uno_on");
      } catch (e) { setUnoErr(e?.message || ""); go("no_uno"); }
      finally { setBusy(false); }
    };
    const toggle = (k) => {
      const next = { ...rgbOn, [k]: !rgbOn[k] };
      setRgbOn(next);
      if (on) setRgb(next).catch((e) => { setUnoErr(e?.message || ""); go("no_uno"); });
    };
    const lit = on && (ckt !== "switch" || sw === true);
    const any = rgbOn.r || rgbOn.g || rgbOn.b;
    const mix = on && any ? `rgb(${rgbOn.r ? 255 : 0},${rgbOn.g ? 255 : 0},${rgbOn.b ? 255 : 0})` : "#fff";
    const lbl = { stroke: "none", fill: "#26332C", fontSize: 13, fontFamily: "Press Start 2P" };
    const status = ckt === "switch" && on
      ? (sw == null ? "Waiting for the switch…" : sw ? "Switch closed · LED on" : "Switch open · LED off")
      : on ? "Uno replied OK" : "Uno ready";
    return (
      <Page lamp={lit || (on && ckt === "rgb" && any) ? "on" : ""} back="home" title="UNO" action={busy ? "SENDING…" : on ? "TURN OFF" : "TURN ON"} goDisabled={busy} onGo={press}>
        <svg className="a" style={{ left: 96, top: 256 }} width="620" height="380" viewBox="0 0 620 380" fill="none" stroke="#26332C" strokeWidth="3">
          <rect x="42" y="76" width="148" height="228" rx="8" fill="#fff" />
          <text x="68" y="196" stroke="none" fill="#26332C" fontSize="20" fontFamily="Press Start 2P">UNO</text>
          {ckt === "rgb" ? <>
            {[110, 150, 190].map((y, n) => <g key={y}>
              <path d={`M190 ${y}H250M320 ${y}H470`} /><rect x="250" y={y - 14} width="70" height="28" rx="6" fill="#F6D64B" />
              <text x="205" y={y - 20} {...lbl}>{`PIN ${9 + n}`}</text></g>)}
            <path d="M470 110V190M470 150H486M520 186V250H190" />
            {on && any && <circle cx="520" cy="150" r="58" fill={mix} opacity=".45" stroke="none" />}
            <circle cx="520" cy="150" r="34" fill={mix} />
            <text x="205" y="270" {...lbl}>GND</text><text x="500" y="156" {...lbl} fontSize="11">RGB</text>
          </> : <>
            <path d="M190 133H304M387 133H476M476 133V175M476 213H190" />
            <rect x="304" y="114" width="84" height="38" rx="6" fill="#F6D64B" />
            {lit && <circle cx="498" cy="194" r="60" fill="#F6D64B" opacity=".5" stroke="none" />}
            <path d="M476 175H520L498 213Z" fill={lit ? "#F6D64B" : "#fff"} />
            <g stroke="none" fill="#26332C" fontSize="13" fontFamily="Press Start 2P"><text x="205" y="118">PIN 8</text><text x="205" y="270">GND</text><text x="535" y="232">LED</text></g>
            <text x="308" y="185" stroke="none" fill="#26332C" fontSize="26" fontFamily="Pixelify Sans">220 Ω</text>
            {ckt === "switch" && <>
              <path d="M190 250H300M380 250H430V213" />
              <path d={sw ? "M300 250H380" : "M300 250L368 222"} strokeWidth="4" />
              <circle cx="300" cy="250" r="5" fill="#26332C" /><circle cx="380" cy="250" r="5" fill="#26332C" />
              <text x="205" y="238" {...lbl}>PIN 2</text></>}
          </>}
        </svg>
        <CircuitPick value={ckt} onChange={setCkt} disabled={on || busy} title={on ? "Turn it off to change circuit" : ""} style={{ left: 822, top: 256, width: 522 }} />
        <div className="a" style={{ left: 822, top: 336, width: 522 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <span className="lamp on" style={{ position: "static", background: lit || (on && ckt === "rgb" && any) ? "var(--yellow)" : "#fff", boxShadow: lit || (on && ckt === "rgb" && any) ? "0 0 10px var(--yellow)" : "none" }} />
            <span className="px" style={{ fontSize: 26 }}>{ckt === "rgb" ? "RGB" : "LED"} {(ckt === "rgb" ? on : lit) ? "ON" : "OFF"}</span></div>
          <p style={{ fontSize: 24, margin: "26px 0" }}>{status}</p>
          {ckt === "rgb" && <div style={{ display: "flex", gap: 14 }}>
            {RGB.map((ch) => <button key={ch.k} className={"chip click" + (rgbOn[ch.k] ? " on" : "")} aria-pressed={rgbOn[ch.k]} onClick={() => toggle(ch.k)}><i style={{ background: ch.color }} />{ch.name}</button>)}
          </div>}
          <button className="btn sec click" style={{ width: 522, height: 77, marginTop: ckt === "rgb" ? 40 : 110, fontSize: 18 }} onClick={() => go("uno_off")}>RECONNECT</button>
        </div>
      </Page>
    );
  }
  function NoUno() {
    return (
      <Page lamp="issue" back="home" title="NO UNO" action="RECONNECT" onGo={() => go("uno_off")}>
        <p className="a px" style={{ left: 96, top: 256, width: 640, fontSize: 22, lineHeight: 1.6, margin: 0 }}>Check the USB cable.</p>
        <p className="a" style={{ left: 96, top: 320, fontSize: 26, margin: 0 }}>Close Serial Monitor.</p>
        {unoErr && <p className="a" style={{ left: 96, top: 380, width: 760, fontSize: 20, margin: 0, color: "var(--mute)" }}>{unoErr}</p>}
      </Page>
    );
  }

  return (
    <Go.Provider value={go}>
      <Slots.Provider value={{ head, dock }}>
        <div className="app">
          <svg className="shell" width={w} height={h} viewBox={`0 0 ${w} ${h}`} fill="none" stroke="#26332C">
            <path d={shellOuter} fill="#F6D64B" strokeWidth="4" />
            <path d={`M26 90H${w - 26}V${h - 88}L${w - 75} ${h - 26}H28L26 90Z`} fill="#FBFAF1" stroke="none" />
            <path d={`M14 90H112L130 76H${w - 16}`} strokeWidth="2" />
            <path d={`M42 ${h - 56}H82M42 ${h - 48}H74M42 ${h - 40}H66`} strokeWidth="3" />
            <path d={`M${w - 52} ${h - 116}V${h - 80}L${w - 88} ${h - 44}`} strokeWidth="2" />
          </svg>
          <div className="scroller">
            <div className="canvas" style={{ width: 1388 * scale, height: 768 * scale + 24 }}>
              <div className="stage" style={{ transform: `scale(${scale}) translate(-26px,-112px)` }}>{screens[scr]}</div>
            </div>
          </div>
          <div className="layer" ref={setHead} />
          <div className="layer" ref={setDock} />
        </div>
      </Slots.Provider>
    </Go.Provider>
  );
}
