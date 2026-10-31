"""Synthetic test of the free-text query parser. No API calls.

Builds questions from KNOWN values (make/model pairs and dockets from the real corpus, random serials, dates, part numbers) in many
phrasings, then checks that parse_query recovers exactly what was put in. The expected values are the inputs, so the oracle is exact.
Usage: python eval/parser_fuzz.py [--seed N] [--n N]
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from extract import norm_model  # noqa: E402
from query_parse import parse_query  # noqa: E402

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
TEMPLATES = [
    "Does the proposed AD in docket {docket} apply to my {make} {model}, serial number {sn}, original certificate of airworthiness issued {date}?",
    "I operate a {make} {model} (S/N {sn}) with part number {pn} installed. Is it affected by docket {docket}?",
    "my {make} {model}, MSN {sn}, CofA {date}. does the NPRM {docket} apply?",
    "Is a {model} with serial number {sn} covered by the latest proposed AD in docket {docket}? Original airworthiness certificate dated {date}.",
    "Our {make} {model} has P/N {pn} fitted and the original certificate of airworthiness was issued on {date}. Does docket {docket} apply to us?",
    "Does {docket} apply to a {make} {model}?",
    "Which proposed ADs could affect my {make} {model}, serial {sn}?",
    "I own a {model} serial number {sn}. Original CofA {date}. Does the proposed AD in docket {docket} apply?",
    "Check docket {docket} against my aircraft: {make} {model}, S/N {sn}, part number {pn}, certificate issued {date}.",
    "does the proposed rule {docket} cover a {model}?",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--show", type=int, default=14)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    recs = [json.loads(line)["rec"] for line in open(ROOT / "data" / "processed" / "ad_records.jsonl", encoding="utf-8")]
    pool = []
    for r in recs:
        mk = r.get("make_norm")
        for m in (r.get("models") or [])[:3]:
            if mk and re.search(r"\d", m) and 3 <= len(m) <= 14 and " " not in m:
                pool.append((mk, m, r["docket"]))
    rnd.shuffle(pool)
    miss, tot = Counter(), Counter()
    bad = []
    for i in range(a.n):
        make, model, docket = rnd.choice(pool)
        d = date(rnd.randint(1988, 2025), rnd.randint(1, 12), rnd.randint(1, 28))
        iso = d.isoformat()
        long_ = f"{MONTHS[d.month - 1]} {d.day}, {d.year}"
        want = {"serial": str(rnd.randint(100, 99999)), "pn": f"{rnd.randint(100, 999)}A{rnd.randint(1000, 9999)}-{rnd.randint(1, 9)}"}
        t = rnd.choice(TEMPLATES)
        q = t.format(make=make if rnd.random() < 0.6 else "", model=model, sn=want["serial"], pn=want["pn"], docket=docket,
                     date=iso if rnd.random() < 0.5 else long_)
        q = re.sub(r"\s+", " ", q).replace(" ,", ",").replace("a  ", "a ")
        p = parse_query(q)
        cfg = p["cfg"]
        checks = {}
        if "{sn}" in t:
            checks["serial"] = cfg.get("serial") == want["serial"]
        if "{pn}" in t:
            checks["part_number"] = want["pn"] in (cfg.get("part_numbers") or [])
        if "{date}" in t:
            checks["cofa_date"] = cfg.get("cofa_date") == iso
        checks["docket"] = docket.upper() in p["dockets"] if "{docket}" in t else True
        cands = [norm_model(c) for c in p.get("model_candidates", [])]
        checks["model"] = bool(cands) and (norm_model(model) == cands[0] or norm_model(model) in cands[0] or cands[0] in norm_model(model))
        for k, ok in checks.items():
            tot[k] += 1
            if not ok:
                miss[k] += 1
                bad.append((k, q, {"serial": cfg.get("serial"), "date": cfg.get("cofa_date"), "pn": cfg.get("part_numbers"), "cands": p.get("model_candidates", [])[:3]}))
    print(f"seed={a.seed} questions={a.n}")
    for k in tot:
        print(f"  {k:12s} {tot[k] - miss[k]}/{tot[k]} = {100 * (tot[k] - miss[k]) / tot[k]:.1f}%")
    shown = Counter()
    for k, q, got in bad:
        if shown[k] < a.show // 3 + 1:
            shown[k] += 1
            print(f"MISS {k}: {q}\n      got {got}")


if __name__ == "__main__":
    main()
