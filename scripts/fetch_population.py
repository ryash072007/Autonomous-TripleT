"""Fetch active-satellite population by altitude (one request to CelesTrak GP, no account) -> artifacts/population_by_altitude.json.

Altitude from mean motion assuming a circular orbit: a = (mu / n^2)^(1/3), h = a - 6378.137 km. 25 km bands up to 2000 km.
If the request fails, falls back to a coarse table from the test events' own target altitudes (labelled as such).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

import numpy as np

from ca_triage.consequence import BAND_KM, MAX_ALT_KM, MU, POP_PATH, RE, band_edges

URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json"


def from_celestrak(saved: str | None = None) -> dict:
    if saved:  # response saved from the single request, to avoid hitting CelesTrak again (it rate-limits repeats with HTTP 403)
        import os
        gp = json.load(open(saved))
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(saved)))
        return _table(gp, stamp)
    req = urllib.request.Request(URL, headers={"User-Agent": "OrbitGuard-hackathon/0.1 (single request, research use)"})
    with urllib.request.urlopen(req, timeout=90) as r:
        gp = json.loads(r.read())
    return _table(gp, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def _table(gp, stamp) -> dict:
    n = np.array([g["MEAN_MOTION"] for g in gp if g.get("MEAN_MOTION", 0) > 0], float)
    a = (MU / (n * 2 * np.pi / 86400.0) ** 2) ** (1 / 3)
    h = a - RE
    counts, _ = np.histogram(h, bins=band_edges())
    return {"source": URL, "kind": "CelesTrak GP active group, altitude from mean motion (circular orbit assumption)",
            "retrieved_utc": stamp, "n_objects": int(len(gp)),
            "n_in_0_2000km": int(counts.sum()), "band_km": BAND_KM, "bands_lo_km": band_edges()[:-1].tolist(), "counts": counts.tolist()}


def fallback() -> dict:
    from ca_triage.data import load
    from ca_triage.display import load_display_orbits
    d = load_display_orbits("test")
    h = ((d.t_h_per + d.t_h_apo) / 2).dropna().to_numpy()
    counts, _ = np.histogram(h, bins=band_edges())
    ev = d.event_id.nunique()
    scale = 1.0  # event-level target altitudes only: a tiny, biased sample of the real population
    return {"source": "FALLBACK: test CDM target altitudes (NOT the real active population)", "kind": "coarse table from the events themselves",
            "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_objects": int(ev), "n_in_0_2000km": int(counts.sum()),
            "band_km": BAND_KM, "bands_lo_km": band_edges()[:-1].tolist(), "counts": (counts / len(d) * ev * scale).round(3).tolist()}


if __name__ == "__main__":
    try:
        t = from_celestrak(sys.argv[sys.argv.index("--from-file") + 1] if "--from-file" in sys.argv else None)
    except Exception as exc:  # noqa: BLE001
        print("CelesTrak fetch failed:", exc, file=sys.stderr)
        t = fallback()
    POP_PATH.parent.mkdir(exist_ok=True)
    POP_PATH.write_text(json.dumps(t, indent=1))
    c = np.array(t["counts"])
    print(t["source"][:60], t["n_objects"], "in 0-2000 km:", t["n_in_0_2000km"], "peak band", t["bands_lo_km"][int(c.argmax())], c.max())
