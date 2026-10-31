# Data contract between the ML scripts and the API

The ML side writes these files; the API only reads them. Fields may be added, never renamed or removed without
updating this file. Version bumps go in `schema_version`.

## `artifacts/scored/{dataset}_events.json`

`dataset` is `test` (default view) or `live` (Space-Track public CDMs, see below).

```jsonc
{
  "schema_version": 1,
  "dataset": "test",
  "model": {"name": "B0 max_risk_estimate rule", "version": "<sha256[:12] of model file or 'rule'>", "trained_utc": "..."},
  "generated_utc": "2026-10-31T09:00:00Z",
  "events": [
    {
      "event_id": 17,
      "c_object_type": "DEBRIS",
      "n_cdms": 9,
      "latest": {                       // the most recent CDM (smallest time_to_tca)
        "time_to_tca": 2.13, "miss_distance": 812.0, "relative_speed": 13500.0,
        "relative_position_r": -12.0, "relative_position_t": 790.0, "relative_position_n": 180.0,
        "c_sigma_r": 45.0, "t_sigma_r": 3.1, "max_risk_estimate": -5.2, "F10": 72, "AP": 5,
        "risk": -7.1                    // observed log10 Pc in the CDM; display only, never a model input
      },
      "tier": 2,                        // 0 Safe, 1 Elevated, 2 Critical: the tool's call for this event now
      "tier_name": "Critical",
      "p_tier": [0.01, 0.09, 0.90],     // null for rule-only models
      "tier_set": [2],                  // conformal set (D1); equals [tier] until D1 lands
      "abstain": false,                 // true -> "Analyst decides"
      "rule": "Critical: miss distance 0.81 km < 1.0 km",
      "forecast_tier_at_tca": 2,        // Task B; null until S3 lands
      "p_forecast": [0.05, 0.15, 0.80], // null until S3 lands
      "recommendation": null,           // D2: "Act" | "Wait" | "Dismiss"
      "flags": [],                      // e.g. "covariance_fragile", "out_of_distribution", "short_history"
      "cdms": [                         // full history, sorted by time_to_tca descending
        {"time_to_tca": 6.9, "miss_distance": 2400.0, "risk": -9.3, "max_risk_estimate": -6.0,
         "relative_position_r": 0, "relative_position_t": 0, "relative_position_n": 0,
         "relative_speed": 13500.0, "c_sigma_r": 120.0, "t_sigma_r": 5.0}
      ]
    }
  ]
}
```

## `artifacts/evidence/*.json`

Each file: `{"generated_utc", "git_commit", "command", "data_sha256", ...metrics}`. The console's Evidence page
lists every file and shows its fields; README numbers are copied from these files.

## `artifacts/demo.json`

The three guided-demo event IDs with a one-line reason each: `{"clear_critical": id, "caught_early": id,
"model_wrong": id}`. Written by the ML side once evaluation exists.

## Live dataset (`live`)

Space-Track `cdm_public` (free account; `SPACETRACK_USER` / `SPACETRACK_PASS` in env). Those public CDMs carry TCA,
minimum range and Pc but none of the model's other inputs, so live events are tiered **by the rule only**
(`p_tier`, `forecast_tier_at_tca` null) and the console says so. A snapshot is committed under
`artifacts/live_snapshot.json` so the toggle works without credentials or network.
