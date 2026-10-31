"""Phase 2: deterministic applicability engine. Pure functions, NO LLM.

verdict(rec, appl, config) -> Verdict with APPLIES | DOES_NOT_APPLY | CANNOT_DETERMINE, reason codes, and evidence spans.
Fixed evaluation order: Part 39 -> withdrawn -> text available -> model -> part number -> certificate date -> serial
-> exclusions -> external documents -> APPLIES.
Cert-date reason codes describe the user's date relative to the cutoff (BEFORE = on or before, AFTER = after), not scope.
"""
import re
from dataclasses import dataclass, field, asdict
from datetime import date

from extract import model_in_text, norm_model, expand_models
from ingest import norm_make

APPLIES, NOT_APPLY, CANNOT = "APPLIES", "DOES_NOT_APPLY", "CANNOT_DETERMINE"


@dataclass
class AircraftConfig:
    make: str | None = None
    model: str | None = None
    serial: str | None = None
    cofa_date: str | None = None            # ISO yyyy-mm-dd
    part_numbers: list = field(default_factory=list)


@dataclass
class Verdict:
    doc_id: str
    verdict: str
    reason_codes: list
    main_reason: str
    rule_fired: str
    evidence: list = field(default_factory=list)   # [{"label","char_start","char_end","quote"}]
    detail: str = ""

    def as_dict(self):
        return asdict(self)


def _ev(label, span, rec):
    if not span:
        return None
    a, b = span
    return {"label": label, "char_start": a, "char_end": b, "quote": rec["text"][a:b]}


def _mk(rec, v, codes, main, rule, evidence, detail=""):
    return Verdict(rec["doc_id"], v, codes, main, rule, [e for e in evidence if e], detail)


def _to_int(s):
    d = re.sub(r"\D", "", str(s))
    return int(d) if d else None


def _serial_in_ranges(serial, ranges):
    s = _to_int(serial)
    for r in ranges:
        lo, hi = _to_int(r["lo"]), _to_int(r["hi"])
        if None not in (s, lo, hi):
            if lo <= s <= hi:
                return True
        elif str(r["lo"]) <= str(serial) <= str(r["hi"]):
            return True
    return False


def verdict(rec: dict, appl: dict, cfg: AircraftConfig) -> Verdict:
    sec = appl.get("section")
    sec_ev = _ev("applicability section", (sec["char_start"], sec["char_end"]) if sec else None, rec)
    if rec["cfr_part"] != "Part 39":
        return _mk(rec, CANNOT, ["NOT_PART_39"], "NOT_PART_39", "part39", [], "Not a Part 39 airworthiness directive.")
    if rec["is_withdrawal"]:
        return _mk(rec, NOT_APPLY, ["DOC_WITHDRAWN"], "DOC_WITHDRAWN", "withdrawn", [],
                   "This notice withdraws a proposed AD; nothing is proposed to apply.")
    if appl.get("scope") == "none":
        return _mk(rec, CANNOT, ["SUMMARY_ONLY_COVERAGE"], "SUMMARY_ONLY_COVERAGE", "no_text", [],
                   "Applicability text is not available for this document; check the source notice.")
    if not cfg.model:
        return _mk(rec, CANNOT, ["INPUT_MISSING_MODEL"], "INPUT_MISSING_MODEL", "model", [sec_ev], "Aircraft model not supplied.")

    # --- model ---
    groups = appl["groups"]
    lead_text = groups[0]["lead"] if groups else ""
    matched = [g for g in groups if model_in_text(cfg.model, g["text"])]
    if not matched and lead_text and model_in_text(cfg.model, lead_text):
        matched = list(groups)
    if not matched:
        return _mk(rec, NOT_APPLY, ["MODEL_NOT_LISTED"], "MODEL_NOT_LISTED", "model", [sec_ev],
                   f"Model {cfg.model} is not named in the applicability paragraph.")
    codes, ev, main = ["MODEL_LISTED"], [sec_ev], "MODEL_LISTED"

    # --- part number (only if every matched group requires it) ---
    if all(g["pn_required"] for g in matched):
        pns = {p.upper() for g in matched for p in g["part_numbers"]}
        if not pns or any(g.get("pn_messy") for g in matched):
            return _mk(rec, CANNOT, codes + ["AMBIGUOUS_SCOPE"], "AMBIGUOUS_SCOPE", "part_number", ev,
                       "Applicability depends on an installed part number that could not be read reliably.")
        if not cfg.part_numbers:
            return _mk(rec, CANNOT, codes + ["INPUT_MISSING_PN"], "INPUT_MISSING_PN", "part_number", ev,
                       "Applicability depends on an installed part number; none supplied.")
        if {p.upper() for p in cfg.part_numbers} & pns:
            codes.append("PN_INSTALLED"); main = "PN_INSTALLED"
        else:
            return _mk(rec, NOT_APPLY, codes + ["PN_NOT_INSTALLED"], "PN_NOT_INSTALLED", "part_number", ev,
                       "None of the supplied part numbers is in the applicability list.")

    # --- certificate date ---
    cut = appl.get("cofa_cutoff")
    if cut and cut["date"]:
        cev = _ev("certificate-date condition", tuple(cut["span"]), rec)
        if not cfg.cofa_date:
            return _mk(rec, CANNOT, codes + ["INPUT_MISSING_CERT_DATE"], "INPUT_MISSING_CERT_DATE", "cert_date", ev + [cev],
                       "Applicability depends on the original certificate of airworthiness date; none supplied.")
        d, c = date.fromisoformat(cfg.cofa_date), date.fromisoformat(cut["date"])
        rel_before = d <= c
        d_ok = {"on or before": d <= c, "before": d < c, "on or after": d >= c, "after": d > c}[cut["direction"]]
        rel_code = "CERT_DATE_BEFORE_CUTOFF" if rel_before else "CERT_DATE_AFTER_CUTOFF"
        if not d_ok:
            return _mk(rec, NOT_APPLY, codes + [rel_code], rel_code, "cert_date", ev + [cev],
                       f"Certificate date {cfg.cofa_date} is outside the condition '{cut['direction']} {cut['date']}'.")
        codes.append(rel_code); main = rel_code; ev.append(cev)

    # --- serial ---
    if appl.get("serial_unparsed"):
        return _mk(rec, CANNOT, codes + ["AMBIGUOUS_SCOPE"], "AMBIGUOUS_SCOPE", "serial", ev,
                   "A serial-number condition is present but could not be read reliably; read the applicability paragraph.")
    if appl.get("serial_ranges"):
        sev = _ev("serial condition", tuple(appl["serial_ranges"][0]["span"]), rec)
        if not cfg.serial:
            return _mk(rec, CANNOT, codes + ["INPUT_MISSING_SERIAL"], "INPUT_MISSING_SERIAL", "serial", ev + [sev],
                       "Applicability depends on serial number; none supplied.")
        if not _serial_in_ranges(cfg.serial, appl["serial_ranges"]):
            return _mk(rec, NOT_APPLY, codes + ["SERIAL_OUT_OF_RANGE"], "SERIAL_OUT_OF_RANGE", "serial", ev + [sev],
                       "Serial number is outside the stated range.")
        codes.append("SERIAL_IN_RANGE"); main = "SERIAL_IN_RANGE"; ev.append(sev)

    # --- exclusions ---
    if appl.get("exclusions"):
        x = appl["exclusions"][0]
        return _mk(rec, CANNOT, codes + ["EXCLUSION_UNVERIFIABLE"], "EXCLUSION_UNVERIFIABLE", "exclusion", ev + [_ev("exclusion", tuple(x["span"]), rec)],
                   "The AD excludes aircraft meeting a condition (e.g. maintenance programme already revised); confirm yours does not.")

    # --- configuration clauses the tool cannot check (equipped with ..., required by ...) ---
    if appl.get("other_conditions"):
        oc = appl["other_conditions"][0]
        return _mk(rec, CANNOT, codes + ["AMBIGUOUS_SCOPE"], "AMBIGUOUS_SCOPE", "other_condition", ev + [_ev("configuration condition", tuple(oc["span"]), rec)],
                   "Applicability has a configuration condition this tool does not evaluate; read the quoted clause.")

    # --- external documents defining applicability ---
    ext = [e for e in appl.get("external_refs", []) if not re.match(r"^paragraphs?\b", e["name"], re.I) and not re.search(r"\bof this AD\b", e["name"], re.I)]
    if ext:
        return _mk(rec, CANNOT, codes + ["EXTERNAL_DOC_REQUIRED"], "EXTERNAL_DOC_REQUIRED", "external", ev + [_ev("external reference", tuple(ext[0]["span"]), rec)],
                   f"Applicability is defined by a document that is not in this corpus: {ext[0]['name'][:160]}")

    return _mk(rec, APPLIES, codes, main, "all_conditions_met", ev, "All applicability conditions that could be checked are satisfied.")


# ---- config sanity (make vs model) ----
def build_model_index(records_with_appl) -> dict:
    """norm(model) -> set(make_norm) over the corpus (xlsx Model column + expanded applicability model lists)."""
    idx = {}
    for rec, appl in records_with_appl:
        mk = rec["make_norm"]
        for m in rec.get("models", []):
            idx.setdefault(norm_model(m), set()).add(mk)
        sec = appl.get("section")
        if sec:
            for m in expand_models(rec["text"][sec["char_start"]:sec["char_end"]]):
                idx.setdefault(m, set()).add(mk)
    return idx


def config_contradiction(cfg: AircraftConfig, model_index: dict):
    """Return a message if the make/model pair contradicts the corpus (model known only under another make)."""
    if not (cfg.make and cfg.model):
        return None
    makes = model_index.get(norm_model(cfg.model))
    if makes and norm_make(cfg.make) not in makes:
        return f"{cfg.model} appears in the corpus only under {', '.join(sorted(makes))}, not {cfg.make}."
    return None
