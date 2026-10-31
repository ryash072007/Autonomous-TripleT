"""T1 step 1: freeze. Complete artifacts/model_card.json with every threshold and config, plus file hashes."""

from __future__ import annotations

import hashlib
import json
import time

from ca_triage.data import ROOT
from ca_triage.evaluation import git_commit

M = ROOT / "artifacts" / "models"


def sha(p) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main() -> None:
    card = json.loads((ROOT / "artifacts/model_card.json").read_text())
    conf = json.loads((M / "conformal.json").read_text())
    card["conformal"] = {"method": "Learn-then-Test on Critical miss rate (Clopper-Pearson, delta 0.1), set = argmax tier + Critical if p_critical >= lambda",
                         "task_a": conf["task_a"] | {"alpha": 0.05}, "task_b": conf["task_b"],
                         "evidence": "artifacts/evidence/conformal.json"}
    card["decision_layer"] = json.loads((M / "decision.json").read_text()) | {
        "evidence": "artifacts/evidence/decision.json",
        "note": "Wait is not shipped unless wait_shipped is true; recommendations are Act / Dismiss / Analyst decides"}
    ood = __import__("joblib").load(M / "ood.joblib")
    card["ood"] = {"method": "IsolationForest on latest CDM, allowed columns", "threshold": ood["threshold"], "quantile": ood["quantile"],
                   "evidence": "artifacts/evidence/drift.json"}
    card["physics_flag"] = {"assumption": "isotropic encounter-plane Gaussian, s = sqrt(c_sigma_r^2 + t_sigma_r^2), R = 10 m",
                            "evidence": "artifacts/evidence/fragility.json"}
    card["model_files_sha256"] = {p.name: sha(p) for p in sorted(M.glob("*")) if p.is_file()}
    card["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    card["frozen_git_commit"] = git_commit()
    card["frozen"] = True
    card["released_test_labels_opened"] = False
    (ROOT / "artifacts/model_card.json").write_text(json.dumps(card, indent=1))
    print("frozen", card["frozen_utc"], card["version"])


if __name__ == "__main__":
    main()
