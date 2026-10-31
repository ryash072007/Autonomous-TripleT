"""Task B experiments (not part of the shipped path). Prints Critical recall at the persistence Critical-flag budget.

    python scripts/exp_task_b.py stack   # add nested-OOF Task A probabilities of the early CDMs as event features
    python scripts/exp_task_b.py nobias  # train on all events with a CDM >= 2 d (not only test-like ones)
"""

from __future__ import annotations

import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from train import build_b, oof_task_b, recall_at_budget  # noqa: E402

from ca_triage.data import DECISION_CUTOFF_DAYS, load
from ca_triage.evaluation import event_labels, fold_of_events, folds_for
from ca_triage.models import LGB_A, LGB_B, cdm_features, event_features, sample_weights
from ca_triage.tiers import tier


def a_probs_event_feats(tr, X, train_ev_ids, apply_ev_ids, inner_seed):
    """Task A probabilities on early CDMs -> per-event features. Events in `train_ev_ids` get inner-OOF probs,
    events in `apply_ev_ids` get probs from a model fit on all of `train_ev_ids`."""
    d = tr[(tr.time_to_tca >= DECISION_CUTOFF_DAYS)]
    inner = fold_of_events(train_ev_ids, 4, inner_seed)
    P = np.zeros((len(tr), 3))
    is_tr = tr.event_id.isin(train_ev_ids).to_numpy()
    fold = tr.event_id.map(inner).to_numpy()
    y = tr.tier.to_numpy()
    for k in range(4):
        fit = is_tr & (fold != k)
        pred = is_tr & (fold == k)
        m = lgb.LGBMClassifier(**{**LGB_A, "n_estimators": 150}).fit(X[fit], y[fit], sample_weight=sample_weights(y[fit]))
        P[pred] = m.predict_proba(X[pred])
    m = lgb.LGBMClassifier(**{**LGB_A, "n_estimators": 150}).fit(X[is_tr], y[is_tr], sample_weight=sample_weights(y[is_tr]))
    app = tr.event_id.isin(apply_ev_ids).to_numpy()
    P[app] = m.predict_proba(X[app])
    keep = (is_tr | app) & (tr.time_to_tca >= DECISION_CUTOFF_DAYS).to_numpy()
    q = pd.DataFrame({"event_id": tr.event_id[keep].to_numpy(), "tte": tr.time_to_tca[keep].to_numpy(),
                      "pc": P[keep, 2], "pa": P[keep, 1] + P[keep, 2]}).sort_values(["event_id", "tte"], ascending=[True, False])
    g = q.groupby("event_id")
    out = pd.DataFrame({"a_last_pc": g.pc.last(), "a_last_pa": g.pa.last(), "a_max_pc": g.pc.max(), "a_max_pa": g.pa.max(),
                        "a_mean_pc": g.pc.mean(), "a_first_pc": g.pc.first()})
    return out


def main(mode: str) -> None:
    tr = load("train")
    X, y, f, persist, last = build_b(tr)
    pers_crit = int((persist == 2).sum())
    base = oof_task_b(X, y, f)
    print("baseline model recall@persistence critical budget", recall_at_budget(y, base[:, 2], pers_crit, 2))
    if mode == "stack":
        Xc = cdm_features(tr)
        oof = np.zeros((len(X), 3))
        all_ids = tr.event_id.unique()
        for k in range(5):
            tr_ids = X.index[f != k]
            te_ids = X.index[f == k]
            # A trained on all train events outside fold k, evaluated on fold k; inner OOF for the training events
            fe = a_probs_event_feats(tr, Xc, pd.Index(np.setdiff1d(all_ids, te_ids)), te_ids, 100 + k)
            Xs = X.join(fe)
            a = f != k
            m = lgb.LGBMClassifier(**LGB_B).fit(Xs[a], y[a], sample_weight=sample_weights(y[a]))
            oof[~a] = m.predict_proba(Xs[~a])
            print("fold", k, flush=True)
        print("stack recall@persistence critical budget", recall_at_budget(y, oof[:, 2], pers_crit, 2))
        print("stack alert recall@persistence alert budget", recall_at_budget(y, oof[:, 1] + oof[:, 2], int((persist >= 1).sum()), 1))


if __name__ == "__main__":
    main(sys.argv[1])
