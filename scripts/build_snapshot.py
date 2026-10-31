"""Write a read-only snapshot of the API responses into web/public/snapshot/ (committed, served by Vercel).

The front end falls back to these files when the backend is unreachable. They are produced by calling the real API
in-process, so the shapes match exactly. Briefs are the deterministic template text (no LLM). Live data is not included.

    python scripts/build_snapshot.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["ANTHROPIC_API_KEY"] = ""  # force template briefs; load_env never overrides an existing variable
os.environ["ALLOWED_ORIGINS"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from ca_triage import api  # noqa: E402

OUT = ROOT / "web" / "public" / "snapshot"
CHUNK = 150
DROP_EVENT = {"recommendation_by_ratio", "decision_inputs", "forecast_tier_set", "forecast_abstain"}


def trim(o, sig: int = 5):
    """Round floats to `sig` significant digits to keep the files small."""
    if isinstance(o, float):
        return float(f"{o:.{sig}g}")
    if isinstance(o, list):
        return [trim(x, sig) for x in o]
    if isinstance(o, dict):
        return {k: trim(v, sig) for k, v in o.items()}
    return o


def write(rel: str, data) -> int:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(trim(data), separators=(",", ":")), encoding="utf-8")
    return p.stat().st_size


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    c = TestClient(api.app)

    def get(path: str):
        r = c.get(path)
        r.raise_for_status()
        return r.json()

    write("summary.json", get("/api/summary"))
    write("health.json", get("/api/health"))
    write("sky.json", get("/api/events?fields=sky"))
    lite = get("/api/events")
    for e in lite["events"]:  # the list needs far fewer fields than the event page
        for k in DROP_EVENT | {"sensitivity", "rule", "forecast_tier_set"}:
            e.pop(k, None)
        for k in ("relative_position_r", "relative_position_t", "relative_position_n", "relative_speed", "t_sigma_r", "F10", "AP"):
            e["latest"].pop(k, None)
        if e.get("consequence"):
            e["consequence"] = {k: v for k, v in e["consequence"].items() if k in ("pc_rank", "harm_rank", "expected_harm", "consequence_score", "has_cloud", "fragments_10cm", "catastrophic")}
    write("events.json", lite)
    write("evidence.json", get("/api/evidence"))
    write("insights.json", get("/api/insights"))
    write("demo.json", get("/api/demo"))

    ids = [e["event_id"] for e in lite["events"]]
    index: dict[str, int] = {}
    full_bytes = brief_bytes = 0
    for k in range(0, len(ids), CHUNK):
        part = ids[k:k + CHUNK]
        evs, brs = {}, {}
        for i in part:
            e = get(f"/api/events/{i}")
            for key in DROP_EVENT:
                e.pop(key, None)
            evs[str(i)] = e
            b = get(f"/api/events/{i}/brief")
            brs[str(i)] = {"text": b["text"], "source": "template", "fallback_reason": "snapshot"}
            index[str(i)] = k // CHUNK
        full_bytes += write(f"events/{k // CHUNK}.json", evs)
        brief_bytes += write(f"briefs/{k // CHUNK}.json", brs)
    write("index.json", index)

    total = sum(f.stat().st_size for f in OUT.rglob("*.json"))
    print(f"{len(ids)} events -> {OUT}")
    print(f"events chunks {full_bytes / 1e6:.1f} MB, briefs {brief_bytes / 1e6:.1f} MB, total {total / 1e6:.1f} MB (before gzip)")
    big = max(OUT.rglob("*.json"), key=lambda f: f.stat().st_size)
    print(f"largest file: {big.relative_to(OUT)} {big.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
