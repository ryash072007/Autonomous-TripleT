import { ReactNode, useEffect, useState } from "react";
import { DemoResp, EvidenceResp, WindowResp, api } from "./api";
import { TierBadge, Term, fmtClock, fmtMiss, fmtPc } from "./ui";

export function Next24({ win, clockLabel, onOpen }: { win: WindowResp | null; clockLabel: string; onOpen: (id: number) => void }) {
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
            <b>{win.n}</b> events in the window, <b className="crit-text">{win.n_dangerous}</b> dangerous.
          </p>
          <table className="tbl">
            <thead>
              <tr>
                <th>Remaining</th><th>Tier</th><th>Event</th><th>Miss</th><th>Pc</th><th></th>
              </tr>
            </thead>
            <tbody>
              {win.events.length === 0 && <tr><td colSpan={6} className="dim">Nothing enters the 24 h window at this clock time.</td></tr>}
              {win.events.map((e) => (
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

export function Evidence() {
  const [d, setD] = useState<EvidenceResp | null>(null);
  useEffect(() => { api.evidence().then(setD).catch(() => setD({ files: [] })); }, []);
  return (
    <div className="page">
      <h2>Evidence</h2>
      <p className="dim">Every number here is read from a JSON file under artifacts/evidence/ written by a script.</p>
      {!d && <div className="empty">Loading...</div>}
      {d && d.files.length === 0 && <div className="empty">No evidence files yet. They appear here once the evaluation scripts have run.</div>}
      {d?.files.map((f) => (
        <div className="card" key={f.file}>
          <h3>{f.name} <span className="mono dim small">{f.file}</span></h3>
          <Value v={f.content} />
        </div>
      ))}
    </div>
  );
}

const DEMO_TITLES: Record<string, string> = {
  clear_critical: "A clear Critical",
  caught_early: "Caught early",
  model_wrong: "Where the tool is least reliable",
};

export function DemoBar({ step, setStep, demo, onExit }: { step: number; setStep: (n: number) => void; demo: DemoResp | null; onExit: () => void }) {
  if (!demo) return null;
  const it = demo.items[step];
  if (!it) return null;
  return (
    <div className="demo-bar card" role="region" aria-label="Guided demo">
      <div className="mono small dim">
        Guided demo {step + 1} / {demo.items.length} {demo.provisional && <span className="flag">provisional picks</span>}
      </div>
      <b>{DEMO_TITLES[it.key] ?? it.key.replace(/_/g, " ")}</b>: event #{it.event_id}
      <div className="small">{it.reason}</div>
      <div className="demo-actions">
        <button className="link-btn" onClick={onExit}>Exit</button>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button>
        <button className="btn primary" onClick={() => (step + 1 < demo.items.length ? setStep(step + 1) : onExit())}>
          {step + 1 < demo.items.length ? "Next" : "Done"}
        </button>
      </div>
    </div>
  );
}

export { fmtClock };
