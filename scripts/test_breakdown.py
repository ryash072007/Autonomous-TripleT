"""POST-HOC analysis of the released-label test result -> artifacts/evidence/task_b_test_breakdown.json.

Run after scripts/score_test_b.py. Nothing in the model, thresholds or task_b_test.json changes; this only explains
the result. Pc branch only (true_risk >= -4), as in task_b_test.json.
"""

from __future__ import annotations

import json
import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from fetch_labels import load_labels  # noqa: E402

from ca_triage.data import ROOT
from ca_triage.evaluation import write_evidence


def group_of(e) -> str:
    """Why is this event forecast Critical? Priority order, based on CDMs >= 2 d only."""
    miss = np.array([c["miss_distance"] for c in e["cdms"]][::-1], float)  # oldest first
    latest = e["latest"]
    if latest["miss_distance"] < 1000:
        return "latest_miss_lt_1km"
    if e["tier"] == 2:
        return "latest_tier_critical_from_pc"
    if len(miss) >= 3 and miss[-1] <= 0.5 * miss[0] and miss[-1] < miss[-2]:
        return "miss_collapse_trend"
    return "other_forecast_only"


def history(e):
    return [{"tte": c["time_to_tca"], "miss_m": c["miss_distance"], "max_risk_estimate": c["max_risk_estimate"], "risk": c["risk"],
             "c_sigma_r": c.get("c_sigma_r"), "t_sigma_r": c.get("t_sigma_r")} for c in e["cdms"]]


def modes(e) -> list[str]:
    out = []
    if e["n_cdms"] <= 2:
        out.append("single_or_two_cdms")
    s = max(e["latest"].get("c_sigma_r") or 0, e["latest"].get("t_sigma_r") or 0)
    if s > 1e6:
        out.append("huge_sigma")
    miss = [c["miss_distance"] for c in e["cdms"]][::-1]
    if len(miss) >= 2 and miss[-1] < 0.8 * miss[0]:
        out.append("miss_distance_falling")
    if e["latest"]["miss_distance"] > 5000:
        out.append("far_miss_at_2d")
    return out


def main() -> None:
    lab = load_labels().set_index("event_id").true_risk
    ev = {e["event_id"]: e for e in json.loads((ROOT / "artifacts/scored/test_events.json").read_text())["events"]}
    crit = {i: bool(lab[i] >= -4.0) for i in ev}
    fc = [e for e in ev.values() if e["forecast_tier_at_tca"] == 2]
    groups: dict[str, dict] = {}
    for e in fc:
        g = groups.setdefault(group_of(e), {"forecast_critical": 0, "true_critical": 0, "event_ids_true_critical": []})
        g["forecast_critical"] += 1
        if crit[e["event_id"]]:
            g["true_critical"] += 1
            g["event_ids_true_critical"].append(e["event_id"])
    for g in groups.values():
        g["hit_rate"] = round(g["true_critical"] / g["forecast_critical"], 5)
    misses = []
    for i, e in ev.items():
        if not crit[i]:
            continue
        fmiss = e["forecast_tier_at_tca"] != 2
        cmiss = 2 not in e["forecast_tier_set"]
        if fmiss or cmiss:
            misses.append({"event_id": i, "true_risk": round(float(lab[i]), 3), "forecast_tier": e["forecast_tier_at_tca"],
                           "p_forecast": e["p_forecast"], "forecast_tier_set": e["forecast_tier_set"], "missed_by_forecast": fmiss,
                           "missed_by_conformal_set": cmiss, "tier_now": e["tier"], "n_cdms": e["n_cdms"], "abstain": e["abstain"],
                           "recommendation": e["recommendation"], "failure_modes_seen_in_cv": modes(e), "cdms_ge_2d": history(e)})
    true_ids = [i for i in ev if crit[i]]
    res = {
        "POST_HOC": "Explains the released-label result after the fact. The model, thresholds and task_b_test.json were not changed by anything here.",
        "scope": "Pc branch only (true_risk >= -4); the released file has no final miss distance",
        "forecast_critical_total": len(fc), "true_critical_total": len(true_ids),
        "forecast_critical_by_reason": groups,
        "group_definitions": {
            "latest_miss_lt_1km": "latest CDM >= 2 d already has miss distance < 1 km (Critical by the miss branch, which true_risk cannot confirm)",
            "latest_tier_critical_from_pc": "latest CDM tier is Critical through the model's Pc estimate while miss >= 1 km",
            "miss_collapse_trend": "latest miss <= 0.5 x the first miss in the history and still falling, tier not Critical now",
            "other_forecast_only": "forecast Critical with none of the above"},
        "true_critical_event_ids": true_ids,
        "true_critical_not_in_forecast_critical_or_set": misses,
        "reading_note": "Compare failure_modes_seen_in_cv with artifacts/evidence/failure_cases.json (late miss collapse, huge sigma, single CDM).",
    }
    print(write_evidence("task_b_test_breakdown.json", res, splits=("train", "test")))
    print(json.dumps({k: res[k] for k in ("forecast_critical_total", "forecast_critical_by_reason")}, indent=1))
    for m in misses:
        print(m["event_id"], m["true_risk"], m["forecast_tier"], m["p_forecast"], m["forecast_tier_set"], m["failure_modes_seen_in_cv"], m["recommendation"], m["n_cdms"])


if __name__ == "__main__":
    main()
