"""Shape checks for the organisers' files. They fail loudly if a regenerated submission is malformed."""

import pandas as pd

from ca_triage.data import ROOT

N_TEST_CDMS = 24_484
COLS = ["row", "event_id", "time_to_tca", "tier_pred", "tier_name", "p_safe", "p_elevated", "p_critical", "rule"]


def test_test_predictions_shape():
    df = pd.read_csv(ROOT / "submission/test_predictions.csv")
    assert len(df) == N_TEST_CDMS
    assert list(df.columns) == COLS
    assert (df["row"].to_numpy() == range(N_TEST_CDMS)).all()
    assert set(df.tier_pred.unique()) <= {0, 1, 2}
    assert df[["p_safe", "p_elevated", "p_critical"]].notna().all().all()
    assert ((df[["p_safe", "p_elevated", "p_critical"]].sum(axis=1) - 1).abs() < 1e-3).all()
    assert df.rule.notna().all()
    # probabilities and tier agree on the exact miss-distance floor: a Critical call is never below P(Critical) 0
    assert (df.loc[df.tier_pred == 2, "p_critical"] > 0).all()


def test_event_forecasts_shape():
    f = pd.read_csv(ROOT / "submission/test_event_forecasts.csv")
    p = pd.read_csv(ROOT / "submission/test_predictions.csv")
    assert list(f.columns) == ["event_id", "forecast_tier_at_tca", "p_safe", "p_elevated", "p_critical"]
    assert set(f.event_id) == set(p.event_id) and f.event_id.is_unique
    assert set(f.forecast_tier_at_tca.unique()) <= {0, 1, 2}
    assert ((f[["p_safe", "p_elevated", "p_critical"]].sum(axis=1) - 1).abs() < 1e-3).all()
