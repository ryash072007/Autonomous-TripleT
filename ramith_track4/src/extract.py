"""Phase 2: rule-based extraction of applicability conditions from an AD's Applicability section.

No LLM. Every extracted condition keeps (char_start, char_end) into the record's stored text so a verifier can
re-check it verbatim. Anything the rules cannot read is flagged (never guessed) so the engine returns CANNOT_DETERMINE.
"""
import re
from datetime import datetime

from parse_sections import get_section

GROUP_RE = re.compile(r"(?:(?<=\s)|^)\((\d{1,2})\)\s+(?=[A-Z])")
# "A330-201, -202, -203, -223, and -243"  /  "737-600, -700, -700C, -800"  /  "747-400 and -8"
# Blind-set finding: lists can drop a dash mid-way ("-223, 223F, -243"); items after the first only need to start with a digit.
EXPAND_RE = re.compile(
    r"\b([A-Z0-9][A-Z0-9]*[A-Z]?\d*)-([A-Z0-9][A-Za-z0-9/]*)((?:\s*,?\s*(?:and\s+|or\s+)?-?\s?\d[A-Za-z0-9/]*)+)"
)
SUFFIX_RE = re.compile(r"(?:^|[\s,])(?:(?:and|or)\s+)?-?\s?(\d[A-Za-z0-9/]*)")
CUTOFF_RE = re.compile(
    # \s+ everywhere: the Federal Register text wraps lines mid-phrase ("original \nairworthiness certificate")
    r"original\s+(?:airworthiness\s+certificate|export\s+certificate\s+of\s+airworthiness)[^.]{0,200}?"
    r"(on\s+or\s+before|before|on\s+or\s+after|after)\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    re.I | re.S,
)
EXCEPT_RE = re.compile(r"\bexcept\b[^.]{0,400}?(?:airplanes|helicopters|aircraft|engines|propellers)[^.]*\.", re.I | re.S)
# Blind-set finding: "identified as Group 3 in Boeing Alert Requirements Bulletin ..." and "as specified in paragraph 1.A.1 of ... Service Bulletin"
ASID_RE = re.compile(r"\b(?:identified|listed|specified|defined|described)\s+(?:as\s+[^.]{0,60}?\s+)?in\s+((?:[^.]|\.(?=\w)){5,260}?)(?=\.\s|\.$|$)", re.I | re.S)
PN_CLAUSE_RE = re.compile(r"(?:part\s+number|P/N)[^.]*?(?:installed|\.)", re.I | re.S)
PN_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?=[A-Z0-9./-]*\d)[A-Z0-9][A-Z0-9./-]{4,}(?![A-Za-z0-9])")
AD_NUM_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$|^\d{2}-\d{2}-\d{2}$")
SERIAL_RANGE_RE = re.compile(r"serial\s+numbers?\s+([A-Z0-9-]+)\s+(?:through|to|-)\s+([A-Z0-9-]+)", re.I)
SERIAL_LIST_RE = re.compile(
    r"(?:serial\s+numbers?\s*(?:\(\s*(?:S/Ns?|ESNs?|MSNs?)\s*\))?|\bS/Ns|\bESNs|\bMSNs)\s*:?\s*([^;]{3,400}?)(?=,?\s+(?:certificated|certified|with|that|on\s+which|installed)\b|[.;]|$)",
    re.I | re.S)
COND_RE = re.compile(
    r"\b(?:with|having|has|equipped|fitted|installed|delivered|manufactured|produced|that\s+(?:were|are|have|has)|"
    r"on\s+which|in\s+which|incorporating|modified|altered|operating|required\s+by|maintained)\b", re.I)
SUPERSEDE_RE = re.compile(r"supersed\w*[^.]{0,40}?(?:Airworthiness Directive \(AD\)|AD)\s+(\d{4}-\d{2}-\d{2})(?:\s+and\s+(?:AD\s+)?(\d{4}-\d{2}-\d{2}))?", re.I)


def norm_model(s: str) -> str:
    """Upper-case, strip spaces, normalise dashes: 'Falcon 7X' -> 'FALCON7X', 'A330 - 243' -> 'A330-243'."""
    s = re.sub(r"\s*[-‐-―]\s*", "-", str(s).upper())
    return re.sub(r"\s+", "", s)


def _clean(raw: str) -> str:
    """Whitespace/hyphen normalisation for MODEL matching only (never used for spans)."""
    t = re.sub(r"(?<=\w)-\s+(?=[A-Z0-9])", "-", raw)      # 'CFM56- 7B22' -> 'CFM56-7B22'
    t = re.sub(r"(?<=[ ,])-\s+(?=\d)", "-", t)             # ', - 700C' -> ', -700C'
    return re.sub(r"\s+", " ", t)


# "DHC-8-401 and -402", "CL-600-2B16, -2B19": the shared prefix is everything before the last dash of the first item
EXPAND2_RE = re.compile(
    r"\b([A-Z][A-Z0-9]*-\d+[A-Z]?)-([A-Z0-9][A-Za-z0-9/]*)((?:\s*,?\s*(?:and\s+|or\s+)?-\s?[A-Z0-9][A-Za-z0-9/]*)+)"
)
SUFFIX2_RE = re.compile(r"(?:^|[\s,])(?:(?:and|or)\s+)?-\s?([A-Z0-9][A-Za-z0-9/]*)")


def expand_models(text: str) -> set:
    """Normalised model strings implied by the text, including dash-suffix list expansion."""
    t = _clean(text)
    out = set()
    for m in EXPAND_RE.finditer(t):
        base, first, rest = m.group(1), m.group(2), m.group(3)
        out.add(norm_model(f"{base}-{first}"))
        for suf in SUFFIX_RE.findall(rest):
            out.add(norm_model(f"{base}-{suf}"))
    for m in EXPAND2_RE.finditer(t):
        base, first, rest = m.group(1), m.group(2), m.group(3)
        out.add(norm_model(f"{base}-{first}"))
        for suf in SUFFIX2_RE.findall(rest):
            out.add(norm_model(f"{base}-{suf}"))
    return out


def model_in_text(model: str, text: str) -> bool:
    """True if the user's model appears in `text`, directly (tolerating space/hyphen differences) or via list expansion."""
    u = norm_model(model)
    if not u:
        return False
    exp = expand_models(text)
    hay = _clean(text).upper()
    # "CL-600-2B16 (604 Variant)": the base designation is listed and every numeric token of the parenthetical appears in the text
    if "(" in str(model):
        base_, _, inner = str(model).partition("(")
        inner_tokens = re.findall(r"\d[\w-]*", inner)
        if inner_tokens and base_.strip() and model_in_text(base_.strip(), text) and all(t.upper() in hay for t in inner_tokens):
            return True
    # Candidates: the full designation, plus its "tail" without a family prefix ("RB211 Trent 772B-60" -> "772B-60"),
    # because notices list "Trent 768-60, 772-60, and 772B-60" once under a shared prefix.
    cands = [u]
    toks = str(model).split()
    for i in range(1, len(toks)):
        tail = norm_model(" ".join(toks[i:]))
        if re.search(r"\d", tail) and len(tail) >= 3:
            cands.append(tail)
    # a marketing name after the designation ("P-180 Avanti II") must not stop the designation itself ("P-180") from matching
    dig = [i for i, t in enumerate(toks) if re.search(r"\d", t)]
    if dig and dig[-1] < len(toks) - 1:
        head = norm_model(" ".join(toks[: dig[-1] + 1]))
        if len(head) >= 3 and head not in cands:
            cands.append(head)
    for c in cands:
        if c in exp:
            return True
        base = c.split("-")[0]
        # "Model 747 series" names every 747-xxx variant; require a bare base token followed by "series"
        # ... and "Model 747-8 series" names 747-8, 747-8F, 747-8I: every dash-prefix of the designation and its numeric stem may be the series
        parts_ = c.split("-")
        stems = {base} | {"-".join(parts_[:k]) for k in range(1, len(parts_))}
        if re.match(r"\d+", parts_[-1]):
            stems.add("-".join(parts_[:-1] + [re.match(r"\d+", parts_[-1]).group()]))
        if "-" in c and any(re.search(r"(?<![A-Z0-9-])" + re.escape(st) + r"\s+series\b", hay, re.I) for st in stems):
            return True
        chars = [re.escape(ch) for ch in c if ch != "-"]
        # a longer designation continuing the same name ("BK117" inside "BK 117 D-2", "205A" inside "205A-1") is a different model
        # a bare tail without a dash ("350" from "King Air 350") must not match inside a longer designator such as "PC-6/350"
        lead = r"(?<![A-Z0-9/.-])" if (c != u and "-" not in c) else r"(?<![A-Z0-9])"
        pat = lead + r"[\s-]*".join(chars) + r"(?![A-Z0-9])(?!-[A-Z0-9])(?!\s?[A-Z]-\d)"
        if re.search(pat, hay):
            return True
    return False


def _span(cs: int, m: re.Match, g: int = 0):
    return cs + m.start(g), cs + m.end(g)


def _parse_date(s: str):
    try:
        return datetime.strptime(s, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def extract_applicability(rec: dict) -> dict:
    """Return the structured applicability record for one corpus row (see ADRecord in the control prompt)."""
    key, sec = get_section(rec["sections"], "Applicability")
    if sec is None:
        return {"scope": "none", "reason": "withdrawal" if rec["is_withdrawal"] else "no_applicability_section", "section": None}
    cs, ce = sec["char_start"], sec["char_end"]
    raw = rec["text"][cs:ce]
    out = {
        "scope": "listed", "section": {"key": key, "page": sec["page"], "char_start": cs, "char_end": ce},
        "groups": [], "cofa_cutoff": None, "exclusions": [], "external_refs": [], "serial_ranges": [],
        "serial_unparsed": False, "supersedes_ads": [],
    }
    if re.search(r"\ball\b", raw[:200], re.I) and not re.search(r"as identified in", raw, re.I):
        out["scope"] = "all"
    # "applies to all airplanes ... with part X installed": no make or model restricts it, so MODEL_NOT_LISTED would be wrong
    out["model_agnostic"] = bool(re.search(r"applies\s+to\s+all\s+(?:airplanes|aircraft|helicopters|rotorcraft|engines|propellers)\b", raw))

    # groups: (c)(1), (c)(2)... or (1), (2)...; the lead text applies to every group
    marks = list(GROUP_RE.finditer(raw))
    if len(marks) >= 2:
        lead = raw[: marks[0].start()]
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(raw)
            out["groups"].append({"label": m.group(1), "lead": lead, "text": raw[m.start():end], "char_start": cs + m.start(), "char_end": cs + end})
    else:
        out["groups"].append({"label": None, "lead": "", "text": raw, "char_start": cs, "char_end": ce})
    for g in out["groups"]:
        body = g["lead"] + g["text"]
        # audit: a part-number clause without the word "installed" ("with ... P/N X") was missed -> any P/N mention is a condition
        g["pn_required"] = bool(re.search(r"part\s+number|P/N", body, re.I))
        pns = []
        for pm in PN_CLAUSE_RE.finditer(body):
            pns += [t.rstrip(".,;") for t in PN_TOKEN_RE.findall(pm.group(0)) if not AD_NUM_RE.match(t.rstrip(".,;"))]
        g["part_numbers"] = sorted(set(pns))
        # composite tokens ("SC1L500031-3/20218-3") or wrapped fragments cannot be matched reliably against a user's P/N
        g["pn_messy"] = any("/" in t or t.endswith("-") for t in g["part_numbers"])

    m = CUTOFF_RE.search(raw)
    if m:
        out["cofa_cutoff"] = {"direction": re.sub(r"\s+", " ", m.group(1).lower()), "date": _parse_date(re.sub(r"\s+", " ", m.group(2))),
                              "span": list(_span(cs, m)), "quote": m.group(0)}
    for m in EXCEPT_RE.finditer(raw):
        out["exclusions"].append({"span": list(_span(cs, m)), "quote": m.group(0)})
    for m in ASID_RE.finditer(raw):
        out["external_refs"].append({"name": re.sub(r"\s+", " ", m.group(1)).strip(), "span": list(_span(cs, m)), "quote": m.group(0)})
    def _group_of(pos):
        """Index of the (1)/(2) group containing offset `pos` of the section, None when the notice has a single group."""
        for gi, g_ in enumerate(out["groups"]):
            if g_["char_start"] - cs <= pos < g_["char_end"] - cs:
                return gi if len(out["groups"]) > 1 else None
        return None

    scrub = re.sub(r"(?:all|any)\s+(?:manufacturer\s+)?serial\s+numbers|model\s+and\s+serial\s+number", "", raw, flags=re.I)
    serial_clauses = []        # (start, end) in raw, blanked out of the residual-condition scan so "having serial number ..." is not a config clause
    if True:
        # Blind-set finding: lists like "serial numbers (S/Ns) 1002, 1004 through 1234 inclusive, 3001 through 3012 inclusive, and 3016"
        for m in SERIAL_LIST_RE.finditer(raw):
            # the Federal Register wraps lines inside serial numbers ("560- 6296"); re-join before splitting
            items = [i.strip() for i in re.split(r",\s*(?:and\s+)?|\s+and\s+", re.sub(r"(?<=[A-Z0-9])-\s+(?=[A-Z0-9])", "-", m.group(1))) if i.strip()]
            parsed = []
            for it in items:
                r1 = re.fullmatch(r"(?:serial\s+numbers?\s+)?([A-Z0-9-]+)\s+(?:through|to)\s+([A-Z0-9-]+)(?:\s+inclusive)?", it, re.I)
                r2 = re.fullmatch(r"(?:serial\s+numbers?\s+)?([A-Z0-9][A-Z0-9-]*)", it, re.I)
                if r1:
                    parsed.append((r1.group(1), r1.group(2)))
                elif r2 and re.search(r"\d", r2.group(1)):
                    parsed.append((r2.group(1), r2.group(1)))
                else:
                    parsed = []
                    break
            for lo, hi in parsed:
                out["serial_ranges"].append({"lo": lo, "hi": hi, "span": list(_span(cs, m, 1)), "group": _group_of(m.start())})
            if parsed:
                serial_clauses.append((m.start(), m.end(1)))
    if not out["serial_ranges"]:
        for m in SERIAL_RANGE_RE.finditer(raw):
            out["serial_ranges"].append({"lo": m.group(1), "hi": m.group(2), "span": list(_span(cs, m)), "group": _group_of(m.start())})
            serial_clauses.append((m.start(), m.end()))
    # Restraint (audit: serial extraction 3/4 correct): anything beyond a clean range is "unparsed" -> CANNOT_DETERMINE.
    n_serial_mentions = len(re.findall(r"serial\s+numbers?|\bS/N\b|\bMSN\b|\bESN\b", scrub, re.I))
    out["serial_unparsed"] = n_serial_mentions > len(out["serial_ranges"])
    # Configuration clauses the tool does not evaluate (STC installed, delivered before, equipped with, required by ...).
    # Audit: three silent misses -> detect by residual keywords after removing every clause we DO parse.
    # Skipped when a part-number clause was parsed (it contains "with ... installed" itself).
    resid = raw
    for sp in [out["cofa_cutoff"]["span"]] if out["cofa_cutoff"] else []:
        lead_in = re.search(r"\bwith\s+an?\s+$", raw[: sp[0] - cs], re.I)   # "..., with an original airworthiness certificate ..."
        a_ = sp[0] - cs - (len(lead_in.group(0)) if lead_in else 0)
        resid = resid[:a_] + " " * (sp[1] - cs - a_) + resid[sp[1] - cs:]
    for x in out["exclusions"] + out["external_refs"]:
        a_, b_ = x["span"]
        resid = resid[: a_ - cs] + " " * (b_ - a_) + resid[b_ - cs:]
    for a_, b_ in serial_clauses:       # a parsed serial clause (and its "having"/"with" lead-in) is handled by the serial rules
        lead = re.search(r"\b(?:having|with)\s+(?:the\s+)?$", raw[:a_], re.I)
        a2 = a_ - (len(lead.group(0)) if lead else 0)
        resid = resid[:a2] + " " * (b_ - a2) + resid[b_:]
    # "Note 1 to paragraph (c): ..." is explanatory (it restates model names, "helicopters with an EC135P3H designation are Model EC135P3"),
    # not a condition; blank it out up to the next numbered group or the end of the section
    resid = re.sub(r"Note\s+\d*\s*to\s+paragraph\s+\(c\)[^:]{0,40}:.*?(?=\n\s*\(\d{1,2}\)\s+[A-Z]|\Z)", lambda m_: " " * len(m_.group(0)), resid, flags=re.S)
    resid = re.sub(r"certifi(?:cated|ed)\s+in\s+any\s+category|with\s+an?\s+(?=original)|model\s+and\s+serial\s+number", lambda m_: " " * len(m_.group(0)), resid, flags=re.I)
    out["other_conditions"] = []
    if not any(g["pn_required"] for g in out["groups"]):
        for m in COND_RE.finditer(resid):
            out["other_conditions"].append({"span": list(_span(cs, m)), "quote": raw[m.start():m.end() + 80].split(".")[0]})
    sm = SUPERSEDE_RE.search(rec["summary"] or "")
    if sm:
        out["supersedes_ads"] = [x for x in sm.groups() if x]
    return out
