"""D3: covariance-fragility experiment -> artifacts/evidence/fragility.json.

Does adding physics Pc features help Task B (Critical recall at the persistence budget)? Is the fragile flag
informative about the final tier?
"""

from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from train import oof_task_b, recall_at_budget  # noqa: E402

from ca_triage.data import DECISION_CUTOFF_DAYS, load
from ca_triage.evaluation import event_labels, fold_of_events, test_like_events, write_evidence
from ca_triage.models import event_features
from ca_triage.physics import FRAGILE_PC_MIN, HARD_BODY_RADIUS_M, K_GRID, fragility
from ca_triage.tiers import tier


def main() -> None:
    tr = load("train")
    te = load("test")
    ev = test_like_events(tr)
    d = tr[tr.event_id.isin(ev.index)]
    y_all = event_labels(d)
    f_map = fold_of_events(tr.event_id)
    last = (d[d.time_to_tca >= DECISION_CUTOFF_DAYS].sort_values(["event_id", "time_to_tca"])
            .groupby("event_id").head(1).set_index("event_id"))
    res = {"assumptions": f"isotropic Gaussian, s = sqrt(c_sigma_r^2 + t_sigma_r^2), R = {HARD_BODY_RADIUS_M} m, k in [0.1, 10] x25, "
                          f"fragile = dPc/dk < 0 at k=1 and Pc_max >= {FRAGILE_PC_MIN}"}
    out = {}
    for name, ph in (("without_physics", False), ("with_physics", True)):
        X = event_features(d, physics=ph)
        y = y_all.reindex(X.index).to_numpy()
        f = X.index.to_series().map(f_map).to_numpy()
        lt = last.reindex(X.index)
        pers = tier(lt.risk, lt.miss_distance)
        oof = oof_task_b(X, y, f)
        per_fold = []
        for k in range(5):
            m = f == k
            budget = int(round((pers == 2).sum() * m.mean()))
            per_fold.append(recall_at_budget(y[m], oof[m, 2], budget, 2))
        out[name] = {"n_features": int(X.shape[1]),
                     "critical_recall_at_persistence_budget_pooled": round(recall_at_budget(y, oof[:, 2], int((pers == 2).sum()), 2), 5),
                     "per_fold": [round(v, 4) for v in per_fold], "mean": round(float(np.mean(per_fold)), 4), "std": round(float(np.std(per_fold)), 4)}
    res["task_b_features_experiment"] = out
    # informativeness of the flag on the latest CDM >= 2 d
    fr = fragility(last.reset_index())
    flag = fr.phys_fragile.to_numpy() > 0
    yy = y_all.reindex(last.index).to_numpy()
    res["flag_vs_final_tier"] = {
        "fragile_events": int(flag.sum()), "events": int(len(flag)),
        "p_final_critical_if_fragile": round(float((yy[flag] == 2).mean()), 4) if flag.any() else None,
        "p_final_critical_if_not": round(float((yy[~flag] == 2).mean()), 4),
        "p_final_ge_elevated_if_fragile": round(float((yy[flag] >= 1).mean()), 4) if flag.any() else None,
        "p_final_ge_elevated_if_not": round(float((yy[~flag] >= 1).mean()), 4)}
    frt = fragility(te)
    res["share_fragile_cdms"] = {"train": round(float(fragility(tr).phys_fragile.mean()), 4), "test": round(float(frt.phys_fragile.mean()), 4)}
    res["decision"] = "see docs/EXPERIMENTS.md: physics features are not added to the models; the fragile flag is shown on events only"
    print(write_evidence("fragility.json", res, splits=("train", "test")))
    print(out, res["flag_vs_final_tier"], res["share_fragile_cdms"])


if __name__ == "__main__":
    main()
