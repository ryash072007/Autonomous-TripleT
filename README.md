# OrbitGuard: collision triage for satellite operators

Autonomous SG 2026 (Acacia Hackathon Society x NUS Product Club) · AI & Aerospace track · **Airbus Challenge #1**

> Classifying one conjunction message is easy. Knowing **two days before closest approach** which events will
> still be dangerous, and knowing when you don't know, is the hard part. OrbitGuard reads conjunction data
> messages (CDMs), sorts every event into **Safe / Elevated / Critical (manoeuvre required)**, forecasts the tier
> at closest approach with a calibrated miss-rate guarantee, and hands uncertain events to the analyst. The
> analyst decides.

## The problem

**User.** A conjunction-assessment analyst on a LEO operator's flight-dynamics team. For every close approach
they receive a stream of CDMs (`cdms_per_event` in [`baselines.json`](artifacts/evidence/baselines.json)), and by roughly 2 days before the time of
closest approach (TCA) they must decide whether to start manoeuvre planning.

**Today.** Read each CDM, check Pc and miss distance against thresholds (NASA CARA, NASA/SP-20205011318; ESA
Space Debris Office practice), judge whether the covariance is credible, and watch the numbers drift. Most events
fade; a few get worse late.

**What that costs, measured on the ESA Collision Avoidance Challenge data** (8,293 training events that look like
the test set, [`baselines.json`](artifacts/evidence/baselines.json)):
- Acting on the 2-day view ("persistence") misses **99 of 551** events that end Critical.
- 113 events that look Critical at 2 days end lower (`persistence_false_critical`): unnecessary manoeuvres.
- In the 2019 ESA competition on this data, "copy the latest CDM" was a hard baseline to beat: the winning
  score was 0.556 against the baseline's 0.694 (Uriot et al., *Spacecraft collision avoidance challenge: design and
  results of a machine learning competition*, arXiv:2008.03069).

## Risk tiers

From the problem statement, implemented once in [ca_triage/tiers.py](ca_triage/tiers.py):

| Tier | Rule |
| --- | --- |
| Critical (manoeuvre required) | Pc ≥ 10⁻⁴, or miss distance < 1.0 km |
| Elevated | 10⁻⁶ ≤ Pc < 10⁻⁴, or 1.0 km ≤ miss distance ≤ 5.0 km |
| Safe | Pc < 10⁻⁶ and miss distance > 5.0 km |

## What it does

| Step | What the analyst gets | Method |
| --- | --- | --- |
| Tier each CDM | Tier, the rule that fired, P(tier) | LightGBM on the 13 allowed columns, floored by the exact miss-distance rule |
| Forecast the tier at TCA | P(Critical at TCA) from CDMs ≥ 2 days out | LightGBM on event history features |
| Know when it doesn't know | A **set** of possible tiers. More than one tier → "Analyst decides" | Conformal risk control (Learn-then-Test), target Critical miss rate ≤ 5% |
| Flag unreliable inputs | `covariance_fragile`, `out_of_distribution`, placeholder sigmas | Encounter-plane Pc sweep over covariance scale; isolation forest; drift audit |
| Recommend | Act / Dismiss / Analyst decides, with a cost-ratio slider | Expected cost with C_miss / C_man (default 100) |
| Explain | A short brief per event | LLM restates computed facts; every number is checked, otherwise a template is shown |
| Account | Accept / Escalate / Dismiss with a note | Hash-chained audit log |

### Where AI is used, and where it deliberately is not

- **The tier rule is a fixed rule.** No model and no LLM decides a threshold.
- **Statistics and ML estimate** the Pc branch and the forecast, with calibrated sets and explicit abstention.
- **Physics** (encounter-plane Gaussian Pc) is a baseline and a fragility flag, with its assumptions written down
  ([ca_triage/physics.py](ca_triage/physics.py)).
- **The LLM only writes the explanation.** It never computes, ranks or decides. A numeric guard rejects any brief
  containing a number that is not a computed fact ([ca_triage/brief/guard.py](ca_triage/brief/guard.py)). The app
  works with no API key.
- **The analyst decides.** Every output is labelled as tool output and every action is logged.

## Results

Every number below is copied from a JSON file under [artifacts/evidence/](artifacts/evidence/) that a script
wrote. The two one-shot test scores (`task_a_test.json`, `task_b_test.json`) and the post-hoc breakdown keep the
commit stamp from when they were measured, because re-running them would mean scoring the test set again. The history was tidied before
publishing, so those three stamps name pre-publication commits; their generated times sit in each file. The console's Results page reads the same files and shows the source path under each figure.

### Per-CDM tier, organiser test set (24,484 CDMs, scored once) · [`task_a_test.json`](artifacts/evidence/task_a_test.json)

| | OrbitGuard | Baseline B0 (rule on `max_risk_estimate`) |
| --- | --- | --- |
| Critical recall | **1.000** (0 of 2,227 missed) | 1.000 |
| Alerts per 100 CDMs | **39.8** | 54.2 |
| Safe CDMs flagged as alerts | **6.7%** | 28.8% |
| Macro-F1 | **0.951** | 0.841 |

Same Critical recall, about three quarters fewer false alarms on Safe CDMs. 5-fold grouped CV agrees
([`task_a_cv.json`](artifacts/evidence/task_a_cv.json)). A physics Pc baseline (B1) is **stronger than B0** and beats
us on macro-F1 (0.957 vs 0.949 in CV on CDMs ≥ 2 days out) with fewer alerts, but it misses 304 Critical CDMs
where we miss 2
([`baselines.json`](artifacts/evidence/baselines.json)).

### Forecasting the tier at TCA (event level)

**Cross-validation, 8,293 train events** ([`task_b_cv.json`](artifacts/evidence/task_b_cv.json)): at the same number of
Critical flags, the model **ties persistence** (Critical recall 0.829 vs 0.820, inside the fold spread). It does
not beat it. We ship a recall-first operating point instead (CV recall 0.951, which holds by construction because
the threshold was chosen on the same out-of-fold predictions) and control the cost with abstention and the
decision layer.

**Guaranteed miss rate** ([`conformal.json`](artifacts/evidence/conformal.json)): at α = 0.05 the conformal sets miss
**3.3%** of Critical events in held-out folds (target ≤ 5%), and hand **11.7%** of events to the analyst. On the
released test labels the sets missed **2 of 17** Critical events (11.8%, a very wide interval with only 17 events),
above the 5% target ([`task_b_test.json`](artifacts/evidence/task_b_test.json)). The guarantee did not hold on test,
and we report that as is.

**Decision layer, cost ratio 100** ([`decision.json`](artifacts/evidence/decision.json)): expected cost 0.40 vs 1.26 for
persistence; missed Critical 0.22 vs 1.19 per 100 events; but **17.8 manoeuvres per 100 vs 6.8**, plus 11.1 analyst
reviews per 100. We trade more manoeuvres for fewer misses; the slider shows the trade at other cost ratios.

**ESA's released test labels, scored once after freezing** ([`task_b_test.json`](artifacts/evidence/task_b_test.json)).
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

A post-hoc breakdown, with no changes to the model ([`task_b_test_breakdown.json`](artifacts/evidence/task_b_test_breakdown.json)):
- 179 of the 408 flags already have a miss distance under 1 km at 2 days, so they are Critical by rule, but this
  label cannot confirm them.
- 7 are Critical by Pc at 2 days, and 3 of those were confirmed.
- 210 are forecast-only flags from the recall-first threshold, and 1 of those hit.
- The 2 Critical events outside the conformal set (107 and 801) were still not dismissed: the decision layer sent
  both to "Analyst decides", because their current-CDM tier set was {Elevated, Critical} (the forecast sets alone
  missed them).

### Some collisions are worse: consequence and expected harm

Pc says how likely a collision is, not how much damage it would do. For each test event, OrbitGuard estimates the
debris a collision would create and how many active satellites sit in that debris band
([ca_triage/consequence.py](ca_triage/consequence.py), [`consequence.json`](artifacts/evidence/consequence.json)).
- **Masses** come from the CDM's radar cross-section and area-to-mass ratio, with a typical mass by object type as
  the fallback. **Fragments ≥ 10 cm** come from a simplified NASA Standard Breakup Model.
- **Exposure** counts active satellites in the affected altitude band. The count uses a 25 km binned table built
  from CelesTrak's public active-satellite list ([population_by_altitude.json](artifacts/population_by_altitude.json)),
  combined with a kinetic-gas flux proxy over 30 days.
- **Check against real breakups.** Predicted / catalogued fragments are 0.51 for Iridium–Cosmos, 0.35 for
  Fengyun-1C and 0.77 for Cosmos 1408. The model undercounts, so treat it as an order-of-magnitude estimate and use
  it for ranking only.
- **Ranking by expected harm (Pc × consequence) instead of Pc** keeps the order broadly (Spearman 0.86), but 9 of
  the top 20 events by Pc move 5 or more places. Event 1983 ranks 110th by Pc and 17th by harm: a collision at 779 km
  would put about 2,800 fragments into a band holding about 400 active satellites
([demo.json](artifacts/demo.json), `worst_consequence`).
- This is **display and prioritisation only**. It never changes the tier or the model, and a test checks that.

## Where it fails

From held-out folds ([`failure_cases.json`](artifacts/evidence/failure_cases.json)), shown in the console under
Results → Where it fails:
- **Late miss-distance collapse.** Events 8732, 11790, 11623 and 2958 look Safe at 2 days (P(Critical) < 0.1%) and
  end Critical when the miss distance collapses from 8–35 km to under 1 km in the last two days. Nothing in the
  allowed early CDMs predicts it. Event 8732 also has a placeholder covariance; 2958 has a single early CDM.
- **Borderline Pc.** Two Critical CDMs (events 1176, 11573) have Pc just above 10⁻⁴ and are scored Elevated.
- **What the analyst sees:** placeholder sigmas, single-CDM history and out-of-distribution inputs are flagged on
  the event, and those events go to "Analyst decides" instead of getting a confident tier.
- **Train/test drift is mild** (adversarial AUC 0.55, [`drift.json`](artifacts/evidence/drift.json)); 25 test events
  are out of distribution and are routed to the analyst.

Everything we tried and dropped is in [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md).

## Run it

Needs Python 3.11+ and Node 20+.

```bash
python -m pip install -e ".[dev]"
python scripts/fetch_data.py      # dataset/ from the organisers' Drive folder
python -m pytest -q
python scripts/serve.py           # builds web/ on first run, then http://localhost:8000
```

Rebuild every model and evidence file: `sh scripts/rerun_evidence.sh` (the two one-shot test scores are not re-run).
Model binaries are not committed. A retrain on a fresh clone is accepted only if its predictions match the reference
sample stored in the frozen [model card](artifacts/model_card.json) within 1e-6. LightGBM pickles are not
byte-identical across runs, so the file hashes can differ while the predictions match.
Optional: `ANTHROPIC_API_KEY` for LLM briefs, and `SPACETRACK_USER` / `SPACETRACK_PASS` for live mode. See
`.env.example`.

## Submission files

- [submission/test_predictions.csv](submission/test_predictions.csv): one row per test CDM (`row` = 0-based row in
  `test_data.csv`, `event_id`, `time_to_tca`, `tier_pred`, `tier_name`, `p_safe`, `p_elevated`, `p_critical`, `rule`).
- [submission/test_event_forecasts.csv](submission/test_event_forecasts.csv): one row per test event with the forecast
  tier at TCA and its probabilities.

## Data

ESA Collision Avoidance Challenge dataset (CC BY 4.0), as distributed by the organisers. **Model inputs** are only the
allowed columns: `event_id, time_to_tca, miss_distance, relative_speed, relative_position_{r,t,n}, c_object_type,
c_sigma_r, t_sigma_r, max_risk_estimate, F10, AP`. `risk` (log10 Pc) is the label only. The globe draws orbits from
the CDMs' orbital elements (`*_j2k_sma/ecc/inc`, `*_h_apo/per`): **display only**, never a model input, and a test
checks it ([tests/test_features.py](tests/test_features.py)).

## Limitations

- Only radial sigmas are available, so the physics Pc assumes an isotropic covariance and a 10 m hard-body radius.
- Conformal guarantees assume test events resemble the calibration events; the drift audit shows a mild shift, and
  the test-set miss rate (2 of 17) was above target.
- The conformal CV reuses out-of-fold scores from models that saw the evaluation fold, so the CV coverage is
  slightly optimistic. The released-label test is the clean check.
- The released test labels have no final miss distance and only 17 Critical events.
- Live mode uses Space-Track public CDMs, which carry Pc and miss distance but not our other inputs, so live events
  are tiered by rule only.
- Decision support only. It never commands a spacecraft.

## Repository map

```
ca_triage/   tiers, data, models, physics, OOD, brief + guard, audit storage, FastAPI app
scripts/     fetch, evaluate, train, conformal, decision, freeze, predict, serve
web/         React + Vite console (landing, queue, event detail with globe, next 24 h, insights, results)
artifacts/   evidence/*.json (committed), scored/*.json (committed), model_card.json
submission/  test predictions
docs/        DESIGN, PITCH, CONTRACT, EXPERIMENTS, REFERENCE_REPO_ANALYSIS
```

## Team

Team TripleT: Raj Yash, Bhavya Puri, Aslan Shaukat Vaida, Ramith Vaid.
