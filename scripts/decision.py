"""D2: cost-aware Act / Wait / Dismiss / Analyst-decides layer.

    python scripts/decision.py           # evaluate on train OOF -> artifacts/evidence/decision.json,
                                         # fit gating models -> artifacts/models/decision_*.joblib + decision.json config
Costs are in units of C_man (one manoeuvre = 1); a missed avoidable collision costs `ratio`.

State model: Task B-style LightGBM trained on every prefix of each test-like train event (first k CDMs >= 2 d), grouped
OOF. At the last prefix (the 2-day decision point) the shipped Task B OOF probabilities are used, so numbers match
`p_forecast`. Waiting is only possible while the latest CDM is > 2 d out; after the last CDM >= 2 d nothing new arrives
before the cutoff, which the gating models learn because the training target for such states uses the unchanged state.
"""

from __future__ import annotations

import json
import sys
import time

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from conformal import sets_ltt  # noqa: E402
from train import build_b, oof_task_b  # noqa: E402
from conformal import cached  # noqa: E402

from ca_triage import SEED
from ca_triage.data import ROOT, load
from ca_triage.evaluation import event_labels, fold_of_events, test_like_events, write_evidence
from ca_triage.models import LGB_B, decide, prefix_event_features, sample_weights
from ca_triage.tiers import tier

RATIOS = [10, 20, 50, 100, 200, 500, 1000]
DEFAULT_RATIO = 100
VOI_MIN = 0.02          # wait only if one more CDM is expected to save at least 0.02 C_man
WAIT_MIN_TTE = 2.05     # latest CDM must be this far out for Wait to be possible
LGB_G = dict(n_estimators=150, learning_rate=0.05, num_leaves=15, min_child_samples=40, subsample=0.8, subsample_freq=1,
             colsample_bytree=0.8, random_state=SEED, verbose=-1, n_jobs=4)


def build_prefixes(tr):
    ev = test_like_events(tr)
    d = tr[tr.event_id.isin(ev.index)]
    P = prefix_event_features(d)
    y = event_labels(d)
    P["y"] = P.event_id.map(y).to_numpy()
    P["m"] = P.groupby("event_id").k.transform("max")
    P["fold"] = P.event_id.map(fold_of_events(tr.event_id)).to_numpy()
    return P


def oof_state(P, feats):
    out = np.zeros((len(P), 3))
    for k in range(5):
        a = (P.fold != k).to_numpy()
        y = P.y.to_numpy()
        m = lgb.LGBMClassifier(**LGB_B).fit(P.loc[a, feats], y[a], sample_weight=sample_weights(y[a]))
        out[~a] = m.predict_proba(P.loc[~a, feats])
    return out


def gating_frame(P, feats, probs):
    G = P[feats].copy()
    for c in range(3):
        G[f"p{c}"] = probs[:, c]
    return G


def next_state_targets(P, probs):
    """For each prefix row: probs of the next prefix of the same event; if none, the unchanged state."""
    nxt = probs.copy()
    same = (P.event_id.to_numpy()[:-1] == P.event_id.to_numpy()[1:])
    nxt[:-1][same] = probs[1:][same]
    return nxt


def fit_gating(G, y_change, y_wait, folds, oof=True):
    """OOF predictions (or final models if oof=False) of P(change) and E[min(1, ratio * p_crit')] per ratio."""
    names = ["change"] + [f"wait_{r}" for r in RATIOS]
    targets = [y_change] + [y_wait[r] for r in RATIOS]
    if not oof:
        models = {}
        for nm, t in zip(names, targets):
            m = lgb.LGBMClassifier(**LGB_G) if nm == "change" else lgb.LGBMRegressor(**LGB_G)
            models[nm] = m.fit(G, t)
        return models
    out = {nm: np.zeros(len(G)) for nm in names}
    for k in range(5):
        a = folds != k
        for nm, t in zip(names, targets):
            m = lgb.LGBMClassifier(**LGB_G) if nm == "change" else lgb.LGBMRegressor(**LGB_G)
            m.fit(G[a], t[a])
            out[nm][~a] = m.predict_proba(G[~a])[:, 1] if nm == "change" else m.predict(G[~a])
    return out


def decide_one(pc, cset, tte, voi, ratio, wait_enabled=True, can_wait=True):
    """Return (recommendation, reason). `cset` = conformal forecast tier set (list)."""
    risk_cost = min(1.0, ratio * pc)
    if wait_enabled and can_wait and tte > WAIT_MIN_TTE and voi > VOI_MIN:
        return "Wait", f"One more CDM is expected to save {voi:.2f} C_man (P(Critical) = {pc:.3f}); {tte:.1f} d to TCA"
    crit_in, single = 2 in cset, len(cset) == 1
    if pc * ratio >= 1:
        if single and crit_in:
            return "Act", f"P(Critical at TCA) = {pc:.3f} x ratio {ratio} >= 1 and the forecast set is {{Critical}}"
        return "Analyst decides", f"P(Critical at TCA) = {pc:.3f} x ratio {ratio} >= 1 but the forecast set is not {{Critical}}"
    if not crit_in:
        return "Dismiss", f"P(Critical at TCA) = {pc:.3f} x ratio {ratio} < 1 and Critical is outside the forecast set"
    if wait_enabled and can_wait and tte > WAIT_MIN_TTE:
        return "Wait", f"Critical not excluded; {tte:.1f} d to TCA, no manoeuvre yet"
    return "Analyst decides", f"Critical is in the forecast set {cset} and P x ratio < 1"


def simulate(P, probs, sets, tte, voi, p_final_y, ratio, mode):
    """Walk each event's prefixes. mode: 'wait_voi' | 'no_wait' (decide at the first CDM) | 'decide_last' (always wait)."""
    ev, k = P.event_id.to_numpy(), P.k.to_numpy()
    n_cdm = P.n_cdms.to_numpy()
    res = {}
    start = 0
    for end in np.r_[np.where(ev[1:] != ev[:-1])[0] + 1, len(ev)]:
        rows = range(start, end)
        for i in rows:
            last = i == end - 1
            if mode == "decide_last":
                if not last:
                    continue
                rec, _ = decide_one(probs[i, 2], sets[i], tte[i], 0, ratio, wait_enabled=False)
            elif mode == "no_wait":
                rec, _ = decide_one(probs[i, 2], sets[i], tte[i], 0, ratio, wait_enabled=False)
                if rec == "Analyst decides" and not last:
                    continue  # keep watching until the 2 d point if the tool cannot decide
            else:
                rec, _ = decide_one(probs[i, 2], sets[i], tte[i], voi[i], ratio, can_wait=not last)
                if rec in ("Wait", "Analyst decides") and not last:
                    continue  # the analyst is only asked at the 2 d point; until then keep watching
            res[ev[start]] = (rec, i)
            break
        start = end
    return res


def score(res, P, probs, y_event, persist, ratio):
    ids = list(res)
    yy = np.array([y_event[e] for e in ids])
    rec = np.array([res[e][0] for e in ids])
    idx = np.array([res[e][1] for e in ids])
    pc = probs[idx, 2]
    analyst = rec == "Analyst decides"
    act = (rec == "Act") | (analyst & (pc * ratio >= 1))  # analyst assumed to follow the same cost rule
    act_oracle = (rec == "Act") | (analyst & (yy == 2))
    n = len(ids)
    out = {"events": n}
    for nm, a in (("analyst_follows_rule", act), ("analyst_oracle", act_oracle)):
        missed = int(((yy == 2) & ~a).sum())
        unnecessary = int((a & (yy != 2)).sum())
        out[nm] = {"manoeuvres_per_100": round(100 * a.sum() / n, 3), "unnecessary_manoeuvres_per_100": round(100 * unnecessary / n, 3),
                   "missed_critical_per_100": round(100 * missed / n, 3), "missed_critical": missed,
                   "expected_cost_per_event": round((a.sum() + ratio * missed) / n, 4)}
    out["analyst_reviews_per_100"] = round(100 * analyst.sum() / n, 3)
    out["act_per_100"] = round(100 * (rec == "Act").sum() / n, 3)
    out["dismiss_per_100"] = round(100 * (rec == "Dismiss").sum() / n, 3)
    out["median_tte_at_decision"] = round(float(np.median(P.tte_last.to_numpy()[idx])), 3)
    return out


def baselines(yv, persist, b0, ratio):
    n = len(yv)
    out = {}
    for nm, a in (("persistence_observed_risk", persist == 2), ("b0_at_2d", b0 == 2)):
        missed = int(((yv == 2) & ~a).sum())
        out[nm] = {"manoeuvres_per_100": round(100 * a.sum() / n, 3), "unnecessary_manoeuvres_per_100": round(100 * (a & (yv != 2)).sum() / n, 3),
                   "missed_critical_per_100": round(100 * missed / n, 3), "missed_critical": missed, "analyst_reviews_per_100": 0.0,
                   "expected_cost_per_event": round((a.sum() + ratio * missed) / n, 4)}
    out["review_every_event"] = {"analyst_reviews_per_100": 100.0, "note": "workload bound: every event read by an analyst; cost depends on the analyst, oracle lower bound = "
                                 f"{round(float((yv == 2).mean()), 4)} manoeuvres per event, 0 missed"}
    return out


def main() -> None:
    tr = load("train")
    P = build_prefixes(tr)
    feats = [c for c in P.columns if c not in ("event_id", "k", "y", "fold", "m")]
    conf = json.loads((ROOT / "artifacts/models/conformal.json").read_text())
    lam = conf["task_b"]["ltt_lambda"]
    probs = oof_state(P, feats)
    # last prefix of each event: shipped Task B OOF, so the 2-day numbers match p_forecast
    X, yb, fb_, _, last = build_b(tr)
    pb = cached("oof_b", lambda: oof_task_b(X, yb, fb_))
    pos = {e: i for i, e in enumerate(X.index)}
    is_last = (P.k == P.m).to_numpy()
    probs[is_last] = pb[[pos[e] for e in P.event_id[is_last]]]
    fcast = decide(probs, 0.02, 0.1)
    S = sets_ltt(probs, lam)
    S[np.arange(len(P)), fcast] = True
    sets = [list(np.where(r)[0]) for r in S]
    nxt = next_state_targets(P, probs)
    ev = P.event_id.to_numpy()
    next_f = decide(nxt, 0.02, 0.1)
    y_change = (next_f != fcast).astype(int)
    y_wait = {r: np.minimum(1.0, r * nxt[:, 2]) for r in RATIOS}
    G = gating_frame(P, feats, probs)
    g = fit_gating(G, y_change, y_wait, P.fold.to_numpy())
    y_event = event_labels(tr[tr.event_id.isin(P.event_id.unique())]).to_dict()
    tte = P.tte_last.to_numpy()

    last_tbl = last.reindex(X.index)
    persist = pd.Series(tier(last_tbl.risk, last_tbl.miss_distance), index=X.index)
    b0 = pd.Series(tier(last_tbl.max_risk_estimate, last_tbl.miss_distance), index=X.index)
    ids_sorted = list(X.index)
    yv = np.array([y_event[e] for e in ids_sorted])
    folds_ev = X.index.to_series().map(fold_of_events(tr.event_id)).to_numpy()

    curve, per_fold, default_tbl = [], {}, {}
    fmap = fold_of_events(tr.event_id)
    for r in RATIOS:
        voi = np.maximum(0.0, np.minimum(1.0, r * probs[:, 2]) - g[f"wait_{r}"])
        row = {"ratio": r}
        for mode in ("wait_voi", "no_wait", "decide_last"):
            res = simulate(P, probs, sets, tte, voi, None, r, mode)
            sc = score(res, P, probs, y_event, None, r)
            row[mode] = sc
            if r == DEFAULT_RATIO:
                fold_costs = []
                for k in range(5):
                    sub = {e: v for e, v in res.items() if fmap[e] == k}
                    fold_costs.append(score(sub, P, probs, y_event, None, r)["analyst_follows_rule"]["expected_cost_per_event"])
                per_fold[mode] = {"expected_cost_per_event_by_fold": fold_costs, "mean": round(float(np.mean(fold_costs)), 4), "std": round(float(np.std(fold_costs)), 4)}
        row["baselines"] = baselines(yv, persist.to_numpy(), b0.to_numpy(), r)
        curve.append(row)

    wait_default = next(c for c in curve if c["ratio"] == DEFAULT_RATIO)
    # kill rule: does Wait beat deciding at the first CDM, by cost, at the default ratio (mean over folds)?
    wait_gain = per_fold["no_wait"]["mean"] - per_fold["wait_voi"]["mean"]
    fold1_gain = per_fold["no_wait"]["expected_cost_per_event_by_fold"][1] - per_fold["wait_voi"]["expected_cost_per_event_by_fold"][1]
    ship_wait = wait_gain > 0.005 and fold1_gain > 0
    res = {
        "units": "costs in C_man; ratio = C_miss / C_man", "default_ratio": DEFAULT_RATIO, "ratios": RATIOS,
        "n_events": int(len(ids_sorted)), "voi_min": VOI_MIN, "wait_min_tte": WAIT_MIN_TTE, "conformal_lambda": lam,
        "rules": "Wait if latest CDM > 2.05 d out and expected saving from one more CDM > 0.02 C_man; else Act if P(Critical) x ratio >= 1 and set == {Critical}; "
                 "else Analyst decides if P x ratio >= 1; Dismiss if P x ratio < 1 and Critical is outside the forecast set; otherwise Wait (> 2 d) or Analyst decides.",
        "analyst_assumption": "'analyst_follows_rule' = analyst manoeuvres iff P x ratio >= 1; 'analyst_oracle' = analyst always right (lower bound)",
        "curve_over_ratios": curve, "default_ratio_fold_costs": per_fold,
        "wait_value": {"mean_cost_gain_vs_no_wait": round(float(wait_gain), 5), "fold1_gain": round(float(fold1_gain), 5), "wait_shipped": bool(ship_wait)},
        "p_change_mean_by_tte_bucket": {str(b): round(float(g["change"][(tte >= b) & (tte < b + 1)].mean()), 4) for b in range(2, 7) if ((tte >= b) & (tte < b + 1)).any()},
    }
    print(write_evidence("decision.json", res))
    d = wait_default
    for m in ("wait_voi", "no_wait", "decide_last"):
        print(m, d[m]["analyst_follows_rule"], "reviews", d[m]["analyst_reviews_per_100"], "act", d[m]["act_per_100"])
    print(d["baselines"])
    print(res["wait_value"], per_fold)

    # final gating models on all prefix states, saved for scoring the test set
    models = fit_gating(G, y_change, y_wait, P.fold.to_numpy(), oof=False)
    joblib.dump({"models": models, "feature_cols": list(G.columns), "ratios": RATIOS, "wait_shipped": bool(ship_wait)}, ROOT / "artifacts/models/decision.joblib")
    cfg = {"default_ratio": DEFAULT_RATIO, "ratios": RATIOS, "voi_min": VOI_MIN, "wait_min_tte": WAIT_MIN_TTE, "wait_shipped": bool(ship_wait),
           "conformal_lambda_task_b": lam, "trained_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (ROOT / "artifacts/models/decision.json").write_text(json.dumps(cfg, indent=1))


if __name__ == "__main__":
    main()
