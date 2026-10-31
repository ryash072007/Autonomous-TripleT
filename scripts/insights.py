"""Data for the Insights page -> artifacts/evidence/insights.json. Orbit heights come from the display-only loader."""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from conformal import cached  # noqa: E402
from train import build_b, oof_task_b  # noqa: E402

from ca_triage import SEED
from ca_triage.data import DECISION_CUTOFF_DAYS, ROOT, load
from ca_triage.display import load_display_orbits
from ca_triage.evaluation import event_labels, test_like_events, write_evidence
from ca_triage.tiers import tier

NAMES = ["Safe", "Elevated", "Critical"]
ALT_EDGES = list(range(0, 1000, 100))  # 100 km bins of target perigee height


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(float(c - h), 5), round(float(c + h), 5)]


def alt_bin(h):
    h = np.asarray(h, float)
    return np.clip((h // 100).astype(int), 0, len(ALT_EDGES) - 1)


def alt_label(i):
    return f"{ALT_EDGES[i]}-{ALT_EDGES[i] + 100}" if i < len(ALT_EDGES) - 1 else f"{ALT_EDGES[i]}+"


def main() -> None:
    tr = load("train")
    disp_tr = load_display_orbits("train")
    ev_ids = test_like_events(tr)
    d = tr[tr.event_id.isin(ev_ids.index)]
    y = event_labels(d)
    early_last = (d[d.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"]).groupby("event_id").head(1))
    el = early_last.set_index("event_id")
    obs_tier = pd.Series(tier(el.risk, el.miss_distance), index=el.index)
    out: dict = {}

    # ---- funnel (test)
    events = json.loads((ROOT / "artifacts/scored/test_events.json").read_text())["events"]
    rec = pd.Series([e["recommendation"] for e in events])
    out["funnel_test"] = {
        "cdms": int(sum(e["n_cdms"] for e in events)), "events": len(events),
        "model_alerts_elevated_or_above": int(sum(e["tier"] >= 1 for e in events)),
        "forecast_critical_flagged": int(sum(e["forecast_tier_at_tca"] == 2 for e in events)),
        "abstain_analyst_decides": int(sum(e["abstain"] for e in events)),
        "recommendation_counts": {k: int(v) for k, v in rec.value_counts().items()},
        "act": int((rec == "Act").sum()), "default_ratio": 100,
        "note": "alerts use the tier of each event's latest CDM; abstain = tier set > 1 or out-of-distribution"}

    # ---- transition matrix, observed tier at the last CDM >= 2 d -> final tier (train, test-like events)
    M = np.zeros((3, 3), int)
    np.add.at(M, (obs_tier.reindex(y.index).to_numpy(), y.to_numpy()), 1)
    out["transition_matrix_2d_to_tca"] = {"n_events": int(M.sum()), "rows_from_tier_at_2d": NAMES, "cols_final_tier": NAMES, "counts": M.tolist(),
                                          "definition": "tier of the last CDM >= 2 d from observed risk and miss distance, to the tier of the final CDM"}

    # ---- altitude band x final tier (train) and x current tier (test)
    dtr = disp_tr.assign(_i=np.arange(len(disp_tr)))
    pos = early_last.index  # CDM row labels in tr (RangeIndex == row position)
    hper = disp_tr.t_h_per.to_numpy()[tr.index.get_indexer(pos)]
    band = pd.Series(alt_bin(hper), index=early_last.event_id.to_numpy())
    A = np.zeros((len(ALT_EDGES), 3), int)
    np.add.at(A, (band.reindex(y.index).to_numpy(), y.to_numpy()), 1)
    te = load("test")
    disp_te = load_display_orbits("test")
    te_last_idx = te.sort_values(["event_id", "time_to_tca"]).groupby("event_id").head(1).index
    te_ev = {e["event_id"]: e for e in events}
    bt = alt_bin(disp_te.t_h_per.to_numpy()[te_last_idx])
    ct = np.array([te_ev[e]["tier"] for e in te.event_id.to_numpy()[te_last_idx]])
    B = np.zeros((len(ALT_EDGES), 3), int)
    np.add.at(B, (bt, ct), 1)
    out["altitude_band"] = {"bins_km_target_perigee_height": [alt_label(i) for i in range(len(ALT_EDGES))], "tiers": NAMES,
                            "train_final_tier_counts": A.tolist(), "test_current_tier_counts": B.tolist(),
                            "note": "t_h_per of the latest CDM (>= 2 d for train); display column, not a model input"}

    # ---- object type x tier (test)
    ot = pd.crosstab(pd.Series([e["c_object_type"] for e in events], name="type"), pd.Series([e["tier"] for e in events], name="tier"))
    ot = ot.reindex(columns=[0, 1, 2], fill_value=0)
    out["object_type_tier_test"] = {"types": list(ot.index), "tiers": NAMES, "counts": ot.to_numpy().tolist()}

    # ---- risk vs time series
    rng = np.random.default_rng(SEED)
    samples = []
    for t in range(3):
        ids = y.index[y.to_numpy() == t].to_numpy()
        for eid in rng.choice(ids, 20, replace=False):
            g = d[d.event_id == eid].sort_values("time_to_tca", ascending=False)
            samples.append({"event_id": int(eid), "final_tier": NAMES[t],
                            "series": [[round(float(a), 3), round(float(b), 3)] for a, b in zip(g.time_to_tca, g.risk)]})
    bins = np.arange(-0.25, 7.25, 0.25)
    d2 = d.assign(final=d.event_id.map(y), tb=np.digitize(d.time_to_tca, bins))
    band_stats = {}
    for t in range(3):
        rows = []
        for b, g in d2[d2.final == t].groupby("tb"):
            if len(g) < 5:
                continue
            q = np.percentile(g.risk, [25, 50, 75])
            rows.append({"tte_mid": round(float((bins[b - 1] + bins[b]) / 2), 3) if 0 < b < len(bins) else None, "q25": round(float(q[0]), 3),
                         "median": round(float(q[1]), 3), "q75": round(float(q[2]), 3), "n": int(len(g))})
        band_stats[NAMES[t]] = [r for r in rows if r["tte_mid"] is not None]
    out["risk_vs_time"] = {"sampled_events": samples, "median_iqr_by_final_tier": band_stats, "bin_days": 0.25,
                           "note": "risk = log10 Pc of each CDM, floored at -30; 20 sampled train events per final tier (seed 42)"}

    # ---- reliability of P(Critical at TCA), out-of-fold
    X, yb, fb, _, _ = build_b(tr)
    pb = cached("oof_b", lambda: oof_task_b(X, yb, fb))[:, 2]
    edges = [0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0001]
    idx = np.digitize(pb, edges) - 1
    rel = []
    for b in range(10):
        m = idx == b
        rel.append({"bin": f"{edges[b]:.2f}-{min(edges[b + 1], 1):.2f}", "mean_predicted": round(float(pb[m].mean()), 5) if m.any() else None,
                    "observed_rate": round(float((yb[m] == 2).mean()), 5) if m.any() else None, "n": int(m.sum()),
                    "ci95": wilson(int((yb[m] == 2).sum()), int(m.sum()))})
    out["reliability_p_critical"] = {"bins": rel, "n_events": int(len(pb)), "source": "out-of-fold Task B probabilities, 8,293 train events"}

    # ---- Critical rate by F10 bucket
    f10 = el.F10.reindex(y.index)
    edges_f = [0, 70, 75, 80, 90, 110, 1000]
    labs = ["<70", "70-75", "75-80", "80-90", "90-110", "110+", "missing"]
    rows = []
    cr = (y.to_numpy() == 2)
    bk = np.where(f10.isna().to_numpy(), 6, np.digitize(f10.fillna(0).to_numpy(), edges_f) - 1)
    for b, name in enumerate(labs):
        m = bk == b
        k, n = int(cr[m].sum()), int(m.sum())
        rows.append({"bucket": name, "events": n, "final_critical": k, "rate": round(k / n, 5) if n else None, "ci95": wilson(k, n)})
    cis = [r["ci95"] for r in rows if r["events"] >= 30 and r["bucket"] != "missing"]
    overlap = max(c[0] for c in cis) <= min(c[1] for c in cis)
    out["critical_rate_by_f10"] = {"buckets": rows, "all_intervals_overlap": bool(overlap),
                                   "reading": "no clear effect (95% Wilson intervals of the buckets with >= 30 events all overlap)" if overlap
                                   else "intervals do not all overlap: some F10 buckets differ; this is association, not cause",
                                   "note": "F10 of the last CDM >= 2 d; 'Critical' = final tier Critical"}

    print(write_evidence("insights.json", out, splits=("train", "test")))
    print(out["funnel_test"], out["transition_matrix_2d_to_tca"]["counts"], out["critical_rate_by_f10"]["reading"])
    print(rel)


if __name__ == "__main__":
    main()
