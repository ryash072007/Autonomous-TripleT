"""D1: conformal tier sets with a Critical-miss guarantee -> artifacts/evidence/conformal.json, artifacts/models/conformal.json.

Two methods on out-of-fold (OOF) probabilities, evaluated honestly: calibrate on 4 of the 5 grouped folds,
test on the held-out fold, repeat for each fold.

- LTT: rule "Critical in set iff p_critical >= lam" (plus the argmax tier). lam is the largest value whose one-sided
  Clopper-Pearson upper bound (delta = 0.1) on the miss rate among calibration Critical cases is <= alpha
  (fixed-sequence test from the permissive end, so the family-wise error is controlled; Learn-then-Test).
- Mondrian: class-conditional split conformal, score 1 - p_k for true class k, set = {k : 1 - p_k <= q_k}.
Task A sets are intersected with {tier >= miss-distance tier} (exact branch); calibration uses rows whose miss
tier < 2 (the Pc branch); rows with miss < 1 km are Critical with certainty.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import beta

sys.path.insert(0, __file__.rsplit("scripts", 1)[0] + "scripts")
from train import build_b, oof_task_a, oof_task_b  # noqa: E402

from ca_triage import SEED
from ca_triage.data import DECISION_CUTOFF_DAYS, ROOT, load
from ca_triage.evaluation import folds_for, write_evidence
from ca_triage.models import miss_tier

ALPHAS = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30]
DELTA = 0.1
CACHE = ROOT / "artifacts" / "cache"
LAMS = np.unique(np.r_[np.logspace(-6, -2, 25), np.linspace(0.02, 0.99, 98)])


def cp_upper(k: int, n: int, delta: float = DELTA) -> float:
    return 1.0 if n == 0 or k >= n else float(beta.ppf(1 - delta, k + 1, n - k))


def fit_ltt(p, y, alpha) -> float:
    """Largest lam (smallest Critical sets) whose CP upper bound on the Critical miss rate is <= alpha."""
    pc = p[y == 2, 2]
    n, best = len(pc), LAMS[0]
    for lam in LAMS:  # miss rate rises with lam; stop at the first failure
        if cp_upper(int((pc < lam).sum()), n) <= alpha:
            best = lam
        else:
            break
    return float(best)


def fit_mondrian(p, y, alpha) -> list[float]:
    q = []
    for k in range(3):
        s = np.sort(1 - p[y == k, k])
        n = len(s)
        level = min(1.0, np.ceil((n + 1) * (1 - alpha)) / max(n, 1))
        q.append(float(np.quantile(s, level, method="higher")) if n else 1.0)
    return q


def sets_ltt(p, lam):
    S = np.zeros(p.shape, bool)
    S[np.arange(len(p)), p.argmax(1)] = True
    S[:, 2] |= p[:, 2] >= lam
    return S


def sets_mondrian(p, q):
    S = (1 - p) <= np.array(q)[None, :]
    empty = ~S.any(1)
    S[empty, p[empty].argmax(1)] = True
    return S


def floor_sets(S, mt):
    S = S.copy()
    for k in (1, 2):
        S[mt >= k, :k] = False
    empty = ~S.any(1)
    S[empty, mt[empty]] = True
    return S


def evaluate(S, y):
    cov = S[np.arange(len(y)), y]
    size = S.sum(1)
    crit = y == 2
    return {"coverage": float(cov.mean()), "critical_miss": float((~cov[crit]).mean()) if crit.any() else None,
            "critical_n": int(crit.sum()), "critical_missed": int((~cov[crit]).sum()),
            "avg_set_size": float(size.mean()), "abstain_rate": float((size > 1).mean())}


def run_cv(p, y, folds, alpha, method, mt=None, cal_mask=None):
    """Held-out sets for every fold, calibrating on the other folds. Returns the pooled boolean set matrix."""
    S = np.zeros(p.shape, bool)
    cal_ok = np.ones(len(y), bool) if cal_mask is None else cal_mask
    for k in sorted(set(folds)):
        c = (folds != k) & cal_ok
        t = folds == k
        S[t] = sets_ltt(p[t], fit_ltt(p[c], y[c], alpha)) if method == "ltt" else sets_mondrian(p[t], fit_mondrian(p[c], y[c], alpha))
    if mt is not None:
        S = floor_sets(S, mt)
    return S


def summarize(p, y, folds, alpha, method, mt=None, cal_mask=None, n_boot=1000):
    S = run_cv(p, y, folds, alpha, method, mt, cal_mask)
    per = [evaluate(S[folds == k], y[folds == k]) for k in sorted(set(folds))]
    pooled = evaluate(S, y)
    rng = np.random.default_rng(SEED)
    crit_idx = np.where(y == 2)[0]
    hit = S[np.arange(len(y)), y]
    boots = [1 - hit[rng.choice(crit_idx, len(crit_idx))].mean() for _ in range(n_boot)]
    pooled["critical_miss_ci95"] = [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    out = {"pooled": pooled}
    for key in ("coverage", "critical_miss", "avg_set_size", "abstain_rate"):
        v = np.array([m[key] for m in per if m[key] is not None])
        out[f"{key}_fold_mean_std"] = [float(v.mean()), float(v.std())]
    # per-class coverage
    out["class_coverage"] = [float(S[y == k, k].mean()) for k in range(3)]
    return out


def task_curve(p, y, folds, **kw):
    rows = []
    for a in ALPHAS:
        for m in ("ltt", "mondrian"):
            r = summarize(p, y, folds, a, m, n_boot=300, **kw)["pooled"]
            rows.append({"alpha": a, "method": m, "abstain_rate": r["abstain_rate"], "critical_miss": r["critical_miss"],
                         "coverage": r["coverage"], "avg_set_size": r["avg_set_size"]})
    return rows


def cached(name, fn):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.npy"
    if path.exists():
        return np.load(path)
    v = fn()
    np.save(path, v)
    return v


def main() -> None:
    tr = load("train")
    # ---- Task B (per event)
    X, yb, fb, persist, _ = build_b(tr)
    pb = cached("oof_b", lambda: oof_task_b(X, yb, fb))
    # ---- Task A (per CDM >= 2 d)
    early = (tr.time_to_tca >= DECISION_CUTOFF_DAYS).to_numpy()
    pa_all = cached("oof_a", lambda: oof_task_a(tr))
    pa, ya, fa = pa_all[early], tr.tier.to_numpy()[early], folds_for(tr)[early]
    mt = miss_tier(tr.miss_distance.to_numpy()[early])
    pcb = mt < 2  # Pc-branch rows: calibration set

    res = {"method_notes": __doc__, "alphas": ALPHAS, "delta": DELTA, "seed": SEED}
    for name, (p, y, f, kw) in {"task_b_event_forecast": (pb, yb, fb, {}),
                                "task_a_cdm": (pa, ya, fa, {"mt": mt, "cal_mask": pcb})}.items():
        res[name] = {"n": int(len(y)), "critical_n": int((y == 2).sum())}
        for a in (0.05, 0.10):
            for m in ("ltt", "mondrian"):
                res[name][f"alpha_{a}_{m}"] = summarize(p, y, f, a, m, **kw)
        res[name]["curve"] = task_curve(p, y, f, **kw)
    # Task A: also the rate among Pc-branch rows only (the part the model decides)
    S = run_cv(pa, ya, fa, 0.05, "ltt", mt, pcb)
    res["task_a_cdm"]["alpha_0.05_ltt_pc_branch_rows_only"] = evaluate(S[pcb], ya[pcb])

    # operating points
    ob = res["task_b_event_forecast"]
    ltt05 = ob["alpha_0.05_ltt"]["pooled"]
    if ltt05["abstain_rate"] <= 0.40:
        op_alpha, why = 0.05, "abstain at alpha=0.05 is <= 40%"
    else:
        ok = [r for r in ob["curve"] if r["method"] == "ltt" and r["abstain_rate"] <= 0.25]
        best = min(ok, key=lambda r: r["alpha"]) if ok else min((r for r in ob["curve"] if r["method"] == "ltt"), key=lambda r: r["abstain_rate"])
        op_alpha, why = best["alpha"], "abstain at alpha=0.05 exceeds 40%; smallest alpha with abstain <= 25%"
    opB = next(r for r in ob["curve"] if r["method"] == "ltt" and r["alpha"] == op_alpha)
    res["operating_points"] = {"task_a_alpha": 0.05, "task_b_alpha": op_alpha, "task_b_reason": why, "task_b_at_operating_point": opB}

    # ---- final calibration on all OOF, used to score the test set
    cfg = {"task_a": {"alpha": 0.05, "ltt_lambda": fit_ltt(pa[pcb], ya[pcb], 0.05), "mondrian_q": fit_mondrian(pa[pcb], ya[pcb], 0.05)},
           "task_b": {"alpha": op_alpha, "ltt_lambda": fit_ltt(pb, yb, op_alpha), "mondrian_q": fit_mondrian(pb, yb, op_alpha)},
           "delta": DELTA, "method": "ltt"}
    for a in (0.05, 0.10):
        cfg["task_b"][f"ltt_lambda_alpha_{a}"] = fit_ltt(pb, yb, a)
    res["final_calibration"] = cfg
    (ROOT / "artifacts/models").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts/models/conformal.json").write_text(json.dumps(cfg, indent=1))
    print(write_evidence("conformal.json", res))
    for t in ("task_b_event_forecast", "task_a_cdm"):
        for k in ("alpha_0.05_ltt", "alpha_0.05_mondrian", "alpha_0.1_ltt", "alpha_0.1_mondrian"):
            r = res[t].get(k) or res[t].get(k.replace("0.1_", "0.1_"))
            if r:
                p_ = r["pooled"]
                print(t, k, "miss", round(p_["critical_miss"], 4), p_["critical_miss_ci95"], "abstain", round(p_["abstain_rate"], 3), "size", round(p_["avg_set_size"], 3), "cov", round(p_["coverage"], 3))
    print(res["operating_points"])
    print(cfg)


if __name__ == "__main__":
    main()
