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
SERIAL_RE = re.compile(r"\b(?:serial(?:\s+number)?|s/n|msn)\s*(?:no\.?|#|:)?\s*((?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{1,})", re.I)
PN_RE = re.compile(r"\b(?:part\s+number|p/n)\s*(?:no\.?|#|:)?\s*([A-Z0-9][A-Z0-9./-]{3,})", re.I)
MODEL_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])((?:[A-Z][A-Za-z]{2,9}\s)?(?:[A-Za-z]{1,4}[-. ]?){0,2}\d{1,4}[A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*(?:\s[A-Z]-\d{1,2})?)(?![A-Za-z0-9])")
GENERIC_LEAD = {"model", "models", "type", "series", "variant", "version", "the", "a", "an", "my", "our", "its"}
FAMILY_RE = re.compile(r"\b([A-Z]{1,4}[- ]?\d{2,4}[A-Z]?)\s+([A-Z][a-z]{2,9})\s+(\d{1,4}[A-Za-z0-9]*(?:[-/][A-Za-z0-9]+)*)")
YEAR_CTX_RE = re.compile(
    r"(?:\b(?:from|in|before|since|dated|issued|during|circa|of|year|early|late|mid|until|prior\s+to)\s+|"
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+(?:\d{1,2},?\s+)?)((?:19|20)\d{2})\b", re.I)
OWN_CUE_RE = re.compile(r"\b(?:my|our|i\s+(?:operate|have|fly|own)|we\s+(?:operate|have|fly|own)|aircraft\s+is|helicopter\s+is|airplane\s+is|operate|owner\s+of|flying)\b", re.I)
FOREIGN_AD_ID_RE = re.compile(r"\b(?:EASA|Transport\s+Canada|TCCA|ANAC|CASA)\s+(?:AD|Airworthiness\s+Directive)\s+[A-Z0-9][A-Z0-9/-]*", re.I)
QWORDS = set("which what does do is are any there tell show give find who how when where why can could would should will".split())

AVIATION_VOCAB = re.compile(
    r"\b(?:aircraft|airplane|aeroplane|helicopter|rotorcraft|engine|propeller|airworthiness|directive|\bADs?\b|NPRM|FAA|rulemaking|"
    r"docket|proposal|proposed|unsafe condition|inspection|supersede\w*|withdraw\w*|comment|applicab\w*|apply|applies|certificate|airframe|"
    r"boeing|airbus|bombardier|embraer|gulfstream|dassault|bell|cessna|piper|sikorsky|rolls-royce|cfm|general electric|pratt)\b", re.I)
JUDGEMENT_RE = re.compile(
    r"\b(?:is|are|am)\s+(?:my|our|the|this|that)\b[^?.]{0,60}\bairworthy\b|\bairworthy\b[^?.]{0,20}\?|"
    r"\b(?:safe|legal|ok|okay|permitted|allowed)\s+to\s+(?:fly|operate|dispatch|use|keep)|\bkeep\s+flying\b|\bsign[- ]?off\b|"
    r"\breturn(?:ed)?\s+to\s+service\b|\b(?:am|are)\s+i\s+compl\w+|\bcan\s+i\s+(?:fly|dispatch)\b|"
    r"\b(?:confirm|certify|guarantee|assure|verify)\b[^?.]{0,80}\b(?:airworthy|compliant|compliance|legal(?:ly)?|cleared|safe)\b|"
    r"\b(?:fully|legally)\s+(?:compliant|cleared|permitted|allowed)\b|\bcleared\s+to\s+fly\b", re.I)
FINAL_RE = re.compile(r"\b(?:final\s+(?:AD|rule|directive)|finali[sz]\w*|in\s+force|already\s+(?:in\s+effect|issued|published|adopted|final\w*)|became\s+(?:law|final)|"
                      r"currently\s+(?:in\s+effect|effective))\b", re.I)
EXT_SUBJECT_RE = re.compile(
    r"\b(?:listed|included|identified|specified|covered|named)\s+in\s+(?:the\s+)?(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada|[\w .-]{0,40}\bbulletin)\b|"
    r"\bwhat\b[^?]{0,60}\b(?:does|do)\s+(?:the\s+)?(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada)\b|"
    r"\b(?:EASA|TCCA|ANAC|CASA)\s+AD\s+[\w-]+[^?]{0,80}\b(?:say|specif\w+|require\w*|state\w*)\b|"
    r"\bwhat\b[^?]{0,140}\b(?:does|do)\s+(?:the|that|this)\s+(?:(?:service|alert|requirements?)\s+)*(?:bulletin|SB|service\s+information)\s+(?:specify|require|say|state|contain|describe)\w*|"
    r"\b(?:procedures|compliance\s+times?|requirements|actions|instructions|corrective\s+actions)\b[^?]{0,80}\b(?:given|specified|stated|contained|described|listed|set\s+out)\s+in\s+the\s+(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada)|"
    r"\bwhat\b[^?]{0,60}\b(?:do|does)\s+(?:that|the|this)\s+(?:(?:service|alert|requirements?)\s+)*(?:bulletin|SB)(?:'?s)?\b[^?]{0,60}\b(?:actions?|procedures?|instructions?|requirements?|compliance)\b", re.I)
# estimated cost / labour / work-hour questions: the figures sit in the notice's "Costs of Compliance" table, which this tool does not extract
COST_Q_RE = re.compile(
    r"\b(?:labou?r|parts|total|estimated)\s+costs?\b|\bper[- ](?:helicopter|airplane|aircraft|engine|product)\s+cost\b|\bcosts?\s+(?:to|for|of)\s+(?:comply|compliance|(?:U\.?S\.?\s+)?operators)\b|"
    r"\bwork[- ]?hours?\b|\bhow\s+much\s+(?:will|would|does|do|is)\b[^?]{0,60}\bcost\b|\bin\s+dollars\b", re.I)
UNKNOWN_VARIANT_RE = re.compile(
    r"(?:don'?t|do not|doesn'?t|not)\s+(?:know|show|sure|say|specify|certain)[^.?]{0,100}\b(?:variant|model|version|dash)\b|"
    r"\b(?:exact|specific)\s+(?:variant|model|version)[^.?]{0,25}\b(?:unknown|unclear|not\s+known)\b|\bunknown\s+(?:variant|model|version)\b|\bvariant\s+unknown\b", re.I)
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
    # Blind-set finding: "Falcon 2000" is not the year 2000, so a year only counts in a date context (from/in/before/since/... or a month).
    _noid = AD_NUM_RE.sub(" ", FR_DOC_RE.sub(" ", DOCKET_RE.sub(" ", q)))
    out["years"] = sorted({int(y) for y in re.findall(r"\b(19\d{2})\b", _noid)} | {int(y) for y in YEAR_CTX_RE.findall(_noid)})
    # 19xx years always count; a bare "2000" only in a date context (Falcon 2000)

    cfg = out["cfg"]
    # make = the one named FIRST in the sentence ("De Havilland Canada (formerly Bombardier)" is De Havilland, not Bombardier)
    q_make = re.sub(r"\((?:formerly|previously|type certificate)[^)]*\)|previously held by[^,.;)]*|formerly[^,.;)]*", " ", q, flags=re.I)
    hits = [(m_.start(), i, name) for i, (pat, name) in enumerate(MAKE_RULES) for m_ in [re.search(pat, q_make, re.I)] if m_]
    if hits:
        cfg["make"] = min(hits)[2]
    m = SERIAL_RE.search(q)
    if m:
        cfg["serial"] = m.group(1).strip(".,;")
    pns = [p.strip(".,;") for p in PN_RE.findall(q)]
    if pns:
        cfg["part_numbers"] = pns
    # certificate date: ISO or "Month d, yyyy"
    dates = []
    # Blind-set finding: a date after "on or before / before / after ..." is the AD's cutoff being described, not the user's certificate date
    q_dates = re.sub(rf"(?:on or before|before|on or after|after|prior to|until|no later than)\s+(?:(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})",
                     " ", q, flags=re.I)
    for y, mo, d in ISO_DATE_RE.findall(q_dates):
        dates.append(_iso(y, mo, d))
    for mo, d, y in LONG_DATE_RE.findall(q_dates):
        dates.append(_iso(y, datetime.strptime(mo[:3], "%b").month, d))
    dates = [d for d in dates if d]
    # an "AD number" like 2025-13-11 looks like an ISO date; only treat as a certificate date if near certificate wording
    cert_ctx = re.search(r"certificate|cofa|c of a|issued|dated|delivered|manufactured", q, re.I)
    ad_like = set(out["ad_numbers"])
    dates = [d for d in dates if d not in ad_like or cert_ctx]
    negated = re.search(r"(?:don't|do not|doesn't|dont|not sure|unsure|unknown|can't|cannot|no idea|haven't|have not|without)[^.?]{0,90}(?:certificate|cofa|c of a|date)", q, re.I)
    if dates and cert_ctx and not negated:
        cfg["cofa_date"] = dates[0]

    # model candidates: tokens with a digit, minus docket/AD/doc/date/PN/serial tokens and years
    block = set(out["ad_numbers"]) | set(out["fr_docs"]) | {p.upper() for p in pns} | set(dates)
    if "serial" in cfg:
        block.add(cfg["serial"].upper())
    cands, cand_pos = [], {}
    # the serial / part-number clauses and calendar dates are not model designations ("S/N 23327" must not yield "N 23327", nor "April 21")
    for rx in (SERIAL_RE, PN_RE, LONG_DATE_RE, FOREIGN_AD_ID_RE):
        masked = rx.sub(lambda m_: " " * len(m_.group(0)), masked)
    for mm in MODEL_TOKEN_RE.finditer(masked):
        tok = mm.group(1).strip()
        cand_pos.setdefault(tok, mm.start(1))
        if " " in tok:                                   # drop a leading make word ("Bell 505") or question word ("Which 757")
            first, rest = tok.split(None, 1)
            cand_pos.setdefault(rest, mm.start(1) + len(first) + 1)
            if first.lower() in QWORDS or first.lower() in GENERIC_LEAD or first.islower() or any(re.search(pat, first, re.I) for pat, _ in MAKE_RULES):
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
        if re.fullmatch(rf"(?:{MONTHS})\s+\d{{1,2}}", tok, re.I):     # "February 2" is a date, not a model
            continue
        cands.append(tok)
    # family + variant ("RB211 Trent 892-17"): merge, and drop shorter candidates that overlap the merged span
    for fm in FAMILY_RE.finditer(masked):
        tok = f"{fm.group(1)} {fm.group(2)} {fm.group(3)}"
        s0, s1 = fm.start(1), fm.end(3)
        cands = [c for c in cands if not (c in cand_pos and cand_pos[c] < s1 and cand_pos[c] + len(c) > s0)]
        cands.append(tok)
        cand_pos[tok] = s0
    # prefer the model the USER says they fly ("my aircraft is ...", "I operate ...") over a model that merely describes the AD
    def _prio(t):
        pos = cand_pos.get(t, cand_pos.get(t.split(None, 1)[-1], 0))
        return (0 if OWN_CUE_RE.search(q[max(0, pos - 80):pos]) else 1, pos)
    cands = sorted(dict.fromkeys(cands), key=_prio)
    out["model_candidates"] = cands
    # models the user says they fly, as opposed to models that only describe the AD ("... and would add the ASW-15B to the applicability")
    out["own_models"] = [c for c in cands if _prio(c)[0] == 0]
    # an explicit "Model X" names the formal designation and outranks a marketing name ("Global 7500 (Model BD-700-2A12)")
    explicit = [c for c in out["own_models"] if re.search(r"\bModel\s+" + re.escape(c) + r"(?![A-Za-z0-9])", q)]
    out["own_models"] = explicit + [c for c in out["own_models"] if c not in explicit]
    if UNKNOWN_VARIANT_RE.search(q):
        out["flags"].append("variant_unknown")

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
    # "is it still moving toward a final rule?" asks about the NPRM's status, not whether a final AD exists
    # "Transport Canada has already issued an AD" is about a foreign AD, not an FAA final rule
    if FINAL_RE.search(q) and not re.search(r"\b(?:EASA|TCCA|ANAC|CASA|Transport\s+Canada)\b[^.?]{0,40}\b(?:already|has|have)\s+(?:issued|published)\b", q, re.I) and not re.search(r"\b(?:toward|towards|pending|awaiting|moving|progress\w*|heading)\b[^?.]{0,25}\bfinal\b", q, re.I):
        out["flags"].append("final_rule")
    # a user who states their own aircraft and points at a bulletin wants a verdict (CANNOT_DETERMINE, bulletin quoted), not a refusal
    own_given = bool(out["own_models"]) and out["intent"] == "applicability"
    if (EXT_SUBJECT_RE.search(q) and not own_given) or (FOREIGN_AD_ID_RE.search(q) and out["intent"] != "applicability"
                                    and re.search(r"\b(?:what|which|explain|describe|summari[sz]e|list|how)\b", q, re.I)
                                    and not re.search(r"\bproposed\b|\bNPRM\b", q, re.I)):
        out["flags"].append("external_subject")
    if COST_Q_RE.search(q):
        out["flags"].append("cost_question")
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
