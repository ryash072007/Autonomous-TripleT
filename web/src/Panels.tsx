import { ReactNode, useState } from "react";
import { DemoResp, EvidenceResp, WindowResp } from "./api";
import { TierBadge, Term, fmtClock, fmtMiss, fmtPc } from "./ui";

export function Next24({ win, clockLabel, onOpen }: { win: WindowResp | null; clockLabel: string; onOpen: (id: number) => void }) {
  const [onlyDanger, setOnlyDanger] = useState(true);
  const rows = win ? win.events.filter((e) => !onlyDanger || e.dangerous) : [];
  return (
    <div className="page">
      <h2>Next 24 h</h2>
      <p className="dim">
        Events whose <Term k="TCA" /> falls within 24 h of the replay clock ({clockLabel}). Dangerous means Critical or inside
        1 km. Press play in the top bar to advance the clock.
      </p>
      {!win && <div className="empty">Loading...</div>}
      {win && (
        <>
          <p>
            <b>{win.n}</b> events in the window, <b className="crit-text">{win.n_dangerous}</b> dangerous.{" "}
            <label><input type="checkbox" checked={onlyDanger} onChange={(e) => setOnlyDanger(e.target.checked)} /> Dangerous only</label>
          </p>
          <table className="tbl">
            <thead>
              <tr>
                <th>Remaining</th><th>Tier</th><th>Event</th><th>Miss</th><th>Pc</th><th></th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={6} className="dim">Nothing enters the 24 h window at this clock time.</td></tr>}
              {rows.map((e) => (
                <tr key={e.event_id} className={e.dangerous ? "danger" : ""} onClick={() => onOpen(e.event_id)}>
                  <td className="mono">{((e.remaining_days ?? 0) * 24).toFixed(1)} h</td>
                  <td><TierBadge tier={e.tier} /></td>
                  <td className="mono">#{e.event_id}</td>
                  <td className="mono">{fmtMiss(e.latest.miss_distance)}</td>
                  <td className="mono">{fmtPc(e.latest.max_risk_estimate)}</td>
                  <td>{e.dangerous && <span className="flag danger-flag">dangerous</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

function Value({ v, depth = 0 }: { v: unknown; depth?: number }): ReactNode {
  if (v == null) return <span className="dim">null</span>;
  if (typeof v === "number") return <span className="mono">{Number.isInteger(v) ? v : +v.toPrecision(4)}</span>;
  if (typeof v !== "object") return <span>{String(v)}</span>;
  if (Array.isArray(v)) {
    if (v.length && v.every((x) => x !== null && typeof x === "object" && !Array.isArray(x))) {
      const cols = Array.from(new Set(v.flatMap((x) => Object.keys(x as object))));
      return (
        <table className="tbl inner">
          <thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {v.slice(0, 50).map((r, i) => (
              <tr key={i}>{cols.map((c) => <td key={c}><Value v={(r as Record<string, unknown>)[c]} depth={depth + 1} /></td>)}</tr>
            ))}
          </tbody>
        </table>
      );
    }
    return <span className="mono">[{v.map((x) => (typeof x === "number" ? +x.toPrecision(4) : JSON.stringify(x))).join(", ")}]</span>;
  }
  return (
    <table className="tbl inner">
      <tbody>
        {Object.entries(v as object).map(([k, x]) => (
          <tr key={k}><th>{k}</th><td><Value v={x} depth={depth + 1} /></td></tr>
        ))}
      </tbody>
    </table>
  );
}

export function RawFiles({ d }: { d: EvidenceResp }) {
  return (
    <>
      {d.files.length === 0 && <div className="empty">No evidence files yet.</div>}
      {d.files.map((f) => (
        <div className="card" key={f.file}>
          <h3>{f.name} <span className="mono dim small">{f.file}</span></h3>
          <Value v={f.content} />
        </div>
      ))}
    </>
  );
}

const DEMO_TITLES: Record<string, string> = {
  clear_critical: "A clear Critical",
  caught_early: "Caught early",
  model_wrong: "Where the tool is least reliable",
};
const DEMO_LOOK: Record<string, string> = {
  clear_critical: "Look at: the rule that fired, highlighted in the header.",
  caught_early: "Look at: the forecast bars. The latest CDM alone would not have raised this.",
  model_wrong: "Look at: the flags and the Analyst decides badge.",
};
export const demoHighlight = (key?: string): "rule" | "forecast" | "flags" | null =>
  key === "clear_critical" ? "rule" : key === "caught_early" ? "forecast" : key === "model_wrong" ? "flags" : null;

export function DemoBar({ step, setStep, demo, onExit, onFailures }: {
  step: number; setStep: (n: number) => void; demo: DemoResp | null; onExit: () => void; onFailures: () => void;
}) {
  if (!demo) return null;
  const it = demo.items[step];
  if (!it) return null;
  const last = step + 1 >= demo.items.length;
  return (
    <div className="demo-bar card" role="region" aria-label="Guided demo">
      <div className="mono small dim">
        Step {step + 1}/{demo.items.length} {demo.provisional && <span className="flag">provisional picks</span>}
      </div>
      <b>{DEMO_TITLES[it.key] ?? it.key.replace(/_/g, " ")}</b>: event #{it.event_id}
      <div className="small demo-reason">{it.reason}</div>
      <div className="small dim">{DEMO_LOOK[it.key]}</div>
      {it.key === "model_wrong" && (
        <div className="small">
          <b>This is the pattern the model fails on</b>: very large uncertainty or very few CDMs.{" "}
          <button className="link-btn" onClick={onFailures}>See Results: where it fails</button>
        </div>
      )}
      <div className="demo-actions">
        <button className="link-btn" onClick={onExit}>Exit</button>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button className="btn primary" onClick={() => (last ? onExit() : setStep(step + 1))}>{last ? "Done" : "Next"}</button>
      </div>
    </div>
  );
}

export { fmtClock };
