"""Phase 3: FastAPI app. Run: python -m uvicorn api:app --app-dir src --port 8000   (then open http://127.0.0.1:8000)"""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from answer import answer, _vocab
from retrieve import Corpus
from revisions import latest_status

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="AD Applicability Desk")
C = Corpus()
_vocab(C)   # warm the vocabulary so the first query is not slow


class Query(BaseModel):
    query: str
    config: dict | None = None


@app.post("/query")
def query(q: Query):
    if not q.query.strip():
        raise HTTPException(400, "empty query")
    return answer(C, q.query, q.config)


@app.get("/doc/{doc_id:path}")
def doc(doc_id: str):
    r = C.rec.get(doc_id)
    if not r:
        raise HTTPException(404, "unknown document")
    a = C.appl[doc_id]
    return {"doc_id": doc_id, "doc_number": r["doc_number"], "docket": r["docket"], "title": r["subject"], "citation": r["citation"],
            "pages": r["page_field"], "source": r["source"], "summary": r["summary"], "text": r["text"] or r["summary"],
            "is_summary_only": r["text"] is None, "applicability": {k: a.get(k) for k in ("scope", "cofa_cutoff", "section")}}


@app.get("/docket/{docket}")
def docket(docket: str):
    st = latest_status(C.graph, docket)
    if not st["trail"]:
        raise HTTPException(404, "unknown docket")
    return {"docket": docket, "status": st["status"], "latest": st["latest"], "trail": st["trail"]}


@app.get("/results")
def results():
    p = ROOT / "eval" / "results" / "latest.json"
    return JSONResponse(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"available": False})


class EvalReq(BaseModel):
    doc_id: str
    config: dict | None = None


@app.get("/directives")
def directives():
    """Real corpus records for the sidebar stream (no synthetic data)."""
    out = []
    for r, a in C.pairs:
        sec = a.get("section")
        st = latest_status(C.graph, r["docket"])
        text = (r["text"][sec["char_start"]:sec["char_end"]] if sec and r.get("text") else (r["summary"] or ""))
        out.append({"doc_id": r["doc_id"], "docket": r["docket"], "title": r["subject"], "make": r["make_norm"], "issue_date": r["issue_date"],
                    "status": st["status"], "latest": (st["latest"]["doc_id"] if st.get("latest") else r["doc_id"]) == r["doc_id"],
                    "withdrawn": r["is_withdrawal"], "has_text": r["text"] is not None, "scope": a.get("scope"),
                    "snippet": " ".join(text.split())[:170], "citation": r["citation"],
                    "flags": {"serial": bool(a.get("serial_ranges") or a.get("serial_unparsed")),
                              "external": any("of this AD" not in e["name"] for e in a.get("external_refs", [])),
                              "pn": any(g.get("pn_required") for g in a.get("groups", [])), "cutoff": bool(a.get("cofa_cutoff"))}})
    out.sort(key=lambda d: d["issue_date"] or "", reverse=True)
    return out


@app.post("/evaluate")
def evaluate(req: EvalReq):
    """Run the existing deterministic engine on ONE chosen notice and explain it condition by condition."""
    from applicability import AircraftConfig, explain, verdict as engine_verdict
    from ingest import norm_make
    rec = C.rec.get(req.doc_id)
    if not rec:
        raise HTTPException(404, "unknown document")
    c = {k: v for k, v in (req.config or {}).items() if v not in (None, "", [])}
    pns = c.get("part_numbers") or []
    if isinstance(pns, str):
        pns = [x.strip() for x in pns.split(",") if x.strip()]
    cfg = AircraftConfig(make=norm_make(c["make"]) if c.get("make") else None, model=c.get("model"), serial=c.get("serial"),
                         cofa_date=c.get("cofa_date"), part_numbers=pns)
    v = engine_verdict(rec, C.appl[req.doc_id], cfg)
    st = latest_status(C.graph, rec["docket"])
    return {"doc_id": req.doc_id, "verdict": v.as_dict(), "conditions": explain(rec, C.appl[req.doc_id], cfg, v),
            "status": st["status"], "latest_doc_id": st["latest"]["doc_id"] if st.get("latest") else req.doc_id,
            "revision_trail": [{"doc_id": e["doc_id"], "date": e["date"], "event": e["event"]} for e in st["trail"]],
            "config_used": {"make": cfg.make, "model": cfg.model, "cofa_date": cfg.cofa_date, "serial": cfg.serial, "part_numbers": cfg.part_numbers}}


@app.get("/console")
def console():
    return FileResponse(ROOT / "ui" / "console.html")


@app.get("/health")
def health():
    return {"ok": True, "chunks": len(C.chunks), "docs": len(C.rec), "index_build_s": round(C.build_seconds, 2)}


@app.get("/")
def index():
    return FileResponse(ROOT / "ui" / "console.html")


@app.get("/classic")
def classic():
    """The earlier single-page UI, kept for comparison and as a fallback."""
    return FileResponse(ROOT / "ui" / "index.html")
