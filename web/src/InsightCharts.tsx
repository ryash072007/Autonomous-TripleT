import { ReactNode } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

export const TN = ["Safe", "Elevated", "Critical"];
export const TC = ["#2F7A68", "#C77A12", "#B0302A"];
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Obj = Record<string, any>;
const FILE = "artifacts/evidence/insights.json";

export function Card({ title, take, path, children, pending }: { title: string; take?: string; path: string; children?: ReactNode; pending?: boolean }) {
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

export const pct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;
export const sum = (a: number[]) => a.reduce((x, y) => x + y, 0);
const arr = (v: unknown): Obj[] => (Array.isArray(v) ? (v as Obj[]) : []);

export function Funnel({ d }: { d: Obj }) {
  const f: Obj | undefined = d.funnel_test;
  if (!f) return <Card title="Analyst workload funnel" path="funnel_test" pending />;
  const rows = [
    { stage: "CDMs", n: f.cdms as number },
    { stage: "Events", n: f.events as number },
    { stage: "Elevated or above now", n: f.model_alerts_elevated_or_above as number },
    { stage: "Analyst decides", n: (f.recommendation_counts?.["Analyst decides"] ?? f.abstain_analyst_decides) as number },
    { stage: "Act", n: f.act as number },
  ];
  const mx = Math.max(...rows.map((r) => r.n));
  return (
    <Card title="Analyst workload funnel" path="funnel_test.{cdms, events, model_alerts_elevated_or_above, recommendation_counts, act}"
      take={`${rows[0].n.toLocaleString()} CDMs are ${rows[1].n.toLocaleString()} events; ${rows[4].n} need a manoeuvre decision (${pct(rows[4].n / rows[1].n, 1)} of events) and ${rows[3].n} are left to the analyst.`}>
      <div className="bars">
        {rows.map((r) => (
          <div key={r.stage} className="bar-row wide">
            <span>{r.stage}</span>
            <span className="bar"><i style={{ width: `${Math.max(0.5, (r.n / mx) * 100)}%`, background: "var(--rock)" }} /></span>
            <span className="mono">{r.n.toLocaleString()}</span>
          </div>
        ))}
      </div>
      {f.note && <div className="dim small">{f.note}</div>}
    </Card>
  );
}

export function TierFlow({ d }: { d: Obj }) {
  const m: number[][] | undefined = d.transition_matrix_2d_to_tca?.counts;
  if (!m) return <Card title="Tier at 2 days vs tier at closest approach" path="transition_matrix_2d_to_tca.counts" pending />;
  const data = m.map((row, i) => ({ from: `${TN[i]} at T-2 d`, Safe: row[0], Elevated: row[1], Critical: row[2] }));
  const critEnd = sum(m.map((r) => r[2]));
  const critNotCrit = critEnd - m[2][2];
  return (
    <Card title="Tier at 2 days vs tier at closest approach" path="transition_matrix_2d_to_tca.counts (rows: tier at T-2 d, columns: final tier; train events)"
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

export function Strip({ title, path, rows, label, note }: { title: string; path: string; rows: Obj[]; label: string; note?: string }) {
  if (!rows.length) return <Card title={title} path={path} pending />;
  const data = rows.map((r) => {
    const c: number[] = r.counts;
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
      {note && <div className="dim small">{note}</div>}
    </Card>
  );
}

export function Spaghetti({ d }: { d: Obj }) {
  const r: Obj | undefined = d.risk_vs_time;
  const med: Obj | undefined = r?.median_iqr_by_final_tier;
  if (!r || !med) return <Card title="Risk against time to closest approach" path="risk_vs_time" pending />;
  const sampled = arr(r.sampled_events);
  const bands = TN.map((t) =>
    arr(med[t]).filter((x) => x.tte_mid >= 0.2).map((x) => ({ t: x.tte_mid as number, m: x.median as number, band: [x.q25, x.q75] })).sort((a, b) => b.t - a.t));
  const at2 = (b: { t: number; m: number }[]) => b.reduce((best, x) => (Math.abs(x.t - 2) < Math.abs(best.t - 2) ? x : best), b[0]);
  const ends = bands.map((b) => (b.length ? { first: b[0].m, last: at2(b).m } : null));
  return (
    <Card title="Risk against time to closest approach" path="risk_vs_time.{sampled_events, median_iqr_by_final_tier} (train events, grouped by final tier)"
      take={ends[2] && ends[0] ? `The median Critical event goes from log10 Pc ${ends[2].first.toFixed(1)} at -7 d to ${ends[2].last.toFixed(1)} at -2 d; the median Safe event goes from ${ends[0].first.toFixed(1)} to ${ends[0].last.toFixed(1)}.` : undefined}>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
          <XAxis dataKey="t" type="number" reversed domain={[0, 7]} allowDataOverflow fontSize={11} stroke="var(--ink-soft)" tickFormatter={(v: number) => `-${v.toFixed(0)}d`} />
          <YAxis type="number" domain={[-18, -2]} allowDataOverflow fontSize={11} stroke="var(--ink-soft)" width={34} />
          <ReferenceLine x={2} stroke="var(--rock)" strokeDasharray="4 3" />
          <Tooltip />
          {TN.map((t, i) => <Area key={"a" + i} data={bands[i]} dataKey="band" name={`${t} IQR`} fill={TC[i]} stroke="none" fillOpacity={0.12} isAnimationActive={false} legendType="none" />)}
          {sampled.map((e) => (
            <Line key={e.event_id} data={(e.series as number[][]).map(([t, y]) => ({ t, y }))} dataKey="y" stroke={TC[TN.indexOf(e.final_tier)]}
              strokeOpacity={0.22} strokeWidth={1} dot={false} isAnimationActive={false} legendType="none" tooltipType="none" />
          ))}
          {TN.map((t, i) => <Line key={"m" + i} data={bands[i]} dataKey="m" name={`median, ends ${t}`} stroke={TC[i]} strokeWidth={3} dot={false} isAnimationActive={false} />)}
        </ComposedChart>
      </ResponsiveContainer>
      <div className="dim small">Thin lines: {sampled.length} sampled events. Thick lines: median per final tier; bands: interquartile range. Risk is floored at -30.</div>
    </Card>
  );
}

export function Reliability({ d }: { d: Obj }) {
  const rows = arr(d.reliability_p_critical?.bins);
  if (!rows.length) return <Card title="Calibration of P(Critical)" path="reliability_p_critical.bins" pending />;
  const big = rows.filter((r) => r.n >= 50);
  const worst = [...big].sort((a, b) => Math.abs(b.mean_predicted - b.observed_rate) - Math.abs(a.mean_predicted - a.observed_rate))[0];
  return (
    <Card title="Calibration of P(Critical)" path="reliability_p_critical.bins (out-of-fold, train events)"
      take={worst ? `Largest gap in bins with 50+ events: predicted ${pct(worst.mean_predicted, 1)}, observed ${pct(worst.observed_rate, 1)} (bin ${worst.bin}, n = ${worst.n}).` : undefined}>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
          <XAxis dataKey="mean_predicted" type="number" domain={[0, 1]} fontSize={11} stroke="var(--ink-soft)" tickFormatter={(v: number) => pct(v)} />
          <YAxis domain={[0, 1]} fontSize={11} stroke="var(--ink-soft)" width={40} tickFormatter={(v: number) => pct(v)} />
          <Tooltip formatter={(v: number) => pct(v, 1)} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--ink-soft)" strokeDasharray="4 3" />
          <Line dataKey="observed_rate" name="observed" stroke="#B0302A" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="dim small">Dashed diagonal: perfect calibration.</div>
    </Card>
  );
}

export function F10({ d }: { d: Obj }) {
  const c: Obj | undefined = d.critical_rate_by_f10;
  const rows = arr(c?.buckets);
  if (!rows.length) return <Card title="Space weather (F10.7)" path="critical_rate_by_f10.buckets" pending />;
  const hi = [...rows].sort((a, b) => b.rate - a.rate)[0], lo = [...rows].sort((a, b) => a.rate - b.rate)[0];
  return (
    <Card title="Space weather (F10.7)" path="critical_rate_by_f10 (share of events ending Critical)"
      take={`Critical share ranges from ${pct(lo.rate, 1)} (${lo.bucket}) to ${pct(hi.rate, 1)} (${hi.bucket}). ${c?.reading ?? ""}`}>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={rows} margin={{ left: 0, right: 12 }}>
          <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} vertical={false} />
          <XAxis dataKey="bucket" fontSize={11} stroke="var(--ink-soft)" />
          <YAxis tickFormatter={(v: number) => pct(v)} fontSize={11} stroke="var(--ink-soft)" width={40} />
          <Tooltip formatter={(v: number) => pct(v, 1)} />
          <Bar dataKey="rate" name="Critical share" fill="#B0302A" isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </Card>
  );
}
