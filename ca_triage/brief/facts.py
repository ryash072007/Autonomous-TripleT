"""Computed facts for one event. The brief may only restate these; every number in it must match one."""

from __future__ import annotations

import re

TIERS = ["Safe", "Elevated", "Critical"]
# Fixed thresholds from the problem statement (ca_triage.tiers), quoted in the rule text.
THRESHOLD_NUMBERS = [1.0, 5.0, 1000.0, 5000.0, 1e-4, 1e-6, -4.0, -6.0, 4.0, 6.0, 2.0, 24.0]


def build_facts(e: dict) -> dict:
    L = e["latest"]
    cdms = e.get("cdms") or []
    f: dict = {
        "event_id": e["event_id"],
        "object_type": str(e["c_object_type"]).lower(),
        "tier": e["tier_name"],
        "rule": e["rule"],
        "n_cdms": e["n_cdms"],
        "time_to_tca_days": round(L["time_to_tca"], 2),
        "miss_distance_m": round(L["miss_distance"]),
        "miss_distance_km": round(L["miss_distance"] / 1000, 2),
        "max_risk_estimate_log10": round(L["max_risk_estimate"], 1),
        "abstain": bool(e.get("abstain")) or len(e.get("tier_set") or []) > 1,
        "tier_set": [TIERS[t] for t in e.get("tier_set") or []],
        "flags": list(e.get("flags") or []),
    }
    if L.get("relative_speed") is not None:
        f["relative_speed_kms"] = round(L["relative_speed"] / 1000, 1)
    if e.get("p_tier"):
        f["p_tier_pct"] = {TIERS[i]: round(p * 100) for i, p in enumerate(e["p_tier"])}
    if e.get("forecast_tier_at_tca") is not None:
        f["forecast_tier_at_tca"] = TIERS[e["forecast_tier_at_tca"]]
    if e.get("p_forecast"):
        f["p_forecast_pct"] = {TIERS[i]: round(p * 100) for i, p in enumerate(e["p_forecast"])}
    if e.get("recommendation"):
        f["recommendation"] = e["recommendation"]
    if len(cdms) >= 2:
        first = cdms[0]
        f["first_time_to_tca_days"] = round(first["time_to_tca"], 2)
        f["first_miss_distance_km"] = round(first["miss_distance"] / 1000, 2)
        f["first_max_risk_estimate_log10"] = round(first["max_risk_estimate"], 1)
    return f


def numeric_values(facts: dict) -> list[float]:
    """Every number the brief may quote, including the unit variants the template uses."""
    out: list[float] = list(THRESHOLD_NUMBERS)

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(facts)
    # The rule text is itself a computed fact; its numbers (e.g. a model probability) are allowed.
    for tok in re.findall(r"(?<![\w.])\d+(?:\.\d+)?(?:e-?\d+)?", str(facts.get("rule", ""))):
        out.append(float(tok))
    m = facts.get("miss_distance_m")
    if m is not None:
        out += [m / 1000, m * 1.0]
    if facts.get("first_miss_distance_km") is not None:
        out.append(facts["first_miss_distance_km"] * 1000)
    for k in ("p_tier_pct", "p_forecast_pct"):
        for v in (facts.get(k) or {}).values():
            out.append(v / 100)
    return out
