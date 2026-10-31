"""Loading the ESA Collision Avoidance Challenge CDMs, restricted to the columns the organisers allow."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from .tiers import tier

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"

# Model inputs permitted by the problem statement. `event_id` is a group key, not a feature.
ALLOWED_COLUMNS = [
    "event_id",
    "time_to_tca",
    "miss_distance",
    "relative_speed",
    "relative_position_r",
    "relative_position_t",
    "relative_position_n",
    "c_object_type",
    "c_sigma_r",
    "t_sigma_r",
    "max_risk_estimate",
    "F10",
    "AP",
]
FEATURE_COLUMNS = [c for c in ALLOWED_COLUMNS if c != "event_id"]
LABEL_COLUMN = "risk"

# Days before TCA by which the manoeuvre decision is made; every test CDM is at or beyond it.
DECISION_CUTOFF_DAYS = 2.0


def load(split: str, with_label: bool = True) -> pd.DataFrame:
    """Read `train` or `test` with only the allowed columns (plus `risk` when asked) and a `tier` label."""
    if split not in {"train", "test"}:
        raise ValueError("split must be 'train' or 'test'")
    path = DATASET / f"{split}_data.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run `python scripts/fetch_data.py`")
    cols = ALLOWED_COLUMNS + ([LABEL_COLUMN] if with_label else [])
    df = pd.read_csv(path, usecols=cols)[cols]
    df["c_object_type"] = df["c_object_type"].astype("category")
    if with_label:
        df["tier"] = tier(df[LABEL_COLUMN], df["miss_distance"])
    return df


def file_sha256(split: str) -> str:
    h = hashlib.sha256()
    with open(DATASET / f"{split}_data.csv", "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
