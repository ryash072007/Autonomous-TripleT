"""Consequence model driver (display and prioritisation only; never a model input).

    python scripts/fetch_population.py [--from-file saved_gp.json]   # once; population_by_altitude.json is committed
    python scripts/consequence.py                                     # -> artifacts/evidence/consequence.json

`event_consequences()` is also used by scripts/predict.py to write the `consequence` block into test_events.json.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ca_triage import SEED
from ca_triage.consequence import (CATASTROPHIC_J_PER_G, ROOT, cloud_offsets, consequence_score, ejected_mass, exposure_for, is_catastrophic,
                                   cloud_samples, load_consequence_inputs, load_population, mass_estimate, n_fragments, post_kick_extent, standard_samples)
from ca_triage.data import load
from ca_triage.display import load_display_orbits
from ca_triage.evaluation import write_evidence

CACHE = ROOT / "artifacts" / "cache" / "satcat.csv"
SATCAT_URL = "https://celestrak.org/pub/satcat.csv"

# Real break-ups, masses from public reporting (approximate; same inputs as the reference repo's validate.py).
VALIDATION = [
    {"event": "Iridium 33 / Cosmos 2251 (2009-02-10)", "prefixes": ["1997-051", "1993-036"], "m1": 560.0, "m2": 900.0, "v_rel_kms": 11.7,
     "note": "Iridium 33 ~560 kg + Cosmos 2251 ~900 kg, ~11.7 km/s"},
    {"event": "Fengyun-1C ASAT (2007-01-11)", "prefixes": ["1999-025"], "m1": 880.0, "m2": 600.0, "v_rel_kms": 9.0,
     "note": "target ~880 kg + kill vehicle ~600 kg (uncertain), ~9 km/s"},
    {"event": "Cosmos 1408 ASAT (2021-11-15)", "prefixes": ["1982-092"], "m1": 1750.0, "m2": None, "v_rel_kms": None,
     "note": "target ~1750 kg; interceptor mass unknown, treated as catastrophic with M = target mass"},
]


def validate() -> list[dict]:
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SATCAT_URL, headers={"User-Agent": "OrbitGuard-hackathon/0.1 (single request, research use)"})
        CACHE.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    df = pd.read_csv(CACHE, dtype=str, keep_default_na=False)
    rows = []
    for ev in VALIDATION:
        deb = df[df.OBJECT_TYPE.eq("DEB") & df.OBJECT_ID.str.startswith(tuple(ev["prefixes"]))]
        mass = ev["m1"] if ev["m2"] is None else ejected_mass(ev["m1"], ev["m2"], ev["v_rel_kms"])
        pred = n_fragments(mass)
        rows.append({"event": ev["event"], "ejected_mass_kg": mass, "predicted_ge10cm": round(pred), "catalogued_debris_all_time": len(deb),
                     "still_on_orbit": int((deb.DECAY_DATE == "").sum()), "ratio_pred_over_catalogued": round(pred / len(deb), 2) if len(deb) else None,
                     "inputs_note": ev["note"], "designator_prefixes": ev["prefixes"]})
    return rows


def latest_inputs(te: pd.DataFrame, disp: pd.DataFrame, cons: pd.DataFrame) -> pd.DataFrame:
    """Latest CDM per event with the display/consequence columns attached (row-aligned frames)."""
    j = te.assign(_i=np.arange(len(te)))
    last = j.sort_values(["event_id", "time_to_tca"]).groupby("event_id").head(1)
    i = last["_i"].to_numpy()
    out = last[["event_id", "relative_speed", "c_object_type", "max_risk_estimate"]].reset_index(drop=True)
    for c in ("t_rcs_estimate", "t_cd_area_over_mass", "c_rcs_estimate", "c_cd_area_over_mass"):
        out[c] = cons[c].to_numpy()[i]
    out["t_h_per"], out["t_h_apo"] = disp.t_h_per.to_numpy()[i], disp.t_h_apo.to_numpy()[i]
    return out.sort_values("event_id").reset_index(drop=True)


def event_consequences(latest: pd.DataFrame) -> dict[int, dict]:
    pop = load_population()
    counts = np.array(pop["counts"], float)
    dv, dirs = standard_samples(1500)
    out = {}
    for r in latest.itertuples(index=False):
        mt, st = mass_estimate(r.t_rcs_estimate, r.t_cd_area_over_mass, None, True)
        mc, sc = mass_estimate(r.c_rcs_estimate, r.c_cd_area_over_mass, r.c_object_type, False)
        v = float(r.relative_speed) / 1000.0
        cat = is_catastrophic(mt, mc, v)
        n = n_fragments(ejected_mass(mt, mc, v))
        alt = float(np.nanmean([r.t_h_per, r.t_h_apo])) if np.isfinite([r.t_h_per, r.t_h_apo]).any() else 700.0
        per, apo, _ = post_kick_extent(alt, dv, dirs)
        ex = exposure_for(alt, n, counts, per, apo)
        pc = 10.0 ** float(r.max_risk_estimate)
        out[int(r.event_id)] = {
            "mass_t": round(mt, 2), "mass_c": round(mc, 2), "mass_source": {"t": st, "c": sc}, "catastrophic": bool(cat),
            "fragments_10cm": int(round(n)), "collision_altitude_km": round(alt, 1), "band_km": ex["band_km"],
            "active_sats_in_band": ex["active_sats_in_band"], "exposure_30d": float(f"{ex['exposure_30d']:.4g}"),
            "consequence_score": round(consequence_score(ex["exposure_30d"]), 1),
            "pc_display": float(f"{pc:.4g}"), "expected_harm": float(f"{pc * ex['exposure_30d']:.4g}"),
        }
    ids = list(out)
    pcs = np.array([out[i]["pc_display"] for i in ids])
    harm = np.array([out[i]["expected_harm"] for i in ids])
    pr = (-pcs).argsort(kind="stable").argsort() + 1
    hr = (-harm).argsort(kind="stable").argsort() + 1
    for k, i in enumerate(ids):
        out[i]["pc_rank"], out[i]["harm_rank"] = int(pr[k]), int(hr[k])
    return out


def cloud_for(alt_km: float) -> dict:
    dv, dirs = cloud_samples(150)
    return cloud_offsets(alt_km, dv, dirs)


def q(x, ps=(5, 25, 50, 75, 95, 99)):
    return {f"p{p}": float(f"{np.percentile(x, p):.4g}") for p in ps}


def main() -> None:
    te = load("test")
    latest = latest_inputs(te, load_display_orbits("test"), load_consequence_inputs("test"))
    cons = event_consequences(latest)
    ids = np.array(list(cons))
    frag = np.array([cons[i]["fragments_10cm"] for i in ids])
    expo = np.array([cons[i]["exposure_30d"] for i in ids])
    score = np.array([cons[i]["consequence_score"] for i in ids])
    pr = np.array([cons[i]["pc_rank"] for i in ids])
    hr = np.array([cons[i]["harm_rank"] for i in ids])
    pcs = np.array([cons[i]["pc_display"] for i in ids])
    harm = np.array([cons[i]["expected_harm"] for i in ids])
    rho = float(spearmanr(pcs, harm).statistic)
    top20 = ids[np.argsort(pr)[:20]]
    moved = [int(i) for i in top20 if abs(cons[i]["pc_rank"] - cons[i]["harm_rank"]) >= 5]
    gain = pr - hr
    cand = np.where(hr <= 100)[0]
    best = cand[np.argsort(-gain[cand])[:5]]
    pop = load_population()
    src = pd.Series([cons[i]["mass_source"]["t"] for i in ids]).value_counts().to_dict()
    srcc = pd.Series([cons[i]["mass_source"]["c"] for i in ids]).value_counts().to_dict()
    res = {
        "DISPLAY_ONLY": "Consequence is for prioritisation and display. It is not an input to the tier model or the tier rule.",
        "assumptions": ["mass = rcs_estimate / cd_area_over_mass (factor 2-3 at best), clamped [0.05, 20000] kg, else fallback by object type",
                        "simplified NASA SBM, isotropic dv, circular orbit at the collision altitude, no drag/J2/re-entry",
                        "fragments phase-mixed over full spherical shells (ignores inclination confinement)",
                        "active satellites only (CelesTrak GP active), 10 m^2 cross-section, 10 km/s, 30 days",
                        "Pc = CDM max_risk_estimate (display only); loss of the two parents is not counted"],
        "breakup_validation": validate(),
        "breakup_validation_reading": "Order-of-magnitude check only; the catalogue is incomplete for >= 10 cm fragments and masses are approximate.",
        "population_table": {k: pop[k] for k in ("source", "kind", "retrieved_utc", "n_objects", "n_in_0_2000km", "band_km")},
        "mass_source_counts": {"target": src, "chaser": srcc},
        "catastrophic_share": round(float(np.mean([cons[i]["catastrophic"] for i in ids])), 4),
        "fragments_10cm_quantiles": q(frag), "exposure_30d_quantiles": q(expo), "consequence_score_quantiles": q(score),
        "pc_vs_harm": {"n_events": int(len(ids)), "spearman": round(rho, 4), "top20_by_pc_moving_5_or_more_places_by_harm": len(moved),
                       "top20_moved_event_ids": moved,
                       "top5_harm_much_higher_than_pc_rank": [
                           {"event_id": int(ids[k]), "pc_rank": int(pr[k]), "harm_rank": int(hr[k]), "pc_display": cons[int(ids[k])]["pc_display"],
                            "fragments_10cm": cons[int(ids[k])]["fragments_10cm"], "active_sats_in_band": cons[int(ids[k])]["active_sats_in_band"],
                            "exposure_30d": cons[int(ids[k])]["exposure_30d"], "collision_altitude_km": cons[int(ids[k])]["collision_altitude_km"]} for k in best],
                       "selection": "among events with harm_rank <= 100, largest pc_rank - harm_rank"},
    }
    print(write_evidence("consequence.json", res, splits=("test",)))
    print(json.dumps({k: res[k] for k in ("breakup_validation", "catastrophic_share", "fragments_10cm_quantiles", "exposure_30d_quantiles",
                                           "consequence_score_quantiles", "pc_vs_harm", "mass_source_counts")}, indent=1))


if __name__ == "__main__":
    main()
