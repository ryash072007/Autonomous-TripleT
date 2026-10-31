"""D4: train vs test drift audit + event-level OOD threshold -> artifacts/evidence/drift.json, artifacts/models/ood.joblib."""

from __future__ import annotations

import sys

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from train import build_b, oof_task_b  # noqa: E402

from ca_triage.data import DECISION_CUTOFF_DAYS, FEATURE_COLUMNS, ROOT, load
from ca_triage.evaluation import fold_of_events, write_evidence
from ca_triage.models import LGB_B, cdm_features, decide
from ca_triage.ood import OOD_QUANTILE, fit_ood, ood_matrix, ood_score
from ca_triage import SEED


def latest_early(df: pd.DataFrame) -> pd.DataFrame:
    return (df[df.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"])
            .groupby("event_id").head(1).set_index("event_id"))


def main() -> None:
    tr, te = load("train"), load("test")
    tr_e = tr[tr.time_to_tca >= DECISION_CUTOFF_DAYS]
    X = pd.concat([cdm_features(tr_e, False), cdm_features(te, False)], ignore_index=True)
    y = np.r_[np.zeros(len(tr_e)), np.ones(len(te))]
    groups = np.r_[tr_e.event_id.to_numpy(), te.event_id.to_numpy() + 1_000_000]  # test ids reuse train numbers
    params = dict(n_estimators=200, learning_rate=0.05, num_leaves=31, random_state=SEED, verbose=-1, n_jobs=4, is_unbalance=True)
    oof = np.zeros(len(y))
    aucs = []
    for a, b in GroupKFold(5).split(X, y, groups):
        m = lgb.LGBMClassifier(**params).fit(X.iloc[a], y[a])
        oof[b] = m.predict_proba(X.iloc[b])[:, 1]
        aucs.append(roc_auc_score(y[b], oof[b]))
    full = lgb.LGBMClassifier(**params, importance_type="gain").fit(X, y)
    imp = pd.Series(full.feature_importances_, X.columns)
    imp = (imp / imp.sum()).sort_values(ascending=False)
    # univariate shift on raw allowed columns
    ks = []
    for c in FEATURE_COLUMNS:
        if c == "c_object_type":
            continue
        a_, b_ = tr_e[c].dropna(), te[c].dropna()
        ks.append({"feature": c, "ks": round(float(ks_2samp(a_, b_).statistic), 4), "median_train": float(a_.median()), "median_test": float(b_.median())})
    ks.sort(key=lambda r: -r["ks"])
    obj = {"train": tr_e.c_object_type.value_counts(normalize=True).round(4).to_dict(), "test": te.c_object_type.value_counts(normalize=True).round(4).to_dict()}

    # event-level OOD: isolation forest on the latest CDM >= 2 d; threshold from out-of-fold train scores
    ltr, lte = latest_early(tr), latest_early(te.assign())
    fmap = fold_of_events(ltr.index)
    fl = ltr.index.to_series().map(fmap).to_numpy()
    sc = np.zeros(len(ltr))
    for k in range(5):
        sc[fl == k] = ood_score(fit_ood(ltr[fl != k]), ltr[fl == k])
    thr = float(np.quantile(sc, OOD_QUANTILE))
    model = fit_ood(ltr)
    (ROOT / "artifacts/models").mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "threshold": thr, "quantile": OOD_QUANTILE}, ROOT / "artifacts/models/ood.joblib")
    st = ood_score(model, lte)
    flagged_test = st > thr

    # is OOD harder? Task B Critical recall on train test-like events, OOD vs not (OOF scores)
    Xb, yb, fb, _, last = build_b(tr)
    ood_b = pd.Series(sc, index=ltr.index).reindex(Xb.index).to_numpy() > thr
    oofb = oof_task_b(Xb, yb, fb)
    pb = decide(oofb, 0.02, 0.1)
    def rec(mask):
        pos = (yb == 2) & mask
        return {"events": int(mask.sum()), "final_critical": int(pos.sum()), "critical_recall": round(float((pb[pos] == 2).mean()), 4) if pos.any() else None}
    res = {
        "adversarial_validation": {"auc_grouped_cv_mean": round(float(np.mean(aucs)), 4), "auc_std": round(float(np.std(aucs)), 4),
                                   "auc_per_fold": [round(a, 4) for a in aucs], "n_train_cdms_ge_2d": int(len(tr_e)), "n_test_cdms": int(len(te)),
                                   "reading": "0.5 = indistinguishable; higher = test differs from train on allowed columns",
                                   "top_features_by_gain": {k: round(float(v), 4) for k, v in imp.head(10).items()}},
        "univariate_shift_ks": ks, "object_type_share": obj,
        "event_ood": {"method": "IsolationForest on latest CDM >= 2 d (log miss, log sigmas, log speed, max_risk_estimate, log |rel pos|)",
                      "threshold_rule": f"{OOD_QUANTILE} quantile of out-of-fold train event scores", "threshold": round(thr, 5),
                      "train_events": int(len(ltr)), "test_events": int(len(lte)), "test_flagged": int(flagged_test.sum()),
                      "test_flagged_share": round(float(flagged_test.mean()), 4), "train_flagged_share_by_construction": round(1 - OOD_QUANTILE, 4),
                      "task_b_critical_recall_train_ood": rec(ood_b), "task_b_critical_recall_train_in_dist": rec(~ood_b)},
    }
    print(write_evidence("drift.json", res, splits=("train", "test")))
    print(res["adversarial_validation"], ks[:4], res["event_ood"])


if __name__ == "__main__":
    main()
