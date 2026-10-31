"""D6: model sensitivity of the tier to the latest CDM's miss distance and max_risk_estimate.

This is how the frozen Task A model + miss floor would answer if one input changed. It is NOT physics and NOT a
causal statement about the encounter.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .models import cdm_features, decide, floor_by_miss

MISS_FACTORS = np.round(np.exp(np.linspace(np.log(0.5), np.log(2.0), 31)), 4)
MISS_FACTORS = MISS_FACTORS[np.abs(np.log(MISS_FACTORS)) > 1e-6]
MRE_DELTAS = np.round(np.arange(-2.0, 2.0001, 0.1), 2)
MRE_DELTAS = MRE_DELTAS[np.abs(MRE_DELTAS) > 1e-9]
NOTE = ("Model sensitivity: the smallest single-input change (miss distance x0.5..x2, or max_risk_estimate +-2 in log10) that moves the "
        "frozen Task A tier down/up. Not physics, not causal.")


def _candidates():
    """(feature, factor_or_delta, size) sorted by relative size; size = |log2 factor| for miss, |delta|/2 for mre."""
    c = [("miss_distance", float(f), abs(np.log2(f))) for f in MISS_FACTORS] + [("max_risk_estimate", float(d), abs(d) / 2) for d in MRE_DELTAS]
    return sorted(c, key=lambda t: t[2])


def sensitivity(model, latest: pd.DataFrame, t_crit: float, t_alert: float, current: np.ndarray) -> list[dict]:
    cands = _candidates()
    n, k = len(latest), len(cands)
    rep = latest.loc[latest.index.repeat(k)].copy()
    feat = np.tile([c[0] for c in cands], n)
    val = np.tile([c[1] for c in cands], n)
    miss0, mre0 = rep.miss_distance.to_numpy(float), rep.max_risk_estimate.to_numpy(float)
    rep["miss_distance"] = np.where(feat == "miss_distance", miss0 * val, miss0)
    rep["max_risk_estimate"] = np.where(feat == "max_risk_estimate", mre0 + val, mre0)
    P = model.predict_proba(cdm_features(rep))
    tiers = floor_by_miss(decide(P, t_crit, t_alert), rep.miss_distance.to_numpy()).reshape(n, k)
    out = []
    for i in range(n):
        res = {"note": None}
        for name, ok in (("down", tiers[i] < current[i]), ("up", tiers[i] > current[i])):
            hit = np.where(ok)[0]
            if len(hit) == 0:
                res[name] = None
                continue
            j = hit[0]  # candidates are ordered by size
            f, v, _ = cands[j]
            frm = float(latest.iloc[i][f])
            to = frm * v if f == "miss_distance" else frm + v
            res[name] = {"feature": f, "from": round(frm, 3), "to": round(float(to), 3), "tier": int(tiers[i, j])}
        del res["note"]
        out.append(res)
    return out
