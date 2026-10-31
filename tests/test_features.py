"""No display-only or non-allowed column may reach a model feature list."""

import pandas as pd

from ca_triage.data import ALLOWED_COLUMNS, FEATURE_COLUMNS
from ca_triage.display import DISPLAY_COLUMNS
from ca_triage.models import cdm_features, event_features

N = 40


def _frame() -> pd.DataFrame:
    import numpy as np
    r = np.random.default_rng(0)
    d = pd.DataFrame({"event_id": np.repeat(np.arange(4), N // 4), "time_to_tca": np.tile(np.linspace(6, 2, N // 4), 4),
                      "miss_distance": r.uniform(10, 5e4, N), "relative_speed": r.uniform(1e3, 1.5e4, N)})
    for c in ("relative_position_r", "relative_position_t", "relative_position_n"):
        d[c] = r.normal(0, 1e3, N)
    d["c_object_type"] = "DEBRIS"
    d["c_sigma_r"], d["t_sigma_r"] = r.uniform(1, 1e3, N), r.uniform(1, 10, N)
    d["max_risk_estimate"] = r.uniform(-9, -3, N)
    d["F10"], d["AP"] = 70.0, 5.0
    return d


def test_cdm_features_start_with_feature_columns_and_exclude_display():
    X = cdm_features(_frame())
    assert list(X.columns[: len(FEATURE_COLUMNS)]) == FEATURE_COLUMNS
    assert not set(DISPLAY_COLUMNS) & set(X.columns)
    assert not any(k in c for c in X.columns for k in ("j2k", "h_apo", "h_per", "risk_label"))


def test_event_features_exclude_display_and_label():
    E = event_features(_frame())
    assert not any(k in c for c in E.columns for k in ("j2k", "h_apo", "h_per", "true_risk")) and "risk" not in E.columns
    assert set(ALLOWED_COLUMNS).isdisjoint(DISPLAY_COLUMNS)
