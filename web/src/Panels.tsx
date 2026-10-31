import { ReactNode, useState } from "react";
import { DemoResp, EvidenceResp, WindowResp } from "./api";
import { TierBadge, Term, fmtClock, fmtMiss, fmtPc } from "./ui";

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
  worst_consequence: "Low Pc, but if they collide...",
};
const DEMO_LOOK: Record<string, string> = {
  clear_critical: "Look at: the headline and the decision row under it. Your decision is logged with a tamper-evident hash, and the tool never acts on its own.",
  caught_early: "Look at: HOW SURE, the forecast bar. The latest update alone would not have raised this.",
  model_wrong: "Look at: HOW SURE, the plain-language flags and the Not sure line.",
  worst_consequence: "Look at: IF THEY COLLIDE. The debris simulation plays by itself.",
};
export type Hl = "rule" | "forecast" | "flags" | "collide" | null;
export const demoHighlight = (key?: string): Hl =>
  key === "clear_critical" ? "rule" : key === "caught_early" ? "forecast" : key === "model_wrong" ? "flags" : key === "worst_consequence" ? "collide" : null;

export function DemoBar({ step, setStep, demo, onExit, onFailures }: {
  step: number; setStep: (n: number) => void; demo: DemoResp | null; onExit: () => void; onFailures: () => void;
}) {
  if (!demo) return null;
  const it = demo.items[step];
  if (!it) return null;
  const last = step + 1 >= demo.items.length;
  return (
    <div className="demo-bar card" role="region" aria-label="Guided tour">
      <div className="tour-progress" aria-hidden="true"><i style={{ width: `${((step + 1) / demo.items.length) * 100}%` }} /></div>
      <div className="label">Guided tour · step {step + 1} of {demo.items.length} {demo.provisional && <span className="flag">provisional picks</span>}</div>
      <div className="display demo-title">{DEMO_TITLES[it.key] ?? it.key.replace(/_/g, " ")}</div>
      <div className="small">Event #{it.event_id}</div>
      <div className="small demo-reason">{it.reason}</div>
      <div className="small dim">{DEMO_LOOK[it.key]}</div>
      {it.key === "model_wrong" && (
        <div className="small">
          <b>This is the pattern the model fails on</b>: very large uncertainty or very few updates.{" "}
          <button className="link-btn" onClick={onFailures}>See Results: where it fails</button>
        </div>
      )}
      <div className="demo-actions">
        <button className="link-btn" onClick={onExit}>Skip tour</button>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button className="btn primary" onClick={() => (last ? onExit() : setStep(step + 1))}>{last ? "Done" : "Next"}</button>
      </div>
    </div>
  );
}

export { fmtClock };
