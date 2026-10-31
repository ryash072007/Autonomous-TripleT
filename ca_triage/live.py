"""Map Space-Track cdm_public rows to the scored-events contract (rule-only tiers). No network here."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from ca_triage.tiers import TIER_NAMES, Tier, rule_fired, tier as tier_fn

FLOOR = -30.0


def _dt(s: str) -> datetime:
    s = s.strip().replace("T", " ")
    fmt = "%Y-%m-%d %H:%M:%S.%f" if "." in s else "%Y-%m-%d %H:%M:%S"
    return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)


def _log10_pc(pc) -> float | None:
    try:
        v = float(pc)
    except (TypeError, ValueError):
        return None
    return FLOOR if v <= 0 else max(FLOOR, math.log10(v))


def _cdm(row: dict, now: datetime) -> dict:
    risk = _log10_pc(row.get("PC"))
    r = FLOOR if risk is None else risk
    return {
        "time_to_tca": (_dt(row["TCA"]) - now).total_seconds() / 86400,
        "miss_distance": float(row["MIN_RNG"]),  # Space-Track MIN_RNG is in metres
        "risk": risk,
        "max_risk_estimate": r,
        "relative_position_r": None, "relative_position_t": None, "relative_position_n": None,
        "relative_speed": None, "c_sigma_r": None, "t_sigma_r": None,
        "cdm_id": row.get("CDM_ID"), "created": row["CREATED"],
    }


def map_cdms(rows: list[dict], now: datetime | None = None) -> dict:
    """Group CDMs by object pair and TCA day, tier the latest CDM by the rule only."""
    now = now or datetime.now(timezone.utc)
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        try:
            key = (*sorted((row["SAT_1_ID"], row["SAT_2_ID"])), row["TCA"][:10])  # unordered pair
            float(row["MIN_RNG"])
            _dt(row["TCA"]), _dt(row["CREATED"])
        except (KeyError, ValueError, TypeError):
            continue
        groups.setdefault(key, []).append(row)

    events = []
    for grp in groups.values():
        grp.sort(key=lambda r: _dt(r["CREATED"]))
        last = grp[-1]
        cdms = sorted((_cdm(r, now) for r in grp), key=lambda c: -c["time_to_tca"])
        lat = _cdm(last, now)
        pc_known = lat["risk"] is not None
        t = Tier(int(tier_fn(lat["max_risk_estimate"], lat["miss_distance"])))
        rule = rule_fired(lat["max_risk_estimate"], lat["miss_distance"])
        if not pc_known:
            rule += " (Pc not published; tiered by miss distance only)"
        flags = ["rule_only"] + (["pc_missing"] if not pc_known else [])
        if last.get("EMERGENCY_REPORTABLE") == "Y":
            flags.append("emergency_reportable")
        if len(grp) == 1:
            flags.append("short_history")
        events.append({
            "event_id": int(last["CDM_ID"]),
            "cdm_id": last["CDM_ID"], "created": last["CREATED"],
            "names": {"t": last.get("SAT_1_NAME"), "c": last.get("SAT_2_NAME")},
            "object_types": {"t": last.get("SAT1_OBJECT_TYPE"), "c": last.get("SAT2_OBJECT_TYPE")},
            "c_object_type": last.get("SAT2_OBJECT_TYPE") or "UNKNOWN",
            "n_cdms": len(grp), "latest": lat,
            "tier": int(t), "tier_name": TIER_NAMES[t],
            "p_tier": None, "tier_set": [int(t)], "abstain": False,
            "rule": rule, "forecast_tier_at_tca": None, "p_forecast": None,
            "recommendation": None, "flags": flags, "cdms": cdms,
        })
    events.sort(key=lambda e: (-e["tier"], e["latest"]["time_to_tca"]))
    created = max((r["CREATED"] for r in rows if r.get("CREATED")), default=None)
    return {
        "schema_version": 1, "dataset": "live",
        "model": {"name": "Rule only (Space-Track public CDMs)", "version": "rule", "trained_utc": None},
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot": {"source": "Space-Track cdm_public", "latest_cdm_created": created, "n_cdms": len(rows)},
        "events": events,
    }
