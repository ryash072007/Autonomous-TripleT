import { Suspense, lazy, useEffect, useState } from "react";
import {
  CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { AuditRec, Dataset, EventFull, EventLight, api } from "./api";
import { CollidePanel } from "./Consequence";
import { CostSlider, Geometry, WhatIf } from "./EventDetail";
import {
  ForecastFlag, RecChip, useIsMobile, useSnapshotMode, TIER_NAMES, TIER_VAR, Term, TierIcon, flagSentence, fmtMiss, fmtPc, fmtTtca, isThresholdFlag, sigmaUnusable,
} from "./ui";

const Globe = lazy(() => import("./Globe"));
const BAND = { crit: "#B0302A", elev: "#C77A12", safe: "#2F7A68" };

const FLAG_TEXT: Record<string, string> = {
  covariance_fragile: "Collision probability is sensitive to uncertain covariance",
  out_of_distribution: "Unusual event, unlike the training data",
  short_history: "Few updates so far",
  missing_sigma: "Uncertainty data missing",
  rule_only: "Tiered by rule only",
  pc_missing: "Collision probability not published",
  emergency_reportable: "Space-Track emergency flag",
};

function Seg({ p }: { p: number[] }) {
  return (
    <div className="seg-bar" role="img" aria-label={p.map((v, i) => `${TIER_NAMES[i]} ${(v * 100).toFixed(0)}%`).join(", ")}>
      {p.map((v, i) => (v > 0.004 ? (
        <span key={i} style={{ width: `${v * 100}%`, background: TIER_VAR[i] }}>{v >= 0.1 ? `${TIER_NAMES[i]} ${(v * 100).toFixed(0)}%` : ""}</span>
      ) : null))}
    </div>
  );
}

function Trend({ ev }: { ev: EventFull }) {
  const cdms = ev.cdms;
  const maxT = Math.max(...cdms.map((c) => c.time_to_tca), 2.5);
  const risks = cdms.map((c) => c.max_risk_estimate);
  const rLo = Math.max(-12, Math.min(...risks, -7)) - 0.5, rHi = Math.max(...risks, -3.5) + 0.5;
  const misses = cdms.map((c) => c.miss_distance);
  const mLo = Math.max(10, Math.min(...misses, 800) * 0.6), mHi = Math.max(...misses, 6000) * 1.3;
  return (
    <ResponsiveContainer width="100%" height={250}>
      <ComposedChart data={cdms} margin={{ left: 0, right: 0, top: 8, bottom: 0 }}>
        <ReferenceArea yAxisId="r" y1={-4} y2={rHi} fill={BAND.crit} fillOpacity={0.1} ifOverflow="hidden" />
        <ReferenceArea yAxisId="r" y1={-6} y2={-4} fill={BAND.elev} fillOpacity={0.12} ifOverflow="hidden" />
        <ReferenceArea yAxisId="r" y1={rLo} y2={-6} fill={BAND.safe} fillOpacity={0.1} ifOverflow="hidden" />
        <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.4} />
        <XAxis type="number" dataKey="time_to_tca" reversed domain={[0, maxT]} tickFormatter={(v: number) => `-${v.toFixed(0)}d`} stroke="var(--ink-soft)" fontSize={11} />
        <YAxis yAxisId="m" scale="log" domain={[mLo, mHi]} allowDataOverflow stroke="#5A3A33" fontSize={11} width={38}
          ticks={[100, 1000, 5000, 10000, 100000].filter((t) => t > mLo && t < mHi)} tickFormatter={(v: number) => (v >= 1000 ? `${v / 1000}k` : `${v}`)} />
        <YAxis yAxisId="r" orientation="right" domain={[rLo, rHi]} allowDataOverflow stroke="#5B5F8F" fontSize={11} width={30}
          ticks={[-12, -10, -8, -6, -4].filter((t) => t > rLo && t < rHi)} />
        <ReferenceLine yAxisId="m" x={2} stroke="var(--rock)" strokeDasharray="4 3" label={{ value: "T-2 d", fontSize: 10, fill: "var(--rock)", position: "top" }} />
        <Tooltip formatter={(v: number, n: string) => (n.startsWith("Miss") ? fmtMiss(v) : v.toFixed(2))} labelFormatter={(l: number) => fmtTtca(l)} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line yAxisId="m" dataKey="miss_distance" name="Miss distance (m, left)" stroke="#5A3A33" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
        <Line yAxisId="r" dataKey="max_risk_estimate" name="Pc (log10, right)" stroke="#5B5F8F" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

const RTN_COL = { r: "#2E6FB5", t: "#5B3A9E", n: "#E0589B" }; // distinct from the tier colours

function Trajectory({ ev }: { ev: EventFull }) {
  const cdms = ev.cdms.filter((c) => c.relative_position_r != null);
  if (!cdms.length) return <div className="small dim">Not available: public CDMs do not publish the relative position.</div>;
  const maxT = Math.max(...cdms.map((c) => c.time_to_tca), 2.5);
  return (
    <ResponsiveContainer width="100%" height={250}>
      <ComposedChart data={cdms} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.4} />
        <XAxis type="number" dataKey="time_to_tca" reversed domain={[0, maxT]} tickFormatter={(v: number) => `-${v.toFixed(0)}d`} stroke="var(--ink-soft)" fontSize={11} />
        <YAxis stroke="var(--ink-soft)" fontSize={11} width={46} tickFormatter={(v: number) => (Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : `${v}`)} />
        <ReferenceLine x={2} stroke="var(--rock)" strokeDasharray="4 3" label={{ value: "T-2 d", fontSize: 10, fill: "var(--rock)", position: "top" }} />
        <ReferenceLine y={0} stroke="var(--ridge-far)" />
        <Tooltip formatter={(v: number) => `${v.toFixed(0)} m`} labelFormatter={(l: number) => fmtTtca(l)} />
        <Legend wrapperStyle={{ fontSize: 11 }} />
        <Line dataKey="relative_position_r" name="r (radial)" stroke={RTN_COL.r} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        <Line dataKey="relative_position_t" name="t (along-track)" stroke={RTN_COL.t} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        <Line dataKey="relative_position_n" name="n (cross-track)" stroke={RTN_COL.n} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        <Line dataKey="miss_distance" name="miss distance" stroke="#5A3A33" strokeWidth={2.4} strokeDasharray="6 3" dot={false} isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function TrendTile({ ev }: { ev: EventFull }) {
  const [tab, setTab] = useState<"trend" | "traj">(() => (window.location.hash.includes("tab=traj") ? "traj" : "trend"));
  return (
    <div className="card tile" data-tab="trend">
      <div className="tile-tabs">
        <button className={"label tab" + (tab === "trend" ? " on" : "")} onClick={() => setTab("trend")}>Trend</button>
        <button className={"label tab" + (tab === "traj" ? " on" : "")} onClick={() => setTab("traj")}>Trajectory</button>
      </div>
      {tab === "trend" ? (
        <>
          <Trend ev={ev} />
          <p className="small dim">Miss distance and collision probability across updates. Shading shows the tier bands; the dashed line is 2 days before closest approach.</p>
        </>
      ) : (
        <>
          <Trajectory ev={ev} />
          <p className="small dim">Relative position (r, t, n, in metres) and miss distance as reported in each CDM for the time of closest approach, plotted against time to closest approach. These are the CDM-reported values per update, not a propagated orbit.</p>
        </>
      )}
    </div>
  );
}

function DecisionRow({ ev, dataset }: { ev: EventFull; dataset: Dataset }) {
  const [note, setNote] = useState("");
  const [trail, setTrail] = useState<AuditRec[]>([]);
  const [ok, setOk] = useState(true);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [showTrail, setShowTrail] = useState(false);
  const load = () => api.audit(ev.event_id).then((r) => { setTrail(r.records); setOk(r.chain_ok); }).catch(() => {});
  useEffect(() => { setNote(""); setErr(""); setDone(null); setShowTrail(false); load(); }, [ev.event_id]);
  const act = async (action: string, text: string, label: string) => {
    try { await api.postAudit(ev.event_id, action, [text, note].filter(Boolean).join(": "), dataset); setNote(""); setErr(""); setDone(label); load(); }
    catch { setErr("Could not write the audit record."); }
  };
  const snap = useSnapshotMode();
  const off = "Decisions are logged by the backend; offline snapshot is read-only";
  const rec = ev.recommendation;
  const decided = rec === "Act" || rec === "Dismiss";
  const other = rec === "Act" ? "Dismiss" : "Act";
  return (
    <div className="decision-row" title={snap ? off : "Your decision is logged with a tamper-evident hash chain; the tool never acts on its own"}>
      <div className="decision-line">
        <span className="decision-q">OrbitGuard recommends: <b>{rec ?? "no recommendation"}</b>. <b>Your call:</b></span>
        {decided ? (
          <>
            <button className="btn primary" disabled={snap} onClick={() => act("Accept", `agreed with ${rec}`, "Agree")}>Agree</button>
            <button className="btn warn" disabled={snap} onClick={() => act("Escalate", "escalated", "Escalate")}>Escalate</button>
            <button className="btn" disabled={snap} onClick={() => act("Override", `override ${rec} to ${other}`, `Override to ${other}`)}>Override → {other}</button>
          </>
        ) : (
          <>
            <button className="btn primary" disabled={snap} onClick={() => act("Accept", "decided Act", "Act")}>Act</button>
            <button className="btn warn" disabled={snap} onClick={() => act("Escalate", "escalated", "Escalate")}>Escalate</button>
            <button className="btn" disabled={snap} onClick={() => act("Dismiss", "decided Dismiss", "Dismiss")}>Dismiss</button>
          </>
        )}
        <input type="text" placeholder="Note (optional)" disabled={snap} value={note} maxLength={400} onChange={(e) => setNote(e.target.value)} aria-label="Decision note" />
      </div>
      <button className="link-btn small trail-toggle" onClick={() => setShowTrail((x) => !x)} aria-expanded={showTrail}>
        {snap ? "audit trail unavailable offline" : `${trail.length} decision${trail.length === 1 ? "" : "s"} on record`} {showTrail ? "▾" : "▸"}{done ? ` · just logged: ${done}` : ""}
      </button>
      {err && <div className="err">{err}</div>}
      {showTrail && (
        <div className="trail-inline">
          <ol className="trail">
            {snap && <li className="dim">Unavailable offline: the audit log lives on the backend.</li>}
            {!snap && trail.length === 0 && <li className="dim">No decisions recorded for this event.</li>}
            {trail.map((r) => (
              <li key={r.seq}><b>{r.action}</b> <span className="dim small">{r.ts.replace("T", " ").replace("Z", " UTC")}</span>
                {r.note && <span> "{r.note}"</span>}<span className="mono hash" title={`prev ${r.prev_hash}`}>{r.hash.slice(0, 8)}</span></li>
            ))}
          </ol>
          <div className="dim small">Hash chain {ok ? "verified" : "BROKEN"}: each record hashes the one before it, so edits are detectable.</div>
        </div>
      )}
    </div>
  );
}

export interface PageProps {
  id: number | null; dataset: Dataset; modelName: string | null; onBack: () => void;
  highlight?: "rule" | "forecast" | "flags" | "collide" | null;
  sensNote?: string | null; forecastFlag?: ForecastFlag | null; fleet: EventLight[]; autoSim?: boolean;
}

export default function EventPage({ id, dataset, modelName, onBack, highlight, sensNote, forecastFlag, fleet, autoSim }: PageProps) {
  const [ev, setEv] = useState<EventFull | null>(null);
  const [brief, setBrief] = useState<{ text: string; source: string; fallback_reason: string | null } | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    if (id == null) return;
    setErr(false);
    api.event(id, dataset).then(setEv).catch(() => setErr(true));
    setBrief(null);
    api.brief(id, dataset).then(setBrief).catch(() => {});
  }, [id, dataset]);

  const mobile = useIsMobile();
  // On a phone, switching tabs brings the content to the top of the screen, just under the sticky bars.
  const toTabs = () => {
    if (!window.matchMedia("(max-width: 860px)").matches) return;
    window.setTimeout(() => {
      const el = document.querySelector(".m-tabs");
      if (el) window.scrollTo({ top: Math.max(0, el.getBoundingClientRect().top + window.scrollY - 100), behavior: "auto" });
    }, 30);
  };
  type MTab = "overview" | "trend" | "where" | "collide" | "details";
  const hashTab = (/mtab=(\w+)/.exec(window.location.hash)?.[1] as MTab | undefined) ?? "overview";
  const [mTab, setMTab] = useState<MTab>(hashTab);
  useEffect(() => { setMTab(hashTab); }, [id]);
  useEffect(() => { if (ev && /mtab=/.test(window.location.hash)) window.setTimeout(toTabs, 700); }, [ev?.event_id]);
  // Tour: show the tab that holds the highlighted panel and scroll it to the top part of the screen.
  useEffect(() => {
    if (!highlight || !ev) return;
    setMTab(highlight === "collide" ? "collide" : "overview");
    const t = window.setTimeout(() => document.querySelector(".detail .hl")?.scrollIntoView({ block: "start", behavior: "auto" }), 450);
    return () => window.clearTimeout(t);
  }, [highlight, ev?.event_id]);
  useEffect(() => {
    if (ev && window.location.hash.includes("focus=collide")) window.setTimeout(() => document.getElementById("collide")?.scrollIntoView({ block: "start" }), 600);
  }, [ev?.event_id]);

  if (id == null) return <section className="detail"><div className="card empty">Pick an event from the list.</div></section>;
  if (err) return <section className="detail"><button className="link-btn back" onClick={onBack}>← List</button><div className="card empty">Could not load event {id}.</div></section>;
  if (!ev || ev.event_id !== id) return <section className="detail"><div className="card empty">Loading...</div></section>;

  const L = ev.latest;
  const uncertain = ev.abstain || ev.tier_set.length > 1;
  const sentence = brief ? brief.text.split(/(?<=[a-z0-9)]\.)\s/)[0] : ev.rule;
  const hl = (k: string) => (highlight === k ? " hl" : "");
  const flags = [...ev.flags.map((f) => FLAG_TEXT[f] ?? f.replace(/_/g, " "))];
  if (sigmaUnusable(L.c_sigma_r)) flags.unshift("Uncertainty data unusable");
  const od = ev.orbit_display;

  const TABS: ["overview" | "trend" | "where" | "collide" | "details", string][] = [["overview", "Overview"], ["trend", "Trend"], ["where", "Where"], ["collide", "Collide"], ["details", "Details"]];
  return (
    <section className="detail" data-mtab={mTab}>
      <button className="link-btn back" onClick={onBack}>← Events</button>

      <div className={"card hero-card" + hl("rule")}>
        <div className="label">Collision triage</div>
        <div className="hero-row">
          <h1 className="display hero-id">EVENT {ev.event_id}</h1>
          <span className="display hero-tier" style={{ color: TIER_VAR[ev.tier] }}><TierIcon tier={ev.tier} size={34} /> {TIER_NAMES[ev.tier].toUpperCase()}</span>
          <RecChip rec={ev.recommendation} reason={ev.recommendation_reason} />
        </div>
        <p className="hero-sentence">{sentence}</p>
        <DecisionRow ev={ev} dataset={dataset} />
        <p className="small dim">
          {ev.names ? `${ev.names.t} × ${ev.names.c} · ` : ""}{ev.c_object_type.toLowerCase()} · {ev.n_cdms} <Term k="CDM">updates</Term> · <Term k="TCA" /> in {L.time_to_tca.toFixed(2)} days
          {ev.recommendation_reason ? ` · ${ev.recommendation_reason}` : ""}
        </p>
      </div>

      <div className="m-tabs" role="tablist" aria-label="Event sections">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={mTab === k} className={mTab === k ? "on" : ""} onClick={() => { setMTab(k); toTabs(); }}>{l}</button>)}
      </div>

      <div className="tiles">
        <div className="card tile" data-tab="where">
          <div className="label">Where</div>
          {od ? (
            <Suspense fallback={<div className="empty">Loading globe...</div>}>
              <Globe kind="event" id={ev.event_id} t={od.t} c={od.c} tier={ev.tier} height={250} />
            </Suspense>
          ) : <div className="dim small">pending data: no orbit data in the scored file.</div>}
          <p className="small dim">The orbit drawing uses the orbital-element columns in the CDMs (semi-major axis, eccentricity, inclination, apogee and perigee height). They are display only and never a model input. The orbit orientation (RAAN) is not in the data, so both orbits are drawn through the conjunction point (pulsing).</p>
        </div>
        <TrendTile ev={ev} />
        <div className={"card tile" + hl("forecast") + hl("flags")} data-tab="overview">
          <div className="label">How sure</div>
          {ev.p_tier ? (
            <>
              <div className="small dim">Now</div>
              <Seg p={ev.p_tier} />
            </>
          ) : <div className="small dim">{ev.flags.includes("rule_only") ? "Public data lacks the model inputs, so this is tiered by the rule only." : "Rule only: no probabilities."}</div>}
          <p className="sure-line">
            {uncertain ? <><b>Not sure</b>: could be {ev.tier_set.map((t) => TIER_NAMES[t]).join(" or ")}. The analyst decides.</> : <><b>Confident</b> in {TIER_NAMES[ev.tier]} now.</>}
          </p>
          {ev.p_forecast && ev.forecast_tier_at_tca != null && (
            <>
              <div className="small dim">At closest approach <Term k="TCA" /> {isThresholdFlag(ev.forecast_tier_at_tca, ev.p_forecast) && <span className="fc-chip flag-soft">Critical flag</span>}</div>
              <Seg p={ev.p_forecast} />
              {isThresholdFlag(ev.forecast_tier_at_tca, ev.p_forecast) && <div className="small">{flagSentence(ev.p_forecast, forecastFlag)}</div>}
            </>
          )}
          <div className="chips-row">
            {flags.map((f) => <span key={f} className="flag">{f}</span>)}
          </div>
        </div>
      </div>

      <div className={"card" + hl("collide")} id="collide" data-tab="collide">
        <CollidePanel ev={ev} fleet={fleet} autoPlay={autoSim} />
      </div>

      <details className="card drawer" data-tab="details" open={mobile ? true : undefined}>
        <summary className="label">Specialist detail</summary>
        <div className="drawer-body">
          {brief && (
            <div>
              <h4 className="label">Full brief</h4>
              <p className="brief">{brief.text}</p>
              <span className={"flag " + (brief.source === "llm" ? "ok-flag" : "")}>
                {brief.source === "llm" ? "Checked against computed facts" : `Template (${brief.fallback_reason ?? "no LLM"})`}
              </span>
            </div>
          )}
          <div className="telemetry">
            <h4 className="label">Raw numbers (latest update)</h4>
            <span><Term k="miss distance" /> {fmtMiss(L.miss_distance)}</span>
            <span>max_risk_estimate {fmtPc(L.max_risk_estimate)}</span>
            {L.relative_speed != null && <span>relative speed {(L.relative_speed / 1000).toFixed(1)} km/s</span>}
            {L.c_sigma_r != null && <span>sigma r {L.c_sigma_r.toFixed(0)} m</span>}
            {L.t_sigma_r != null && <span>sigma t {L.t_sigma_r.toFixed(1)} m</span>}
            <span>{fmtTtca(L.time_to_tca)}</span>
            <span>rule: {ev.rule}</span>
            <span>source: {modelName ?? "unknown model"}</span>
          </div>
          <Geometry ev={ev} />
          <CostSlider ev={ev} />
          <WhatIf ev={ev} note={sensNote ?? null} />
        </div>
      </details>
    </section>
  );
}
