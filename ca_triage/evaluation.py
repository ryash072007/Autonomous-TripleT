"""Eval harness: grouped folds, metrics, evidence writer. Tier ints: 0 Safe, 1 Elevated, 2 Critical."""

from __future__ import annotations

import json
import subprocess
import sys
import time

import numpy as np
import pandas as pd

from . import SEED
from .data import DECISION_CUTOFF_DAYS, ROOT, file_sha256
from .tiers import tier

N_FOLDS = 5
EVIDENCE = ROOT / "artifacts" / "evidence"


def fold_of_events(event_ids, n_folds: int = N_FOLDS, seed: int = SEED) -> pd.Series:
    """Deterministic grouped fold id per event_id (shuffled, balanced by count)."""
    ids = np.array(sorted(pd.unique(event_ids)))
    perm = np.random.default_rng(seed).permutation(len(ids))
    return pd.Series(np.arange(len(ids))[np.argsort(perm)] % n_folds, index=ids)


def folds_for(df: pd.DataFrame) -> np.ndarray:
    return df["event_id"].map(fold_of_events(df["event_id"])).to_numpy()


def _f(x):
    x = float(x)
    return None if x != x else round(x, 5)


def metrics(y, pred, proba=None) -> dict:
    y = np.asarray(y).astype(int)
    pred = np.asarray(pred).astype(int)
    cm = np.zeros((3, 3), dtype=int)
    np.add.at(cm, (y, pred), 1)
    out: dict = {"n": int(len(y)), "confusion_matrix": cm.tolist(),
                 "confusion_axes": "rows=true, cols=pred, order Safe/Elevated/Critical"}
    f1s = []
    for k, name in enumerate(["safe", "elevated", "critical"]):
        tp = cm[k, k]
        p = tp / cm[:, k].sum() if cm[:, k].sum() else float("nan")
        r = tp / cm[k].sum() if cm[k].sum() else float("nan")
        f = 2 * p * r / (p + r) if p == p and r == r and (p + r) > 0 else 0.0
        out[f"{name}_precision"], out[f"{name}_recall"], out[f"{name}_f1"] = _f(p), _f(r), _f(f)
        f1s.append(f)
    out["macro_f1"] = _f(float(np.mean(f1s)))
    out["critical_missed"] = int(cm[2].sum() - cm[2, 2])
    out["critical_total"] = int(cm[2].sum())
    out["critical_flagged_critical"] = int(cm[:, 2].sum())
    alerts = int((pred >= 1).sum())
    out["alerts"] = alerts
    out["alerts_per_100"] = _f(100 * alerts / max(len(y), 1))
    out["safe_flagged_as_alert"] = int(cm[0, 1] + cm[0, 2])
    out["safe_false_alarm_rate"] = _f((cm[0, 1] + cm[0, 2]) / max(cm[0].sum(), 1))
    out["alert_recall"] = _f(cm[1:, 1:].sum() / max(cm[1:].sum(), 1))
    if proba is not None:
        proba = np.asarray(proba, dtype=float)
        onehot = np.eye(3)[y]
        out["brier_multiclass"] = _f(float(((proba - onehot) ** 2).sum(1).mean()))
        out["brier_critical"] = _f(float(((proba[:, 2] - (y == 2)) ** 2).mean()))
    return out


def mean_std(per_fold: list[dict], keys: list[str]) -> dict:
    out = {}
    for k in keys:
        v = np.array([m[k] for m in per_fold if m.get(k) is not None], dtype=float)
        out[k] = {"mean": _f(v.mean()), "std": _f(v.std(ddof=0)), "per_fold": [_f(x) for x in v]}
    return out


SUMMARY_KEYS = ["critical_recall", "critical_precision", "macro_f1", "elevated_f1", "safe_f1", "alerts_per_100",
                "safe_false_alarm_rate", "alert_recall", "critical_missed", "brier_critical"]


def cv_summary(y, pred, folds, proba=None, mask=None) -> dict:
    """Per-fold metrics (optionally restricted by `mask`) with mean/std, plus pooled metrics."""
    y, pred, folds = map(np.asarray, (y, pred, folds))
    mask = np.ones(len(y), bool) if mask is None else np.asarray(mask)
    pr = None if proba is None else np.asarray(proba)
    per = [metrics(y[(folds == f) & mask], pred[(folds == f) & mask],
                   None if pr is None else pr[(folds == f) & mask]) for f in sorted(set(folds))]
    keys = [k for k in SUMMARY_KEYS if k in per[0]]
    return {"folds": mean_std(per, keys), "pooled": metrics(y[mask], pred[mask], None if pr is None else pr[mask])}


# ---- Task B helpers -------------------------------------------------------------------------

def test_like_events(df: pd.DataFrame) -> pd.Series:
    """Events with a CDM at >= 2 d and a final CDM < 1 d before TCA (the ESA competition setup). Index = event_id."""
    g = df.groupby("event_id")["time_to_tca"]
    ok = (g.max() >= DECISION_CUTOFF_DAYS) & (g.min() < 1.0)
    return ok[ok].index.to_series()


def event_labels(df: pd.DataFrame) -> pd.Series:
    """Final tier per event: tier of the CDM with the smallest time_to_tca, from true risk and miss distance."""
    last = df.sort_values(["event_id", "time_to_tca"]).groupby("event_id").head(1).set_index("event_id")
    return pd.Series(tier(last["risk"], last["miss_distance"]), index=last.index)


# ---- evidence -------------------------------------------------------------------------------

def git_commit() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        return sha + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def write_evidence(name: str, payload: dict, splits=("train",)) -> str:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    doc = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "command": "python " + " ".join(sys.argv),
        "data_sha256": {s: file_sha256(s) for s in splits},
        "seed": SEED,
        **payload,
    }
    path = EVIDENCE / name
    path.write_text(json.dumps(doc, indent=1))
    return str(path)
