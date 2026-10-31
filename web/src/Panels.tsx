import { ReactNode, useLayoutEffect, useRef, useState } from "react";
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

type Pos = { left: number; top: number; side: "right" | "left" | "below" | "above"; arrow: number } | null;

/** Place the callout beside the highlighted panel, on the side with room, and keep it there while the page scrolls. */
function useAnchor(step: number, active: boolean, ref: React.RefObject<HTMLDivElement>): Pos {
  const [pos, setPos] = useState<Pos>(null);
  useLayoutEffect(() => {
    if (!active || window.matchMedia("(max-width: 860px)").matches) { setPos(null); return; }
    let raf = 0, stop = false;
    const W = 340, GAP = 16;
    const place = () => {
      const t = document.querySelector(".detail .hl") as HTMLElement | null;
      const h = ref.current?.offsetHeight ?? 260;
      if (!t) { setPos(null); return; }
      const r = t.getBoundingClientRect();
      const vw = window.innerWidth, vh = window.innerHeight;
      let p: Pos;
      const cy = Math.min(Math.max(r.top + 24, 12), vh - h - 12);
      if (vw - r.right >= W + GAP + 8) p = { left: r.right + GAP, top: cy, side: "right", arrow: Math.min(Math.max(r.top + 40 - cy, 16), h - 24) };
      else if (r.left >= W + GAP + 8) p = { left: r.left - W - GAP, top: cy, side: "left", arrow: Math.min(Math.max(r.top + 40 - cy, 16), h - 24) };
      else if (vh - r.bottom >= h + GAP + 8) p = { left: Math.min(Math.max(r.left + 24, 12), vw - W - 12), top: r.bottom + GAP, side: "below", arrow: 28 };
      else p = { left: Math.min(Math.max(r.left + 24, 12), vw - W - 12), top: Math.max(12, r.top - h - GAP), side: "above", arrow: 28 };
      setPos((o) => (o && o.left === p!.left && o.top === p!.top && o.side === p!.side ? o : p));
    };
    const t0 = performance.now();
    const loop = () => { place(); if (!stop && performance.now() - t0 < 900) raf = requestAnimationFrame(loop); };
    loop();
    const on = () => place();
    window.addEventListener("scroll", on, { passive: true });
    window.addEventListener("resize", on);
    return () => { stop = true; cancelAnimationFrame(raf); window.removeEventListener("scroll", on); window.removeEventListener("resize", on); };
  }, [step, active, ref]);
  return pos;
}

export function DemoBar({ step, setStep, demo, onExit, onFailures, hidden, setHidden }: {
  step: number; setStep: (n: number) => void; demo: DemoResp | null; onExit: () => void; onFailures: () => void;
  hidden: boolean; setHidden: (h: boolean) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const pos = useAnchor(step, !!demo && !hidden && !collapsed, ref);
  if (!demo) return null;
  const it = demo.items[step];
  if (!it) return null;
  const n = demo.items.length;
  const last = step + 1 >= n;
  const title = DEMO_TITLES[it.key] ?? it.key.replace(/_/g, " ");
  if (hidden)
    return <button className="tour-chip" onClick={() => setHidden(false)} aria-label="Resume the tour">Tour {step + 1}/{n}</button>;
  if (collapsed)
    return (
      <div className="demo-bar card collapsed" role="region" aria-label="Guided tour">
        <button className="demo-slim" onClick={() => setCollapsed(false)}>Step {step + 1}/{n} · {title} ▸</button>
        <button className="link-btn" onClick={() => setHidden(true)}>Hide</button>
      </div>
    );
  return (
    <div ref={ref} className={"demo-bar card callout" + (pos ? " anchored side-" + pos.side : "")} role="region" aria-label="Guided tour"
      style={pos ? { left: pos.left, top: pos.top, bottom: "auto", ["--arrow" as string]: pos.arrow + "px" } : undefined}>
      <div className="tour-progress" aria-hidden="true"><i style={{ width: `${((step + 1) / n) * 100}%` }} /></div>
      <div className="demo-head">
        <div className="label">Step {step + 1} of {n} {demo.provisional && <span className="flag">provisional</span>}</div>
        <span className="demo-ctl">
          <button className="link-btn mobile-only" onClick={() => setCollapsed(true)} aria-label="Collapse the tour card">Collapse ▾</button>
          <button className="link-btn" onClick={() => setHidden(true)}>Hide</button>
        </span>
      </div>
      <div className="display demo-title">{title}</div>
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
        <button className="link-btn" onClick={onExit}>Skip tour (Esc)</button>
        <span style={{ flex: 1 }} />
        <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)} aria-label="Previous step">←</button>
        <button className="btn primary" onClick={() => (last ? onExit() : setStep(step + 1))}>{last ? "Done" : "Next →"}</button>
      </div>
    </div>
  );
}

export { fmtClock };
