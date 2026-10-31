"""Out-of-distribution score for an event's latest CDM (isolation forest on allowed columns only)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from . import SEED

OOD_QUANTILE = 0.99  # threshold = this quantile of out-of-fold train scores


def ood_matrix(d: pd.DataFrame) -> np.ndarray:
    lg = lambda s: np.log10(np.clip(np.asarray(s, float), 1e-3, None))  # noqa: E731
    cols = [lg(d.miss_distance), lg(d.c_sigma_r.fillna(d.c_sigma_r.median() if d.c_sigma_r.notna().any() else 1.0)), lg(d.t_sigma_r),
            lg(d.relative_speed), d.max_risk_estimate.to_numpy(float), lg(d.relative_position_r.abs() + 1),
            lg(d.relative_position_t.abs() + 1), lg(d.relative_position_n.abs() + 1)]
    return np.column_stack(cols)


def fit_ood(d: pd.DataFrame) -> IsolationForest:
    return IsolationForest(n_estimators=200, random_state=SEED, n_jobs=4).fit(ood_matrix(d))


def ood_score(model: IsolationForest, d: pd.DataFrame) -> np.ndarray:
    """Higher = more unusual."""
    return -model.score_samples(ood_matrix(d))
