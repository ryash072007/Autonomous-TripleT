"""S1: baselines. B0 per CDM (Task A, train) and persistence + B0-at-2d (Task B). -> artifacts/evidence/baselines.json"""

from __future__ import annotations

import numpy as np

from ca_triage.data import DECISION_CUTOFF_DAYS, load
from ca_triage.evaluation import cv_summary, event_labels, fold_of_events, folds_for, test_like_events, write_evidence
from ca_triage.tiers import tier


def task_b_frame(df):
    """One row per test-like event: label + tier of the last CDM >= 2 d under persistence (true risk) and B0."""
    ev = test_like_events(df)
    d = df[df.event_id.isin(ev.index)]
    y = event_labels(d)
    early = (d[d.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"])
             .groupby("event_id").head(1).set_index("event_id"))
    out = y.rename("y").to_frame().join(early[["risk", "miss_distance", "max_risk_estimate"]])
    out["persist"] = tier(out["risk"], out["miss_distance"])
    out["b0"] = tier(out["max_risk_estimate"], out["miss_distance"])
    return out


def main() -> None:
    tr = load("train")
    folds = folds_for(tr)
    b0 = tier(tr.max_risk_estimate, tr.miss_distance)
    early = (tr.time_to_tca >= DECISION_CUTOFF_DAYS).to_numpy()
    res = {
        "task_a_b0_all_cdms": cv_summary(tr.tier, b0, folds),
        "task_a_b0_cdms_ge_2d": cv_summary(tr.tier, b0, folds, mask=early),
    }
    tb = task_b_frame(tr)
    f = tb.index.to_series().map(fold_of_events(tr.event_id)).to_numpy()
    res["task_b_n_events"] = int(len(tb))
    res["task_b_label_counts"] = np.bincount(tb.y, minlength=3).tolist()
    res["task_b_persistence_true_risk"] = cv_summary(tb.y, tb.persist, f)
    res["task_b_b0_at_2d"] = cv_summary(tb.y, tb.b0, f)
    res["notes"] = ("persistence_true_risk uses the observed risk of the last CDM >= 2 d (an analyst reading Pc); "
                    "b0_at_2d uses only allowed columns (max_risk_estimate). Task B label = tier of final CDM.")
    print(write_evidence("baselines.json", res))
    for k in ("task_a_b0_all_cdms", "task_a_b0_cdms_ge_2d", "task_b_persistence_true_risk", "task_b_b0_at_2d"):
        p = res[k]["pooled"]
        print(k, "critRecall", p["critical_recall"], "macroF1", p["macro_f1"], "alerts/100", p["alerts_per_100"],
              "missed", p["critical_missed"], "/", p["critical_total"])


if __name__ == "__main__":
    main()
