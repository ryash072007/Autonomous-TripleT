# Results in detail

The README has the headline numbers; this page has the rest. 
Every number below is copied from a JSON file under [artifacts/evidence/](../artifacts/evidence/) that a script
wrote. The two one-shot test scores (`task_a_test.json`, `task_b_test.json`) and the post-hoc breakdown keep the
commit stamp from when they were measured, because re-running them would mean scoring the test set again. The history was tidied before
publishing, so those three stamps name pre-publication commits; their generated times sit in each file. The console's Results page reads the same files and shows the source path under each figure.

## Supporting result: per-CDM tier on the test CDMs (24,484 CDMs, scored once)

The organisers note that tiers can be read straight from `risk`, so this is not the challenge. We report it because the
model does not see `risk` and has to estimate the Pc branch from the allowed columns.

Evidence: [`task_a_test.json`](../artifacts/evidence/task_a_test.json)

| | OrbitGuard | Baseline B0 (rule on `max_risk_estimate`) |
| --- | --- | --- |
| Critical recall | **1.000** (0 of 2,227 missed) | 1.000 |
| Alerts per 100 CDMs | **39.8** | 54.2 |
| Safe CDMs flagged as alerts | **6.7%** | 28.8% |
| Macro-F1 | **0.951** | 0.841 |

Same Critical recall, about three quarters fewer false alarms on Safe CDMs. 5-fold grouped CV agrees
([`task_a_cv.json`](../artifacts/evidence/task_a_cv.json)). A physics Pc baseline (B1) is **stronger than B0** and beats
us on macro-F1 (0.957 vs 0.949 in CV on CDMs ≥ 2 days out) with fewer alerts, but it misses 304 Critical CDMs
where we miss 2
([`baselines.json`](../artifacts/evidence/baselines.json)).

## Forecasting the tier at TCA (event level)

**Cross-validation, 8,293 train events** ([`task_b_cv.json`](../artifacts/evidence/task_b_cv.json)): at the same number of
Critical flags, the model **ties persistence** (Critical recall 0.829 vs 0.820, inside the fold spread). It does
not beat it. We ship a recall-first operating point instead (CV recall 0.951, which holds by construction because
the threshold was chosen on the same out-of-fold predictions) and control the cost with abstention and the
decision layer.

**Guaranteed miss rate** ([`conformal.json`](../artifacts/evidence/conformal.json)): at α = 0.05 the conformal sets miss
**3.3%** of Critical events in held-out folds (target ≤ 5%), and hand **11.7%** of events to the analyst. On the
released test labels the sets missed **2 of 17** Critical events (11.8%, a very wide interval with only 17 events),
above the 5% target ([`task_b_test.json`](../artifacts/evidence/task_b_test.json)). The guarantee did not hold on test,
and we report that as is.

**Decision layer, cost ratio 100** ([`decision.json`](../artifacts/evidence/decision.json)): expected cost 0.40 vs 1.26 for
persistence; missed Critical 0.22 vs 1.19 per 100 events; but **17.8 manoeuvres per 100 vs 6.8**, plus 11.1 analyst
reviews per 100. We trade more manoeuvres for fewer misses; the slider shows the trade at other cost ratios.

**Extra check: ESA's publicly released test labels** (not provided by the organisers, who use `test_data` for demo
predictions only), **scored once after freezing** ([`task_b_test.json`](../artifacts/evidence/task_b_test.json)).
Only the Pc branch can be scored (the final miss distance is not released), and only 17 test events end with
Pc ≥ 10⁻⁴, so every interval is wide:

| | OrbitGuard | Persistence | B0 at 2 days |
| --- | --- | --- | --- |
| Critical events found (of 17) | **15** | 9 | 12 |
| Events flagged Critical | 408 | **23** | 61 |
| Critical dismissed by the decision layer | **0** (9 Act, 8 to the analyst) | 8 missed | 5 missed |

Our forecast finds more of the dangerous events but with **very low precision on this label (4%)**. Part of that is
the label: many of our flags come from the miss-distance branch, which this file cannot score. Part of it is real:
the model is tuned for recall. We did not retune after seeing these numbers.

A post-hoc breakdown, with no changes to the model ([`task_b_test_breakdown.json`](../artifacts/evidence/task_b_test_breakdown.json)):
- 179 of the 408 flags already have a miss distance under 1 km at 2 days, so they are Critical by rule, but this
  label cannot confirm them.
- 7 are Critical by Pc at 2 days, and 3 of those were confirmed.
- 210 are forecast-only flags from the recall-first threshold, and 1 of those hit.
- The 2 Critical events outside the conformal set (107 and 801) were still not dismissed: the decision layer sent
  both to "Analyst decides", because their current-CDM tier set was {Elevated, Critical} (the forecast sets alone
  missed them).

## Some collisions are worse: consequence and expected harm

Pc says how likely a collision is, not how much damage it would do. For each test event, OrbitGuard estimates the
debris a collision would create and how many active satellites sit in that debris band
([ca_triage/consequence.py](../ca_triage/consequence.py), [`consequence.json`](../artifacts/evidence/consequence.json)).
- **Masses** come from the CDM's radar cross-section and area-to-mass ratio, with a typical mass by object type as
  the fallback. **Fragments ≥ 10 cm** come from a simplified NASA Standard Breakup Model.
- **Exposure** counts active satellites in the affected altitude band. The count uses a 25 km binned table built
  from CelesTrak's public active-satellite list ([population_by_altitude.json](../artifacts/population_by_altitude.json)),
  combined with a kinetic-gas flux proxy over 30 days.
- **Check against real breakups.** Predicted / catalogued fragments are 0.51 for Iridium–Cosmos, 0.35 for
  Fengyun-1C and 0.77 for Cosmos 1408. The model undercounts, so treat it as an order-of-magnitude estimate and use
  it for ranking only.
- **Ranking by expected harm (Pc × consequence) instead of Pc** keeps the order broadly (Spearman 0.86), but 9 of
  the top 20 events by Pc move 5 or more places. Event 1983 ranks 110th by Pc and 17th by harm: a collision at 779 km
  would put about 2,800 fragments into a band holding about 400 active satellites
([demo.json](../artifacts/demo.json), `worst_consequence`).
- This is **display and prioritisation only**. It never changes the tier or the model, and a test checks that.
