"""Fetch Space-Track public CDMs once and write the live scored file.

One login+query request per run (ajaxauth/login with `query`), no loops, User-Agent set, per Space-Track terms.
Needs SPACETRACK_USER and SPACETRACK_PASS. Without them it prints a message and exits 0.
`--fixture FILE` maps a local JSON file instead (for tests/dev); point --out at a scratch directory for that.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ca_triage.live import map_cdms  # noqa: E402

LOGIN = "https://www.space-track.org/ajaxauth/login"
QUERY = "https://www.space-track.org/basicspacedata/query/class/cdm_public/TCA/>now/orderby/TCA%20asc/format/json"
UA = "OrbitGuard-hackathon/0.1 (single query per run; contact via GitHub repo)"


def fetch(user: str, password: str) -> list[dict]:
    body = urllib.parse.urlencode({"identity": user, "password": password, "query": QUERY}).encode()
    req = urllib.request.Request(LOGIN, data=body, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", help="map this JSON file instead of calling Space-Track")
    ap.add_argument("--out", default=str(ROOT / "artifacts"), help="artifacts directory to write into")
    a = ap.parse_args()
    if a.fixture:
        rows = json.loads(Path(a.fixture).read_text(encoding="utf-8"))
    else:
        user, pw = os.environ.get("SPACETRACK_USER"), os.environ.get("SPACETRACK_PASS")
        if not user or not pw:
            print("SPACETRACK_USER / SPACETRACK_PASS not set: skipping live fetch. "
                  "The console will use artifacts/live_snapshot.json if present.")
            return 0
        rows = fetch(user, pw)
    data = map_cdms(rows)
    out = Path(a.out)
    (out / "scored").mkdir(parents=True, exist_ok=True)
    text = json.dumps(data)
    (out / "scored" / "live_events.json").write_text(text, encoding="utf-8")
    (out / "live_snapshot.json").write_text(text, encoding="utf-8")
    print(f"{len(rows)} CDMs -> {len(data['events'])} events -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
