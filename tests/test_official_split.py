"""The official 80/20 holdout must never overlap the training part."""

import json

import pytest

from ca_triage.data import ROOT
from ca_triage.labels import PATH, load_official_labels, official_splits

pytestmark = pytest.mark.skipif(not PATH.exists(), reason="dataset/challenge1_event_labels.xlsx not present")


def test_holdout_disjoint_and_reproducible():
    lab = load_official_labels()
    usable = set(lab[lab.usable].index)
    assert len(usable) == 11942
    splits = official_splits(lab)
    seen = set()
    for train_ids, hold_ids in splits:
        assert not set(train_ids) & set(hold_ids)
        assert set(train_ids) | set(hold_ids) == usable
        assert not seen & set(hold_ids)
        seen |= set(hold_ids)
    assert seen == usable
    path = ROOT / "artifacts/evidence/official_holdout_ids.json"
    if path.exists():
        ids = json.loads(path.read_text())["holdout_event_ids"]
        assert set(ids) == set(splits[0][1]) and not set(ids) & set(splits[0][0])
