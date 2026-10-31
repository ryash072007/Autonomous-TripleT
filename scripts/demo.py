"""artifacts/demo.json: three guided-demo events picked from artifacts/scored/test_events.json by fixed rules."""

from __future__ import annotations

import json

from ca_triage.data import ROOT

ev = json.loads((ROOT / "artifacts/scored/test_events.json").read_text())["events"]
km = lambda e: e["latest"]["miss_distance"] / 1000  # noqa: E731


def pick(cands, key):
    return max(cands, key=key)


clear = pick([e for e in ev if e["tier"] == 2 and e["forecast_tier_at_tca"] == 2 and not e["abstain"] and e["p_tier"][2] > 0.99
              and "miss distance" in e["rule"] and e["n_cdms"] >= 6 and not e["flags"]], key=lambda e: (e["n_cdms"], -km(e)))
early = pick([e for e in ev if e["tier"] < 2 and e["forecast_tier_at_tca"] == 2 and not e["abstain"] and "out_of_distribution" not in e["flags"]
              and e["n_cdms"] >= 5], key=lambda e: e["p_forecast"][2])
wrong = pick([e for e in ev if (e["abstain"] or 2 in e["forecast_tier_set"])
              and (e["latest"]["c_sigma_r"] or 0) > 1e6 and e["n_cdms"] <= 3], key=lambda e: e["p_forecast"][2])
# worst_consequence: modest Pc, very high consequence (display-only consequence model)
cand = [e for e in ev if e["consequence"]["harm_rank"] <= 30 and e["consequence"]["pc_rank"] > 2 * e["consequence"]["harm_rank"]]
worst = max(cand, key=lambda e: e["consequence"]["pc_rank"] - e["consequence"]["harm_rank"]) if cand else None
out = {
    "clear_critical": {"event_id": clear["event_id"], "reason": f"{clear['rule']}; {clear['n_cdms']} CDMs; model P(Critical) = {clear['p_tier'][2]:.2f} now and "
                       f"{clear['p_forecast'][2]:.2f} at TCA. Nothing for the model to be unsure about."},
    "caught_early": {"event_id": early["event_id"], "reason": f"Latest CDM is {early['tier_name']} ({early['rule']}), but the forecast for TCA is Critical "
                     f"(P = {early['p_forecast'][2]:.2f}) from {early['n_cdms']} CDMs at least 2 d out. The latest tier alone would not have raised it."},
    "model_wrong": {"event_id": wrong["event_id"], "reason": f"Pattern we fail on, not a known error (no test labels used): latest sigma {wrong['latest']['c_sigma_r']:.2g} m and only "
                    f"{wrong['n_cdms']} CDM(s), tier {wrong['tier_name']} now (tier set {wrong['tier_set']}, abstain = {wrong['abstain']}), forecast P(Critical at TCA) = {wrong['p_forecast'][2]:.2f}. "
                    "In CV the missed Critical events were late miss-distance collapses, huge-sigma or single-CDM cases (train events 8732, 11790, 11623, 2958; "
                    "artifacts/evidence/failure_cases.json). The console flags or abstains here instead of asserting a tier."},
}
if worst:
    c = worst["consequence"]
    out["worst_consequence"] = {"event_id": worst["event_id"], "reason": (
        f"Pc is modest (estimate {c['pc_display']:.1e}, Pc rank {c['pc_rank']} of 2,167) but a collision at {c['collision_altitude_km']:.0f} km would release "
        f"about {c['fragments_10cm']} fragments >= 10 cm into a band holding {c['active_sats_in_band']:,} active satellites "
        f"(expected {c['exposure_30d']:.2f} encounters in 30 days), so it ranks {c['harm_rank']} by Pc x consequence. "
        "Model-based estimate with stated assumptions; display and prioritisation only, the tier is unchanged.")}
(ROOT / "artifacts/demo.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
