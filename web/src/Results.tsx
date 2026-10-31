import { ReactNode, useEffect, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EvidenceResp, api } from "./api";
import { Term } from "./ui";

type Json = unknown;

function get(o: Json, path: string): Json {
  return path.split(".").reduce<Json>((a, k) => (a != null && typeof a === "object" ? (a as Record<string, Json>)[k] : undefined), o);
}
const num = (v: Json): number | null => (typeof v === "number" ? v : null);
const pct = (v: number | null, d = 1) => (v == null ? "n/a" : `${(v * 100).toFixed(d)}%`);
const dec = (v: number | null, d = 1) => (v == null ? "n/a" : v.toFixed(d));

function Src({ file, path }: { file: string; path: string }) {
  return <div className="src mono">{`artifacts/evidence/${file}.json · ${path}`}</div>;
}

interface Row {
  label: ReactNode;
  path: string; // under model / b0
  kind: "pct" | "num";
  better: "high" | "low";
  cvKey: string;
}

const ROWS: Row[] = [
  { label: <>Critical recall</>, path: "critical_recall", kind: "pct", better: "high", cvKey: "critical_recall" },
  { label: <>Alerts per 100 <Term k="CDM">CDMs</Term></>, path: "alerts_per_100", kind: "num", better: "low", cvKey: "alerts_per_100" },
  { label: <>Safe false-alarm rate</>, path: "safe_false_alarm_rate", kind: "pct", better: "low", cvKey: "safe_false_alarm_rate" },
  { label: <>Macro-F1</>, path: "macro_f1", kind: "pct", better: "high", cvKey: "macro_f1" },
];

function TaskA({ ev }: { ev: Record<string, Json> }) {
  const test = ev["task_a_test"], cv = ev["task_a_cv"];
  if (!test) return <div className="empty">task_a_test.json not available yet.</div>;
  const f = (v: number | null, k: Row["kind"]) => (k === "pct" ? pct(v) : dec(v));
  return (
    <table className="tbl res">
      <thead>
        <tr><th>Metric (per CDM)</th><th>Model, test set</th><th>B0 rule, test set</th><th>Model, 5-fold CV</th><th>B0, 5-fold CV</th></tr>
      </thead>
      <tbody>
        {ROWS.map((r) => {
          const m = num(get(test, `model.${r.path}`)), b = num(get(test, `b0.${r.path}`));
          const win = m != null && b != null && (r.better === "high" ? m > b : m < b);
          const cell = (root: string) => {
            const mean = num(get(cv, `${root}.folds.${r.cvKey}.mean`)), sd = num(get(cv, `${root}.folds.${r.cvKey}.std`));
            return mean == null ? "n/a" : `${f(mean, r.kind)} ± ${r.kind === "pct" ? pct(sd) : dec(sd)}`;
          };
          return (
            <tr key={r.path} style={{ cursor: "default" }}>
              <td>{r.label}
                <Src file="task_a_test" path={`model.${r.path} / b0.${r.path}`} />
              </td>
              <td className={"big" + (win ? " win" : "")}>{f(m, r.kind)}</td>
              <td className="big dim">{f(b, r.kind)}</td>
              <td className="mono">{cell("model_floored_all_cdms")}<Src file="task_a_cv" path={`model_floored_all_cdms.folds.${r.cvKey}`} /></td>
              <td className="mono dim">{cell("b0_all_cdms")}<Src file="task_a_cv" path={`b0_all_cdms.folds.${r.cvKey}`} /></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function TaskB({ ev }: { ev: Record<string, Json> }) {
  const b = ev["task_b_cv"];
  if (!b) return <div className="empty">task_b_cv.json not available yet.</div>;
  const mp = num(get(b, "equal_budget.model_at_persistence_critical_budget.critical_recall"));
  const pp = num(get(b, "equal_budget.persistence.critical_recall"));
  const flags = num(get(b, "equal_budget.persistence.critical_flags"));
  const mb = num(get(b, "equal_budget.model_at_b0_critical_budget.critical_recall"));
  const bb = num(get(b, "equal_budget.b0_at_2d.critical_recall"));
  const diff = mp != null && pp != null ? mp - pp : null;
  const verdict = diff == null ? "" : Math.abs(diff) < 0.02 ? "ties persistence" : diff > 0 ? "beats persistence" : "is below persistence";
  const opRecall = num(get(b, "model.folds.critical_recall.mean"));
  const opAlerts = num(get(b, "model.folds.alerts_per_100.mean"));
  const perAlerts = num(get(b, "persistence_true_risk.folds.alerts_per_100.mean"));
  const perRecall = num(get(b, "persistence_true_risk.folds.critical_recall.mean"));
  return (
    <>
      <p className="verdict">
        Forecasting the final tier from CDMs at least 2 days out: at an equal number of Critical flags ({flags ?? "n/a"}),
        the model <b>{verdict}</b> ({pct(mp)} vs {pct(pp)} Critical recall).
      </p>
      <table className="tbl res">
        <thead><tr><th>Critical recall at equal Critical-flag budget</th><th>Model</th><th>Baseline</th></tr></thead>
        <tbody>
          <tr style={{ cursor: "default" }}>
            <td>vs persistence (latest CDM's true risk carried forward)
              <Src file="task_b_cv" path="equal_budget.model_at_persistence_critical_budget / equal_budget.persistence" /></td>
            <td className="big">{pct(mp)}</td><td className="big dim">{pct(pp)}</td>
          </tr>
          <tr style={{ cursor: "default" }}>
            <td>vs B0 rule applied at T-2 d
              <Src file="task_b_cv" path="equal_budget.model_at_b0_critical_budget / equal_budget.b0_at_2d" /></td>
            <td className="big">{pct(mb)}</td><td className="big dim">{pct(bb)}</td>
          </tr>
          <tr style={{ cursor: "default" }}>
            <td>At the shipped operating point (more alerts, higher recall)
              <Src file="task_b_cv" path="model.folds.{critical_recall,alerts_per_100} / persistence_true_risk.folds" /></td>
            <td className="big">{pct(opRecall)} <span className="small dim">at {dec(opAlerts)} alerts/100</span></td>
            <td className="big dim">{pct(perRecall)} <span className="small">at {dec(perAlerts)}</span></td>
          </tr>
        </tbody>
      </table>
      <p className="dim small">Grouped 5-fold CV over {String(get(b, "n_events") ?? "n/a")} train events that look like test events. Read as an honest tie at equal budget, not a win.</p>
    </>
  );
}

interface FailEv { event_id: number; why?: string[]; forecast?: number; final_tier?: number; p_forecast?: number[]; final_cdm?: Record<string, number> }
const TN = ["Safe", "Elevated", "Critical"];

function Failures({ ev, testIds, onOpen }: { ev: Record<string, Json>; testIds: Set<number>; onOpen: (id: number) => void }) {
  const fc = ev["failure_cases"];
  if (!fc) return <div className="empty">failure_cases.json not available yet.</div>;
  const b = (get(fc, "task_b_missed_critical_events") as FailEv[] | undefined) ?? [];
  const a = (get(fc, "task_a_missed_critical_cdms") as { event_id: number; predicted: number; p_model: number[]; cdm: Record<string, number> }[] | undefined) ?? [];
  const fa = (get(fc, "task_a_false_critical_cdms") as { event_id: number; p_critical: number; true_tier: number; cdm: Record<string, number> }[] | undefined) ?? [];
  const link = (id: number) =>
    testIds.has(id) ? <button className="link-btn" onClick={() => onOpen(id)}>Open event #{id}</button> : <span className="flag">train CV event</span>;
  return (
    <>
      <div className="cards">
        {b.map((x) => (
          <div className="card mini" key={"b" + x.event_id}>
            <b>Event #{x.event_id}</b> {link(x.event_id)}
            <p>Forecast <b>{TN[x.forecast ?? 0]}</b> at T-2 d, ended <b>{TN[x.final_tier ?? 2]}</b>
              {x.p_forecast ? ` (P(Critical) ${pct(x.p_forecast[2], 2)})` : ""}.</p>
            <p className="dim small">{(x.why ?? []).join("; ")}</p>
            <Src file="failure_cases" path="task_b_missed_critical_events" />
          </div>
        ))}
        {a.map((x, i) => (
          <div className="card mini" key={"a" + i}>
            <b>Event #{x.event_id}</b> {link(x.event_id)}
            <p>A Critical CDM scored {TN[x.predicted]} (model P(Critical) {pct(x.p_model[2], 1)}), miss distance {((x.cdm.miss_distance ?? 0) / 1000).toFixed(1)} km.</p>
            <Src file="failure_cases" path="task_a_missed_critical_cdms" />
          </div>
        ))}
        {fa.map((x, i) => (
          <div className="card mini" key={"f" + i}>
            <b>Event #{x.event_id}</b> {link(x.event_id)}
            <p>False Critical: model P(Critical) {pct(x.p_critical, 1)}, true tier {TN[x.true_tier]}, miss distance {((x.cdm.miss_distance ?? 0) / 1000).toFixed(1)} km.</p>
            <Src file="failure_cases" path="task_a_false_critical_cdms" />
          </div>
        ))}
      </div>
      <p className="dim small">{String(get(fc, "note") ?? "")}</p>
    </>
  );
}

function Conformal({ ev }: { ev: Record<string, Json> }) {
  const c = ev["conformal"];
  if (!c) return <div className="empty">Conformal tier sets: appears once artifacts/evidence/conformal.json exists.</div>;
  const curve = ((get(c, "task_b_event_forecast.curve") as Record<string, number | string>[] | undefined) ?? [])
    .filter((r) => r.method === "ltt")
    .map((r) => ({ alpha: r.alpha as number, abstain: (r.abstain_rate as number) * 100, miss: (r.critical_miss as number) * 100 }));
  const op = get(c, "operating_points.task_b_at_operating_point");
  return (
    <>
      <p className="dim small">Event-level forecast sets. When a set holds more than one tier the tool abstains and the analyst decides.</p>
      {curve.length === 0 ? <div className="empty">No curve in conformal.json.</div> : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={curve} margin={{ left: 0, right: 12, top: 8, bottom: 18 }}>
            <CartesianGrid stroke="var(--ridge-far)" strokeOpacity={0.5} />
            <XAxis dataKey="alpha" type="number" domain={[0, "dataMax"]} fontSize={11} stroke="var(--ink-soft)" label={{ value: "alpha (target Critical-miss budget)", position: "insideBottom", offset: -2, fontSize: 11 }} height={42} />
            <YAxis unit="%" fontSize={11} stroke="var(--ink-soft)" width={44} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)}%`} />
            <Legend verticalAlign="top" wrapperStyle={{ fontSize: 11 }} />
            <Line dataKey="abstain" name="Abstain rate (analyst decides)" stroke="#5B5F8F" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
            <Line dataKey="miss" name="Critical events missed" stroke="#B0302A" strokeWidth={2} dot={{ r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
      {op != null && (
        <p>At alpha = {String(get(op, "alpha"))}: abstain {pct(num(get(op, "abstain_rate")))}, Critical missed {pct(num(get(op, "critical_miss")))}, coverage {pct(num(get(op, "coverage")))}.</p>
      )}
      <Src file="conformal" path="task_b_event_forecast.curve (method = ltt), operating_points" />
    </>
  );
}

function Drift({ ev }: { ev: Record<string, Json> }) {
  const d = ev["drift"];
  if (!d) return <div className="empty">Train vs test drift: appears once artifacts/evidence/drift.json exists.</div>;
  const top = Object.entries((get(d, "adversarial_validation.top_features_by_gain") as Record<string, number> | undefined) ?? {}).slice(0, 6);
  const mx = Math.max(...top.map(([, v]) => v), 1e-9);
  const auc = num(get(d, "adversarial_validation.auc_grouped_cv_mean"));
  return (
    <>
      <p>
        A classifier tries to tell train from test CDMs using the allowed columns: AUC <b>{dec(auc, 3)}</b>
        {" "}(0.5 = indistinguishable). {String(get(d, "adversarial_validation.reading") ?? "")}
      </p>
      <div className="bars">
        {top.map(([k, v]) => (
          <div key={k} className="bar-row wide">
            <span className="mono">{k}</span>
            <span className="bar"><i style={{ width: `${(v / mx) * 100}%`, background: "var(--abstain)" }} /></span>
            <span className="mono">{v.toFixed(3)}</span>
          </div>
        ))}
      </div>
      <Src file="drift" path="adversarial_validation.top_features_by_gain" />
      {num(get(d, "event_ood.test_flagged")) != null && (
        <p className="small">
          Out-of-distribution events flagged in the test set: <b>{String(get(d, "event_ood.test_flagged"))}</b> of {String(get(d, "event_ood.test_events"))}.
          <Src file="drift" path="event_ood.test_flagged" />
        </p>
      )}
    </>
  );
}

export default function Results({ testIds, onOpen, anchor }: { testIds: Set<number>; onOpen: (id: number) => void; anchor?: string | null }) {
  const [d, setD] = useState<EvidenceResp | null>(null);
  useEffect(() => { api.evidence().then(setD).catch(() => setD({ files: [] })); }, []);
  useEffect(() => {
    if (d && anchor) setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
  }, [d, anchor]);
  if (!d) return <div className="page"><div className="empty">Loading...</div></div>;
  const ev: Record<string, Json> = Object.fromEntries(d.files.map((f) => [f.name, f.content]));
  return (
    <div className="page results">
      <h2>Results</h2>
      <p className="dim">Every number is read from a JSON file under artifacts/evidence/; the source path is under each figure.</p>
      <section className="card"><h3>Per-CDM tier: model vs the B0 rule</h3><TaskA ev={ev} /></section>
      <section className="card"><h3>Forecasting the tier at closest approach</h3><TaskB ev={ev} /></section>
      <section className="card" id="where-it-fails"><h3>Where it fails</h3><Failures ev={ev} testIds={testIds} onOpen={onOpen} /></section>
      <section className="card"><h3>Knowing when it does not know (conformal sets)</h3><Conformal ev={ev} /></section>
      <section className="card"><h3>Train vs test drift</h3><Drift ev={ev} /></section>
      <details className="raw">
        <summary>Raw evidence files ({d.files.length})</summary>
        <RawFiles d={d} />
      </details>
    </div>
  );
}

import { RawFiles } from "./Panels";
