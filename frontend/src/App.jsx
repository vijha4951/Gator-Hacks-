import { createContext, useContext, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { analyzeCircuit, setLed as sendLed } from "./api";

const Go = createContext(() => {});
const Slots = createContext({ head: null, dock: null });

const A = (n) => `/assets/${n}.svg`;
const LEDS = { Red: 2, Green: 2.2, Blue: 3, White: 3 };
const LIMIT = 20;
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
  const [prog, setProg] = useState(0);
  const [scanDone, setScanDone] = useState(false);
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
    analyzeCircuit({ voltage: V, resistance: R, led_forward_voltage: Vf })
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

  const Dex = ({ ok }) => (
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
            <img src={A("circuit")} style={{ width: 430, maxWidth: "100%" }} /></div>
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
          <p className="label">PROJECT NIGHT LIGHT</p>
          <div className="row px" style={{ fontSize: 12, color: "var(--mute)", marginTop: 14 }}><span>PARTS</span><span>HAVE IT?</span></div>
          {["Arduino Uno", "Light sensor (LDR)", "LED", "Resistors 220 Ω, 10 kΩ", "Breadboard + wires"].map((p, i) => (
            <div key={p} className="row"><span>{p}</span>
              <button className={"chk click" + (have[i] ? " on" : "")} aria-label={"Have " + p} onClick={() => setHave(have.map((h, j) => (j === i ? !h : h)))}>{have[i] ? "✓" : ""}</button></div>))}
          <p style={{ fontSize: 20, margin: "6px 0 14px", color: "var(--mute)" }}>{have.filter((h) => !h).length} part to buy</p>
          <p className="label" style={{ borderTop: "2px solid var(--ink)", paddingTop: 14 }}>PLAN</p>
          {["Light up the LED", "Read the light sensor", "Make the LED react"].map((s, i) => (
            <div key={s} className="row" style={{ height: 48 }}><span style={{ display: "flex", gap: 14, alignItems: "center" }}><span className="num">{i + 1}</span>{s}</span>
              <button className="click" aria-label="Check this step" style={{ width: 48, height: 44, border: "2px solid var(--ink)", borderRadius: 8, background: "#fff" }} onClick={() => go("check")}>{ICON.camS}</button></div>))}
        </div>
        
      </Page>
    ),
    check: (
      <Page lamp="" back="home" title="CHECK" step={0} action="CHECK CIRCUIT" goDisabled={volErr || !(R > 0)} onGo={() => go("scanning")}>
        <div className="a card" style={{ left: 96, top: 256, width: 600, height: 520 }}>
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
            <select aria-label="LED color" style={{ fontSize: 26 }} value={led} onChange={(e) => setLed(e.target.value)}>{Object.keys(LEDS).map((c) => <option key={c}>{c}</option>)}</select>
            <span style={{ fontSize: 24, whiteSpace: "nowrap" }}>{Vf} V</span></div>
          {tip === "LED" && <div className="tip" style={{ left: 72, top: 412 }}><p style={{ margin: 0, fontSize: 24 }}>Pick a color.</p><p style={{ margin: "8px 0 0", fontSize: 18, color: "var(--mute)" }}>We set the voltage.</p></div>}
                  </div>
        <div className="a card" style={{ left: 744, top: 256, width: 600, height: 520 }}>
          <p className="label a" style={{ left: 32, top: 32 }}>PREVIEW</p>
          <img className="a" src={A("circuit")} style={{ left: 32, top: 128, width: 536, height: 280, objectFit: "contain" }} />
          <div className="a circuit-values" style={{ left: 32, top: 440, width: 536 }}>
            <span>POWER <b>{volErr ? "—" : V} V</b></span>
            <span>RESISTOR <b>{R || "—"} Ω</b></span>
            <span>LED <b>{Vf} V</b></span>
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
<span className="caret">▼</span></div></div>
      </Page>
    ),
    result: (
      <Page lamp={(c || o)?.status === "safe" ? "ok" : "warn"} title="RESULT" back={c ? "found" : "check"} step={2} action="CHECK AGAIN" onGo={() => { if (c) setOhms(String(c.resistance)); go("check"); }}>
        <Dex ok />
        {c && <div className="a card next-action rise" style={{ left: 790, top: 256, width: 554, minHeight: 300, padding: 24 }}>
          <p className="label">NEXT · ON YOUR BOARD</p><h3 className="next-title">Try the fix</h3><p className="next-note">Power off before changing parts.</p>
          {["Swap in a " + fixR + " Ω resistor", "Check again"].map((t, i) => (
            <div key={t} style={{ display: "flex", gap: 18, alignItems: "center", fontSize: 28, marginTop: 24 }}><span className="num">{i + 1}</span>{t}</div>))}
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
      try { await sendLed(on ? "off" : "on"); go(on ? "uno_off" : "uno_on"); }
      catch { go("no_uno"); }
      finally { setBusy(false); }
    };
    return (
      <Page lamp={on ? "on" : ""} back="home" title="UNO" action={busy ? "SENDING…" : on ? "TURN OFF" : "TURN ON"} goDisabled={busy} onGo={press}>
        <svg className="a" style={{ left: 96, top: 256 }} width="620" height="380" viewBox="0 0 620 380" fill="none" stroke="#26332C" strokeWidth="3">
          <rect x="42" y="76" width="148" height="228" rx="8" fill="#fff" />
          <text x="68" y="196" stroke="none" fill="#26332C" fontSize="20" fontFamily="Press Start 2P">UNO</text>
          <path d="M190 133H304M387 133H476M476 133V175M476 213H190" />
          <rect x="304" y="114" width="84" height="38" rx="6" fill="#F6D64B" />
          {on && <circle cx="498" cy="194" r="60" fill="#F6D64B" opacity=".5" stroke="none" />}
          <path d="M476 175H520L498 213Z" fill={on ? "#F6D64B" : "#fff"} />
          <g stroke="none" fill="#26332C" fontSize="13" fontFamily="Press Start 2P"><text x="205" y="118">PIN 8</text><text x="205" y="270">GND</text><text x="535" y="232">LED</text></g>
          <text x="308" y="185" stroke="none" fill="#26332C" fontSize="26" fontFamily="Pixelify Sans">220 Ω</text>
        </svg>
        <div className="a" style={{ left: 822, top: 256, width: 522 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <span className="lamp on" style={{ position: "static", background: on ? "var(--yellow)" : "#fff", boxShadow: on ? "0 0 10px var(--yellow)" : "none" }} />
            <span className="px" style={{ fontSize: 26 }}>LED {on ? "ON" : "OFF"}</span></div>
          <p style={{ fontSize: 24, margin: "26px 0" }}>{on ? "Uno replied OK" : "Uno ready"}</p>
          <button className="btn sec click" style={{ width: 522, height: 77, marginTop: 190, fontSize: 18 }} onClick={() => go("uno_off")}>RECONNECT</button>
        </div>
      </Page>
    );
  }
  function NoUno() {
    return (
      <Page lamp="issue" back="home" title="NO UNO" action="RECONNECT" onGo={() => go("uno_off")}>
        <p className="a px" style={{ left: 96, top: 256, width: 640, fontSize: 22, lineHeight: 1.6, margin: 0 }}>Check the USB cable.</p>
        <p className="a" style={{ left: 96, top: 320, fontSize: 26, margin: 0 }}>Close Serial Monitor.</p>
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
