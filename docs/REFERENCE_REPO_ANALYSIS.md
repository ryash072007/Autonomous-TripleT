# Reference repo: Datathon2-OrbitGuard

`../Datathon2-OrbitGuard` was built by the same team for the IBM Z Datathon 2026 (theme: real-time AI for
critical decisions, on IBM LinuxONE). It is a reference only; this repo starts clean.

## Overall match: roughly 60%

Same domain, same dataset, and the same idea of trust (abstain, grounded LLM, audit log). Different scoring
target, a narrower allowed feature set, and a lot of IBM-specific work that earns nothing here.

| Challenge #1 asks for | OrbitGuard has | Match |
| --- | --- | --- |
| Read CDM telemetry (ESA Collision Avoidance Challenge) | Same dataset, provenance-checked download, sealed test labels | High |
| Calculate Pc | NASA CARA-validated encounter-plane Pc (`physics/risk.py`), but it needs full 3x3 covariances and state vectors; here we only have `c_sigma_r`, `t_sigma_r` | Medium: method ports, inputs don't |
| 3-tier classification (Safe / Elevated / Critical) with the given thresholds | Forecasts final `risk` and Act/Wait/Monitor at Pc ≥ 1e-6. No miss-distance branch, different thresholds | Low: must rebuild |
| Only the 13 allowed columns | Used the full CDM column set | Low: features must be redone |
| Predictions on `test_data` rows | Event-level forecast of the final risk; ESA loss | Medium |
| Dashboard: trajectories, risk scores, miss distances | React console with globe, encounter replay, charts | Medium: ideas port, stack too heavy for one day |
| 24 h warnings and insights | 24 h network sweep on the real CelesTrak catalogue (different data) | Low |
| Rubric: trust, traceability, failure cases, baselines | Strong: paired bootstrap CIs, baseline-first, Granite guard evaluated and turned off when it failed, hash-chained audit | High |

## Reuse (ideas and small, self-contained pieces)

- `orbitguard/ml/data.py`: Zenodo byte-range download of the released test labels (`true_risk` per event) and the
  "labels sealed until model freeze" pattern. Gives us an honest event-level test score.
- `orbitguard/physics/risk.py`: encounter-plane 2D Gaussian integral. Port the disk integral for baseline B1
  with a diagonal covariance built from the radial sigmas (assumption documented).
- `orbitguard/brief/grounding.py`, `claims.py`: the numeric guard (every number must match a fact) and
  template fallback.
- `orbitguard/audit/log.py`: SHA-256 hash-chained JSONL audit log.
- `orbitguard/decision/features.py`: per-event trend features (`_delta_last2`, CDM count).
- README structure: "where AI is used and where it deliberately is not", results with the platform and command
  that produced each number, limitations section.
- Its finding that ML did **not** significantly beat "copy the latest CDM" on point forecasts but helped ranking.
  Expect the same here; plan the story around ranking, recall and calibration, not a headline accuracy.

## Don't carry over

- LinuxONE, s390x, NNPA / zDNN, Snap ML, Granite on llama.cpp, Docker for s390x: platform-specific, no rubric
  value here.
- CelesTrak catalogue screening, burn planning, Bayesian optimisation, debris consequence model: impressive, but
  outside the allowed data and hard to finish in one day. At most a single "next step" line in the README.
- The React frontend: Streamlit gets us a working, testable dashboard in hours.

## Differences that change the approach

1. The tier is a fixed rule on (Pc, miss distance). Miss distance is an allowed input, so the job is estimating Pc
   from the allowed columns, plus forecasting how the tier moves before TCA.
2. `max_risk_estimate` is allowed and is a strong upper bound on Pc. It is the baseline to beat.
3. Judges score restraint and visible failure cases. OrbitGuard's honesty about losses fits this rubric well;
   its breadth does not.
