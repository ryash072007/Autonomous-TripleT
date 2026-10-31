"""Display-only orbital elements for the globe and Insights page.

WARNING: these columns (t_*/c_* j2k elements and perigee/apogee heights) are NOT in ALLOWED_COLUMNS. They must never
reach a model, a feature function or a drift/OOD score. Only the API/UI payload and insights.json read them.
Units in the ESA data: sma in km, ecc dimensionless, inc in degrees, h_apo/h_per are altitudes in km.
"""

from __future__ import annotations

import pandas as pd

from .data import DATASET

_SRC = {"sma_km": "j2k_sma", "ecc": "j2k_ecc", "inc_deg": "j2k_inc", "h_apo_km": "h_apo", "h_per_km": "h_per"}
DISPLAY_COLUMNS = [f"{o}_{s}" for o in ("t", "c") for s in _SRC.values()]


def load_display_orbits(split: str) -> pd.DataFrame:
    """Row-aligned frame with event_id, time_to_tca and the display columns (named like the CSV)."""
    return pd.read_csv(DATASET / f"{split}_data.csv", usecols=["event_id", "time_to_tca"] + DISPLAY_COLUMNS)


def orbit_block(row) -> dict:
    """{'t': {...}, 'c': {...}} for one row of load_display_orbits()."""
    def one(o):
        return {k: (None if pd.isna(row[f"{o}_{v}"]) else round(float(row[f"{o}_{v}"]), 6)) for k, v in _SRC.items()}
    return {"t": one("t"), "c": one("c")}
