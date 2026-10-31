"""Synthetic stress test: random aircraft configurations against every real notice, checked with oracles that do NOT use the extractor.

No API calls, no cost. Each oracle is a statement that must hold whatever the extractor did:
  O1  a model whose letters/digits do not occur anywhere in the notice text can never get APPLIES
  O2  a model that occurs literally in the applicability paragraph never gets DOES_NOT_APPLY from MODEL_NOT_LISTED
      (exclusions / serial / date can still legitimately say no, so only the model reason is checked)
  O3  APPLIES requires every input the notice's own words make necessary: if the paragraph mentions a serial number or a part
      number or an original certificate date, an APPLIES answer needs that field to have been supplied
  O4  determinism: the same input twice gives the same verdict
  O5  inputs that the notice does not mention must not change the verdict (extra serial / date / part numbers on a notice that has
      no such condition)
  O6  a withdrawn notice never says APPLIES
Violations are listed so a person can read the notice. Usage: python eval/synthetic_fuzz.py [--seed N] [--per-doc N]
"""
import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from applicability import AircraftConfig, verdict  # noqa: E402


def squash(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--per-doc", type=int, default=12)
    ap.add_argument("--show", type=int, default=12)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    recs = [json.loads(line) for line in open(ROOT / "data" / "processed" / "ad_records.jsonl", encoding="utf-8")]
    # model pool: every distinct token that looks like a model designation in any notice title
    pool = set()
    for r in recs:
        for t in re.findall(r"\b[A-Z]{1,4}-?\d{2,4}[A-Z0-9-]*\b", r["rec"].get("title") or ""):
            pool.add(t)
    pool = sorted(pool) + ["Falcon 7X", "Bell 505", "King Air 350", "Cessna 172", "ATR 72-600", "A330-243", "787-9", "CFM56-7B24"]
    viol, n, kinds = [], 0, Counter()

    def check(tag, r, cfg, v, why):
        viol.append((tag, r["rec"]["doc_id"], dict(model=cfg.model, serial=cfg.serial, cofa=cfg.cofa_date, pn=cfg.part_numbers), v.verdict, v.main_reason, why))

    for r in recs:
        rec, appl = r["rec"], r["appl"]
        text = rec["text"] or ""
        sq_all = squash(text)
        sec = appl.get("section")
        sq_sec = squash(text[sec["char_start"]:sec["char_end"]]) if sec else ""
        sec_txt = text[sec["char_start"]:sec["char_end"]] if sec else ""
        no_all = re.sub(r"(?:all|any)\s+(?:manufacturer\s+)?serial\s+numbers?", "", sec_txt, flags=re.I)   # "all serial numbers" is no condition
        needs_serial = bool(re.search(r"serial\s+numbers?|\bS/Ns?\b|\bMSN", no_all, re.I))
        needs_pn = bool(re.search(r"part\s+number|\bP/N\b", sec_txt, re.I))
        needs_date = bool(re.search(r"original\s+(?:airworthiness|export)", sec_txt, re.I))
        for _ in range(a.per_doc):
            model = rnd.choice(pool)
            cfg = AircraftConfig(model=model,
                                 serial=rnd.choice([None, str(rnd.randint(1, 9999)), f"{rnd.randint(1, 9)}00{rnd.randint(10, 99)}"]),
                                 cofa_date=rnd.choice([None, f"{rnd.randint(1985, 2026)}-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}"]),
                                 part_numbers=rnd.choice([[], [f"{rnd.randint(100, 999)}A{rnd.randint(1000, 9999)}-{rnd.randint(1, 9)}"]]))
            v = verdict(rec, appl, cfg)
            n += 1
            m = squash(model)
            parts = [squash(x) for x in model.split("-") if x.strip()]
            # a short-form list ("A330-201, -202 ... and -243") never spells the whole designation: accept family + suffix both present
            listed = m in sq_all or (len(parts) >= 2 and parts[0] in sq_all and parts[-1] in sq_all)
            if v.verdict == "APPLIES" and not listed:
                check("O1", r, cfg, v, "APPLIES for a model absent from the notice")
            if v.main_reason == "MODEL_NOT_LISTED" and sec and m in sq_sec and len(m) >= 4:
                check("O2", r, cfg, v, "model occurs in the applicability paragraph but was called not listed")
            if v.verdict == "APPLIES":
                miss = [k for k, need, got in (("serial", needs_serial, cfg.serial), ("part number", needs_pn, cfg.part_numbers), ("cert date", needs_date, cfg.cofa_date)) if need and not got]
                if miss:
                    check("O3", r, cfg, v, "APPLIES without " + ", ".join(miss) + " although the paragraph mentions it")
            if verdict(rec, appl, cfg).verdict != v.verdict:
                check("O4", r, cfg, v, "non-deterministic")
            if rec.get("is_withdrawal") and v.verdict == "APPLIES":
                check("O6", r, cfg, v, "withdrawn notice says APPLIES")
            if not (needs_serial or needs_pn or needs_date) and not appl.get("serial_ranges") and not appl.get("cofa_cutoff") and v.verdict != "CANNOT_DETERMINE":
                bare = AircraftConfig(model=model)
                if verdict(rec, appl, bare).verdict != v.verdict:
                    check("O5", r, cfg, v, "extra inputs changed the verdict")
    c = Counter(x[0] for x in viol)
    print(f"seed={a.seed} cases={n} violations={len(viol)}  by oracle: {dict(c)}")
    seen = set()
    for x in viol:
        key = (x[0], x[1])
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > a.show:
            break
        print(x)
    return len(viol)


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
