"""Evaluation runner for the frozen test set.

Overfitting guard: the held-out `test` split can only be run with --final, every such run is appended to
eval/results/test_run_log.txt (so the number of times the test split was touched is visible), and each run records the git
commit and the test-set SHA-256. Tuning is done on `dev` only.

Usage:
  python eval/run_eval.py --split dev
  python eval/run_eval.py --split test --final        # Phase 4 only
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from answer import answer, _vocab  # noqa: E402
from retrieve import Corpus  # noqa: E402

TESTSET = ROOT / "eval" / "testset_v1.jsonl"
FROZEN_SHA = "3097beda9d7118d0cfbaf90ffb50f4945287fc1705cc426b56fa2f8ff9ed609b"


def sha256(p: Path) -> str:
    # normalise CRLF so the hash matches the frozen LF file on any checkout
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def score_one(t, a, C):
    cat, gold = t["category"], t["gold_docs"]
    refused = a["type"] == "refusal"
    row = {"id": t["id"], "category": cat, "split": t["split"], "refused": refused, "ok": False, "detail": ""}
    cards = a.get("cards", [])
    ids = [c["doc_id"] for c in cards]
    if cat == "refuse":
        row["ok"] = refused
        row["code_ok"] = refused and a["refusal"]["code"] == t["gold_refusal"]
        row["detail"] = a["refusal"]["code"] if refused else "answered"
    elif cat == "lookup":
        rank = next((i + 1 for i, d in enumerate(ids[:5]) if d in gold), None)
        row.update(ok=rank is not None and rank <= 3, rank=rank, detail=f"rank {rank}")
    elif cat == "applicability":
        c = next((c for c in cards if c["doc_id"] in gold), None)
        v = c["verdict"] if c else None
        row.update(ok=bool(v and v["verdict"] == t["gold_verdict"]), reason_ok=bool(v and v["main_reason"] == t["gold_reason"]),
                   retrieved=c is not None, detail=(f"{v['verdict']}/{v['main_reason']}" if v else ("refused " + a["refusal"]["code"] if refused else "gold doc not returned")))
    elif cat == "revision":
        gs = (t["gold_status"] or "").lower()
        c = cards[0] if cards else None
        trail = {e["doc_id"] for cc in cards for e in cc["revision_trail"]}
        docs_ok = set(gold) <= trail
        if "withdrawn" in gs and "no." in gs:
            st_ok = bool(c) and c["status"] == "WITHDRAWN"
        elif "revis" in gs:
            st_ok = bool(c) and c["status"].startswith("REVISED_NPRM") and c["latest_doc_id"] == gold[-1]
        elif "extended" in gs:
            st_ok = bool(c) and any(e["event"] == "comment_extension" for cc in cards for e in cc["revision_trail"]) and bool(c["comments_due"])
        else:
            st_ok = False
        row.update(ok=bool(c) and docs_ok and st_ok, detail=f"status {c['status'] if c else None}; trail_ok {docs_ok}")
    return row


def pct(x, n):
    return round(100 * x / n, 1) if n else None


def summarise(rows, lat, quote_stats):
    s = {"n": len(rows)}
    for cat in ("lookup", "applicability", "revision", "refuse"):
        r = [x for x in rows if x["category"] == cat]
        s[cat] = {"n": len(r), "ok": sum(x["ok"] for x in r), "pct": pct(sum(x["ok"] for x in r), len(r))}
    r = [x for x in rows if x["category"] == "lookup"]
    s["lookup"]["recall_at_3"] = pct(sum(x["ok"] for x in r), len(r))
    s["lookup"]["mrr"] = round(sum(1 / x["rank"] for x in r if x.get("rank")) / len(r), 3) if r else None
    r = [x for x in rows if x["category"] == "applicability"]
    s["applicability"]["verdict_accuracy"] = pct(sum(x["ok"] for x in r), len(r))
    s["applicability"]["reason_accuracy"] = pct(sum(x.get("reason_ok", False) for x in r), len(r))
    refused = [x for x in rows if x["refused"]]
    should = [x for x in rows if x["category"] == "refuse"]
    tp = sum(1 for x in refused if x["category"] == "refuse")
    s["refusal"] = {"precision": pct(tp, len(refused)), "recall": pct(tp, len(should)), "code_accuracy": pct(sum(x.get("code_ok", False) for x in should), len(should)),
                    "n_refused": len(refused), "n_should_refuse": len(should)}
    kept, dropped = quote_stats
    s["unsupported_quote_rate"] = {"dropped_before_filter": dropped, "kept": kept, "pct": pct(dropped, kept + dropped)}
    lat = sorted(lat)
    if lat:
        s["latency_ms_total"] = {"p50": round(lat[len(lat) // 2], 1), "p95": round(lat[int(0.95 * (len(lat) - 1))], 1)}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--final", action="store_true", help="required to touch the held-out test split")
    args = ap.parse_args()
    if args.split in ("test", "all") and not args.final:
        sys.exit("REFUSED: the test split is held out. Re-run with --final only in Phase 4 (and only once per code state).")
    sha = sha256(TESTSET)
    if sha != FROZEN_SHA:
        sys.exit(f"REFUSED: testset_v1.jsonl changed (sha {sha[:12]} != frozen {FROZEN_SHA[:12]}). Create v2 instead of editing v1.")
    qs = [json.loads(l) for l in open(TESTSET, encoding="utf-8")]
    qs = [q for q in qs if args.split == "all" or q["split"] == args.split]
    C = Corpus()
    _vocab(C)
    rows, lat, kept, dropped, answers = [], [], 0, 0, {}
    for t in qs:
        a = answer(C, t["query"], t.get("config"))
        answers[t["id"]] = a
        lat.append(a["latency_ms"]["total"])
        for c in a.get("cards", []):
            kept += len(c["quotes"])
            dropped += c["dropped_quotes"]
        rows.append(score_one(t, a, C))
    summ = summarise(rows, lat, (kept, dropped))
    meta = {"timestamp": datetime.now().isoformat(timespec="seconds"), "git_commit": git_commit(), "testset_sha256": sha,
            "split": args.split, "final": args.final, "system": "full"}
    out = {"meta": meta, "summary": summ, "rows": rows}
    d = ROOT / "eval" / "results" / (datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{args.split}")
    d.mkdir(parents=True, exist_ok=True)
    (d / "metrics.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (d / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    if args.split in ("test", "all"):
        with open(ROOT / "eval" / "results" / "test_run_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{meta['timestamp']} commit {meta['git_commit']} split {args.split} system {meta['system']}\n")
    print(json.dumps(summ, indent=1))
    for r in rows:
        print(("ok   " if r["ok"] else "MISS ") + r["id"], r["detail"])
    print("saved", d)


if __name__ == "__main__":
    main()
