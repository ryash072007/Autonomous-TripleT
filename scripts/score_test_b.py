"""T1 step 2: score Task B ONCE on the released test labels -> artifacts/evidence/task_b_test.json.

Pc branch only: the released file has `true_risk` (log10 Pc at TCA) but not the final miss distance, so the miss-distance
branch of the tier cannot be scored. Critical = true_risk >= -4, Elevated-or-above = true_risk >= -6.
Nothing is tuned here. Run after scripts/freeze.py and scripts/fetch_labels.py.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from fetch_labels import load_labels  # noqa: E402

from ca_triage.data import ROOT, load
from ca_triage.evaluation import write_evidence


def prf(flag, truth):
    tp = int((flag & truth).sum())
    fp = int((flag & ~truth).sum())
    fn = int((~flag & truth).sum())
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f2 = 5 * tp / (5 * tp + 4 * fn + fp) if (5 * tp + 4 * fn + fp) else 0.0
    return {"flagged": int(flag.sum()), "flagged_per_100": round(100 * flag.mean(), 3), "tp": tp, "fp": fp, "fn": fn,
            "recall": None if r is None else round(r, 5), "precision": None if p is None else round(p, 5), "f2": round(f2, 5)}


def main() -> None:
    lab = load_labels().set_index("event_id").true_risk
    te = load("test")
    last = te.sort_values(["event_id", "time_to_tca"]).groupby("event_id").head(1).set_index("event_id")
    ev = {e["event_id"]: e for e in json.loads((ROOT / "artifacts/scored/test_events.json").read_text())["events"]}
    ids = sorted(ev)
    assert set(ids) == set(lab.index), "label events do not match test events"
    tr = lab.reindex(ids).to_numpy()
    crit, elev = tr >= -4.0, tr >= -6.0
    fc = np.array([ev[i]["forecast_tier_at_tca"] for i in ids])
    pcrit = np.array([ev[i]["p_forecast"][2] for i in ids])
    inset = np.array([2 in ev[i]["forecast_tier_set"] for i in ids])
    fabst = np.array([len(ev[i]["forecast_tier_set"]) > 1 for i in ids])
    risk_now = last.reindex(ids).risk.to_numpy()
    mre = last.reindex(ids).max_risk_estimate.to_numpy()
    rec = np.array([ev[i]["recommendation"] for i in ids])

    res = {
        "scope": "Task B, Pc branch only (final miss distance is not released). Scored once, nothing tuned afterwards.",
        "n_events": len(ids), "true_critical_events": int(crit.sum()), "true_elevated_or_above_events": int(elev.sum()),
        "critical": {
            "model_forecast_critical": prf(fc == 2, crit),
            "persistence_observed_risk_ge_-4": prf(risk_now >= -4.0, crit),
            "b0_at_2d_max_risk_estimate_ge_-4": prf(mre >= -4.0, crit),
        },
        "elevated_or_above": {
            "model_forecast_alert": prf(fc >= 1, elev),
            "persistence_observed_risk_ge_-6": prf(risk_now >= -6.0, elev),
            "b0_at_2d_max_risk_estimate_ge_-6": prf(mre >= -6.0, elev),
        },
        "note_f2": "F2 is the 2019 challenge's classification half (high risk = true_risk >= -6). The MSE half needs a regression "
                   "output, which this tier model does not produce, so the combined loss L = MSE / F2 is not computed.",
    }
    # equal budget: top-N by P(Critical) where N = persistence's flags
    n = int((risk_now >= -4.0).sum())
    top = np.zeros(len(ids), bool)
    top[np.argsort(-pcrit, kind="stable")[:n]] = True
    res["critical"]["model_top_n_by_p_critical_at_persistence_budget"] = prf(top, crit) | {"budget": n}
    # conformal set on test
    res["conformal_forecast_set"] = {
        "alpha": json.loads((ROOT / "artifacts/models/conformal.json").read_text())["task_b"]["alpha"],
        "critical_miss_rate_critical_not_in_set": round(float((~inset[crit]).mean()), 5), "critical_missed_by_set": int((~inset[crit]).sum()),
        "abstain_rate_set_size_gt_1": round(float(fabst.mean()), 5), "critical_in_set_flagged_events": int(inset.sum()),
        "note": "Critical coverage is measured on the Pc branch (true_risk >= -4) only; CV figure is in conformal.json."}
    # calibration of P(Critical)
    res["brier_critical_pc_branch"] = round(float(((pcrit - crit) ** 2).mean()), 5)
    res["mean_p_critical_vs_observed_rate"] = [round(float(pcrit.mean()), 5), round(float(crit.mean()), 5)]
    # decision layer at the default ratio (Act = manoeuvre; Analyst events reported separately)
    r = 100
    act = rec == "Act"
    ana = rec == "Analyst decides"
    res["decision_layer_default_ratio_100"] = {
        "act_per_100": round(100 * act.mean(), 3), "analyst_per_100": round(100 * ana.mean(), 3), "dismiss_per_100": round(100 * (rec == "Dismiss").mean(), 3),
        "critical_among_act": int((act & crit).sum()), "act": int(act.sum()),
        "critical_missed_by_dismiss": int(((rec == "Dismiss") & crit).sum()), "critical_in_analyst_queue": int((ana & crit).sum()),
        "persistence_manoeuvres_per_100": round(100 * float((risk_now >= -4.0).mean()), 3),
        "persistence_critical_missed": int(((risk_now < -4.0) & crit).sum())}
    print(write_evidence("task_b_test.json", res, splits=("train", "test")))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
