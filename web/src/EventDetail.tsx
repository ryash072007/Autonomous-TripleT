import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AuditRec, Cdm, Dataset, EventFull, ScoreResp, api } from "./api";
import {
  AbstainBadge, TIER_NAMES, TIER_VAR, Term, TierBadge, fmtMiss, fmtPc, fmtTtca,
} from "./ui";

const BAND = { crit: "#B0302A", elev: "#C77A12", safe: "#2F7A68" };

function Timeline({ ev }: { ev: EventFull }) {
  const cdms = ev.cdms;
  const maxT = Math.max(...cdms.map((c) => c.time_to_tca), 2.5);
  const risks = cdms.flatMap((c) => [c.max_risk_estimate, c.risk ?? c.max_risk_estimate]);
  const rLo = Math.max(-12, Math.min(...risks, -7)) - 0.5;
  const rHi = Math.max(...risks, -3.5) + 0.5;
  const misses = cdms.map((c) => c.miss_distance);
  const mLo = Math.max(10, Math.min(...misses, 800) * 0.6);
  const mHi = Math.max(...misses, 6000) * 1.3;
  const common = {
    type: "number" as const, dataKey: "time_to_tca", reversed: true, domain: [0, maxT] as [number, number],
    tickFormatter: (v: number) => `-${v.toFixed(0)}d`, stroke: "var(--ink-soft)", fontSize: 11,
  };
  return (
    <div className="chart-pair">
      <div>
        <h4>
          Risk (log10 <Term k="Pc" />) by <Term k="TCA" /> countdown
        </h4>
        <ResponsiveContainer width="100%" height={190}>
          <LineChart data={cdms} margin={{ left: 0, right: 12, top: 6, bottom: 0 }}>
            <ReferenceArea y1={-4} y2={rHi} fill={BAND.crit} fillOpacity={0.1} ifOverflow="hidden" />
            <ReferenceArea y1={-6} y2={-4} fill={BAND.elev} fillOpacity={0.12} ifOverflow="hidden" />
            <ReferenceArea y1={rLo} y2={-6} fill={BAND.safe} fillOpacity={0.1} ifOverflow="hidden" />
            <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
            <XAxis {...common} />
            <YAxis domain={[rLo, rHi]} allowDataOverflow stroke="var(--ink-soft)" fontSize={11} width={34}
              tickFormatter={(v: number) => v.toFixed(0)} />
            <ReferenceLine x={2} stroke="var(--rock)" strokeDasharray="4 3" label={{ value: "T-2 d", fontSize: 10, fill: "var(--rock)", position: "top" }} />
            <Tooltip formatter={(v: number) => v.toFixed(2)} labelFormatter={(l: number) => fmtTtca(l)} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line dataKey="max_risk_estimate" name="max_risk_estimate (rule input)" stroke="#5A3A33" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
            <Line dataKey="risk" name="observed risk (display)" stroke="#5B5F8F" strokeDasharray="5 3" dot={{ r: 2 }} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div>
        <h4>
          <Term k="miss distance" /> (log scale)
        </h4>
        <ResponsiveContainer width="100%" height={190}>
          <LineChart data={cdms} margin={{ left: 0, right: 12, top: 6, bottom: 0 }}>
            <ReferenceArea y1={mLo} y2={1000} fill={BAND.crit} fillOpacity={0.1} ifOverflow="hidden" />
            <ReferenceArea y1={1000} y2={5000} fill={BAND.elev} fillOpacity={0.12} ifOverflow="hidden" />
            <ReferenceArea y1={5000} y2={mHi} fill={BAND.safe} fillOpacity={0.1} ifOverflow="hidden" />
            <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
            <XAxis {...common} />
            <YAxis scale="log" domain={[mLo, mHi]} allowDataOverflow stroke="var(--ink-soft)" fontSize={11} width={44}
              ticks={[100, 1000, 5000, 10000, 100000].filter((t) => t > mLo && t < mHi)}
              tickFormatter={(v: number) => (v >= 1000 ? `${v / 1000}k` : `${v}`)} />
            <ReferenceLine x={2} stroke="var(--rock)" strokeDasharray="4 3" />
            <Tooltip formatter={(v: number) => fmtMiss(v)} labelFormatter={(l: number) => fmtTtca(l)} />
            <Line dataKey="miss_distance" name="miss distance (m)" stroke="#5A3A33" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Proj({ cdms, ax, ay, lx, ly }: { cdms: Cdm[]; ax: keyof Cdm; ay: keyof Cdm; lx: string; ly: string }) {
  const S = 220, c = S / 2;
  const pts = cdms.map((m) => ({ x: m[ax] as number, y: m[ay] as number }));
  const last = pts[pts.length - 1];
  const range = Math.max(1200, ...pts.flatMap((p) => [Math.abs(p.x), Math.abs(p.y)])) * 1.2;
  const k = c / range;
  const X = (v: number) => c + v * k;
  const Y = (v: number) => c - v * k;
  const len = Math.hypot(last.x, last.y);
  // Straight-line fly-by: the secondary moves along the line through the latest miss point, perpendicular to it.
  const dir = len > 1 ? { x: -last.y / len, y: last.x / len } : { x: 1, y: 0 };
  const ext = range * 0.9;
  return (
    <svg viewBox={`0 0 ${S} ${S}`} className="rtn" role="img" aria-label={`Relative position, ${lx} versus ${ly}`}>
      <rect x="0" y="0" width={S} height={S} fill="var(--paper)" stroke="var(--ridge-far)" />
      {[1000, 5000].map((r, i) => r * k < c * 1.4 && (
        <g key={r}>
          <circle cx={c} cy={c} r={r * k} fill="none" stroke={i ? BAND.elev : BAND.crit} strokeDasharray="3 3" opacity="0.8" />
          <text x={c + r * k + 3} y={c - 3} fontSize="8" fill={i ? BAND.elev : BAND.crit}>{r / 1000} km</text>
        </g>
      ))}
      <path d={`M0 ${c} H${S} M${c} 0 V${S}`} stroke="var(--ridge-far)" />
      <line x1={X(last.x - dir.x * ext)} y1={Y(last.y - dir.y * ext)} x2={X(last.x + dir.x * ext)} y2={Y(last.y + dir.y * ext)}
        stroke="var(--rock)" strokeDasharray="5 3" strokeWidth="1.2" />
      <polyline points={pts.map((p) => `${X(p.x)},${Y(p.y)}`).join(" ")} fill="none" stroke="var(--ink-soft)" strokeWidth="1" opacity="0.6" />
      {pts.map((p, i) => (
        <circle key={i} cx={X(p.x)} cy={Y(p.y)} r={i === pts.length - 1 ? 4 : 2.2}
          fill={i === pts.length - 1 ? "var(--rock)" : "var(--ink-soft)"} opacity={i === pts.length - 1 ? 1 : 0.5} />
      ))}
      <circle cx={c} cy={c} r="4.5" fill="var(--abstain)" />
      <text x={S - 4} y={c - 4} fontSize="9" textAnchor="end" fill="var(--ink-soft)">{lx}</text>
      <text x={c + 4} y={10} fontSize="9" fill="var(--ink-soft)">{ly}</text>
    </svg>
  );
}

function Geometry({ ev }: { ev: EventFull }) {
  return (
    <div>
      <h4>
        Encounter geometry (<Term k="RTN" /> relative position)
      </h4>
      <div className="rtn-row">
        <Proj cdms={ev.cdms} ax="relative_position_t" ay="relative_position_r" lx="T" ly="R" />
        <Proj cdms={ev.cdms} ax="relative_position_t" ay="relative_position_n" lx="T" ly="N" />
        <div className="rtn-note dim">
          Purple dot: our satellite. Dark dot: latest predicted position of the other object; grey dots: earlier CDMs. Dashed
          line: straight-line fly-by through that point.
          <br />
          <b>Short-encounter approximation</b>: relative motion is treated as a straight line; the velocity direction is
          not in the allowed inputs, so the line is drawn perpendicular to the miss vector.
        </div>
      </div>
    </div>
  );
}

function WhatIf({ ev }: { ev: EventFull }) {
  const [miss, setMiss] = useState(ev.latest.miss_distance);
  const [risk, setRisk] = useState(ev.latest.max_risk_estimate);
  const [res, setRes] = useState<ScoreResp | null>(null);
  useEffect(() => {
    setMiss(ev.latest.miss_distance);
    setRisk(ev.latest.max_risk_estimate);
    setRes(null);
  }, [ev.event_id]);
  useEffect(() => {
    const t = setTimeout(() => {
      api.score({ miss_distance: miss, max_risk_estimate: risk }).then(setRes).catch(() => setRes(null));
    }, 120);
    return () => clearTimeout(t);
  }, [miss, risk]);
  const changed = res && res.tier !== ev.tier;
  return (
    <div>
      <h4>What if (re-scored live by the API, rule only for now)</h4>
      <div className="whatif">
        <label>
          <Term k="miss distance" />: <b className="mono">{fmtMiss(miss)}</b>
          <input type="range" min={1} max={5} step={0.01} value={Math.log10(Math.max(10, miss))}
            onChange={(e) => setMiss(Math.pow(10, +e.target.value))} />
        </label>
        <label>
          max_risk_estimate (log10 <Term k="Pc" />): <b className="mono">{risk.toFixed(1)}</b>
          <input type="range" min={-20} max={-2} step={0.1} value={Math.max(-20, risk)}
            onChange={(e) => setRisk(+e.target.value)} />
        </label>
        <div className="whatif-out" aria-live="polite">
          {res && (
            <>
              <TierBadge tier={res.tier} /> <span className="dim">{res.rule}</span>
              {changed && <span className="chg"> Changes the tier from {TIER_NAMES[ev.tier]}.</span>}
            </>
          )}
          <button className="link-btn" onClick={() => { setMiss(ev.latest.miss_distance); setRisk(ev.latest.max_risk_estimate); }}>
            reset
          </button>
        </div>
      </div>
    </div>
  );
}

function Actions({ ev, dataset }: { ev: EventFull; dataset: Dataset }) {
  const [note, setNote] = useState("");
  const [trail, setTrail] = useState<AuditRec[]>([]);
  const [ok, setOk] = useState(true);
  const [err, setErr] = useState("");
  const load = () => api.audit(ev.event_id).then((r) => { setTrail(r.records); setOk(r.chain_ok); }).catch(() => {});
  useEffect(() => { setNote(""); setErr(""); load(); }, [ev.event_id]);
  const act = async (a: string) => {
    try {
      await api.postAudit(ev.event_id, a, note, dataset);
      setNote("");
      setErr("");
      load();
    } catch {
      setErr("Could not write the audit record.");
    }
  };
  return (
    <div>
      <h4>Your decision</h4>
      <div className="actions">
        <input type="text" placeholder="Note (optional)" value={note} maxLength={500}
          onChange={(e) => setNote(e.target.value)} aria-label="Decision note" />
        <button className="btn" onClick={() => act("Accept")}>Accept</button>
        <button className="btn warn" onClick={() => act("Escalate")}>Escalate</button>
        <button className="btn" onClick={() => act("Dismiss")}>Dismiss</button>
      </div>
      {err && <div className="err">{err}</div>}
      <ol className="trail">
        {trail.length === 0 && <li className="dim">No actions recorded for this event.</li>}
        {trail.map((r) => (
          <li key={r.seq}>
            <b>{r.action}</b> <span className="mono dim">{r.ts.replace("T", " ").replace("Z", " UTC")}</span>
            {r.note && <span> "{r.note}"</span>}
            <span className="mono hash" title={`prev ${r.prev_hash}`}>{r.hash.slice(0, 8)}</span>
          </li>
        ))}
      </ol>
      <div className="dim small">Hash chain {ok ? "verified" : "BROKEN"}; each record hashes the one before it.</div>
    </div>
  );
}

function Bars({ title, p }: { title: string; p: number[] }) {
  return (
    <div className="bars">
      <div className="dim small">{title}</div>
      {p.map((v, i) => (
        <div key={i} className="bar-row">
          <span>{TIER_NAMES[i]}</span>
          <span className="bar"><i style={{ width: `${v * 100}%`, background: TIER_VAR[i] }} /></span>
          <span className="mono">{(v * 100).toFixed(0)}%</span>
        </div>
      ))}
    </div>
  );
}

export default function EventDetail({ id, dataset, modelName, onBack }: {
  id: number | null; dataset: Dataset; modelName: string | null; onBack: () => void;
}) {
  const [ev, setEv] = useState<EventFull | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (id == null) return;
    setErr(false);
    api.event(id, dataset).then(setEv).catch(() => setErr(true));
  }, [id, dataset]);

  const uncertain = ev && (ev.abstain || ev.tier_set.length > 1);
  const cdms = useMemo(() => ev?.cdms ?? [], [ev]);

  if (id == null) return <section className="detail"><div className="empty">Select an event from the queue.</div></section>;
  if (err) return <section className="detail"><button className="link-btn back" onClick={onBack}>← Queue</button><div className="empty">Could not load event {id}.</div></section>;
  if (!ev || ev.event_id !== id) return <section className="detail"><div className="empty">Loading...</div></section>;
  const L = ev.latest;

  return (
    <section className="detail">
      <button className="link-btn back" onClick={onBack}>← Queue</button>
      <div className="card head">
        <div className="head-top">
          <TierBadge tier={ev.tier} big />
          {uncertain && <AbstainBadge title={`Tier set: ${ev.tier_set.map((t) => TIER_NAMES[t]).join(" / ")}`} />}
          {ev.recommendation && <span className="rec">Recommendation: <b>{ev.recommendation}</b></span>}
          <span className="mono dim">event #{ev.event_id} · {ev.c_object_type.toLowerCase()} · {ev.n_cdms} <Term k="CDM">CDMs</Term></span>
        </div>
        <p className="rule"><span className="dim">Rule that fired:</span> {ev.rule}</p>
        {ev.flags.length > 0 && <p>{ev.flags.map((f) => <span key={f} className="flag">{f.replace(/_/g, " ")}</span>)}</p>}
        <div className="kv mono">
          <span><Term k="TCA" /> {fmtTtca(L.time_to_tca)}</span>
          <span><Term k="miss distance" /> {fmtMiss(L.miss_distance)}</span>
          <span>max_risk_estimate {fmtPc(L.max_risk_estimate)}</span>
          <span>rel. speed {(L.relative_speed / 1000).toFixed(1)} km/s</span>
          <span>sigma r {L.c_sigma_r.toFixed(0)} / {L.t_sigma_r.toFixed(1)} m</span>
        </div>
        <div className="probs">
          {ev.p_tier ? <Bars title="Tier probabilities now" p={ev.p_tier} />
            : <div className="dim small">No tier probabilities: this run uses the rule only.</div>}
          {ev.p_forecast && ev.forecast_tier_at_tca != null
            ? <Bars title={`Forecast tier at TCA: ${TIER_NAMES[ev.forecast_tier_at_tca]}`} p={ev.p_forecast} />
            : <div className="dim small">No forecast of the tier at <Term k="TCA" /> yet.</div>}
        </div>
        <div className="dim small">Source: {modelName ?? "unknown model"}. Output of a tool; the analyst decides.</div>
      </div>
      <div className="card"><Timeline ev={{ ...ev, cdms }} /></div>
      <div className="card"><Geometry ev={ev} /></div>
      <div className="card"><WhatIf ev={ev} /></div>
      <div className="card"><Actions ev={ev} dataset={dataset} /></div>
    </section>
  );
}
