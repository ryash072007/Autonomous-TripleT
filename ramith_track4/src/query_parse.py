"""Phase 3: rule-based query parser. No LLM (an optional LLM fallback lives in llm.py and is OFF by default).

Rules are written from general principles about how engineers phrase AD questions, NOT from the wording of the frozen test set.
"""
import re
from datetime import datetime

from ingest import MAKE_RULES, norm_make

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DOCKET_RE = re.compile(r"\bFAA-\d{4}-\d{1,6}(?:R\d)?\b|\b\d{4}-[A-Z]{2}-\d{1,4}-AD\b", re.I)
AD_NUM_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
FR_DOC_RE = re.compile(r"\b(?:19|20)\d{2}-\d{4,6}\b")
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
LONG_DATE_RE = re.compile(rf"\b({MONTHS})\s+(\d{{1,2}}),?\s+(\d{{4}})\b", re.I)
SERIAL_RE = re.compile(r"\b(?:serial(?:\s+number)?|s/n|msn)\s*(?:no\.?|#|:)?\s*([A-Z0-9][A-Z0-9-]{1,})", re.I)
PN_RE = re.compile(r"\b(?:part\s+number|p/n)\s*(?:no\.?|#|:)?\s*([A-Z0-9][A-Z0-9./-]{3,})", re.I)
MODEL_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])((?:[A-Z][A-Za-z]{2,9}\s)?(?:[A-Za-z]{1,4}[-. ]?)?\d{1,4}[A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*)(?![A-Za-z0-9])")
QWORDS = set("which what does do is are any there tell show give find who how when where why can could would should will".split())

AVIATION_VOCAB = re.compile(
    r"\b(?:aircraft|airplane|aeroplane|helicopter|rotorcraft|engine|propeller|airworthiness|directive|\bADs?\b|NPRM|FAA|rulemaking|"
    r"docket|proposal|proposed|unsafe condition|inspection|supersede\w*|withdraw\w*|comment|applicab\w*|apply|applies|certificate|airframe|"
    r"boeing|airbus|bombardier|embraer|gulfstream|dassault|bell|cessna|piper|sikorsky|rolls-royce|cfm|general electric|pratt)\b", re.I)
JUDGEMENT_RE = re.compile(
    r"\b(?:is|are|am)\s+(?:my|our|the|this|that)\b[^?.]{0,60}\bairworthy\b|\bairworthy\b[^?.]{0,20}\?|"
    r"\b(?:safe|legal|ok|okay|permitted|allowed)\s+to\s+(?:fly|operate|dispatch|use|keep)|\bkeep\s+flying\b|\bsign[- ]?off\b|"
    r"\breturn(?:ed)?\s+to\s+service\b|\b(?:am|are)\s+i\s+compl\w+|\bcan\s+i\s+(?:fly|dispatch)\b", re.I)
FINAL_RE = re.compile(r"\b(?:final\s+(?:AD|rule|directive)|finali[sz]\w*|in\s+force|already\s+(?:in\s+effect|issued|published|adopted|final\w*)|became\s+(?:law|final)|"
                      r"currently\s+(?:in\s+effect|effective))\b", re.I)
EXT_SUBJECT_RE = re.compile(
    r"\b(?:listed|included|identified|specified|covered|named)\s+in\s+(?:the\s+)?(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada|[\w .-]{0,40}\bbulletin)\b|"
    r"\bwhat\b[^?]{0,60}\b(?:does|do)\s+(?:the\s+)?(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada)\b|"
    r"\b(?:EASA|TCCA|ANAC|CASA)\s+AD\s+[\w-]+[^?]{0,80}\b(?:say|specif\w+|require\w*|state\w*)\b", re.I)
VALUE_Q_RE = re.compile(r"\b(?:exact|specific|numeric)\b[^?]{0,40}\b(?:value|number|figure|limit)\b|\b(?:torque|limit|threshold)\s+value\b", re.I)
REVISION_RE = re.compile(r"\b(?:withdrawn|withdrew|withdraw|revised|revision|supplemental|re-?issued|latest|most recent|still\s+active|"
                         r"current\s+version|superseded|extended|extension|updated\s+(?:comment|deadline)|comment\s+(?:deadline|period|due)|"
                         r"how\s+many\s+(?:proposed\s+rules|versions|entries))\b", re.I)
APPLY_RE = re.compile(r"\b(?:apply|applies|applicable|applicability|affect\w*|cover\w*|relevant\s+to|concern\s+my|my\b)", re.I)
STOP = set("the a an of for to in on is are was were be been what which who how does do did and or with that this it its as at by from "
           "any there my me i about tell show give find proposed ad ads nprm directive directives airworthiness apply applies".split())


def _iso(y, m, d):
    try:
        return datetime(int(y), int(m), int(d)).date().isoformat()
    except ValueError:
        return None


def parse_query(q: str, known_makes=None) -> dict:
    """Return entities + intent. `cfg` holds only what the user stated (make, model, serial, cofa_date, part_numbers)."""
    out = {"q": q, "dockets": [], "ad_numbers": [], "fr_docs": [], "years": [], "cfg": {}, "intent": "lookup", "flags": []}
    out["dockets"] = [re.sub(r"R\d$", "", d.upper()) for d in DOCKET_RE.findall(q)]
    out["ad_numbers"] = AD_NUM_RE.findall(q)
    masked = DOCKET_RE.sub(" ", q)
    out["fr_docs"] = [d for d in FR_DOC_RE.findall(masked) if d not in out["ad_numbers"]]
    # years are read only outside identifiers (docket "2000-NM-120-AD", AD "2025-13-11" and FR doc numbers contain years)
    out["years"] = [int(y) for y in re.findall(r"\b((?:19|20)\d{2})\b", AD_NUM_RE.sub(" ", FR_DOC_RE.sub(" ", DOCKET_RE.sub(" ", q))))]

    cfg = out["cfg"]
    for m in MAKE_RULES:
        if re.search(m[0], q, re.I):
            cfg["make"] = m[1]
            break
    m = SERIAL_RE.search(q)
    if m:
        cfg["serial"] = m.group(1).strip(".,;")
    pns = [p.strip(".,;") for p in PN_RE.findall(q)]
    if pns:
        cfg["part_numbers"] = pns
    # certificate date: ISO or "Month d, yyyy"
    dates = []
    for y, mo, d in ISO_DATE_RE.findall(q):
        dates.append(_iso(y, mo, d))
    for mo, d, y in LONG_DATE_RE.findall(q):
        dates.append(_iso(y, datetime.strptime(mo[:3], "%b").month, d))
    dates = [d for d in dates if d]
    # an "AD number" like 2025-13-11 looks like an ISO date; only treat as a certificate date if near certificate wording
    cert_ctx = re.search(r"certificate|cofa|c of a|issued|dated|delivered|manufactured", q, re.I)
    ad_like = set(out["ad_numbers"])
    dates = [d for d in dates if d not in ad_like or cert_ctx]
    if dates and cert_ctx:
        cfg["cofa_date"] = dates[0]

    # model candidates: tokens with a digit, minus docket/AD/doc/date/PN/serial tokens and years
    block = set(out["ad_numbers"]) | set(out["fr_docs"]) | {p.upper() for p in pns} | set(dates)
    if "serial" in cfg:
        block.add(cfg["serial"].upper())
    cands = []
    for mm in MODEL_TOKEN_RE.finditer(masked):
        tok = mm.group(1).strip()
        if " " in tok:                                   # drop a leading make word ("Bell 505") or question word ("Which 757")
            first, rest = tok.split(None, 1)
            if first.lower() in QWORDS or any(re.search(pat, first, re.I) for pat, _ in MAKE_RULES):
                tok = rest
            else:
                cands.append(tok)       # unknown leading word: keep both "Vulcanair P.68" and the tail "P.68"; the corpus decides
                tok = rest
        if re.search(r"(?:^|[-\s])(?:19|20)\d{2}-\d", tok):    # foreign AD ids (CF-2026-20R1, 2026-0132) are not aircraft models
            continue
        if tok.upper() in block or re.fullmatch(r"(?:19|20)\d{2}", tok) or re.fullmatch(r"\d{1,2}", tok):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tok) or re.fullmatch(r"(?:part|ad)\s*\d+", tok, re.I):
            continue
        cands.append(tok)
    out["model_candidates"] = cands

    ql = q.lower()
    weak_apply = re.search(r"\bcover(?:s|ed|ing)?\b", q, re.I) and (cands or re.search(r"\bmy\b", q, re.I) or "serial" in cfg or "cofa_date" in cfg)
    if re.search(r"\b(?:apply|applies|applicable|applicability|affect\w*)\b", q, re.I) or weak_apply:
        out["intent"] = "applicability"          # an explicit apply-verb wins over words like "latest"
    elif REVISION_RE.search(q):
        out["intent"] = "revision"
    elif re.search(r"\bmy\b", q, re.I) and cands:
        out["intent"] = "applicability"
    if JUDGEMENT_RE.search(q):
        out["flags"].append("judgement")
    if FINAL_RE.search(q):
        out["flags"].append("final_rule")
    if EXT_SUBJECT_RE.search(q):
        out["flags"].append("external_subject")
    if VALUE_Q_RE.search(q):
        out["flags"].append("value_question")
    if not AVIATION_VOCAB.search(q) and not out["dockets"] and not out["ad_numbers"] and not cands:
        out["flags"].append("off_topic")
    old = [y for y in out["years"] if y < 2001]
    if old:
        out["flags"].append("pre_2001")
    out["keywords"] = [w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9/.-]*", q) if w.lower() not in STOP]
    return out


def has_entity(p: dict) -> bool:
    return bool(p["dockets"] or p["ad_numbers"] or p["fr_docs"] or p["cfg"].get("make") or p["model_candidates"])
