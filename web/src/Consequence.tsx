import { Suspense, lazy, useEffect, useRef, useState } from "react";
import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { EventFull, EventLight } from "./api";
import type { Obj } from "./InsightCharts";

const Globe = lazy(() => import("./Globe"));

/** Single place that reads the ML-side consequence fields, so the real schema only needs mapping here. */
export interface Conseq {
  fragments: number | null;
  catastrophic: boolean | null;
  satsInBand: number | null;
  exposure30d: number | null;
  harmRank: number | null;
  pcRank: number | null;
  harm: number | null;
  level: string | null;
  assumptions: string | null;
}

const pick = (o: Obj | null | undefined, keys: string[]): any => { // eslint-disable-line @typescript-eslint/no-explicit-any
  if (!o) return null;
  for (const k of keys) if (o[k] != null) return o[k];
  return null;
};

export function conseq(ev: EventLight | EventFull): Conseq | null {
  const c = (ev as unknown as Obj).consequence as Obj | undefined;
  if (!c) return null;
  return {
    fragments: pick(c, ["n_fragments_10cm", "fragments_10cm", "n_fragments", "fragments"]),
    catastrophic: pick(c, ["catastrophic", "is_catastrophic"]),
    satsInBand: pick(c, ["active_sats_in_band", "n_active_in_band", "satellites_in_band", "sats_in_band"]),
    exposure30d: pick(c, ["exposure_30d", "expected_exposure_30d"]),
    harmRank: pick(c, ["harm_rank"]),
    pcRank: pick(c, ["pc_rank"]),
    harm: pick(c, ["harm_score", "expected_harm", "harm"]),
    level: pick(c, ["level", "harm_level"]),
    assumptions: null,
  };
}

/** "high" when the event is in the top 5% by harm rank (or the file says so). */
export function harmLevel(ev: EventLight, n: number): "high" | null {
  const c = conseq(ev);
  if (!c) return null;
  if (c.level) return /high/i.test(c.level) ? "high" : null;
  return c.harmRank != null && c.harmRank <= Math.max(1, n * 0.05) ? "high" : null;
}

export interface Cloud { t_hours: number[]; offsets: (number[] | null)[][]; band: [number, number] | null }
export function cloudOf(ev: EventFull): Cloud | null {
  const c = (ev as unknown as Obj).consequence as Obj | undefined;
  const d = c?.debris_cloud as Obj | undefined;
  if (!d?.offsets) return null;
  return { t_hours: d.t_hours, offsets: d.offsets, band: Array.isArray(c?.band_km) ? (c!.band_km as [number, number]) : null };
}

const STOPS = [1, 6, 24, 168]; // hours: 1 h, 6 h, 24 h, 7 d
const fmtT = (h: number) => (h < 24 ? `${h < 10 ? h.toFixed(1) : h.toFixed(0)} h` : `${(h / 24).toFixed(h < 48 ? 1 : 0)} d`);
const big = (v: number | null) => (v == null ? "n/a" : v >= 1000 ? v.toLocaleString() : String(v));

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="display stat-n">{value}</div>
      {note && <div className="small dim">{note}</div>}
    </div>
  );
}

/** "IF THEY COLLIDE": stat cards plus an on-demand debris simulation on a globe with a time scrubber. */
export function CollidePanel({ ev, fleet, autoPlay }: { ev: EventFull; fleet: EventLight[]; autoPlay?: boolean }) {
  const c = conseq(ev);
  const cloud = cloudOf(ev);
  const od = ev.orbit_display;
  const [on, setOn] = useState(false);
  const [logT, setLogT] = useState(0); // 0..1 across 1 h .. 7 d (log scale)
  const [play, setPlay] = useState(false);
  const [aff, setAff] = useState<[number, number]>([0, 0]);
  const raf = useRef(0);
  const hours = STOPS[0] * Math.pow(STOPS[3] / STOPS[0], logT);

  useEffect(() => { setOn(false); setPlay(false); setLogT(0); }, [ev.event_id]);
  useEffect(() => {
    if ((autoPlay || /simt=/.test(window.location.hash)) && cloud && od) {
      const m = /simt=([\d.]+)/.exec(window.location.hash); // screenshot helper: freeze the scrubber at a given fraction
      setOn(true);
      if (m) { setLogT(+m[1]); setPlay(false); } else { setLogT(0); setPlay(true); }
    }
  }, [autoPlay, ev.event_id, !!cloud]);
  useEffect(() => {
    if (!play) return;
    let last = performance.now();
    const step = (t: number) => {
      const dt = (t - last) / 1000;
      last = t;
      setLogT((x) => {
        const n = x + dt / 9;
        if (n >= 1) { setPlay(false); return 1; }
        return n;
      });
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [play]);

  if (!c && !cloud)
    return (
      <div>
        <h4 className="label">If they collide</h4>
        <div className="dim small">pending data: scored events have no consequence block yet.</div>
      </div>
    );

  return (
    <div>
      <h4 className="label">If they collide</h4>
      <div className="collide">
        <div className="collide-sim">
          {on && od && cloud ? (
            <>
              <div className="sim-wrap"><Suspense fallback={<div className="empty">Loading globe...</div>}>
                <Globe kind="collide" onAffected={(n, t) => setAff([n, t])} id={ev.event_id} t={od.t} c={od.c} tier={ev.tier} cloud={cloud} hours={hours} fleet={fleet} height={340} />
              </Suspense></div>
              <div className="sim-legend" aria-label="Legend" style={{ ["--ember" as string]: 0.95 - 0.4 * logT }}>
                <div className="sim-count"><b className="num">{aff[0]}</b> of {aff[1]} satellites potentially affected</div>
                <div><i className="lg ember" /> Debris fragments</div>
                <div><i className="lg ours" /> Our satellite</div>
                <div><i className="lg other" /> The other object</div>
                <div><i className="lg calm" /> Satellites in the band, not affected</div>
                <div><i className="lg hot" /> Potentially affected</div>
              </div>
              <div className="scrub">
                <button className="icon-btn" onClick={() => { if (logT >= 1) setLogT(0); setPlay((p) => !p); }} aria-label={play ? "Pause" : "Play"}>{play ? "❚❚" : "▶"}</button>
                <input type="range" min={0} max={1} step={0.002} value={logT} onChange={(e) => { setPlay(false); setLogT(+e.target.value); }} aria-label="Time after collision" />
                <b className="num">{fmtT(hours)}</b>
              </div>
              <div className="scrub-ticks small dim">{STOPS.map((h) => <span key={h}>{fmtT(h)}</span>)}</div>
            </>
          ) : (
            <div className="sim-cta">
              <p className="small dim">{od && cloud ? "See where the debris would go." : "The simulation is available for the top events by harm and the demo events; this one has no cloud file."}</p>
              <button className="btn primary" disabled={!od || !cloud} onClick={() => { setOn(true); setLogT(0); setPlay(true); }}>Simulate collision</button>
            </div>
          )}
        </div>
        <div className="collide-stats">
          <Stat label="Fragments 10 cm or larger" value={big(c?.fragments ?? null)} />
          <Stat label="Catastrophic breakup" value={c?.catastrophic == null ? "n/a" : c.catastrophic ? "Yes" : "No"} />
          <Stat label="Active satellites in the band" value={big(c?.satsInBand ?? null)} />
          <Stat label="Expected exposure, 30 days" value={c?.exposure30d == null ? "n/a" : +c.exposure30d.toPrecision(2) + ""} note="encounters with the cloud" />
          <Stat label="Harm rank vs Pc rank" value={c?.harmRank != null && c?.pcRank != null ? `#${c.harmRank} vs #${c.pcRank}` : "n/a"} note="1 = worst, of all test events" />
        </div>
      </div>
      <p className="small dim">
        A model with stated assumptions: simplified NASA breakup model, masses estimated from radar size, linear relative-motion spread (Clohessy-Wiltshire) without drag; fragments kicked faster than 500 m/s are not drawn. {c?.assumptions ?? ""}
        Red points are a sample of the fragments (about {cloud ? Math.round((c?.fragments ?? 0) / (cloud.offsets[0]?.length || 1)) : 0} fragments each); faint points are other test events in the affected altitude band, shown for illustration.
      </p>
    </div>
  );
}

/** Insights: Pc rank vs harm rank (log axes). Events far below the diagonal are low Pc but high harm. */
export function HarmScatter({ events, onOpen }: { events: EventLight[]; onOpen: (id: number) => void }) {
  const pts = events.map((e) => ({ e, c: conseq(e) })).filter((x) => x.c && x.c.pcRank != null && x.c.harmRank != null)
    .map((x) => ({ id: x.e.event_id, pc: x.c!.pcRank as number, harm: x.c!.harmRank as number }));
  const n = pts.length;
  if (!n)
    return (
      <section className="card ins">
        <h3>Probability rank vs harm rank</h3>
        <div className="empty">pending data: events have no consequence.pc_rank / harm_rank yet.</div>
      </section>
    );
  const worst = pts.filter((p) => p.harm <= 300).sort((a, b) => b.pc / b.harm - a.pc / a.harm)[0];
  const off = pts.filter((p) => p.harm <= 300 && p.pc / p.harm >= 5);
  const mx = Math.max(...pts.map((p) => Math.max(p.pc, p.harm)));
  const norm = pts.map((p) => ({ ...p, off: p.harm <= p.pc / 5 }));
  return (
    <section className="card ins wide">
      <h3>Probability rank vs harm rank</h3>
      <p className="take">
        {off.length} of the 300 most harmful events rank at least 5x worse on collision probability than on harm
        {worst ? `; the largest gap is event ${worst.id}: harm rank ${worst.harm}, Pc rank ${worst.pc}` : ""}. Some low-Pc events would do far more damage.
      </p>
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ left: 0, right: 16, top: 8, bottom: 20 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
          <XAxis type="number" dataKey="pc" name="Pc rank" scale="log" domain={[1, mx]} fontSize={11} stroke="var(--ink-soft)" label={{ value: "Pc rank (1 = most likely to collide)", position: "insideBottom", offset: -12, fontSize: 11 }} />
          <YAxis type="number" dataKey="harm" name="Harm rank" scale="log" domain={[1, mx]} fontSize={11} stroke="var(--ink-soft)" width={44} label={{ value: "harm rank", angle: -90, position: "insideLeft", fontSize: 11 }} />
          <ZAxis range={[14, 14]} />
          <ReferenceLine segment={[{ x: 1, y: 1 }, { x: mx, y: mx }]} stroke="var(--ink-soft)" strokeDasharray="4 3" />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} formatter={(v: number) => v} labelFormatter={() => ""} />
          <Scatter data={norm.filter((p) => !p.off)} fill="#7A5A50" fillOpacity={0.35} isAnimationActive={false} onClick={(p: { id: number }) => onOpen(p.id)} />
          <Scatter data={norm.filter((p) => p.off)} fill="#B0302A" fillOpacity={0.8} isAnimationActive={false} onClick={(p: { id: number }) => onOpen(p.id)} />
        </ScatterChart>
      </ResponsiveContainer>
      <div className="small dim">Dashed diagonal: same rank on both. Red: harm rank at least 5x better than Pc rank. Click a point to open the event. Source: events[].consequence.{"{pc_rank, harm_rank}"}.</div>
    </section>
  );
}
