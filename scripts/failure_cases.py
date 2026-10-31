"""Real failure cases from out-of-fold predictions -> artifacts/evidence/failure_cases.json."""

from __future__ import annotations

import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from train import build_b, oof_task_a, oof_task_b  # noqa: E402

from ca_triage.data import DECISION_CUTOFF_DAYS, ROOT, load
from ca_triage.evaluation import write_evidence
from ca_triage.models import decide, floor_by_miss

COLS = ["time_to_tca", "miss_distance", "max_risk_estimate", "c_sigma_r", "t_sigma_r", "relative_speed", "c_object_type"]


def cdm_rows(g, with_risk=True):
    cols = COLS + (["risk"] if with_risk else [])
    return [{k: (None if (isinstance(v, float) and not np.isfinite(v)) else (v if isinstance(v, str) else round(float(v), 4)))
             for k, v in r.items()} for r in g[cols].to_dict("records")]


def main() -> None:
    tr = load("train")
    thr = json.loads((ROOT / "artifacts/models/thresholds.json").read_text())
    out: dict = {"note": "OOF predictions from 5-fold grouped CV at the shipped thresholds; `risk` is shown for the reader only."}

    # Task A: Critical CDMs (>= 2 d) missed by model+floor, and the most confident false Critical alarms
    oof = oof_task_a(tr)
    pred = floor_by_miss(decide(oof, thr["a"]["t_critical"], thr["a"]["t_alert"]), tr.miss_distance)
    early = tr.time_to_tca >= DECISION_CUTOFF_DAYS
    missed = tr[(tr.tier == 2) & (pred < 2) & early]
    fa = tr[(tr.tier < 2) & (pred == 2) & early].assign(p=oof[((tr.tier < 2) & (pred == 2) & early).to_numpy(), 2]).nlargest(3, "p")
    out["task_a_missed_critical_cdms"] = [
        {"row": int(i), "event_id": int(r.event_id), "p_model": [round(float(x), 4) for x in oof[i]],
         "predicted": int(pred[i]), "cdm": cdm_rows(tr.loc[[i]])[0]} for i, r in missed.iterrows()]
    out["task_a_false_critical_cdms"] = [
        {"row": int(i), "event_id": int(r.event_id), "p_critical": round(float(r.p), 4), "true_tier": int(r.tier),
         "cdm": cdm_rows(tr.loc[[i]])[0]} for i, r in fa.iterrows()]

    # Task B: final-Critical events the forecast misses at the shipped thresholds
    X, y, f, persist, last = build_b(tr)
    oofb = oof_task_b(X, y, f)
    pb = decide(oofb, thr["b"]["t_critical"], thr["b"]["t_alert"])
    miss_idx = np.where((y == 2) & (pb < 2))[0]
    order = miss_idx[np.argsort(oofb[miss_idx, 2])][:5]
    cases = []
    for j in order:
        eid = X.index[j]
        g = tr[tr.event_id == eid].sort_values("time_to_tca", ascending=False)
        early_g, final = g[g.time_to_tca >= DECISION_CUTOFF_DAYS], g.iloc[-1]
        why = []
        if len(early_g) <= 2:
            why.append(f"only {len(early_g)} CDM(s) >= 2 d")
        if early_g.c_sigma_r.max() > 1e6 or early_g.t_sigma_r.max() > 1e6:
            why.append("very large sigma (covariance-dominated Pc)")
        if final.risk - early_g.risk.iloc[-1] > 3:
            why.append(f"observed log10 Pc jumps {early_g.risk.iloc[-1]:.1f} -> {final.risk:.1f} after the last early CDM")
        if final.miss_distance < 1000 and early_g.miss_distance.iloc[-1] > 5000:
            why.append(f"miss distance collapses {early_g.miss_distance.iloc[-1]:.0f} m -> {final.miss_distance:.0f} m")
        cases.append({"event_id": int(eid), "p_forecast": [round(float(x), 4) for x in oofb[j]], "forecast": int(pb[j]),
                      "final_tier": 2, "why": why or ["no single cause found; late change not visible in early CDMs"],
                      "early_cdms": cdm_rows(early_g), "final_cdm": cdm_rows(g.iloc[[-1]])[0]})
    out["task_b_missed_critical_events"] = cases
    miss_ev = X.iloc[miss_idx]
    hit_ev = X[(y == 2) & (pb == 2)]
    out["task_b_missed_vs_caught_critical"] = {
        "n_missed": int(len(miss_ev)), "n_caught": int(len(hit_ev)),
        "median_n_cdms": [float(miss_ev.n_cdms.median()), float(hit_ev.n_cdms.median())],
        "median_last_log_miss": [float(miss_ev.last_log_miss.median()), float(hit_ev.last_log_miss.median())],
        "median_last_max_risk_estimate": [float(miss_ev.last_max_risk_estimate.median()), float(hit_ev.last_max_risk_estimate.median())],
        "median_tte_last": [float(miss_ev.tte_last.median()), float(hit_ev.tte_last.median())],
        "order": "[missed, caught]",
    }
    print(write_evidence("failure_cases.json", out))
    print(json.dumps(out["task_b_missed_vs_caught_critical"]))
    for c in cases:
        print(c["event_id"], c["p_forecast"], c["why"])
    for c in out["task_a_missed_critical_cdms"]:
        print("A miss", c["event_id"], c["p_model"], c["cdm"])


if __name__ == "__main__":
    main()
