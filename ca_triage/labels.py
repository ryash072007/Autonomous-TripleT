"""Official Challenge 1 event labels (dataset/challenge1_event_labels.xlsx, sheet train_event_labels, header on row 3)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from . import SEED
from .data import DATASET

PATH = DATASET / "challenge1_event_labels.xlsx"
TIER_INT = {"Safe": 0, "Elevated": 1, "Critical": 2}
N_SPLITS = 5


def load_official_labels() -> pd.DataFrame:
    """Event table indexed by event_id with `tier` (0/1/2) and boolean `usable`."""
    if not PATH.exists():
        raise FileNotFoundError(f"{PATH} missing: place the organisers label workbook in dataset/")
    d = pd.read_excel(PATH, sheet_name="train_event_labels", header=2)
    d["tier"] = d.final_tier.map(TIER_INT).astype(int)
    d["usable"] = d.usable_for_training.astype(str).str.lower().eq("yes")
    return d.set_index("event_id")


def official_tiers(lab: pd.DataFrame | None = None) -> pd.Series:
    lab = load_official_labels() if lab is None else lab
    return lab["tier"]


def official_splits(lab: pd.DataFrame | None = None, seed: int = SEED, n_splits: int = N_SPLITS):
    """Seeded stratified 5-fold split of the usable events by event_id: list of (train_ids, holdout_ids). Fold 0 = the 20% holdout."""
    lab = load_official_labels() if lab is None else lab
    u = lab[lab.usable].sort_index()
    ids = u.index.to_numpy()
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    return [(ids[a], ids[b]) for a, b in sgkf.split(np.zeros(len(ids)), u.tier.to_numpy(), groups=ids)]
