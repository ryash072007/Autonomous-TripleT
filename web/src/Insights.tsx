import { ReactNode, Suspense, lazy, useEffect, useState } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { EventLight, api } from "./api";

const Globe = lazy(() => import("./Globe"));
const TN = ["Safe", "Elevated", "Critical"];
const TC = ["#2F7A68", "#C77A12", "#B0302A"];
type Obj = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const FILE = "artifacts/evidence/insights.json";

function Card({ title, take, path, children, pending }: { title: string; take?: string; path: string; children?: ReactNode; pending?: boolean }) {
  return (
    <section className="card ins">
      <h3>{title}</h3>
      {pending ? <div className="empty">pending data: {FILE} has no <span className="mono">{path}</span> yet.</div> : (
        <>
          {take && <p className="take">{take}</p>}
          {children}
          <div className="src mono">{FILE} · {path}</div>
        </>
      )}
    </section>
  );
}

const pct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;
const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
const arr = (v: unknown): Obj[] => (Array.isArray(v) ? (v as Obj[]) : []);

function Funnel({ d }: { d: Obj }) {
  const rows = arr(d.funnel);
  if (!rows.length) return <Card title="Analyst workload funnel" path="funnel" pending />;
  const first = rows[0], last = rows[rows.length - 1];
  const ev = rows.find((r) => /event/i.test(String(r.stage))) ?? first;
  const mx = Math.max(...rows.map((r) => r.n));
  return (
    <Card title="Analyst workload funnel" path="funnel"
      take={`${first.n.toLocaleString()} ${first.stage} reduce to ${last.n.toLocaleString()} ${last.stage}; that is ${pct(last.n / ev.n, 1)} of the ${ev.n.toLocaleString()} ${ev.stage}.`}>
      <div className="bars">
        {rows.map((r) => (
          <div key={r.stage} className="bar-row wide">
            <span>{r.stage}</span>
            <span className="bar"><i style={{ width: `${(r.n / mx) * 100}%`, background: "var(--rock)" }} /></span>
            <span className="mono">{r.n.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function TierFlow({ d }: { d: Obj }) {
  const m: number[][] | undefined = d.tier_flow?.matrix;
  if (!m) return <Card title="Tier at 2 days vs tier at closest approach" path="tier_flow.matrix" pending />;
  const data = m.map((row, i) => ({ from: `${TN[i]} at T-2 d`, Safe: row[0], Elevated: row[1], Critical: row[2] }));
  const critEnd = sum(m.map((r) => r[2]));
  const critNotCrit = critEnd - m[2][2];
  return (
    <Card title="Tier at 2 days vs tier at closest approach" path="tier_flow.matrix (rows: tier at T-2 d, columns: final tier)"
      take={`${critNotCrit} of ${critEnd} events that end Critical (${pct(critNotCrit / critEnd)}) were not Critical at T-2 d; ${sum(m[2]) - m[2][2]} of ${sum(m[2])} that were Critical at T-2 d ended lower.`}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} horizontal={false} />
          <XAxis type="number" fontSize={11} stroke="var(--ink-soft)" />
          <YAxis type="category" dataKey="from" width={110} fontSize={11} stroke="var(--ink-soft)" />
          <Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} />
          {TN.map((t, i) => <Bar key={t} dataKey={t} name={`ends ${t}`} stackId="a" fill={TC[i]} isAnimationActive={false} />)}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Strip({ title, path, rows, label }: { title: string; path: string; rows: Obj[]; label: string }) {
  if (!rows.length) return <Card title={title} path={path} pending />;
  const data = rows.map((r) => {
    const c: number[] = r.counts ?? [r.safe, r.elevated, r.critical];
    const tot = Math.max(1, sum(c));
    return { name: String(r[label]), n: tot, Safe: c[0] / tot, Elevated: c[1] / tot, Critical: c[2] / tot, crit: c[2] / tot };
  });
  const top = [...data].filter((x) => x.n >= 20).sort((a, b) => b.crit - a.crit)[0];
  return (
    <Card title={title} path={path} take={top ? `${top.name} has the highest Critical share, ${pct(top.crit, 1)} of ${top.n} events.` : undefined}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="name" fontSize={10} stroke="var(--ink-soft)" />
          <YAxis domain={[0, 1]} tickFormatter={(v: number) => pct(v)} fontSize={11} stroke="var(--ink-soft)" width={40} />
          <Tooltip formatter={(v: number) => pct(v, 1)} /><Legend wrapperStyle={{ fontSize: 11 }} />
          {TN.map((t, i) => <Bar key={t} dataKey={t} stackId="a" fill={TC[i]} isAnimationActive={false} />)}
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Spaghetti({ d }: { d: Obj }) {
  const s: Obj | undefined = d.risk_vs_time;
  const bands = s?.median_by_final_tier;
  if (!bands) return <Card title="Risk against time to closest approach" path="risk_vs_time.median_by_final_tier" pending />;
  const ts: number[] = Array.from(new Set(TN.flatMap((_, i) => arr(bands[i] ?? bands[String(i)]).map((r) => r.t as number)))).sort((a, b) => b - a);
  const rows = ts.map((t) => {
    const row: Obj = { t };
    TN.forEach((_, i) => {
      const r = arr(bands[i] ?? bands[String(i)]).find((x) => x.t === t);
      if (r) { row[`m${i}`] = r.median; row[`b${i}`] = [r.q25, r.q75]; }
    });
    return row;
  });
  const last = (i: number) => arr(bands[i] ?? bands[String(i)]).slice(-1)[0];
  const first = (i: number) => arr(bands[i] ?? bands[String(i)])[0];
  const rise = last(2) && first(2) ? last(2).median - first(2).median : null;
  return (
    <Card title="Risk against time to closest approach" path="risk_vs_time.median_by_final_tier (median and IQR, grouped by final tier)"
      take={rise != null ? `Events that end Critical rise by ${rise.toFixed(1)} in log10 Pc median from first to last CDM; the other groups stay flatter.` : undefined}>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
          <XAxis dataKey="t" type="number" reversed domain={["dataMax", 0]} fontSize={11} stroke="var(--ink-soft)" tickFormatter={(v: number) => `-${v.toFixed(0)}d`} />
          <YAxis fontSize={11} stroke="var(--ink-soft)" width={34} />
          <ReferenceLine x={2} stroke="var(--rock)" strokeDasharray="4 3" />
          <Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} />
          {TN.map((t, i) => <Area key={"b" + i} dataKey={`b${i}`} name={`${t} IQR`} fill={TC[i]} stroke="none" fillOpacity={0.15} isAnimationActive={false} legendType="none" />)}
          {TN.map((t, i) => <Line key={"m" + i} dataKey={`m${i}`} name={`ends ${t}`} stroke={TC[i]} strokeWidth={2} dot={false} isAnimationActive={false} />)}
        </ComposedChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Reliability({ d }: { d: Obj }) {
  const rows = arr(d.reliability);
  if (!rows.length) return <Card title="Calibration of P(Critical)" path="reliability" pending />;
  const gap = Math.max(...rows.map((r) => Math.abs(r.p_mean - r.frac_pos)));
  return (
    <Card title="Calibration of P(Critical)" path="reliability" take={`Largest gap between predicted and observed Critical rate: ${pct(gap, 1)} across ${rows.length} bins.`}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
          <XAxis dataKey="p_mean" type="number" domain={[0, 1]} fontSize={11} stroke="var(--ink-soft)" tickFormatter={(v: number) => pct(v)} />
          <YAxis domain={[0, 1]} fontSize={11} stroke="var(--ink-soft)" width={40} tickFormatter={(v: number) => pct(v)} />
          <Tooltip formatter={(v: number) => pct(v, 1)} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--ink-soft)" strokeDasharray="4 3" />
          <Line dataKey="frac_pos" name="observed" stroke="#B0302A" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function F10({ d }: { d: Obj }) {
  const rows = arr(d.f10_buckets);
  if (!rows.length) return <Card title="Space weather (F10.7)" path="f10_buckets" pending />;
  const rates = rows.map((r) => r.critical_rate as number);
  const spread = Math.max(...rates) - Math.min(...rates);
  return (
    <Card title="Space weather (F10.7)" path="f10_buckets"
      take={spread < 0.02 ? `No effect seen: Critical rate stays within ${pct(spread, 1)} across F10 buckets.` : `Critical rate varies by ${pct(spread, 1)} across F10 buckets.`}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="bucket" fontSize={11} stroke="var(--ink-soft)" />
          <YAxis tickFormatter={(v: number) => pct(v)} fontSize={11} stroke="var(--ink-soft)" width={40} />
          <Tooltip formatter={(v: number) => pct(v, 1)} />
          <Bar dataKey="critical_rate" fill="#B0302A" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}

export default function Insights({ events, onOpen }: { events: EventLight[]; onOpen: (id: number) => void }) {
  const [ins, setIns] = useState<{ available: boolean; content?: Obj; message?: string } | null>(null);
  useEffect(() => { api.insights().then(setIns).catch(() => setIns({ available: false })); }, []);
  const withOrbit = events.filter((e) => e.orbit_display);
  const d: Obj = ins?.content ?? {};
  return (
    <div className="page insights">
      <h2>Insights</h2>
      <p className="dim">Every chart reads JSON written by a script; the source path is under each one.</p>
      <section className="card ins">
        <h3>The fleet, by altitude</h3>
        {withOrbit.length === 0 ? (
          <div className="empty">pending data: scored events have no orbit_display yet.</div>
        ) : (
          <>
            <p className="take">
              {(() => {
                const alts = withOrbit.map((e) => (e.orbit_display!.t.h_apo_km + e.orbit_display!.t.h_per_km) / 2);
                const bin = (lo: number, hi: number) => alts.filter((a) => a >= lo && a < hi).length;
                const best = [300, 400, 500, 600, 700, 800, 900, 1000].map((lo) => ({ lo, n: bin(lo, lo + 100) })).sort((a, b) => b.n - a.n)[0];
                return `${best.n} of ${withOrbit.length} events sit in the ${best.lo} to ${best.lo + 100} km band, the most crowded.`;
              })()}
            </p>
            <Suspense fallback={<div className="empty">Loading globe...</div>}>
              <Globe kind="fleet" events={withOrbit} onPick={onOpen} height={460} />
            </Suspense>
            <div className="legend small">
              Point = one test event at its altitude (exaggerated 3x), at a deterministic longitude and a latitude bounded by its inclination.
              <span style={{ color: TC[2] }}> ● Critical</span> <span style={{ color: TC[1] }}> ● Elevated</span> <span style={{ color: TC[0] }}> ● Safe</span>. Hover for id and altitude, click to open. Orbit data is display only.
            </div>
          </>
        )}
      </section>
      {!ins?.available && ins && <div className="banner soft">{ins.message ?? "pending data: insights.json not written yet"}</div>}
      <div className="ins-grid">
        <Funnel d={d} />
        <TierFlow d={d} />
        <Strip title="Altitude band and tier" path="altitude_band_tier" rows={arr(d.altitude_band_tier)} label="band" />
        <Strip title="Object type and tier" path="object_type_tier" rows={arr(d.object_type_tier)} label="object_type" />
        <Spaghetti d={d} />
        <Reliability d={d} />
        <F10 d={d} />
      </div>
    </div>
  );
}
