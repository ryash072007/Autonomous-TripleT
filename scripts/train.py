"""S2/S3 cross-validation for Task A and Task B, then S4 final fit.

    python scripts/train.py cv-a      # -> artifacts/evidence/task_a_cv.json
    python scripts/train.py cv-b      # -> artifacts/evidence/task_b_cv.json
    python scripts/train.py final     # -> artifacts/models/*.joblib, artifacts/model_card.json
"""

from __future__ import annotations

import sys
import time

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from ca_triage import SEED
from ca_triage.data import DECISION_CUTOFF_DAYS, FEATURE_COLUMNS, ROOT, file_sha256, load
from ca_triage.evaluation import (cv_summary, event_labels, fold_of_events, folds_for, git_commit, metrics,
                                  test_like_events, write_evidence)
from ca_triage.models import (CLASS_WEIGHTS, LGB_A, LGB_B, cdm_features, decide, event_features, floor_by_miss,
                              sample_weights)
from ca_triage.tiers import tier

MODELS = ROOT / "artifacts" / "models"
RECALL_SLACK = 0.001  # Critical recall must stay within 0.1 pp of the baseline's
ALERT_RECALL_TARGET = 0.99  # Elevated-or-worse CDMs flagged; the Critical constraint is the strict one


def oof_task_a(tr: pd.DataFrame) -> np.ndarray:
    X, y, f = cdm_features(tr), tr.tier.to_numpy(), folds_for(tr)
    oof = np.zeros((len(tr), 3))
    for k in range(5):
        a = f != k
        m = lgb.LGBMClassifier(**LGB_A).fit(X[a], y[a], sample_weight=sample_weights(y[a]))
        oof[~a] = m.predict_proba(X[~a])
    return oof


def pick_thresholds_a(y, oof, miss, b0, mask) -> tuple[float, float, list]:
    """Largest thresholds (fewest alerts) that keep Critical recall within RECALL_SLACK of B0 and alert recall >= target,
    chosen on out-of-fold predictions of test-like CDMs (time_to_tca >= 2 d)."""
    base = metrics(y[mask], b0[mask])
    grid = [0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01, 0.007, 0.005, 0.003, 0.002, 0.001]
    tc = grid[-1]
    for t in grid:
        m = metrics(y[mask], floor_by_miss(decide(oof[mask], t, 0.5), miss[mask]))
        if m["critical_recall"] >= base["critical_recall"] - RECALL_SLACK:
            tc = t
            break
    curve = []
    ta = grid[-1]
    chosen = False
    for t in grid:
        m = metrics(y[mask], floor_by_miss(decide(oof[mask], tc, t), miss[mask]))
        curve.append({"t_alert": t, "alert_recall": m["alert_recall"], "alerts_per_100": m["alerts_per_100"]})
        if not chosen and m["alert_recall"] >= ALERT_RECALL_TARGET:
            ta, chosen = t, True
    return tc, ta, curve


def cv_a() -> None:
    tr = load("train")
    y, miss, f = tr.tier.to_numpy(), tr.miss_distance.to_numpy(), folds_for(tr)
    early = (tr.time_to_tca >= DECISION_CUTOFF_DAYS).to_numpy()
    b0 = tier(tr.max_risk_estimate, tr.miss_distance)
    oof = oof_task_a(tr)
    tc, ta, curve = pick_thresholds_a(y, oof, miss, b0, early)
    pred = floor_by_miss(decide(oof, tc, ta), miss)
    raw = decide(oof, 0.5, 0.5)
    res = {
        "task": "A: per-CDM tier",
        "model": "LightGBM multiclass + miss-distance floor",
        "params": LGB_A, "class_weights": CLASS_WEIGHTS,
        "thresholds": {"t_critical": tc, "t_alert": ta, "chosen_on": "OOF predictions, train CDMs with time_to_tca >= 2",
                       "rule": f"t_critical: largest keeping critical_recall >= B0 - {RECALL_SLACK}; t_alert: largest keeping alert_recall >= {ALERT_RECALL_TARGET}"},
        "alert_threshold_curve": curve,
        "model_floored_cdms_ge_2d": cv_summary(y, pred, f, proba=oof, mask=early),
        "model_floored_all_cdms": cv_summary(y, pred, f, proba=oof),
        "model_argmax_no_floor_cdms_ge_2d": cv_summary(y, oof.argmax(1), f, proba=oof, mask=early),
        "b0_cdms_ge_2d": cv_summary(y, b0, f, mask=early),
        "b0_all_cdms": cv_summary(y, b0, f),
        "note": "Brier is of the raw model probabilities (before the floor).",
    }
    print(write_evidence("task_a_cv.json", res))
    for k in ("model_floored_cdms_ge_2d", "b0_cdms_ge_2d"):
        p = res[k]["pooled"]
        fo = res[k]["folds"]
        print(k, "critR", p["critical_recall"], "missed", p["critical_missed"], "alerts/100", p["alerts_per_100"],
              "macroF1", fo["macro_f1"]["mean"], "+-", fo["macro_f1"]["std"], "safeFA", p["safe_false_alarm_rate"])
    print("thresholds", tc, ta)
    return


# ---- Task B -----------------------------------------------------------------------------------

def build_b(tr: pd.DataFrame):
    ev = test_like_events(tr)
    d = tr[tr.event_id.isin(ev.index)]
    X = event_features(d)
    y = event_labels(d).reindex(X.index)
    f = X.index.to_series().map(fold_of_events(tr.event_id)).to_numpy()
    # persistence: tier of last CDM >= 2 d from observed risk
    last = (d[d.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"])
            .groupby("event_id").head(1).set_index("event_id").reindex(X.index))
    persist = tier(last.risk, last.miss_distance)
    return X, y.to_numpy(), f, persist, last


def oof_task_b(X, y, f, params=LGB_B) -> np.ndarray:
    oof = np.zeros((len(X), 3))
    for k in range(5):
        a = f != k
        m = lgb.LGBMClassifier(**params).fit(X[a], y[a], sample_weight=sample_weights(y[a]))
        oof[~a] = m.predict_proba(X[~a])
    return oof


def recall_at_budget(y, score, n_flag, cls_ge) -> float:
    """Recall of events with y >= cls_ge when flagging the top n_flag events by score."""
    idx = np.argsort(-score, kind="stable")[:n_flag]
    flagged = np.zeros(len(y), bool)
    flagged[idx] = True
    pos = y >= cls_ge
    return float((flagged & pos).sum() / max(pos.sum(), 1))


def cv_b() -> None:
    tr = load("train")
    X, y, f, persist, last = build_b(tr)
    b0_2d = tier(last.max_risk_estimate, last.miss_distance)
    oof = oof_task_b(X, y, f)
    n = len(y)
    pers_alerts, pers_crit = int((persist >= 1).sum()), int((persist == 2).sum())
    budget = {
        "persistence": {"alerts": pers_alerts, "critical_flags": pers_crit,
                        "critical_recall": float(((persist == 2) & (y == 2)).sum() / (y == 2).sum()),
                        "alert_recall": float(((persist >= 1) & (y >= 1)).sum() / (y >= 1).sum())},
        "model_at_persistence_critical_budget": {"critical_flags": pers_crit,
                                                 "critical_recall": recall_at_budget(y, oof[:, 2], pers_crit, 2)},
        "b0_at_2d": {"alerts": int((b0_2d >= 1).sum()), "critical_flags": int((b0_2d == 2).sum()),
                     "critical_recall": float(((b0_2d == 2) & (y == 2)).sum() / (y == 2).sum())},
        "model_at_b0_critical_budget": {"critical_flags": int((b0_2d == 2).sum()),
                                        "critical_recall": recall_at_budget(y, oof[:, 2], int((b0_2d == 2).sum()), 2)},
        "model_at_persistence_alert_budget": {"alerts": pers_alerts,
                                              "alert_recall": recall_at_budget(y, oof[:, 1] + oof[:, 2], pers_alerts, 1)},
    }
    # operating points: Critical flagged if p2 >= t; report the recall/flag curve
    curve = []
    for t in [0.5, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02]:
        pr = decide(oof, t, 0.5)
        m = metrics(y, pr, oof)
        curve.append({"t_critical": t, "critical_recall": m["critical_recall"], "critical_flags": int((pr == 2).sum()),
                      "critical_precision": m["critical_precision"], "alerts_per_100": m["alerts_per_100"],
                      "macro_f1": m["macro_f1"]})
    # operating point: smallest flag count reaching persistence's Critical recall + 0.1 pp slack is not possible
    # if the model is worse; pick the threshold where Critical recall >= 0.95 (recall first) and report cost.
    tc = next((c["t_critical"] for c in curve if c["critical_recall"] is not None and c["critical_recall"] >= 0.95), curve[-1]["t_critical"])
    for c in curve:
        c["selected_on_oof"] = c["t_critical"] == tc
    ta_curve = []
    ta = 0.5
    for t in [0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05]:
        pr = decide(oof, tc, t)
        m = metrics(y, pr)
        ta_curve.append({"t_alert": t, "alert_recall": m["alert_recall"], "alerts_per_100": m["alerts_per_100"]})
    ta = next((c["t_alert"] for c in ta_curve if c["alert_recall"] >= 0.95), ta_curve[-1]["t_alert"])
    pred = decide(oof, tc, ta)
    res = {
        "task": "B: forecast final tier at TCA from CDMs with time_to_tca >= 2 d",
        "n_events": n, "label_counts": np.bincount(y, minlength=3).tolist(),
        "params": LGB_B, "n_features": X.shape[1], "features": list(X.columns),
        "thresholds": {"t_critical": tc, "t_alert": ta, "rule": "largest threshold with OOF Critical recall >= 0.95 / alert recall >= 0.95"},
        "model": cv_summary(y, pred, f, proba=oof),
        "model_argmax": cv_summary(y, oof.argmax(1), f, proba=oof),
        "persistence_true_risk": cv_summary(y, persist, f),
        "b0_at_2d": cv_summary(y, b0_2d, f),
        "equal_budget": budget,
        "critical_curve": curve, "alert_curve": ta_curve,
        "selected_point_note": ("The recall-first point (selected_on_oof = true) was chosen on the OOF predictions themselves (first grid threshold with "
                                "OOF Critical recall >= 0.95, else the most permissive one, here 0.02 at 0.949), so its CV recall is by construction, "
                                "not an independent estimate."),
    }
    print(write_evidence("task_b_cv.json", res))
    for k in ("model", "persistence_true_risk", "b0_at_2d"):
        p, fo = res[k]["pooled"], res[k]["folds"]
        print(k, "critR", p["critical_recall"], "missed", p["critical_missed"], "alerts/100", p["alerts_per_100"],
              "critPrec", p["critical_precision"], "macroF1", fo["macro_f1"]["mean"], "+-", fo["macro_f1"]["std"])
    print(budget)
    print("thresholds", tc, ta)


# ---- final fit --------------------------------------------------------------------------------

def prediction_reference(ma, mb, X, Xb) -> dict:
    """Probabilities on a fixed sample of rows. LightGBM pickles are not byte-reproducible across runs (n_jobs > 1), so a
    frozen card also stores these to check that a retrained model is the same model to within 1e-6."""
    ra = np.arange(0, len(X), 800)
    rb = np.arange(0, len(Xb), 40)
    return {"tolerance": 1e-6,
            "task_a": {"rows": ra.tolist(), "p": np.round(ma.predict_proba(X.iloc[ra]), 8).tolist()},
            "task_b": {"rows": rb.tolist(), "p": np.round(mb.predict_proba(Xb.iloc[rb]), 8).tolist()}}


def same_predictions(ref: dict, new: dict) -> bool:
    return all(np.abs(np.array(ref[k]["p"]) - np.array(new[k]["p"])).max() <= ref["tolerance"] for k in ("task_a", "task_b"))


def final() -> None:
    import json
    tr = load("train")
    ev_a = json.loads((ROOT / "artifacts/evidence/task_a_cv.json").read_text())
    ev_b = json.loads((ROOT / "artifacts/evidence/task_b_cv.json").read_text())
    MODELS.mkdir(parents=True, exist_ok=True)
    X = cdm_features(tr)
    y = tr.tier.to_numpy()
    ma = lgb.LGBMClassifier(**LGB_A).fit(X, y, sample_weight=sample_weights(y))
    Xb, yb, _, _, _ = build_b(tr)
    mb = lgb.LGBMClassifier(**LGB_B).fit(Xb, yb, sample_weight=sample_weights(yb))
    card_path = ROOT / "artifacts" / "model_card.json"
    old = json.loads(card_path.read_text()) if card_path.exists() else {}
    tmp = MODELS / "_new"
    tmp.mkdir(exist_ok=True)
    joblib.dump(ma, tmp / "task_a.joblib")
    joblib.dump(mb, tmp / "task_b.joblib")
    new_hash = {n: file_sha256_of(tmp / n) for n in ("task_a.joblib", "task_b.joblib")}
    if old.get("frozen"):
        want = {n: old.get("model_files_sha256", {}).get(n) for n in new_hash}
        ref = old.get("prediction_reference")
        equivalent = ref is not None and same_predictions(ref, prediction_reference(ma, mb, X, Xb))
        if new_hash != want and equivalent:
            print("retrained model bytes differ from the card but predictions match the frozen reference to 1e-6 (LightGBM pickles are not byte-reproducible)")
        elif new_hash != want:
            for f in tmp.iterdir():
                f.unlink()
            tmp.rmdir()
            sys.exit(f"refusing to overwrite frozen models: retrained hashes {new_hash} differ from model_card.json {want}")
    for n in new_hash:
        (MODELS / n).write_bytes((tmp / n).read_bytes())
        (tmp / n).unlink()
    tmp.rmdir()
    thr = {"a": ev_a["thresholds"], "b": ev_b["thresholds"]}
    (MODELS / "thresholds.json").write_text(json.dumps(thr, indent=1))
    version = file_sha256_of(MODELS / "task_a.joblib")[:12] + "-" + file_sha256_of(MODELS / "task_b.joblib")[:12]
    card = {
        "name": "OrbitGuard LightGBM tier models",
        "version": version,
        "trained_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "command": "python scripts/train.py final",
        "data_sha256": {"train": file_sha256("train")},
        "seed": SEED,
        "task_a": {"features_raw": FEATURE_COLUMNS, "features_model": list(X.columns), "params": LGB_A,
                   "class_weights": CLASS_WEIGHTS, "thresholds": ev_a["thresholds"],
                   "floor": "final tier = max(model tier, miss-distance-only tier)",
                   "cv_cdms_ge_2d": ev_a["model_floored_cdms_ge_2d"]["folds"], "cv_evidence": "artifacts/evidence/task_a_cv.json"},
        "task_b": {"features_model": list(Xb.columns), "params": LGB_B, "thresholds": ev_b["thresholds"],
                   "n_train_events": int(len(Xb)), "cv": ev_b["model"]["folds"], "cv_evidence": "artifacts/evidence/task_b_cv.json"},
        "allowed_columns_only": True,
        "released_test_labels_opened": False,
    }
    if old.get("frozen"):  # identical models: keep the frozen card (frozen, labels_opened and timestamps) untouched
        print("frozen card left unchanged (retrained version label", version)
        return
    card_path.write_text(json.dumps(card, indent=1))
    print("models + model_card.json written; version", version)


def file_sha256_of(path) -> str:
    import hashlib
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


if __name__ == "__main__":
    {"cv-a": cv_a, "cv-b": cv_b, "final": final}[sys.argv[1]]()
