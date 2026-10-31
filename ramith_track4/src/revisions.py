"""Phase 2: docket revision graph and deterministic latest-status. No LLM.

Entry events are read from each notice's own summary / comments text; the latest status is the last dated entry.
"""
import re
from collections import defaultdict

EVENT_RULES = [  # first match wins
    ("withdrawal", re.compile(r"\bis withdrawing\b|\bNPRM is withdrawn\b|\bwithdraws?\b[^.]{0,120}\b(?:NPRMs?|notices?\s+of\s+proposed\s+rulemaking)\b", re.I | re.S)),
    ("revised_nprm", re.compile(r"\bis revising (?:a|the) notice of proposed rulemaking\b|\bSNPRM\b|supplemental notice of proposed rulemaking|\bis revising an NPRM\b", re.I)),
    ("comment_extension", re.compile(r"extension of the comment period|extend(?:s|ing) the comment period|comment period (?:is )?(?:extended|reopened)", re.I)),
    ("reopened", re.compile(r"\breopen", re.I)),
    ("correction", re.compile(r"\bis correcting\b|\bcorrection\b", re.I)),
    ("nprm", re.compile(r"proposes to (?:adopt|supersede|revise|remove)", re.I)),
]
R1_RE = re.compile(r"R\d$")


def classify(rec: dict) -> str:
    text = (rec["summary"] or "") + " " + (rec.get("comments") or "")
    if re.search(r"\bWithdrawal\b", rec.get("subject") or ""):      # "Airworthiness Directives; Withdrawal -- Cessna ..." (some summaries are empty or plural)
        return "withdrawal"
    for name, rx in EVENT_RULES:
        if rx.search(text):
            return name
    return "nprm" if rec["summary"] else "unknown"


def docket_keys(docket: str) -> list:
    """Split multi-docket cells and fold 'R1' re-issues into their base docket."""
    out = []
    for d in str(docket).split(","):
        d = d.strip()
        if d:
            out.append(R1_RE.sub("", d))
    return out


def build_graph(records: list) -> dict:
    g = defaultdict(list)
    for r in records:
        ev = {"doc_id": r["doc_id"], "date": r["issue_date"], "event": classify(r), "docket_raw": r["docket"]}
        for k in docket_keys(r["docket"]):
            g[k].append(ev)
    for k in g:
        g[k].sort(key=lambda e: (e["date"] or "", e["doc_id"]))
    return dict(g)


def latest_status(graph: dict, docket: str) -> dict:
    """Deterministic status for a docket: the last dated entry decides (withdrawal / revised NPRM / comment extension / NPRM)."""
    keys = docket_keys(docket)
    entries = []
    for k in keys:
        entries += graph.get(k, [])
    if not entries:
        return {"docket": docket, "status": "unknown", "trail": [], "latest": None}
    entries = sorted({e["doc_id"]: e for e in entries}.values(), key=lambda e: (e["date"] or "", e["doc_id"]))
    last = entries[-1]
    # a comment-extension notice does not replace the proposal it extends; look back for the substantive entry
    substantive = [e for e in entries if e["event"] not in ("comment_extension", "correction", "reopened")]
    head = substantive[-1] if substantive else last
    label = {"withdrawal": "WITHDRAWN", "revised_nprm": "REVISED_NPRM (supplemental)", "nprm": "NPRM"}.get(head["event"], head["event"].upper())
    return {"docket": docket, "status": label, "latest": head, "last_entry": last, "trail": entries,
            "multiple_versions": len(entries) > 1}
