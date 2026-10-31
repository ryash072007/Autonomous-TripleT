"""Official evaluation: 80/20 split of train_data by event_id over the usable events (11,942), final tier from the
organisers label workbook, inputs = CDMs with time_to_tca >= 2 d only.

Writes artifacts/evidence/official_holdout.json and official_holdout_ids.json. Evaluation only: the shipped model, thresholds
and test predictions are not touched. Thresholds and the conformal lambda are chosen on the training part's inner OOF.
"""

from __future__ import annotations

import json
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from conformal import fit_ltt, sets_ltt  # noqa: E402

from ca_triage import SEED
from ca_triage.data import DECISION_CUTOFF_DAYS, ROOT, load
from ca_triage.evaluation import event_labels, fold_of_events, mean_std, metrics, test_like_events, write_evidence
from ca_triage.labels import load_official_labels, official_splits, official_tiers
from ca_triage.models import LGB_B, decide, event_features, sample_weights
from ca_triage.tiers import tier

CRIT_GRID = [0.5, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05, 0.03, 0.02]
ALERT_GRID = [0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.07, 0.05]


def inner_oof(X, y):
    f = fold_of_events(X.index, 5, SEED).reindex(X.index).to_numpy()
    oof = np.zeros((len(X), 3))
    for k in range(5):
        a = f != k
        m = lgb.LGBMClassifier(**LGB_B).fit(X[a], y[a], sample_weight=sample_weights(y[a]))
        oof[~a] = m.predict_proba(X[~a])
    return oof


def thresholds(oof, y):
    tc = CRIT_GRID[-1]
    for t in CRIT_GRID:
        if metrics(y, decide(oof, t, 0.5))["critical_recall"] >= 0.95:
            tc = t
            break
    ta = ALERT_GRID[-1]
    for t in ALERT_GRID:
        if metrics(y, decide(oof, tc, t))["alert_recall"] >= 0.95:
            ta = t
            break
    return tc, ta


def view(y, pred, proba, persist, b0, sets):
    out = {"events": int(len(y)), "label_counts": np.bincount(y, minlength=3).tolist(),
           "model": metrics(y, pred, proba), "persistence_observed_risk": metrics(y, persist), "b0_at_2d": metrics(y, b0)}
    crit = y == 2
    hit = sets[np.arange(len(y)), y]
    out["conformal_sets"] = {"critical_miss": round(float((~hit[crit]).mean()), 5) if crit.any() else None,
                             "critical_missed": int((~hit[crit]).sum()), "coverage": round(float(hit.mean()), 5),
                             "abstain_rate": round(float((sets.sum(1) > 1).mean()), 5)}
    return out


def run_split(train_ids, hold_ids, X_all, y_all, persist_all, b0_all, like_ids, train_on):
    if train_on == "test_like_subset":
        tr_ids = np.array(sorted(set(train_ids) & set(like_ids)))
    else:
        tr_ids = np.array(sorted(train_ids))
    Xtr, ytr = X_all.loc[tr_ids], y_all.loc[tr_ids].to_numpy()
    oof = inner_oof(Xtr, ytr)
    tc, ta = thresholds(oof, ytr)
    lam = fit_ltt(oof, ytr, 0.05)
    m = lgb.LGBMClassifier(**LGB_B).fit(Xtr, ytr, sample_weight=sample_weights(ytr))
    hid = np.array(sorted(hold_ids))
    P = m.predict_proba(X_all.loc[hid])
    pred = decide(P, tc, ta)
    S = sets_ltt(P, lam)
    S[np.arange(len(hid)), pred] = True
    y = y_all.loc[hid].to_numpy()
    pers, b0 = persist_all.loc[hid].to_numpy(), b0_all.loc[hid].to_numpy()
    sub = np.isin(hid, list(like_ids))
    return {"train_events": int(len(tr_ids)),
            "thresholds": {"t_critical": tc, "t_alert": ta, "conformal_lambda": lam, "chosen_on": "inner OOF of the training part"},
            "holdout_all_usable": view(y, pred, P, pers, b0, S),
            "holdout_test_like_subset": view(y[sub], pred[sub], P[sub], pers[sub], b0[sub], S[sub])}


def main() -> None:
    lab = load_official_labels()
    tr = load("train")
    ours = event_labels(tr)
    off = official_tiers(lab).reindex(ours.index)
    agree = float((ours == off).mean())
    assert agree == 1.0, f"official final_tier disagrees with ours on {1 - agree:.4%} of events"
    usable = lab[lab.usable].index
    d = tr[tr.event_id.isin(usable)]
    X = event_features(d)  # CDMs >= 2 d only
    y = official_tiers(lab).reindex(X.index)
    assert len(X) == len(usable) == 11942, (len(X), len(usable))
    last = (d[d.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"])
            .groupby("event_id").head(1).set_index("event_id").reindex(X.index))
    persist = pd.Series(tier(last.risk, last.miss_distance), index=X.index)
    b0 = pd.Series(tier(last.max_risk_estimate, last.miss_distance), index=X.index)
    like = set(test_like_events(tr).index) & set(X.index)

    splits = official_splits(lab)
    hold = splits[0][1]
    assert not set(splits[0][0]) & set(hold)
    (ROOT / "artifacts/evidence").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/evidence/official_holdout_ids.json").write_text(json.dumps({
        "seed": SEED, "split": "StratifiedGroupKFold(5, shuffle=True, random_state=42) over usable events, stratified by final tier; fold 0 is the holdout",
        "n_usable": int(len(usable)), "n_holdout": int(len(hold)), "holdout_event_ids": [int(i) for i in hold]}))

    res = {
        "label_check": {"events": int(len(ours)), "agreement_with_ours": agree, "source": "dataset/challenge1_event_labels.xlsx, sheet train_event_labels"},
        "population": {"usable_events": int(len(usable)), "test_like_subset_final_cdm_lt_1d": int(len(like)),
                       "note": "official view = all usable events; test-like subset (final CDM < 1 d) is the harder secondary view"},
        "shipped_model_note": "The shipped Task B model was trained on the 8,293 test-like events (final CDM < 1 d) because the ESA test events were built "
                              "that way. It is not retrained or changed here; this script retrains the same recipe on the 80% part only.",
    }
    primary = run_split(*splits[0], X, y, persist, b0, like, "test_like_subset")
    variant = run_split(*splits[0], X, y, persist, b0, like, "all_usable")
    res["holdout_20pct_shipped_recipe"] = primary
    res["holdout_20pct_trained_on_all_usable_80pct"] = variant
    folds = [run_split(a, b, X, y, persist, b0, like, "test_like_subset") for a, b in splits]
    keys = ["critical_recall", "critical_precision", "macro_f1", "alerts_per_100"]
    pops = ("holdout_all_usable", "holdout_test_like_subset")
    res["five_fold_shipped_recipe"] = {pop: {nm: mean_std([f[pop][nm] for f in folds], keys)
                                             for nm in ("model", "persistence_observed_risk", "b0_at_2d")} for pop in pops}
    res["five_fold_conformal"] = {pop: mean_std([f[pop]["conformal_sets"] for f in folds], ["critical_miss", "abstain_rate"]) for pop in pops}
    print(write_evidence("official_holdout.json", res, splits=("train",)))
    for tag, r in (("shipped recipe", primary), ("trained on all usable 80%", variant)):
        print("==", tag, r["thresholds"], "train events", r["train_events"])
        for pop in pops:
            v = r[pop]
            print(" ", pop, v["events"], v["label_counts"])
            for nm in ("model", "persistence_observed_risk", "b0_at_2d"):
                m = v[nm]
                print("   ", nm, "critR", m["critical_recall"], "critP", m["critical_precision"], "macroF1", m["macro_f1"],
                      "alerts/100", m["alerts_per_100"], "brierC", m.get("brier_critical"))
            print("    conformal", v["conformal_sets"])
    print(primary["holdout_all_usable"]["model"]["confusion_matrix"])
    print(primary["holdout_test_like_subset"]["model"]["confusion_matrix"])
    for pop in pops:
        print(pop, {nm: {k: (v["mean"], v["std"]) for k, v in res["five_fold_shipped_recipe"][pop][nm].items()} for nm in ("model", "persistence_observed_risk", "b0_at_2d")})
        print(pop, "conformal 5-fold", {k: (v["mean"], v["std"]) for k, v in res["five_fold_conformal"][pop].items()})


if __name__ == "__main__":
    main()
