"""Generalisation / robustness check on ad-hoc queries (NOT the frozen test set). Reports pass/fail per query and any crash.
Run: python eval/run_adhoc.py
"""
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from answer import answer, _vocab  # noqa: E402
from retrieve import Corpus  # noqa: E402


def check(exp, a):
    if exp["type"] == "no_crash":
        return True, ""
    if a["type"] != exp["type"]:
        return False, f"expected {exp['type']}, got {a['type']}" + (f" ({a['refusal']['code']})" if a["type"] == "refusal" else "")
    if exp["type"] == "refusal":
        return (a["refusal"]["code"] == exp.get("code"), f"code {a['refusal']['code']}")
    docs = [c["doc_id"] for c in a["cards"][:3]]
    if exp.get("doc_any") and not set(exp["doc_any"]) & set(docs):
        return False, f"docs {docs}"
    if exp.get("verdict"):
        hit = [c for c in a["cards"] if c["doc_id"] in exp["doc_any"] and c["verdict"]]
        if not hit or hit[0]["verdict"]["verdict"] != exp["verdict"]:
            return False, f"verdict {[c['verdict']['verdict'] if c['verdict'] else None for c in a['cards'][:3]]}"
    if exp.get("status"):
        hit = [c for c in a["cards"] if c["status"] == exp["status"]]
        if not hit:
            return False, f"status {[c['status'] for c in a['cards'][:3]]}"
    return True, ""


def main():
    C = Corpus()
    _vocab(C)
    rows, crashes = [], 0
    src = sys.argv[1] if len(sys.argv) > 1 else "adhoc_queries.jsonl"
    for line in open(ROOT / "eval" / src, encoding="utf-8"):
        t = json.loads(line)
        try:
            a = answer(C, t["query"])
            ok, why = check(t["expect"], a)
        except Exception:  # noqa: BLE001
            crashes += 1
            ok, why = False, "CRASH " + traceback.format_exc().splitlines()[-1]
        rows.append({"id": t["id"], "ok": ok, "why": why, "query": t["query"]})
        print(("PASS " if ok else "FAIL ") + t["id"], why)
    n_ok = sum(r["ok"] for r in rows)
    print(f"\nadhoc: {n_ok}/{len(rows)} pass, {crashes} crashes")
    out = ROOT / "eval" / "results" / (Path(src).stem + "_latest.json")
    out.write_text(json.dumps({"pass": n_ok, "total": len(rows), "crashes": crashes, "rows": rows}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
