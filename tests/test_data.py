import pytest

from ca_triage.data import ALLOWED_COLUMNS, DATASET, LABEL_COLUMN, load

pytestmark = pytest.mark.skipif(not (DATASET / "test_data.csv").exists(), reason="dataset not downloaded")


def test_only_allowed_columns_without_label():
    df = load("test", with_label=False)
    assert list(df.columns) == ALLOWED_COLUMNS
    assert LABEL_COLUMN not in df.columns


def test_test_split_is_beyond_decision_cutoff():
    df = load("test", with_label=False)
    assert df.time_to_tca.min() >= 2.0
