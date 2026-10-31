"""S4: score the test set with the frozen models.

    python scripts/predict.py            # submission CSVs + artifacts/scored/test_events.json
    python scripts/predict.py --score    # also write artifacts/evidence/task_a_test.json (per-CDM score vs test `risk`)
"""

from __future__ import annotations

import json
import sys
import time

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from score_baseline import CDM_FIELDS, LATEST_FIELDS, _clean  # noqa: E402

from ca_triage.data import ROOT, load
from ca_triage.evaluation import cv_summary, metrics, write_evidence
from ca_triage.models import cdm_features, decide, event_features, floor_by_miss, miss_tier
from ca_triage.tiers import TIER_NAMES, Tier, rule_fired, tier

MODELS = ROOT / "artifacts" / "models"


def rule_text(t_final: int, mt: int, p: np.ndarray, miss: float) -> str:
    """Which branch decided: the exact miss-distance branch, or the model's Pc estimate."""
    if t_final == mt and mt > 0:
        return rule_fired(-30.0, miss)  # Pc branch not triggered, so the miss-distance text applies
    if t_final == 2:
        return f"Critical: model P(Pc >= 1e-4) = {p[2]:.3f}; miss distance {miss / 1000:.2f} km"
    if t_final == 1:
        return f"Elevated: model P(Pc >= 1e-6) = {p[1] + p[2]:.3f}; miss distance {miss / 1000:.2f} km"
    return f"Safe: miss distance {miss / 1000:.2f} km > 5.0 km and model P(Pc >= 1e-6) = {p[1] + p[2]:.3f}"


def floor_proba(p: np.ndarray, mt: np.ndarray) -> np.ndarray:
    """Zero out tiers below the exact miss-distance tier and renormalise so probabilities stay consistent."""
    q = p.copy()
    for k in (1, 2):
        q[mt >= k, :k] = 0.0
    s = q.sum(1, keepdims=True)
    onehot = np.eye(3)[mt]
    return np.where(s > 0, q / np.where(s > 0, s, 1), onehot)


def main() -> None:
    thr = json.loads((MODELS / "thresholds.json").read_text())
    card = json.loads((ROOT / "artifacts/model_card.json").read_text())
    ma, mb = joblib.load(MODELS / "task_a.joblib"), joblib.load(MODELS / "task_b.joblib")
    te = load("test")
    te.insert(0, "row", np.arange(len(te)))  # 0-based row index in test_data.csv

    # ---- Task A, per CDM
    P = ma.predict_proba(cdm_features(te))
    mt = miss_tier(te.miss_distance)
    pred = floor_by_miss(decide(P, thr["a"]["t_critical"], thr["a"]["t_alert"]), te.miss_distance)
    Pf = floor_proba(P, mt)
    rules = [rule_text(int(pred[i]), int(mt[i]), P[i], float(te.miss_distance.iat[i])) for i in range(len(te))]
    sub = pd.DataFrame({"row": te.row, "event_id": te.event_id, "time_to_tca": te.time_to_tca, "tier_pred": pred,
                        "tier_name": [TIER_NAMES[Tier(int(t))] for t in pred], "p_safe": Pf[:, 0].round(5),
                        "p_elevated": Pf[:, 1].round(5), "p_critical": Pf[:, 2].round(5), "rule": rules})
    (ROOT / "submission").mkdir(exist_ok=True)
    sub.to_csv(ROOT / "submission/test_predictions.csv", index=False)

    # ---- Task B, per event (inputs: CDMs >= 2 d, which is all of the test set)
    EF = event_features(te)
    PB = mb.predict_proba(EF)
    fb = decide(PB, thr["b"]["t_critical"], thr["b"]["t_alert"])
    fc = pd.DataFrame({"event_id": EF.index, "forecast_tier_at_tca": fb, "p_safe": PB[:, 0].round(5),
                       "p_elevated": PB[:, 1].round(5), "p_critical": PB[:, 2].round(5)})
    fc.to_csv(ROOT / "submission/test_event_forecasts.csv", index=False)
    fmap = {int(e): i for i, e in enumerate(EF.index)}

    # ---- artifacts/scored/test_events.json
    tes = te.assign(_i=np.arange(len(te))).sort_values(["event_id", "time_to_tca"], ascending=[True, False])
    events = []
    for eid, g in tes.groupby("event_id", sort=True):
        last = g.iloc[-1]
        i = int(last._i)
        j = fmap[int(eid)]
        t = int(pred[i])
        flags = ["short_history"] if len(g) <= 2 else []
        if not np.isfinite(last.c_sigma_r):
            flags.append("missing_sigma")
        events.append({
            "event_id": int(eid), "c_object_type": str(last.c_object_type), "n_cdms": len(g),
            "latest": {k: _clean(last[k]) for k in LATEST_FIELDS if k in last.index},
            "tier": t, "tier_name": TIER_NAMES[Tier(t)],
            "p_tier": [round(float(x), 4) for x in Pf[i]],
            "tier_set": [t], "abstain": False, "rule": rules[i],
            "forecast_tier_at_tca": int(fb[j]), "p_forecast": [round(float(x), 4) for x in PB[j]],
            "recommendation": None, "flags": flags,
            "cdms": [{k: _clean(r[k]) for k in CDM_FIELDS if k in r.index} for _, r in g.iterrows()],
        })
    out = {"schema_version": 1, "dataset": "test",
           "model": {"name": "OrbitGuard LightGBM tiers (Task A per CDM, Task B forecast)", "version": card["version"],
                     "trained_utc": card["trained_utc"]},
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "events": events}
    path = ROOT / "artifacts/scored/test_events.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"{len(sub)} CDM rows, {len(fc)} events; test_events.json {path.stat().st_size / 1e6:.1f} MB")
    print("CDM tier counts", np.bincount(pred, minlength=3).tolist(), "event forecast counts", np.bincount(fb, minlength=3).tolist())

    # ---- one-off test score against the `risk` column that ships in test_data.csv (not a model input)
    if "--score" in sys.argv:
        y = te["tier"].to_numpy()
        b0 = tier(te.max_risk_estimate, te.miss_distance)
        res = {"task": "A on test_data.csv rows, label = tier(risk, miss_distance); measured once",
               "model_version": card["version"],
               "model": metrics(y, pred, Pf), "b0": metrics(y, b0),
               "note": "Brier uses floor-adjusted probabilities."}
        print(write_evidence("task_a_test.json", res, splits=("train", "test")))
        for k in ("model", "b0"):
            m = res[k]
            print(k, "critR", m["critical_recall"], "missed", m["critical_missed"], "/", m["critical_total"],
                  "critPrec", m["critical_precision"], "macroF1", m["macro_f1"], "alerts/100", m["alerts_per_100"],
                  "safeFA", m["safe_false_alarm_rate"])


if __name__ == "__main__":
    main()
