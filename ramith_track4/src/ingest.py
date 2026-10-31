"""Phase 1A: load the AD NPRM index, normalise makes, resolve FR document numbers, fetch full text (cached)."""
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "ad_nprm.xlsx"
CACHE = ROOT / "data" / "cache" / "fr"
PROCESSED = ROOT / "data" / "processed"
API = "https://www.federalregister.gov/api/v1/documents/{doc}.json?fields[]=raw_text_url&fields[]=type&fields[]=page_length&fields[]=docket_ids&fields[]=title&fields[]=publication_date&fields[]=citation&fields[]=start_page&fields[]=end_page"
HEADERS = {"User-Agent": "Autonomous-SG-2026-track4 (student hackathon project; contact via GitHub ryash072007/Autonomous-TripleT)"}
# Handles .../documents/YYYY/MM/DD/NNNN-NNNNN/..., .../documents/NNNN-NNNNN and the short .../d/NNNN-NNNNN forms.
DOC_RE = re.compile(r"federalregister\.gov/(?:documents|d|a)/(?:\d{4}/\d{2}/\d{2}/)?([A-Za-z0-9]+-\d+(?:-\d+)?)")

# Explicit, reviewable make normalisation (substring rules, first match wins). Logged in DECISIONS.md.
MAKE_RULES = [
    (r"boeing", "Boeing"),
    (r"mcdonnell", "McDonnell Douglas"),
    (r"airbus helicopters", "Airbus Helicopters"),
    (r"airbus canada", "Airbus Canada"),
    (r"airbus defence", "Airbus Defence and Space"),
    (r"airbus", "Airbus"),
    (r"bombardier", "Bombardier"),
    (r"gulfstream", "Gulfstream"),
    (r"rolls-royce", "Rolls-Royce"),
    (r"general electric|ge aerospace", "General Electric"),
    (r"cfm international", "CFM International"),
    (r"pratt", "Pratt & Whitney"),
    (r"bell", "Bell"),
    (r"dassault", "Dassault"),
    (r"embraer", "Embraer"),
    (r"cessna|textron aviation", "Cessna"),
    (r"piper", "Piper"),
    (r"de havilland", "De Havilland"),
    (r"sikorsky", "Sikorsky"),
    (r"ontic", "Ontic"),
]


def norm_make(raw) -> str:
    s = str(raw or "").lower()
    for pat, name in MAKE_RULES:
        if re.search(pat, s):
            return name
    return str(raw or "").split("|")[0].strip() or "UNKNOWN"


def load_index() -> pd.DataFrame:
    df = pd.read_excel(RAW)
    df["Link for Submitting Public Comment"] = df["Link for Submitting Public Comment"].fillna("")
    df["doc_number"] = df["Link for Submitting Public Comment"].str.extract(DOC_RE)[0]
    df["make_norm"] = df["Make"].map(norm_make)
    df["issue_iso"] = pd.to_datetime(df["Issue Date"], errors="coerce").dt.strftime("%Y-%m-%d")
    # doc id: FR document number if resolved, else docket@issue date (convention in DECISIONS.md #5)
    df["doc_id"] = df["doc_number"].where(df["doc_number"].notna(), df["Docket Number"].astype(str) + "@" + df["issue_iso"].astype(str))
    return df


def fetch_one(doc: str, session: requests.Session) -> str:
    """Return 'cached', 'ok' or 'err:<reason>'. Idempotent."""
    meta_p, txt_p = CACHE / f"{doc}.json", CACHE / f"{doc}.txt"
    if meta_p.exists() and txt_p.exists():
        return "cached"
    for attempt in range(4):
        try:
            r = session.get(API.format(doc=doc), headers=HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            meta = r.json()
            t = session.get(meta["raw_text_url"], headers=HEADERS, timeout=45)
            t.raise_for_status()
            txt_p.write_text(t.text, encoding="utf-8")
            meta_p.write_text(json.dumps(meta), encoding="utf-8")
            return "ok"
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
            time.sleep(1 + attempt)
    return f"err:{err}"


def fetch_all(df: pd.DataFrame) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    docs = df["doc_number"].dropna().unique().tolist()
    out, s = {}, requests.Session()
    for i, d in enumerate(docs, 1):
        out[d] = fetch_one(d, s)
        if out[d] == "ok":
            time.sleep(0.2)  # <= ~5 req/s
        if i % 25 == 0:
            print(f"fetched {i}/{len(docs)}", flush=True)
    return out


if __name__ == "__main__":
    PROCESSED.mkdir(parents=True, exist_ok=True)
    idx = load_index()
    print("rows", len(idx), "with doc_number", idx.doc_number.notna().sum(), "unique", idx.doc_number.nunique())
    res = fetch_all(idx)
    (PROCESSED / "fetch_results.json").write_text(json.dumps(res, indent=1))
    from collections import Counter
    print(Counter(v.split(":")[0] for v in res.values()))
    print([ (k, v) for k, v in res.items() if v.startswith("err")][:10])
