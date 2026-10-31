"""Phase 4 harness: score the full system and the baselines on the frozen sets.

Sets:    b1      fresh documents never seen by the rules (engine-level, annotator labels)
         b2      fresh questions on the corpus (end to end, annotator labels)
         v1test  the 30 held-out questions of testset_v1 (NOT blind: author = builder). Needs --final.
Systems: full | naive_summary | fulltext_bm25 | llm_only   (b1 supports full and naive_summary)

Every invocation is appended to eval/results/blind_run_log.txt with the git commit and a hash of src/*.py, so any change to the
system between runs is visible. Frozen files are hash-checked before use.

Usage: python eval/run_blind.py --sets b1,b2 --systems full
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))
from answer import answer, _vocab  # noqa: E402
from applicability import AircraftConfig, verdict as engine_verdict  # noqa: E402
from extract import extract_applicability, model_in_text  # noqa: E402
from retrieve import Corpus  # noqa: E402
import baselines  # noqa: E402

FROZEN = {"blind_B1.jsonl": None, "blind_B2.jsonl": None}   # filled from DECISIONS.md at run time (see check_frozen)
REFUSE_MAP = {"OUT_OF_SCOPE_judgement": "OUT_OF_SCOPE", "OUT_OF_SCOPE_offtopic": "OUT_OF_SCOPE", "OUT_OF_CORPUS_entity": "OUT_OF_CORPUS",
              "OUT_OF_CORPUS_final": "OUT_OF_CORPUS", "OUT_OF_CORPUS_old_date": "OUT_OF_CORPUS", "EXTERNAL_DOC_REQUIRED": "EXTERNAL_DOC_REQUIRED",
              "AMBIGUOUS_QUERY": "AMBIGUOUS_QUERY", "CONTRADICTORY_CONFIG": "CONTRADICTORY_CONFIG", "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def code_hash():
    h = hashlib.sha256()
    for p in sorted((ROOT / "src").glob("*.py")):
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:12]


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def check_frozen():
    txt = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    for name in sorted(q.name for q in (ROOT / "eval" / "blind").glob("blind_B*.jsonl")):
        h = sha(ROOT / "eval" / "blind" / name)
        if h not in txt:
            sys.exit(f"REFUSED: {name} hash {h[:12]} is not the frozen hash recorded in DECISIONS.md")


def load(setname):
    if setname == "v1test":
        rows = [json.loads(l) for l in open(ROOT / "eval" / "testset_v1.jsonl", encoding="utf-8")]
        return [dict(x, set="v1test") for x in rows if x["split"] == "test"]
    if setname.startswith("b2"):
        out = []
        for l in open(ROOT / "eval" / "blind" / f"blind_B2{setname[2:]}.jsonl", encoding="utf-8"):
            x = json.loads(l)
            x["set"] = setname
            x["gold_refusal"] = REFUSE_MAP.get(x.get("refusal_category"))
            out.append(x)
        return out
    raise ValueError(setname)


def score(t, a):
    cat = t["category"]
    refused = a["type"] == "refusal"
    cards = a.get("cards", [])
    ids = [c["doc_id"] for c in cards]
    gold = t.get("gold_docs") or []
    row = {"id": t["id"], "set": t["set"], "category": cat, "refused": refused, "ok": False, "detail": "", "query": t["query"]}
    if cat == "refuse":
        row["ok"] = refused
        row["code_ok"] = refused and a["refusal"]["code"] == t["gold_refusal"]
        row["detail"] = a["refusal"]["code"] if refused else "answered"
    elif cat == "lookup":
        rank = next((i + 1 for i, d in enumerate(ids[:5]) if d in gold), None)
        row.update(ok=rank is not None and rank <= 3, rank=rank, detail=f"rank {rank}")
    elif cat == "applicability":
        agnostic = "llm" in a
        c = next((c for c in cards if c["doc_id"] in gold), None) if not agnostic else (cards[0] if cards else None)
        v = c["verdict"] if c else None
        row.update(ok=bool(v and v["verdict"] == t["gold_verdict"]), reason_ok=bool(v and v.get("main_reason") == t.get("gold_reason")),
                   retrieved=c is not None,
                   detail=(f"{v['verdict']}/{v.get('main_reason')}" if v else ("refused " + a["refusal"]["code"] if refused else "gold doc not returned")))
    elif cat == "revision":
        c = cards[0] if cards else None
        trail = {e["doc_id"] for cc in cards for e in cc["revision_trail"]}
        if t.get("gold_latest_doc") is not None or "withdrawn" in t:
            gl = t.get("gold_latest_doc")
            if t.get("withdrawn"):
                ok = any(cc["status"] == "WITHDRAWN" for cc in cards) and bool(set(gold) & trail)
            else:
                ok = bool(c) and (c["latest_doc_id"] == gl or gl in [cc["latest_doc_id"] for cc in cards[:3]])
        else:
            gs = (t.get("gold_status") or "").lower()
            docs_ok = set(gold) <= trail
            if "withdrawn" in gs and "no." in gs:
                st_ok = bool(c) and c["status"] == "WITHDRAWN"
            elif "revis" in gs:
                st_ok = bool(c) and (c["status"] or "").startswith("REVISED_NPRM") and c["latest_doc_id"] == gold[-1]
            elif "extended" in gs:
                st_ok = bool(c) and any(e["event"] == "comment_extension" for cc in cards for e in cc["revision_trail"]) and bool(c["comments_due"])
            else:
                st_ok = False
            ok = bool(c) and docs_ok and st_ok
        row.update(ok=ok, detail=f"status {c['status'] if c else None}")
    return row


def pct(x, n):
    return round(100 * x / n, 1) if n else None


def summarise(rows, answers, name):
    s = {"system": name, "n": len(rows)}
    for cat in ("lookup", "applicability", "revision", "refuse"):
        r = [x for x in rows if x["category"] == cat]
        s[cat] = {"n": len(r), "ok": sum(x["ok"] for x in r), "pct": pct(sum(x["ok"] for x in r), len(r))}
    refused = [x for x in rows if x["refused"]]
    should = [x for x in rows if x["category"] == "refuse"]
    tp = sum(1 for x in refused if x["category"] == "refuse")
    s["refusal"] = {"precision": pct(tp, len(refused)), "recall": pct(tp, len(should)), "code_accuracy": pct(sum(x.get("code_ok", False) for x in should), len(should)),
                    "n_refused": len(refused), "n_should_refuse": len(should)}
    r = [x for x in rows if x["category"] == "applicability"]
    s["applicability"]["reason_accuracy"] = pct(sum(x.get("reason_ok", False) for x in r), len(r))
    answered = [x for x in rows if x["category"] != "refuse"]
    s["answered_correct_overall"] = pct(sum(x["ok"] for x in answered), len(answered))
    kept = sum(len(c["quotes"]) for a in answers.values() for c in a.get("cards", []))
    dropped = sum(c["dropped_quotes"] for a in answers.values() for c in a.get("cards", []))
    if kept + dropped:
        s["unsupported_quote_rate_pct"] = pct(dropped, kept + dropped)
    cited = sum(len(a["llm"]["cited"]) for a in answers.values() if "llm" in a)
    hall = sum(len(a["llm"]["hallucinated"]) for a in answers.values() if "llm" in a)
    if cited:
        s["llm_cited_ids"] = {"cited": cited, "not_in_corpus": hall, "pct_not_in_corpus": pct(hall, cited)}
    lat = sorted(a["latency_ms"]["total"] for a in answers.values() if a.get("latency_ms", {}).get("total"))
    if lat:
        s["latency_ms_total"] = {"p50": round(lat[len(lat) // 2], 1), "p95": round(lat[int(0.95 * (len(lat) - 1))], 1)}
    return s


def run_b1(system, suffix=""):
    items = [json.loads(l) for l in open(ROOT / "eval" / "blind" / f"blind_B1{suffix}.jsonl", encoding="utf-8")]
    docs = {d["doc_id"]: d for d in (json.loads(l) for l in open(ROOT / "eval" / "blind" / f"fresh_docs{suffix}.jsonl", encoding="utf-8"))}
    rows = []
    for it in items:
        an = it["annotation"]
        if not an or not an.get("feasible"):
            continue
        rec = docs[it["doc_id"]]
        cfgd = an["config"]
        cfg = AircraftConfig(make=cfgd.get("make"), model=cfgd.get("model"), serial=cfgd.get("serial"), cofa_date=cfgd.get("cofa_date"),
                             part_numbers=cfgd.get("part_numbers") or [])
        if system == "full":
            v = engine_verdict(rec, extract_applicability(rec), cfg)
            got, why = v.verdict, v.main_reason
        else:
            hay = re.sub(r"\s+", "", rec["text"].upper())
            got, why = ("APPLIES" if (cfg.model or "").upper().replace(" ", "") in hay else "DOES_NOT_APPLY"), None
        rows.append({"id": it["id"], "doc": it["doc_id"], "gold": an["gold_verdict"], "gold_reason": an["gold_reason"], "got": got, "got_reason": why,
                     "ok": got == an["gold_verdict"], "reason_ok": why == an["gold_reason"], "config": cfgd})
    n = len(rows)
    conf = {}
    for r in rows:
        conf[f"{r['gold']}->{r['got']}"] = conf.get(f"{r['gold']}->{r['got']}", 0) + 1
    summ = {"system": system, "n": n, "verdict_accuracy": pct(sum(r["ok"] for r in rows), n), "reason_accuracy": pct(sum(r["reason_ok"] for r in rows), n),
            "confusion": conf, "per_gold": {g: pct(sum(r["ok"] for r in rows if r["gold"] == g), sum(1 for r in rows if r["gold"] == g)) for g in ("APPLIES", "DOES_NOT_APPLY", "CANNOT_DETERMINE")}}
    return summ, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="b1,b2")
    ap.add_argument("--systems", default="full")
    ap.add_argument("--final", action="store_true")
    args = ap.parse_args()
    sets, systems = args.sets.split(","), args.systems.split(",")
    if "v1test" in sets and not args.final:
        sys.exit("REFUSED: v1test is the held-out split; pass --final.")
    check_frozen()
    if sha(ROOT / "eval" / "testset_v1.jsonl") != "3097beda9d7118d0cfbaf90ffb50f4945287fc1705cc426b56fa2f8ff9ed609b":
        sys.exit("REFUSED: testset_v1.jsonl changed")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "eval" / "results" / f"{ts}_blind"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "eval" / "results" / "blind_run_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{ts} commit {git_commit()} src_hash {code_hash()} sets {args.sets} systems {args.systems}\n")
    C = Corpus()
    _vocab(C)
    sysmap = {"naive_summary": lambda: baselines.NaiveSummary(C), "fulltext_bm25": lambda: baselines.FulltextBM25(C), "llm_only": lambda: baselines.LLMOnly(C)}
    results = {}
    for sname in sets:
        for sy in systems:
            key = f"{sname}/{sy}"
            if sname.startswith("b1"):
                if sy not in ("full", "naive_summary"):
                    continue
                summ, rows = run_b1("full" if sy == "full" else "naive", sname[2:])
                results[key] = {"summary": summ, "rows": rows}
            else:
                items = load(sname)
                if sy == "full":
                    answers = {t["id"]: answer(C, t["query"], t.get("config")) for t in items}
                else:
                    system = sysmap[sy]()
                    if sy == "llm_only":
                        res = system.batch(items)
                        answers = {t["id"]: a for t, a in zip(items, res)}
                    else:
                        answers = {t["id"]: system(t["query"], t.get("config")) for t in items}
                rows = [score(t, answers[t["id"]]) for t in items]
                results[key] = {"summary": summarise(rows, answers, sy), "rows": rows}
                (out_dir / f"{sname}_{sy}_answers.json").write_text(json.dumps(answers), encoding="utf-8")
            print("=" * 20, key)
            print(json.dumps(results[key]["summary"], indent=1))
    meta = {"timestamp": ts, "git_commit": git_commit(), "src_hash": code_hash(), "sets": sets, "systems": systems,
            "testset_v1_sha": sha(ROOT / "eval" / "testset_v1.jsonl"), "B1_sha": sha(ROOT / "eval" / "blind" / "blind_B1.jsonl"),
            "B2_sha": sha(ROOT / "eval" / "blind" / "blind_B2.jsonl")}
    (out_dir / "results.json").write_text(json.dumps({"meta": meta, "results": results}, indent=1), encoding="utf-8")
    print("saved", out_dir)


if __name__ == "__main__":
    main()
