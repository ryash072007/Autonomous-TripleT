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


def test_consequence_columns_never_reach_models():
    from pathlib import Path

    from ca_triage import consequence
    from ca_triage.data import ALLOWED_COLUMNS
    banned = set(consequence.INPUT_COLUMNS) - {"event_id", "time_to_tca"}
    assert banned.isdisjoint(ALLOWED_COLUMNS)
    X, E = cdm_features(_frame()), event_features(_frame())
    for c in list(X.columns) + list(E.columns):
        assert not any(k in c for k in ("rcs", "area_over_mass", "mass_", "consequence", "harm", "exposure", "fragments"))
    root = Path(__file__).resolve().parents[1]
    for f in ("ca_triage/models.py", "ca_triage/data.py", "ca_triage/tiers.py", "ca_triage/evaluation.py", "ca_triage/ood.py", "scripts/train.py"):
        assert "consequence" not in (root / f).read_text().lower(), f


def test_breakup_basics():
    from ca_triage.consequence import is_catastrophic, mass_estimate, n_fragments
    assert is_catastrophic(5.0, 500.0, 12.0) and not is_catastrophic(0.01, 500.0, 0.5)
    assert mass_estimate(float("nan"), 0.1, "ROCKET BODY", False) == (1500.0, "fallback:rocket body")
    assert mass_estimate(1.0, 0.01, "DEBRIS", True)[1] == "rcs/area"
    assert n_fragments(1000.0) > n_fragments(10.0) > 0


def test_debris_cloud_is_bounded_and_wraps():
    import numpy as np

    from ca_triage.consequence import cloud_offsets, cloud_samples
    dv, dirs = cloud_samples(150)
    assert len(dv) == 150 and dv.max() <= 0.5
    for alt in (350.0, 550.0, 800.0, 1400.0):
        c = cloud_offsets(alt, dv, dirs)
        arr = np.array(c["offsets"], float)  # (times, fragments, 3)
        assert np.abs(arr[:, :, 1]).max() < 2000, "radial offset must stay bounded (CW linear motion)"
        assert np.abs(arr[:, :, 2]).max() < 2000
        assert np.abs(arr[:, :, 0]).max() <= np.pi + 1e-6
    assert np.allclose(np.array(cloud_offsets(550.0, dv, dirs)["offsets"][0]), 0)  # t = 0: all at the collision point
    spread = lambda h: np.ptp(np.array(cloud_offsets(550.0, dv, dirs, hours=(h,))["offsets"][0], float)[:, 0])  # noqa: E731
    assert spread(168) > spread(1)  # the cloud smears along the ring
