"""Blind set B1, step 1: fetch Federal Register AD NPRMs that are NOT in the spreadsheet corpus (never seen by the rules).

Seeded random sample. Writes eval/blind/fresh_docs.jsonl (one record per document, same shape as the corpus records).
"""
import json
import random
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build_records import load_docs  # noqa: E402
from parse_sections import parse_document  # noqa: E402

HEAD = {"User-Agent": "Autonomous-SG-2026-track4 (student hackathon project)"}
SEED, N = 20261031, 30
URL = ("https://www.federalregister.gov/api/v1/documents.json?conditions[agencies][]=federal-aviation-administration"
       "&conditions[type][]=PRORULE&conditions[term]=%22airworthiness+directives%22"
       "&conditions[publication_date][gte]={a}&conditions[publication_date][lte]={b}&per_page=100&page={p}"
       "&fields[]=document_number&fields[]=title&fields[]=abstract&fields[]=publication_date&fields[]=raw_text_url&fields[]=citation&fields[]=start_page&fields[]=end_page&fields[]=docket_ids")


def search(a, b):
    out, p = [], 1
    while True:
        r = requests.get(URL.format(a=a, b=b, p=p), headers=HEAD, timeout=30).json()
        out += r.get("results", [])
        if p >= r.get("total_pages", 1) or p >= 8:
            return out
        p += 1
        time.sleep(0.3)


def main():
    have = {d["doc_number"] for d in load_docs() if d["doc_number"]}
    pool = []
    for a, b in [("2025-01-01", "2025-12-31"), ("2026-10-20", "2026-10-31")]:
        pool += search(a, b)
    pool = [d for d in pool if d["title"].startswith("Airworthiness Directives") and d["document_number"] not in have]
    seen, uniq = set(), []
    for d in pool:
        if d["document_number"] not in seen:
            seen.add(d["document_number"]); uniq.append(d)
    print("candidate fresh docs:", len(uniq), "(corpus overlap excluded)")
    random.Random(SEED).shuffle(uniq)
    out = []
    for d in uniq:
        if len(out) >= N:
            break
        t = requests.get(d["raw_text_url"], headers=HEAD, timeout=45)
        if t.status_code != 200 or len(t.text) < 3000:
            continue
        text = t.text
        parsed = parse_document(text, d.get("start_page"))
        out.append({"doc_id": d["document_number"], "doc_number": d["document_number"], "docket": ", ".join(d.get("docket_ids") or []),
                    "subject": d["title"], "cfr_part": "Part 39", "issue_date": d["publication_date"], "citation": d.get("citation"),
                    "page_field": f"{d.get('start_page')}-{d.get('end_page')}", "start_page": d.get("start_page"), "summary": d.get("abstract") or "",
                    "source": "fr_text", "text": text, "sections": parsed["sections"], "is_withdrawal": parsed["is_withdrawal"],
                    "make_norm": "", "models": [], "comments": None, "comments_due": None})
        time.sleep(0.3)
    p = ROOT / "eval" / "blind" / "fresh_docs.jsonl"
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote", len(out), "fresh docs to", p)
    print("parsed Applicability section:", sum(1 for r in out if any(s["title"].lower().startswith("applicability") for s in r["sections"].values())),
          "| withdrawal:", sum(r["is_withdrawal"] for r in out))


if __name__ == "__main__":
    main()
