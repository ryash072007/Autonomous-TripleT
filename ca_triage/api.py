"""FastAPI layer. Reads only files under artifacts/; no dataset/ and no training libraries at startup."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ca_triage import storage
from ca_triage.env import load_env
from ca_triage.tiers import TIER_NAMES, Tier, rule_fired, tier as tier_fn

ROOT = Path(__file__).resolve().parents[1]
load_env()
ART = Path(os.environ.get("ORBITGUARD_ARTIFACTS", ROOT / "artifacts"))
DIST = ROOT / "web" / "dist"
LIVE_MSG = "Live mode not yet available"

app = FastAPI(title="OrbitGuard API")
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Cross-origin access for a separately hosted front end (e.g. Vercel). Default: none, so same-origin only.
_ORIGINS = [o.strip().rstrip("/") for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=_ORIGINS, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


@app.get("/api/health")
def health():
    d = _scored("test")
    return {"ok": d is not None, "dataset_generated_utc": d.get("generated_utc") if d else None,
            "model_version": (d.get("model") or {}).get("version") if d else None}

_cache: dict[str, tuple[float, dict]] = {}


def _scored(dataset: str) -> dict | None:
    """Load artifacts/scored/{dataset}_events.json, reloading when the file changes."""
    p = ART / "scored" / f"{dataset}_events.json"
    if not p.exists() and dataset == "live":
        p = ART / "live_snapshot.json"  # committed fallback
    if not p.exists():
        return None
    m = p.stat().st_mtime
    hit = _cache.get(dataset)
    if hit and hit[0] == m:
        return hit[1]
    data = json.loads(p.read_text(encoding="utf-8"))
    data["_by_id"] = {e["event_id"]: e for e in data["events"]}
    _cache[dataset] = (m, data)
    return data


def _load(dataset: str) -> dict:
    if dataset == "live":
        d = _scored("live")
        if d is None:
            return {"dataset": "live", "model": None, "generated_utc": None, "events": [], "_by_id": {},
                    "message": LIVE_MSG}
        return d
    d = _scored("test")
    if d is None:
        raise HTTPException(503, "artifacts/scored/test_events.json not found")
    return d


def _light(e: dict) -> dict:
    out = {k: v for k, v in e.items() if k not in ("cdms", "debris_cloud")}
    c = out.get("consequence")
    if c and c.get("debris_cloud") is not None:
        out["consequence"] = {**{k: v for k, v in c.items() if k != "debris_cloud"}, "has_cloud": True}
    return out


def _sort_key(e: dict):
    return (-e["tier"], e["latest"]["time_to_tca"])


@app.get("/api/summary")
def summary(dataset: Literal["test", "live"] = "test"):
    d = _load(dataset)
    ev = d["events"]
    counts = {name: 0 for name in TIER_NAMES.values()}
    for e in ev:
        counts[e["tier_name"]] += 1
    ttc = [e["latest"]["time_to_tca"] for e in ev]
    return {
        "dataset": dataset,
        "total": len(ev),
        "counts": counts,
        "n_critical": counts["Critical"],
        "n_abstain": sum(1 for e in ev if e.get("abstain")),
        "model": d.get("model"),
        "generated_utc": d.get("generated_utc"),
        "has_model_probs": any(e.get("p_tier") for e in ev),
        "max_time_to_tca": max(ttc) if ttc else 0,
        "min_time_to_tca": min(ttc) if ttc else 0,
        "object_types": sorted({e["c_object_type"] for e in ev}),
        "message": d.get("message"),
        "snapshot": d.get("snapshot"),
        "sensitivity_note": d.get("sensitivity_note"),
        "forecast_flag": _forecast_flag(),
    }


def _sky(d: dict) -> list[dict]:
    """Small sample for the landing: every Critical plus a sparse set of the rest, few fields."""
    ev = d["events"]
    rest = [e for e in ev if e["tier"] != 2]
    step = max(1.0, len(rest) / 60)
    pick = [e for e in ev if e["tier"] == 2] + [rest[int(i * step)] for i in range(min(60, int(len(rest) / step)))]
    return [{"event_id": e["event_id"], "tier": e["tier"], "tier_name": e["tier_name"],
             "c_object_type": e["c_object_type"], "latest": {"miss_distance": e["latest"]["miss_distance"]}}
            for e in pick]


@app.get("/api/events")
def events(dataset: Literal["test", "live"] = "test", tier: int | None = None, object_type: str | None = None,
           fields: str | None = None):
    d = _load(dataset)
    if fields == "sky":
        return {"dataset": dataset, "message": d.get("message"), "events": _sky(d)}
    out = [e for e in d["events"]
           if (tier is None or e["tier"] == tier) and (object_type is None or e["c_object_type"] == object_type)]
    out.sort(key=_sort_key)
    return {"dataset": dataset, "message": d.get("message"), "events": [_light(e) for e in out]}


@app.get("/api/events/{event_id}")
def event(event_id: int, dataset: Literal["test", "live"] = "test"):
    e = _load(dataset)["_by_id"].get(event_id)
    if e is None:
        raise HTTPException(404, "event not found")
    return e


_brief_cache: dict[tuple, dict] = {}


def _forecast_flag() -> dict | None:
    """Task B alert threshold and its CV Critical recall, read from the evidence file (never hard-coded)."""
    p = ART / "evidence" / "task_b_cv.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"t_critical": d["thresholds"]["t_critical"],
                "critical_recall_cv": d["model"]["folds"]["critical_recall"]["mean"],
                "source": "artifacts/evidence/task_b_cv.json"}
    except (KeyError, json.JSONDecodeError):
        return None


@app.get("/api/events/{event_id}/brief")
def event_brief(event_id: int, dataset: Literal["test", "live"] = "test"):
    from ca_triage.brief import make_brief  # lazy: keeps startup light

    d = _load(dataset)
    e = d["_by_id"].get(event_id)
    if e is None:
        raise HTTPException(404, "event not found")
    key = (dataset, event_id, (d.get("model") or {}).get("version"), bool(os.environ.get("ANTHROPIC_API_KEY")))
    if key not in _brief_cache:
        _brief_cache[key] = make_brief(e, forecast_flag=_forecast_flag())
    return _brief_cache[key]


@app.get("/api/window")
def window(elapsed_days: float = Query(0.0, ge=0), dataset: Literal["test", "live"] = "test"):
    """Replay clock: an event's remaining time is latest.time_to_tca - elapsed; in the 24 h window if 0..1 d."""
    d = _load(dataset)
    out = []
    for e in d["events"]:
        rem = e["latest"]["time_to_tca"] - elapsed_days
        if 0 <= rem <= 1:
            x = _light(e)
            x["remaining_days"] = rem
            x["dangerous"] = e["tier"] == 2 or e["latest"]["miss_distance"] < 1000
            out.append(x)
    out.sort(key=lambda x: x["remaining_days"])
    return {"elapsed_days": elapsed_days, "n": len(out), "n_dangerous": sum(x["dangerous"] for x in out),
            "events": out}


class ScoreIn(BaseModel):
    miss_distance: float
    max_risk_estimate: float
    # Reserved for the model hook; unused by the rule.
    relative_speed: float | None = None
    c_sigma_r: float | None = None
    t_sigma_r: float | None = None
    time_to_tca: float | None = None


@app.post("/api/score")
def score(body: ScoreIn):
    # Rule-only for now. Model hook: when a trained model exists, load it lazily here and add p_tier / tier_set.
    t = Tier(int(tier_fn(body.max_risk_estimate, body.miss_distance)))
    return {"tier": int(t), "tier_name": TIER_NAMES[t],
            "rule": rule_fired(body.max_risk_estimate, body.miss_distance),
            "p_tier": None, "tier_set": [int(t)], "source": "rule"}


@app.get("/api/evidence")
def evidence():
    out = []
    for p in sorted((ART / "evidence").glob("*.json")):
        try:
            out.append({"file": f"artifacts/evidence/{p.name}", "name": p.stem,
                        "content": json.loads(p.read_text(encoding="utf-8"))})
        except json.JSONDecodeError:
            continue
    return {"files": out}


@app.get("/api/insights")
def insights():
    p = ART / "evidence" / "insights.json"
    if not p.exists():
        return {"available": False, "message": "pending data: artifacts/evidence/insights.json not written yet"}
    return {"available": True, "file": "artifacts/evidence/insights.json", "content": json.loads(p.read_text(encoding="utf-8"))}


class AuditIn(BaseModel):
    event_id: int
    action: Literal["Accept", "Escalate", "Dismiss", "Override"]
    note: str = ""


@app.post("/api/audit")
def audit_post(body: AuditIn, dataset: Literal["test", "live"] = "test"):
    d = _load(dataset)
    e = d["_by_id"].get(body.event_id)
    model = (d.get("model") or {}).get("name")
    return storage.store.append(body.event_id, body.action, body.note[:500], e["tier_name"] if e else None, model)


@app.get("/api/audit")
def audit_get(event_id: int | None = None):
    return {"records": storage.store.read(event_id), "chain_ok": storage.store.verify()}


def _pick_demo(d: dict) -> dict:
    ev = d["events"]
    crit = sorted((e for e in ev if e["tier"] == 2), key=lambda e: e["latest"]["miss_distance"])
    elev = [e for e in ev if e["tier"] == 1 and len(e["cdms"]) > 1]
    rising = max(elev, key=lambda e: e["latest"]["max_risk_estimate"] - e["cdms"][0]["max_risk_estimate"],
                 default=None)
    sig = max(ev, key=lambda e: e["latest"].get("c_sigma_r") or 0, default=None)
    items = []
    if crit:
        e = crit[0]
        items.append({"key": "clear_critical", "event_id": e["event_id"],
                      "reason": f"Closest Critical: miss distance {e['latest']['miss_distance']:.0f} m."})
    if rising:
        items.append({"key": "caught_early", "event_id": rising["event_id"],
                      "reason": "Elevated with the largest rise in max_risk_estimate across its CDMs."})
    if sig:
        items.append({"key": "model_wrong", "event_id": sig["event_id"],
                      "reason": f"Extreme radial sigma ({sig['latest']['c_sigma_r']:.0f} m): Pc is least trustworthy here."})
    return {"provisional": True, "items": items}


@app.get("/api/demo")
def demo(dataset: Literal["test", "live"] = "test"):
    p = ART / "demo.json"
    if p.exists():
        raw = json.loads(p.read_text(encoding="utf-8"))
        items = []
        for key, val in raw.items():
            if isinstance(val, dict):
                items.append({"key": key, "event_id": val.get("event_id"), "reason": val.get("reason", "")})
            elif isinstance(val, int):
                items.append({"key": key, "event_id": val, "reason": ""})
        return {"provisional": False, "items": items}
    return _pick_demo(_load("test"))


FRONTEND_URL = os.environ.get("FRONTEND_URL", "").strip()
# API-only by default; SERVE_WEB=1 (or `python scripts/serve.py --with-web`) also serves the built console locally.
SERVE_WEB = os.environ.get("SERVE_WEB", "").strip() == "1"

if SERVE_WEB and DIST.exists():
    if (DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")

else:
    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    def root():
        if FRONTEND_URL:
            return RedirectResponse(FRONTEND_URL)
        return {"service": "OrbitGuard API", "health": "/api/health", "docs": "/docs"}
