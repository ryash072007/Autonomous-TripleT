"""Features and LightGBM models for Task A (per CDM) and Task B (per event forecast)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import SEED
from .data import DECISION_CUTOFF_DAYS, FEATURE_COLUMNS
from .tiers import CRITICAL_MISS_M, ELEVATED_MISS_M, tier

OBJECT_TYPES = ["DEBRIS", "PAYLOAD", "ROCKET BODY", "TBA", "UNKNOWN"]
CLASS_WEIGHTS = {0: 1.0, 1: 2.0, 2: 6.0}

LGB_A = dict(objective="multiclass", num_class=3, n_estimators=300, learning_rate=0.05, num_leaves=31,
             min_child_samples=40, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
             random_state=SEED, verbose=-1, n_jobs=4)
LGB_B = dict(objective="multiclass", num_class=3, n_estimators=250, learning_rate=0.04, num_leaves=15,
             min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=2.0,
             random_state=SEED, verbose=-1, n_jobs=4)


def miss_tier(miss) -> np.ndarray:
    """Tier from the miss-distance branch only (exact part of the rule)."""
    m = np.asarray(miss, dtype=float)
    return np.where(m < CRITICAL_MISS_M, 2, np.where(m <= ELEVATED_MISS_M, 1, 0)).astype(int)


def _cat_code(s: pd.Series) -> np.ndarray:
    return pd.Categorical(s.astype(str), categories=OBJECT_TYPES).codes.astype(float)


PHYS_COLS = ["phys_log10_pc", "phys_log10_pc_max", "phys_dilution", "phys_fragile"]


TASK_A_PHYSICS = False  # D3 physics Pc features in the per-CDM model (see docs/EXPERIMENTS.md)


def cdm_features(df: pd.DataFrame, physics: bool | None = None) -> pd.DataFrame:
    """Per-CDM features from the allowed columns only (plus transforms of them)."""
    physics = TASK_A_PHYSICS if physics is None else physics
    X = df[FEATURE_COLUMNS].copy()
    X["c_object_type"] = _cat_code(df["c_object_type"])
    ls_c = np.log10(df["c_sigma_r"].astype(float).clip(lower=1e-3))
    ls_t = np.log10(df["t_sigma_r"].astype(float).clip(lower=1e-3))
    miss = df["miss_distance"].astype(float).clip(lower=1.0)
    rp = np.sqrt(df.relative_position_r**2 + df.relative_position_t**2 + df.relative_position_n**2)
    X["log_sigma_c"], X["log_sigma_t"] = ls_c, ls_t
    X["log_miss"] = np.log10(miss)
    X["rel_pos_norm"] = np.log10(rp.clip(lower=1.0))
    X["miss_over_sigma_c"] = np.log10(miss) - ls_c
    X["miss_over_sigma_t"] = np.log10(miss) - ls_t
    X["abs_r"], X["abs_t"], X["abs_n"] = df.relative_position_r.abs(), df.relative_position_t.abs(), df.relative_position_n.abs()
    X["mre_minus_logmiss"] = df["max_risk_estimate"] - np.log10(miss)
    X["miss_tier"] = miss_tier(df["miss_distance"])
    X["b0_tier"] = tier(df["max_risk_estimate"], df["miss_distance"])
    if physics:
        from .physics import fragility
        X = X.join(fragility(df))
    return X


def sample_weights(y) -> np.ndarray:
    return np.vectorize(CLASS_WEIGHTS.get)(np.asarray(y).astype(int)).astype(float)


def decide(proba: np.ndarray, t_crit: float, t_alert: float) -> np.ndarray:
    """Tier from probabilities: Critical if p2 >= t_crit; Elevated if p1+p2 >= t_alert."""
    return np.where(proba[:, 2] >= t_crit, 2, np.where(proba[:, 1] + proba[:, 2] >= t_alert, 1, 0)).astype(int)


def floor_by_miss(pred, miss) -> np.ndarray:
    return np.maximum(np.asarray(pred), miss_tier(miss))


# ---- Task B -----------------------------------------------------------------------------------

def _slope(t: np.ndarray, v: np.ndarray) -> float:
    ok = np.isfinite(v)
    if ok.sum() < 2 or np.ptp(t[ok]) < 1e-6:
        return 0.0
    return float(np.polyfit(t[ok], v[ok], 1)[0])


def event_features(df: pd.DataFrame, cutoff: float = DECISION_CUTOFF_DAYS, physics: bool = False) -> pd.DataFrame:
    """One row per event from CDMs with time_to_tca >= cutoff only. Index = event_id."""
    d = df[df.time_to_tca >= cutoff].copy()
    F = cdm_features(d, physics)
    F["event_id"] = d["event_id"].to_numpy()
    F["time_to_tca"] = d["time_to_tca"].to_numpy()
    order = np.lexsort((-F["time_to_tca"].to_numpy(), F["event_id"].to_numpy()))  # by event, tte descending
    F = F.iloc[order]
    series = ["log_miss", "max_risk_estimate", "log_sigma_c", "log_sigma_t", "b0_tier", "miss_tier", "relative_speed"]
    extra_last = []
    if physics:
        series += ["phys_log10_pc", "phys_log10_pc_max"]
        extra_last = PHYS_COLS
    rows = []
    for eid, g in F.groupby("event_id", sort=True):
        t = g["time_to_tca"].to_numpy()
        last = g.iloc[-1]
        r = {"event_id": eid, "n_cdms": len(g), "tte_last": last.time_to_tca, "tte_first": t[0],
             "span": t[0] - t[-1]}
        for c in FEATURE_COLUMNS + ["log_sigma_c", "log_sigma_t", "log_miss", "rel_pos_norm", "miss_over_sigma_c",
                                    "miss_over_sigma_t", "mre_minus_logmiss", "miss_tier", "b0_tier"] + extra_last:
            if c not in ("time_to_tca",):
                r[f"last_{c}"] = last[c]
        for c in series:
            v = g[c].to_numpy(dtype=float)
            r[f"min_{c}"], r[f"max_{c}"], r[f"mean_{c}"] = np.nanmin(v), np.nanmax(v), np.nanmean(v)
            r[f"slope_{c}"] = _slope(t, v)
            r[f"d1_{c}"] = v[-1] - v[-2] if len(v) >= 2 else 0.0
            r[f"first_{c}"] = v[0]
        if physics:
            r["n_fragile"] = float(g["phys_fragile"].sum())
        r["n_b0_critical"] = int((g["b0_tier"] == 2).sum())
        r["n_b0_alert"] = int((g["b0_tier"] >= 1).sum())
        r["tte_gap_last"] = t[-2] - t[-1] if len(t) >= 2 else 0.0
        rows.append(r)
    return pd.DataFrame(rows).set_index("event_id")
