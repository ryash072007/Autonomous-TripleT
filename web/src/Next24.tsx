import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { EventLight, Summary } from "./api";
import { conseq, harmLevel } from "./Consequence";
import { TIER_NAMES, TIER_VAR, Term, TierBadge, fmtMiss, fmtPc } from "./ui";

const SPEEDS = [0.02, 0.05, 0.1, 0.25];
// Same rule as /api/window: dangerous means Critical or inside 1 km. The window is 0 to 1 day left to TCA.
const dangerous = (e: EventLight) => e.tier === 2 || e.latest.miss_distance < 1000;
const prefersReduced = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function hash(n: number) {
  let x = (n + 1) * 2654435761;
  x ^= x >>> 15; x = Math.imul(x, 2246822519); x ^= x >>> 13;
  return ((x >>> 0) % 100000) / 100000;
}

function shape(tier: number, r: number): string {
  if (tier === 0) return `M${-r},0 a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0`;
  if (tier === 1) return `M0,${-r * 1.15} L${r * 1.05},${r * 0.85} L${-r * 1.05},${r * 0.85} Z`;
  const a = r * 0.42, b = r;
  return `M${-a},${-b} L${a},${-b} L${b},${-a} L${b},${a} L${a},${b} L${-a},${b} L${-b},${a} L${-b},${-a} Z`;
}

const W = 1000, H = 150, X0 = 34, X1 = 976;
const xOf = (h: number) => X0 + (h / 24) * (X1 - X0);

export default function Next24({ events, summary, onOpen }: { events: EventLight[]; summary: Summary | null; onOpen: (id: number) => void }) {
  const reduced = useMemo(prefersReduced, []);
  const dEv = useMemo(() => events.filter(dangerous), [events]);
  const [showAll, setShowAll] = useState(false);
  const pool = showAll ? events : dEv;
  const min = summary ? Math.max(0, summary.min_time_to_tca - 1) : 0;
  const max = summary?.max_time_to_tca ?? 0;

  const [elapsed, setElapsed] = useState(min);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(0.05); // days of replay per real second
  const elRef = useRef(min);
  useEffect(() => {
    const m = /rt=([\d.]+)/.exec(window.location.hash); // screenshot helper: start the replay part-way
    const t0 = min + (m ? +m[1] : 0);
    elRef.current = t0;
    setElapsed(t0);
  }, [min]);

  useEffect(() => {
    if (!playing || !max) return;
    const advance = (dd: number) => {
      let n = elRef.current + dd;
      if (n > max) n = min;
      elRef.current = n;
      setElapsed(n);
    };
    if (reduced) {
      const id = setInterval(() => advance(speed), 1000);
      return () => clearInterval(id);
    }
    let last = performance.now(), raf = 0;
    const loop = (t: number) => {
      advance(((t - last) / 1000) * speed);
      last = t;
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, max, min, reduced]);

  // hours left to TCA for every pooled event at the current replay time
  const inWin = pool
    .map((e) => ({ e, h: (e.latest.time_to_tca - elapsed) * 24 }))
    .filter((x) => x.h >= -1 && x.h <= 24);
  const nDanger = dEv.reduce((n, e) => { const h = (e.latest.time_to_tca - elapsed) * 24; return h >= 0 && h <= 24 ? n + 1 : n; }, 0);

  const series = useMemo(() => {
    const pts: [number, number][] = [];
    for (let t = min; t <= max; t += 0.02) pts.push([t, dEv.reduce((n, e) => { const r = e.latest.time_to_tca - t; return r >= 0 && r <= 1 ? n + 1 : n; }, 0)]);
    return pts;
  }, [dEv, min, max]);

  // the table refreshes a little slower than the timeline, with FLIP reordering
  const [tableEl, setTableEl] = useState(min);
  useEffect(() => {
    const id = setInterval(() => setTableEl(elRef.current), reduced ? 1000 : 450);
    return () => clearInterval(id);
  }, [reduced]);
  useEffect(() => { if (!playing) setTableEl(elapsed); }, [elapsed, playing]);

  const rows = useMemo(
    () => pool.map((e) => ({ e, h: (e.latest.time_to_tca - tableEl) * 24 })).filter((x) => x.h >= 0 && x.h <= 24).sort((a, b) => a.h - b.h).slice(0, 24),
    [pool, tableEl],
  );
  const refs = useRef(new Map<number, HTMLTableRowElement>());
  const prevTops = useRef(new Map<number, number>());
  const prevRows = useRef<typeof rows>([]);
  const [ghosts, setGhosts] = useState<typeof rows>([]);

  useLayoutEffect(() => {
    const seenNow = new Set(rows.map((r) => r.e.event_id));
    const gone = prevRows.current.filter((r) => !seenNow.has(r.e.event_id));
    if (gone.length && !reduced) {
      setGhosts((g) => [...g, ...gone].slice(-6));
      window.setTimeout(() => setGhosts((g) => g.filter((x) => !gone.includes(x))), 650);
    }
    const tops = new Map<number, number>();
    refs.current.forEach((el, id) => {
      if (!seenNow.has(id)) return;
      const top = el.getBoundingClientRect().top;
      tops.set(id, top);
      const prev = prevTops.current.get(id);
      if (reduced) return;
      if (prev == null) {
        if (prevTops.current.size) { el.classList.add("flash"); window.setTimeout(() => el.classList.remove("flash"), 1300); }
      } else if (Math.abs(prev - top) > 1) {
        el.style.transition = "none";
        el.style.transform = `translateY(${prev - top}px)`;
        void el.offsetHeight;
        el.style.transition = "transform 0.45s ease";
        el.style.transform = "";
      }
    });
    prevTops.current = tops;
    prevRows.current = rows;
  }, [rows, reduced]);

  const n = events.length || 1;
  const radius = (e: EventLight) => {
    const c = conseq(e);
    return c?.harmRank != null ? 3.5 + 6 * Math.pow(1 - (c.harmRank - 1) / n, 3) : 4.5;
  };
  const sMax = Math.max(1, ...series.map((s) => s[1]));
  const sx = (t: number) => 4 + ((t - min) / Math.max(1e-6, max - min)) * 232;
  const sy = (v: number) => 44 - (v / sMax) * 38;

  return (
    <div className="page next24">
      <div className="label">Collision triage</div>
      <h2 className="display page-h">NEXT 24 HOURS</h2>

      <div className="card n24-head">
        <div className="n24-count">
          <span key={nDanger} className="display n24-num tick">{nDanger}</span>
          <span className="n24-text"><b>dangerous</b> in the next 24 h<br /><span className="small dim">Critical, or closer than 1 km, at the replay time</span></span>
        </div>
        <svg className="spark" viewBox="0 0 240 50" role="img" aria-label="Dangerous count over the replay">
          <polyline fill="none" stroke="var(--critical)" strokeWidth="1.6" points={series.map(([t, v]) => `${sx(t).toFixed(1)},${sy(v).toFixed(1)}`).join(" ")} />
          <line x1={sx(elapsed)} x2={sx(elapsed)} y1="2" y2="46" stroke="var(--rock)" strokeWidth="1" strokeDasharray="2 2" />
          <circle cx={sx(elapsed)} cy={sy(nDanger)} r="3.2" fill="var(--rock)" />
        </svg>
        <div className="n24-ctl">
          <button className="icon-btn" onClick={() => setPlaying((p) => !p)} aria-label={playing ? "Pause replay" : "Play replay"}>{playing ? "❚❚" : "▶"}</button>
          <input type="range" min={min} max={max} step={0.005} value={Math.min(Math.max(elapsed, min), max)}
            onChange={(e) => { elRef.current = +e.target.value; setElapsed(+e.target.value); }} aria-label="Replay clock" />
          <span className="num small">replay hour {Math.max(0, (elapsed - min) * 24).toFixed(0)}</span>
          <select value={speed} onChange={(e) => setSpeed(+e.target.value)} aria-label="Replay speed">
            {SPEEDS.map((v) => <option key={v} value={v}>{(v * 24).toFixed(1)} h/s</option>)}
          </select>
          <label className="small"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} /> include other events</label>
        </div>
      </div>

      <div className="card n24-strip">
        <div className="label">Hours to <Term k="TCA">closest approach</Term></div>
        <svg viewBox={`0 0 ${W} ${H}`} className="strip" role="img" aria-label="24 hour timeline">
          {[0, 6, 12, 18, 24].map((h) => (
            <g key={h}>
              <line x1={xOf(h)} x2={xOf(h)} y1="14" y2={H - 26} stroke="var(--ridge-far)" strokeWidth={h === 0 ? 2 : 1} strokeDasharray={h === 0 ? "" : "3 4"} />
              <text x={xOf(h)} y={H - 8} textAnchor="middle" fontSize="12" fill="var(--ink-soft)">{h === 0 ? "0 h" : `${h} h`}</text>
            </g>
          ))}
          <text x={xOf(0) + 6} y="12" fontSize="10.5" fill="var(--ink-soft)">passed ✓</text>
          {inWin.map(({ e, h }) => {
            const r = radius(e);
            const entering = h > 22.5;
            const o = h < 0 ? Math.max(0, 1 + h) : entering ? Math.max(0.15, (24 - h) / 1.5) : 1;
            const y = 26 + Math.floor(hash(e.event_id) * 6) * 19;
            const dg = dangerous(e);
            return (
              <g key={e.event_id} transform={`translate(${xOf(Math.max(h, -0.6)).toFixed(1)} ${y})`} opacity={o} style={{ cursor: "pointer" }} onClick={() => onOpen(e.event_id)}>
                <title>{`#${e.event_id} · ${TIER_NAMES[e.tier]} · ${h.toFixed(1)} h to go · miss ${fmtMiss(e.latest.miss_distance)}`}</title>
                {dg && <circle r={r + 3.5} fill="none" stroke={TIER_VAR[e.tier]} strokeOpacity="0.38" strokeWidth="2" />}
                {entering && !reduced && <circle r={r + 8} fill="none" stroke="#fff" strokeWidth="2.5" strokeOpacity={0.9 * (h - 22.5) / 1.5} />}
                <path d={shape(e.tier, r)} fill={TIER_VAR[e.tier]} stroke="#fff" strokeWidth="1.2" />
                {h < 0 && <path d="M-4,0 l3,3 l6,-6" stroke="#fff" strokeWidth="2" fill="none" />}
              </g>
            );
          })}
        </svg>
        <div className="small dim">Marker size grows with the debris a collision would release. Halo: dangerous. Circle: Safe, triangle: Elevated, octagon: Critical. Click a marker to open the event.</div>
      </div>

      <div className="card">
        <table className="tbl n24-tbl">
          <thead><tr><th>To go</th><th>Tier</th><th>Event</th><th>Miss</th><th>Pc</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={6} className="dim">Nothing is inside the 24 h window at this replay time.</td></tr>}
            {ghosts.map((g) => (
              <tr key={"g" + g.e.event_id} className="row-out">
                <td className="num">0.0 h</td><td><TierBadge tier={g.e.tier} /></td><td>#{g.e.event_id}</td><td>{fmtMiss(g.e.latest.miss_distance)}</td><td>{fmtPc(g.e.latest.max_risk_estimate)}</td><td>passed</td>
              </tr>
            ))}
            {rows.map(({ e, h }) => (
              <tr key={e.event_id} ref={(el) => { if (el) refs.current.set(e.event_id, el); else refs.current.delete(e.event_id); }}
                className={dangerous(e) ? "danger" : ""} onClick={() => onOpen(e.event_id)}>
                <td className="num">{h.toFixed(1)} h</td>
                <td><TierBadge tier={e.tier} /></td>
                <td>#{e.event_id}{e.names ? <span className="names"> {e.names.t} × {e.names.c}</span> : null}</td>
                <td className="num">{fmtMiss(e.latest.miss_distance)}</td>
                <td className="num">{fmtPc(e.latest.max_risk_estimate)}</td>
                <td>{harmLevel(e, n) && <span className="harm-badge">debris risk: high</span>} {dangerous(e) && <span className="flag danger-flag">dangerous</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="small dim">Showing the {rows.length} soonest events in the window. The replay is a demonstration of how events approach closest approach; it is not live tracking.</div>
      </div>
    </div>
  );
}
