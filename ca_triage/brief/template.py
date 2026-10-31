"""Deterministic brief from computed facts. Used when there is no API key or the LLM text fails the guard."""

from __future__ import annotations


def template_brief(f: dict) -> str:
    parts = [
        f"Event {f['event_id']} ({f['object_type']}) is {f['tier']} now: {f['rule']}.",
        f"Latest of {f['n_cdms']} CDMs, {f['time_to_tca_days']} days before closest approach: miss distance "
        f"{f['miss_distance_km']} km, max risk estimate log10 Pc {f['max_risk_estimate_log10']}"
        + (f", relative speed {f['relative_speed_kms']} km/s." if "relative_speed_kms" in f else "."),
    ]
    if "first_miss_distance_km" in f:
        parts.append(
            f"First CDM at {f['first_time_to_tca_days']} days showed {f['first_miss_distance_km']} km and "
            f"log10 Pc {f['first_max_risk_estimate_log10']}."
        )
    if "p_tier_pct" in f:
        p = ", ".join(f"{k} {v}%" for k, v in f["p_tier_pct"].items())
        parts.append(f"Model tier probabilities: {p}.")
    if "forecast_tier_at_tca" in f:
        p = ", ".join(f"{k} {v}%" for k, v in f.get("p_forecast_pct", {}).items())
        parts.append(f"Forecast tier at closest approach: {f['forecast_tier_at_tca']}" + (f" ({p})." if p else "."))
    if f["abstain"]:
        parts.append("The tool is not sure between " + " / ".join(f["tier_set"]) + ".")
    if f["flags"]:
        parts.append("Flags: " + ", ".join(x.replace("_", " ") for x in f["flags"]) + ".")
    if f.get("recommendation") and f["recommendation"] != "Analyst decides":
        parts.append(f"Tool recommendation: {f['recommendation']}.")
    parts.append("Analyst decides.")
    return " ".join(parts)
