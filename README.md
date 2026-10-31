# Autonomous-TripleT: conjunction triage for satellite collision avoidance

Autonomous SG 2026 (Acacia Hackathon Society x NUS Product Club) · AI & Aerospace track · **Airbus Challenge #1**

> A conjunction-assessment analyst gets thousands of close-approach warnings a day. This tool reads each
> conjunction data message (CDM), estimates the collision probability, sorts the event into
> **Safe / Elevated / Critical (manoeuvre required)**, shows the evidence behind that call, and says when it is
> not sure. The analyst decides.

Status: in development. Sections marked *pending* are filled from `artifacts/evidence/` once the scripts run.

## The problem

*pending*: user, today's workflow, cost, data facts (see [docs/PLAN.md](docs/PLAN.md)).

## Risk tiers

From the problem statement (NASA/SP-20205011318, ESA Space Debris Office practice), implemented once in
[ca_triage/tiers.py](ca_triage/tiers.py):

| Tier | Rule |
| --- | --- |
| Critical (manoeuvre required) | Pc ≥ 10⁻⁴, or miss distance < 1.0 km |
| Elevated | 10⁻⁶ ≤ Pc < 10⁻⁴, or 1.0 km ≤ miss distance ≤ 5.0 km |
| Safe | Pc < 10⁻⁶ and miss distance > 5.0 km |

## Where AI is used, and where it is not

| Job | Method |
| --- | --- |
| Estimate Pc from the allowed CDM fields | Gradient-boosted model, checked against a physics Pc and a `max_risk_estimate` rule |
| Assign the tier | Fixed rule above. No model and no LLM |
| Forecast whether an event will be Critical at TCA | Model on the CDM history up to 2 days before TCA |
| Explain an event to the analyst | LLM brief from computed facts, with a numeric check and a template fallback |
| Decide whether to manoeuvre | The analyst |

## Results

*pending*

## Where it fails

*pending*

## Run it

```bash
python -m pip install -e ".[dev]"
python scripts/fetch_data.py
python -m pytest -q
streamlit run app/dashboard.py
```

## Data

ESA Collision Avoidance Challenge dataset (CC BY 4.0), as distributed by the organisers. Only the columns
the problem statement allows are used: `event_id, time_to_tca, miss_distance, relative_speed,
relative_position_{r,t,n}, c_object_type, c_sigma_r, t_sigma_r, max_risk_estimate, F10, AP`. `risk`
(log10 Pc) is the label only.

## Team

*pending*
