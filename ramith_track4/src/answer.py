"""Phase 3: extractive answers with verified quotes, typed refusals, deterministic verdicts and revision status.

NO generated prose: every factual line is a verbatim quote from the stored source or a field rendered from validated
extraction/engine output. Fixed template labels only. Optional LLM never touches this module (see llm.py).
"""
import re
import time

from applicability import AircraftConfig, config_contradiction, verdict as engine_verdict
from extract import model_in_text
from ingest import norm_make
from parse_sections import page_at
from query_parse import parse_query
from retrieve import tokenize
from revisions import docket_keys, latest_status

BANNER = "PROPOSED RULE (NPRM): not legally binding. Verify against the final AD in the Federal Register."
BANNER_WITHDRAWN = "WITHDRAWAL NOTICE: the proposal it refers to has been withdrawn. Not a requirement."
T_LOW = 8.0                    # BM25 floor for an unanchored lookup; tuned on the dev split + adhoc set only (see DECISIONS.md)
MAX_QUOTE = 1500
COMMON_CAPS = set("""federal register faa department transportation united states airworthiness directive directives federal
january february march april may june july august september october november december monday tuesday wednesday thursday friday
saturday sunday""".split())
UNIT_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:N\.?\s?m|Nm|daN|in\.?-?lbs?|ft\.?-?lbs?|lbf|%|percent|hours?|days?|months?|flight\s+(?:hours|cycles)|FH|FC|cycles|mm|inch\w*)", re.I)


# ---------------- helpers ----------------
def refusal(code, message, resolve, parsed=None, t0=None, ret_ms=0.0):
    return {"type": "refusal", "refusal": {"code": code, "message": message, "what_would_resolve_it": resolve}, "cards": [],
            "parsed": _public(parsed), "latency_ms": {"retrieval": round(ret_ms, 1), "total": round((time.perf_counter() - t0) * 1000, 1) if t0 else None}}


def _public(p):
    if not p:
        return None
    return {k: p[k] for k in ("dockets", "ad_numbers", "fr_docs", "cfg", "intent", "flags", "model_candidates")}


def _quote(C, rec, field, a, b, label, section=None):
    b = min(b, a + MAX_QUOTE)
    src = rec["summary"] if field == "summary" else rec["text"]
    s = src[a:b]
    lead = len(s) - len(s.lstrip())
    s = s.strip()
    a2 = a + lead
    page = rec["start_page"] if field == "summary" else page_at(rec["text"], a2, rec["start_page"])
    return {"label": label, "field": field, "section": section, "page": page, "char_start": a2, "char_end": a2 + len(s), "text": s}


def verify_quote(rec, q) -> bool:
    src = rec["summary"] if q["field"] == "summary" else rec["text"]
    return bool(q["text"].strip()) and src[q["char_start"]:q["char_end"]] == q["text"]


def best_sentences(chunk, terms, n=2, maxlen=520):
    text = chunk["text"]
    pos = [0] + [m.end() for m in re.finditer(r"(?<=[.!?])\s+(?=[A-Z(\[])", text)] + [len(text)]
    sents = [(pos[i], text[pos[i]:pos[i + 1]]) for i in range(len(pos) - 1)]
    scored = []
    for i, (off, s) in enumerate(sents):
        toks = set(tokenize(s))
        sc = sum(1 for t in terms if t in toks)
        if s.strip():
            scored.append((-sc, i, off, s))
    scored.sort()
    out = []
    for sc, i, off, s in scored[:n]:
        if -sc == 0 and out:
            break
        out.append((chunk["char_start"] + off, chunk["char_start"] + off + min(len(s.rstrip()), maxlen)))
    return sorted(out)


def _vocab(C):
    if not hasattr(C, "_vocab"):
        C._vocab = {t for c in C.chunks for t in tokenize(c["index"])}
    return C._vocab


def rare_query_tokens(C, q):
    """Query tokens that are entity-like for this corpus: present, but in few chunks (e.g. 'vulcanair', 'aw139')."""
    if not hasattr(C, "_df"):
        from collections import Counter
        C._df = Counter(t for c in C.chunks for t in set(tokenize(c["index"])))
    return [t for t in set(tokenize(q)) if len(t) >= 4 and 1 <= C._df.get(t, 0) <= 25 and not t.isdigit()]


def unknown_entities(C, q):
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", q)
    first = re.match(r"\s*(\w+)", q)
    skip = {first.group(1).lower()} if first else set()
    voc = _vocab(C)
    return [w for w in words if w.lower() not in voc and w.lower() not in COMMON_CAPS and w.lower() not in skip]


def trail_for(C, rec):
    out = []
    for k in docket_keys(rec["docket"]):
        for e in C.graph.get(k, []):
            r = C.rec[e["doc_id"]]
            out.append({"doc_id": e["doc_id"], "date": e["date"], "event": e["event"], "citation": r["citation"], "pages": r["page_field"]})
    return list({e["doc_id"]: e for e in out}.values())


def make_card(C, doc_id, intent, qterms, verdict=None, chunk=None, score=None):
    rec = C.rec[doc_id]
    st = latest_status(C.graph, rec["docket"])
    latest_id = st["latest"]["doc_id"] if st.get("latest") else doc_id
    older = st.get("multiple_versions") and latest_id != doc_id and st["status"] != "WITHDRAWN"
    quotes = []
    if verdict is not None:
        for e in verdict.evidence[:3]:
            quotes.append(_quote(C, rec, "text", e["char_start"], e["char_end"], e["label"]))
    if intent == "revision":
        if rec["summary"]:
            quotes.append(_quote(C, rec, "summary", 0, min(len(rec["summary"]), 600), "notice summary (spreadsheet)", "summary"))
    elif verdict is None and chunk is not None:
        for a, b in best_sentences(chunk, qterms):
            quotes.append(_quote(C, rec, chunk["field"], a, b, "best-matching passage", chunk.get("section")))
    elif verdict is None and rec["summary"]:
        quotes.append(_quote(C, rec, "summary", 0, min(len(rec["summary"]), 500), "notice summary (spreadsheet)", "summary"))
    kept = [q for q in quotes if verify_quote(rec, q)]
    banner = BANNER_WITHDRAWN if rec["is_withdrawal"] else BANNER
    note = None
    if older:
        note = f"OLDER VERSION: this proposal was revised by {latest_id}; read the latest first."
    return {
        "doc_id": doc_id, "doc_number": rec["doc_number"], "docket": rec["docket"], "title": rec["subject"], "issue_date": rec["issue_date"],
        "citation": f"{rec['citation']} {rec['page_field'] or ''}".strip(), "banner": banner, "status": st["status"],
        "latest_doc_id": latest_id, "version_note": note, "verdict": verdict.as_dict() if verdict else None,
        "quotes": kept, "dropped_quotes": len(quotes) - len(kept), "revision_trail": trail_for(C, rec),
        "comments_due": rec.get("comments_due"), "spreadsheet_comment": rec.get("comments"), "score": round(score, 2) if score is not None else None,
        "source": rec["source"], "make": rec["make_norm"],
    }


def resolve_anchors(C, p):
    docs = []
    for d in p["dockets"]:
        docs += C.docs_for_docket(d)
    for n in p["ad_numbers"]:
        docs += C.docs_for_ad_number(n)
    for f in p["fr_docs"]:
        if f in C.doc_by_number:
            docs.append(C.doc_by_number[f])
    docs = list(dict.fromkeys(docs))
    # latest version of each docket first, older versions after
    prim, rest = [], []
    for d in docs:
        st = latest_status(C.graph, C.rec[d]["docket"])
        lid = st["latest"]["doc_id"] if st.get("latest") else d
        (prim if lid == d else rest).append(d)
    return prim + rest


# ---------------- main entry ----------------
def answer(C, query: str, config: dict | None = None, k: int = 3) -> dict:
    t0 = time.perf_counter()
    p = parse_query(query)
    ui = {k_: v for k_, v in (config or {}).items() if v not in (None, "", [])}
    if isinstance(ui.get("part_numbers"), str):
        ui["part_numbers"] = [x.strip() for x in ui["part_numbers"].split(",") if x.strip()]
    if ui.get("make"):
        ui["make"] = norm_make(ui["make"])
    cfg = {**p["cfg"], **ui}
    if not cfg.get("model"):
        cfg["model"] = next((m for m in p["model_candidates"] if C.model_known(m)), None)
    p["cfg"] = {k_: v for k_, v in cfg.items() if v}
    flags = p["flags"]

    # --- 1. typed refusals that need no retrieval ---
    if "off_topic" in flags and not rare_query_tokens(C, query):
        return refusal("OUT_OF_SCOPE", "This tool only answers questions about the FAA airworthiness directive NPRMs in its corpus.",
                       "Ask about a make/model, docket, AD number or an unsafe condition in the corpus.", p, t0)
    if "judgement" in flags:
        return refusal("OUT_OF_SCOPE", "This tool does not decide airworthiness, safety or compliance. A qualified person must make that call from the source documents.",
                       "Ask which proposed ADs name your aircraft (with model, certificate date, part numbers) and review the quoted sources yourself.", p, t0)
    if "pre_2001" in flags:
        return refusal("OUT_OF_CORPUS", "The corpus contains NPRMs issued from April 2001 onward; nothing earlier is held.",
                       "Look the document up in the Federal Register archive directly.", p, t0)
    if "external_subject" in flags:
        return refusal("EXTERNAL_DOC_REQUIRED", "The question is about the content of a document outside this corpus (a foreign-authority AD or a manufacturer bulletin).",
                       "Read that document directly (EASA / Transport Canada / manufacturer).", p, t0)
    if "final_rule" in flags:
        return refusal("OUT_OF_CORPUS", "The corpus holds proposed rules (NPRMs) only; it cannot say whether a final AD has been issued or is in force.",
                       "Check the FAA Dynamic Regulatory System (DRS) for the final AD.", p, t0)

    # --- 2. anchors ---
    anchors = resolve_anchors(C, p)
    if (p["dockets"] or p["ad_numbers"]) and not anchors:
        return refusal("OUT_OF_CORPUS", "No document in the corpus matches the docket / AD number given.",
                       "Check the identifier, or search by make, model or unsafe condition.", p, t0)
    if anchors and all(C.rec[d]["cfr_part"] != "Part 39" for d in anchors):
        return refusal("NOT_PART_39", "The matching document is not an airworthiness directive (it is not a 14 CFR Part 39 rule).",
                       "Read the notice directly; this tool evaluates AD applicability only.", p, t0)
    if not anchors:
        if not any([cfg.get("make"), p["model_candidates"], p["keywords"]]) or len(p["keywords"]) < 2 and not cfg.get("make"):
            return refusal("AMBIGUOUS_QUERY", "The question does not say which aircraft, engine, docket or condition it is about.",
                           "Give a make and model, a docket / AD number, or describe the unsafe condition.", p, t0)
        if p["intent"] == "applicability" and not (cfg.get("make") or cfg.get("model")):
            return refusal("AMBIGUOUS_QUERY", "To check applicability the tool needs the aircraft make and model.",
                           "Give the make, model and (if relevant) certificate date, serial and part numbers.", p, t0)
        unk = unknown_entities(C, query)
        if unk and not cfg.get("model"):
            return refusal("OUT_OF_CORPUS", f"Nothing in the corpus mentions: {', '.join(unk)}.",
                           "Check the spelling, or the product may have no NPRM in this corpus.", p, t0)
    bad = config_contradiction(AircraftConfig(make=cfg.get("make"), model=cfg.get("model")), C.model_index)
    if bad:
        return refusal("CONTRADICTORY_CONFIG", bad, "Correct the make/model, then ask again.", p, t0)

    qterms = [t for t in tokenize(query) if len(t) > 2]
    ret_ms = 0.0

    # --- 3. candidate documents ---
    chunk_for, score_for = {}, {}
    if anchors:
        cand = anchors[:8]
        ranked, ret_ms = C.search(query, allowed_docs=cand, k_docs=len(cand))
        for d, s, i in ranked:
            chunk_for[d], score_for[d] = C.chunks[i], s
    else:
        allowed = None
        if cfg.get("model"):
            allowed = C.docs_naming_model(cfg["model"], cfg.get("make"))
            if not allowed and p["intent"] == "applicability":
                return refusal("OUT_OF_CORPUS", f"No proposed AD in the corpus names the model {cfg['model']}.",
                               "Check the model designation, or there may be no NPRM for it in this corpus.", p, t0)
        ranked, ret_ms = C.search(query, allowed_docs=allowed, k_docs=8 if p["intent"] == "applicability" else k, make=None if allowed else cfg.get("make"))
        rare = rare_query_tokens(C, query)
        rare_hit = bool(ranked) and any(t in set(tokenize(C.chunks[ranked[0][2]]["index"])) for t in rare)
        if not ranked or (p["intent"] == "lookup" and ranked[0][1] < T_LOW and not rare_hit):
            return refusal("INSUFFICIENT_EVIDENCE", "No passage in the corpus matches this question well enough to answer from.",
                           "Rephrase with a make/model, a docket / AD number, or the unsafe condition.", p, t0, ret_ms)
        cand = [d for d, _, _ in ranked]
        for d, s, i in ranked:
            chunk_for[d], score_for[d] = C.chunks[i], s
        # keep newest version of each docket in front
        cand.sort(key=lambda d: (latest_status(C.graph, C.rec[d]["docket"])["latest"]["doc_id"] != d))

    # --- 4. value questions need the number to actually be in the text ---
    if "value_question" in flags:
        topic = [w for w in p["keywords"] if len(w) >= 5 and w.lower() not in {"exact", "specific", "value", "number", "limit", "tightening", "what", "docket"}
                 and not re.search(r"\d", w)]
        found_num = False
        for d in cand[:3]:
            txt = C.rec[d]["text"] or C.rec[d]["summary"] or ""
            for w in topic:
                for m in re.finditer(re.escape(w), txt, re.I):
                    if UNIT_NUM_RE.search(txt[max(0, m.start() - 150): m.end() + 150]):
                        found_num = True
        if not found_num:
            return refusal("INSUFFICIENT_EVIDENCE", "The notice refers to this value but does not state it; the number is in a document outside this corpus.",
                           "Read the referenced service document or foreign-authority AD.", p, t0, ret_ms)

    # --- 5. build cards ---
    cards = []
    if p["intent"] == "applicability":
        ac = AircraftConfig(make=cfg.get("make"), model=cfg.get("model"), serial=cfg.get("serial"), cofa_date=cfg.get("cofa_date"),
                            part_numbers=cfg.get("part_numbers") or [])
        for d in cand[:8]:
            v = engine_verdict(C.rec[d], C.appl[d], ac)
            cards.append(make_card(C, d, "applicability", qterms, verdict=v, chunk=chunk_for.get(d), score=score_for.get(d)))
    elif p["intent"] == "revision":
        for d in cand[:k if not anchors else 6]:
            cards.append(make_card(C, d, "revision", qterms, chunk=chunk_for.get(d), score=score_for.get(d)))
    else:
        for d in cand[:k if not anchors else 5]:
            cards.append(make_card(C, d, "lookup", qterms, chunk=chunk_for.get(d), score=score_for.get(d)))
    cards = [c for c in cards if c["quotes"] or c["verdict"]]
    if not cards:
        return refusal("INSUFFICIENT_EVIDENCE", "No supporting passage survived verification.", "Rephrase the question.", p, t0, ret_ms)
    return {"type": "answer", "intent": p["intent"], "cards": cards, "refusal": None, "parsed": _public(p),
            "config_used": p["cfg"], "n_candidates": len(cand),
            "latency_ms": {"retrieval": round(ret_ms, 1), "total": round((time.perf_counter() - t0) * 1000, 1)}}
