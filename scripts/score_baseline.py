"""Write artifacts/scored/test_events.json using baseline B0 (tier rule on max_risk_estimate and miss distance).

Placeholder scorer so the console can be built before the models exist. Schema: docs/CONTRACT.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from ca_triage.data import ROOT, load
from ca_triage.tiers import TIER_NAMES, Tier, rule_fired, tier

CDM_FIELDS = ["time_to_tca", "miss_distance", "risk", "max_risk_estimate", "relative_position_r",
              "relative_position_t", "relative_position_n", "relative_speed", "c_sigma_r", "t_sigma_r"]
LATEST_FIELDS = CDM_FIELDS + ["F10", "AP"]


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if not np.isfinite(v) else round(float(v), 6)
    if isinstance(v, np.integer):
        return int(v)
    return v


def main() -> None:
    df = load("test").sort_values(["event_id", "time_to_tca"], ascending=[True, False])
    df["b0"] = tier(df.max_risk_estimate, df.miss_distance)
    events = []
    for eid, g in df.groupby("event_id", sort=True):
        last = g.iloc[-1]
        t = int(last.b0)
        events.append({
            "event_id": int(eid),
            "c_object_type": str(last.c_object_type),
            "n_cdms": len(g),
            "latest": {k: _clean(last[k]) for k in LATEST_FIELDS},
            "tier": t,
            "tier_name": TIER_NAMES[Tier(t)],
            "p_tier": None,
            "tier_set": [t],
            "abstain": False,
            "rule": rule_fired(float(last.max_risk_estimate), float(last.miss_distance)),
            "forecast_tier_at_tca": None,
            "p_forecast": None,
            "recommendation": None,
            "flags": [],
            "cdms": [{k: _clean(r[k]) for k in CDM_FIELDS} for _, r in g.iterrows()],
        })
    out = {
        "schema_version": 1,
        "dataset": "test",
        "model": {"name": "B0 max_risk_estimate rule", "version": "rule", "trained_utc": None},
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "events": events,
    }
    path = ROOT / "artifacts/scored/test_events.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")))
    counts = np.bincount([e["tier"] for e in events], minlength=3)
    print(f"{len(events)} events -> {path} (Safe/Elevated/Critical {counts.tolist()})")


if __name__ == "__main__":
    main()
