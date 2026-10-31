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


@app.get("/health")
def health():
    return {"ok": True, "chunks": len(C.chunks), "docs": len(C.rec), "index_build_s": round(C.build_seconds, 2)}


@app.get("/")
def index():
    return FileResponse(ROOT / "ui" / "index.html")
