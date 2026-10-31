"""Phase 3: section-aware chunks + BM25 (bm25s) with metadata filtering. Local, no network."""
import re
import time
from collections import defaultdict

import bm25s
import numpy as np

from applicability import build_model_index
from build_records import load_records
from extract import model_in_text, norm_model
from revisions import build_graph, docket_keys

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-/.][a-z0-9]+)*")
STOPWORDS = set("the a an of for to in on is are was were be been and or with that this it its as at by from any there which what".split())
WIN, STEP = 1100, 900


def tokenize(text: str) -> list:
    """Compound tokens (A330-243, 2025-13-11) plus their pieces, so both exact IDs and partial terms match."""
    toks = []
    for t in TOKEN_RE.findall(text.lower()):
        if t in STOPWORDS:
            continue
        toks.append(t)
        if re.search(r"[-/.]", t):
            toks += [p for p in re.split(r"[-/.]", t) if p and p not in STOPWORDS]
    return toks


def _windows(text, a, b):
    """(start, end) windows inside [a, b) on whitespace boundaries."""
    out, i = [], a
    while i < b:
        j = min(b, i + WIN)
        if j < b:
            k = text.rfind("\n", i + WIN // 2, j)
            j = k if k > i else j
        out.append((i, j))
        if j >= b:
            break
        i = max(j - (WIN - STEP), i + 1)
    return out


class Corpus:
    def __init__(self):
        t0 = time.time()
        self.pairs = load_records()
        self.rec = {r["doc_id"]: r for r, _ in self.pairs}
        self.appl = {r["doc_id"]: a for r, a in self.pairs}
        self.graph = build_graph([r for r, _ in self.pairs])
        self.model_index = build_model_index(self.pairs)
        self.doc_by_number = {r["doc_number"]: r["doc_id"] for r, _ in self.pairs if r["doc_number"]}
        self.ad_refs = defaultdict(set)          # AD number -> doc_ids whose summary mentions it
        for r, _ in self.pairs:
            for n in re.findall(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b", r["summary"] or ""):
                self.ad_refs[n].add(r["doc_id"])
        self.docket_docs = defaultdict(list)
        for k, evs in self.graph.items():
            self.docket_docs[k] = [e["doc_id"] for e in evs]
        self._build_chunks()
        self.build_seconds = time.time() - t0

    def _build_chunks(self):
        self.chunks = []
        for r, a in self.pairs:
            pre = f"{r['subject']} {r['docket']} {r['make_norm']} "
            if r["summary"]:
                self.chunks.append({"doc_id": r["doc_id"], "field": "summary", "section": "summary", "page": r["start_page"],
                                    "char_start": 0, "char_end": len(r["summary"]), "text": r["summary"], "index": pre + r["summary"]})
            text = r["text"]
            if not text:
                continue
            spans = []
            if r["sections"]:
                for key, s in r["sections"].items():
                    spans.append((key, s["char_start"], s["char_end"], s["page"], s["title"]))
            else:
                spans.append(("body", 0, len(text), r["start_page"], "body"))
            for key, a0, b0, page, title in spans:
                if not text[a0:b0].strip():
                    continue
                for (i, j) in _windows(text, a0, b0):
                    seg = text[i:j]
                    if len(seg.strip()) < 20:
                        continue
                    self.chunks.append({"doc_id": r["doc_id"], "field": "text", "section": key, "title": title, "page": page,
                                        "char_start": i, "char_end": j, "text": seg, "index": pre + title + " " + seg})
        self.bm25 = bm25s.BM25()
        self.bm25.index([tokenize(c["index"]) for c in self.chunks], show_progress=False)
        self.chunk_doc = np.array([c["doc_id"] for c in self.chunks])

    # ---- lookups by identifier ----
    def docs_for_docket(self, docket: str) -> list:
        out = []
        for k in docket_keys(docket):
            out += self.docket_docs.get(k, [])
        return list(dict.fromkeys(out))

    def docs_for_ad_number(self, n: str) -> list:
        return sorted(self.ad_refs.get(n, []))

    def model_known(self, model: str) -> bool:
        """True if the model is named anywhere in the corpus (applicability text, subject, summary, Model column)."""
        if norm_model(model) in self.model_index:
            return True
        for r, a in self.pairs:
            hay = " ".join([r["summary"] or "", r["subject"] or ""])
            sec = a.get("section")
            if sec:
                hay += " " + r["text"][sec["char_start"]:sec["char_end"]]
            if model_in_text(model, hay):
                return True
        return False

    def docs_naming_model(self, model: str, make: str | None = None) -> list:
        out = []
        for r, a in self.pairs:
            if make and r["make_norm"] != make:
                continue
            hay = " ".join([r["summary"] or "", r["subject"] or ""])
            sec = a.get("section")
            if sec:
                hay += " " + r["text"][sec["char_start"]:sec["char_end"]]
            if model_in_text(model, hay):
                out.append(r["doc_id"])
        return out

    # ---- ranked search ----
    def search(self, query: str, allowed_docs=None, k_docs: int = 5, make: str | None = None):
        """Return ([(doc_id, score, best_chunk_index)], retrieval_ms). Metadata filter is applied BEFORE ranking docs."""
        t0 = time.perf_counter()
        scores = self.bm25.get_scores(tokenize(query))
        mask = np.ones(len(self.chunks), dtype=bool)
        if allowed_docs is not None:
            mask &= np.isin(self.chunk_doc, list(allowed_docs))
        if make:
            ok = {d for d, r in self.rec.items() if r["make_norm"] == make}
            mask &= np.isin(self.chunk_doc, list(ok))
        scores = np.where(mask, scores, -1.0)
        best = {}
        for i in np.argsort(-scores)[: max(200, k_docs * 40)]:
            if scores[i] <= 0:
                break
            d = self.chunks[i]["doc_id"]
            if d not in best:
                best[d] = (float(scores[i]), int(i))
        ranked = sorted(((d, s, i) for d, (s, i) in best.items()), key=lambda x: -x[1])[:k_docs]
        return ranked, (time.perf_counter() - t0) * 1000
