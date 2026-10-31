"""Encounter-plane Pc under stated assumptions (D3 / baseline B1).

Assumptions (all approximations, labelled as such in the UI):
- 2D Gaussian in the encounter plane with isotropic combined sigma s = sqrt(c_sigma_r^2 + t_sigma_r^2) (metres),
  centred on the miss distance; the full 3D covariance is not in the allowed columns.
- Combined hard-body radius R = 10 m.
Closed form: Pc = P(|X| <= R), X ~ N(mu, s^2 I2), |mu| = miss  =>  ncx2.cdf((R/s)^2, df=2, nc=(miss/s)^2).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ncx2

HARD_BODY_RADIUS_M = 10.0
K_GRID = np.logspace(-1, 1, 25)
FLOOR_LOG10 = -30.0
FRAGILE_PC_MIN = 1e-6


def combined_sigma(c_sigma_r, t_sigma_r) -> np.ndarray:
    return np.sqrt(np.asarray(c_sigma_r, float) ** 2 + np.asarray(t_sigma_r, float) ** 2)


def log10_pc(miss, s, R: float = HARD_BODY_RADIUS_M) -> np.ndarray:
    miss, s = np.broadcast_arrays(np.asarray(miss, float), np.asarray(s, float))
    ok = np.isfinite(miss) & np.isfinite(s) & (s > 0)
    out = np.full(miss.shape, FLOOR_LOG10)
    if ok.any():
        pc = ncx2.cdf((R / s[ok]) ** 2, df=2, nc=(miss[ok] / s[ok]) ** 2)
        out[ok] = np.log10(np.clip(pc, 1e-30, 1.0))
    return out


def fragility(df: pd.DataFrame) -> pd.DataFrame:
    """Per CDM: log10 Pc at k=1, log10 Pc_max over k in [0.1, 10], dilution flag, fragile flag."""
    s = combined_sigma(df["c_sigma_r"], df["t_sigma_r"])
    miss = df["miss_distance"].to_numpy(float)
    grid = np.stack([log10_pc(miss, s * k) for k in K_GRID], axis=1)
    pc1 = log10_pc(miss, s)
    lo, hi = log10_pc(miss, s * 0.95), log10_pc(miss, s * 1.05)
    dilution = hi < lo - 1e-9  # Pc falls as uncertainty grows
    pmax = grid.max(1)
    return pd.DataFrame({
        "phys_log10_pc": pc1, "phys_log10_pc_max": np.maximum(pmax, pc1),
        "phys_dilution": dilution.astype(float),
        "phys_fragile": (dilution & (np.maximum(pmax, pc1) >= np.log10(FRAGILE_PC_MIN))).astype(float),
    }, index=df.index)
