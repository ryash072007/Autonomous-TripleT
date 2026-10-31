"""Baselines for the evaluation. All return an answer dict shaped like src/answer.py output so the same scorer applies.

  naive_summary : BM25 over the 431 spreadsheet Summary fields only; top-5 docs; never refuses; applicability = keyword guess.
  fulltext_bm25 : the system's full-text chunk index with NO metadata filter, NO engine, NO refusals; same keyword guess.
  llm_only      : an Anthropic model with NO documents (answers from its own memory); tests what the LLM alone does.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import bm25s

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from query_parse import parse_query  # noqa: E402
from retrieve import tokenize  # noqa: E402

LLM = "claude-sonnet-5-5"


def _model_guess(query_parse, doc_text) -> str:
    """Keyword guess: APPLIES if any model-like token from the query appears in the document, else DOES_NOT_APPLY (never CANNOT_DETERMINE)."""
    cands = [c.upper().replace(" ", "") for c in query_parse["model_candidates"]] or []
    hay = re.sub(r"\s+", "", (doc_text or "").upper())
    return "APPLIES" if any(c and c in hay for c in cands) else "DOES_NOT_APPLY"


def _card(C, doc_id, verdict=None, score=None):
    r = C.rec[doc_id]
    from revisions import latest_status
    st = latest_status(C.graph, r["docket"])
    return {"doc_id": doc_id, "verdict": ({"verdict": verdict, "main_reason": None} if verdict else None), "status": st["status"],
            "latest_doc_id": st["latest"]["doc_id"] if st.get("latest") else doc_id, "comments_due": r.get("comments_due"),
            "revision_trail": [{"doc_id": e["doc_id"], "event": e["event"], "date": e["date"]} for e in st["trail"]],
            "quotes": [], "dropped_quotes": 0, "score": score}


class NaiveSummary:
    name = "naive_summary"

    def __init__(self, C):
        self.C = C
        self.ids = [r["doc_id"] for r, _ in C.pairs if r["summary"]]
        self.bm = bm25s.BM25()
        self.bm.index([tokenize((C.rec[d]["subject"] or "") + " " + C.rec[d]["summary"]) for d in self.ids], show_progress=False)

    def __call__(self, query, config=None):
        import numpy as np
        sc = self.bm.get_scores(tokenize(query))
        top = [int(i) for i in np.argsort(-sc)[:5] if sc[i] > 0]
        p = parse_query(query)
        cards = []
        for k, i in enumerate(top):
            d = self.ids[i]
            v = _model_guess(p, self.C.rec[d]["summary"]) if p["intent"] == "applicability" else None
            cards.append(_card(self.C, d, v, float(sc[i])))
        return {"type": "answer", "cards": cards, "refusal": None, "latency_ms": {"total": 0}}


class FulltextBM25:
    name = "fulltext_bm25"

    def __init__(self, C):
        self.C = C

    def __call__(self, query, config=None):
        ranked, _ = self.C.search(query, k_docs=5)
        p = parse_query(query)
        cards = []
        for d, s, i in ranked:
            v = _model_guess(p, self.C.rec[d]["text"] or self.C.rec[d]["summary"]) if p["intent"] == "applicability" else None
            cards.append(_card(self.C, d, v, s))
        return {"type": "answer", "cards": cards, "refusal": None, "latency_ms": {"total": 0}}


LLM_SYSTEM = ("You answer questions about FAA airworthiness directive proposed rules (NPRMs). You have NO documents available; answer only from your own "
              "knowledge. Respond with a single JSON object and nothing else.")
LLM_USER = ("Question: {q}\n{cfg}\nReturn JSON: {{\"refuse\": bool, \"refusal_code\": null or one of [OUT_OF_SCOPE, OUT_OF_CORPUS, EXTERNAL_DOC_REQUIRED, AMBIGUOUS_QUERY, "
            "CONTRADICTORY_CONFIG, INSUFFICIENT_EVIDENCE, NOT_PART_39], \"verdict\": null or one of [APPLIES, DOES_NOT_APPLY, CANNOT_DETERMINE], "
            "\"cited_documents\": [FR document numbers or docket numbers you rely on, exactly as you would cite them], \"latest_doc\": null or \"<document number>\", "
            "\"answer\": \"<short answer>\"}}")


class LLMOnly:
    name = "llm_only"

    def __init__(self, C):
        import anthropic
        self.C, self.client = C, anthropic.Anthropic()

    def _one(self, query, config):
        cfg = f"Aircraft configuration: {json.dumps(config)}" if config else ""
        for _ in range(2):
            try:
                r = self.client.messages.create(model=LLM, max_tokens=900, system=LLM_SYSTEM,
                                                messages=[{"role": "user", "content": LLM_USER.format(q=query, cfg=cfg)}])
                txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
                m = re.search(r"\{.*\}", txt, re.S)
                if m:
                    return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                continue
        return {"refuse": False, "verdict": None, "cited_documents": [], "answer": "(no parsable answer)"}

    def __call__(self, query, config=None):
        j = self._one(query, config)
        cited = [str(x).strip() for x in (j.get("cited_documents") or [])]
        mapped, halluc = [], []
        for c in cited:
            ids = []
            if c in self.C.doc_by_number:
                ids = [self.C.doc_by_number[c]]
            elif re.match(r"^(?:FAA-\d{4}-\d+|\d{4}-[A-Z]{2}-\d+-AD)", c, re.I):
                ids = self.C.docs_for_docket(c.upper())
            if ids:
                mapped += ids
            else:
                halluc.append(c)
        if j.get("refuse"):
            return {"type": "refusal", "cards": [], "refusal": {"code": j.get("refusal_code") or "OUT_OF_SCOPE"}, "latency_ms": {"total": 0},
                    "llm": {"cited": cited, "hallucinated": halluc}}
        cards = [_card(self.C, d, j.get("verdict")) for d in dict.fromkeys(mapped)]
        if not cards and j.get("verdict"):
            cards = [{"doc_id": "__none__", "verdict": {"verdict": j["verdict"], "main_reason": None}, "status": None, "latest_doc_id": j.get("latest_doc"),
                      "comments_due": None, "revision_trail": [], "quotes": [], "dropped_quotes": 0}]
        return {"type": "answer", "cards": cards, "refusal": None, "latency_ms": {"total": 0},
                "llm": {"cited": cited, "hallucinated": halluc, "answer": j.get("answer"), "verdict": j.get("verdict"), "latest_doc": j.get("latest_doc")}}

    def batch(self, items, workers=6):
        with ThreadPoolExecutor(workers) as ex:
            return list(ex.map(lambda t: self.__call__(t["query"], t.get("config")), items))
