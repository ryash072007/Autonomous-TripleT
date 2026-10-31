"""Fetch the released ESA test labels (event_id, true_risk): Zenodo record 4463683, one zip member via an HTTP byte range.

Refuses to run unless artifacts/model_card.json exists and says frozen. Only scripts/score_test_b.py may read the result.
Ported from the reference repo's orbitguard/ml/data.py.
"""

from __future__ import annotations

import io
import json
import struct
import sys
import urllib.request
import zlib

import pandas as pd

from ca_triage.data import ROOT

URL = "https://zenodo.org/api/records/4463683/files/Collision%20Avoidance%20Challenge%20-%20Dataset.zip/content"
RANGE = (13659544, 15006671)
SIZE, CRC = 1347128, 0x2B46D216
MEMBER = ROOT / "dataset" / "test_labels_member.bin"


def require_frozen() -> None:
    card = ROOT / "artifacts" / "model_card.json"
    if not card.exists() or not json.loads(card.read_text()).get("frozen"):
        sys.exit("artifacts/model_card.json missing or not frozen: freeze the model (scripts/freeze.py) before touching released labels")


def fetch() -> None:
    require_frozen()
    if MEMBER.exists() and MEMBER.stat().st_size == SIZE:
        return
    MEMBER.parent.mkdir(exist_ok=True)
    req = urllib.request.Request(URL, headers={"Range": f"bytes={RANGE[0]}-{RANGE[1]}"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    if len(data) != SIZE:
        sys.exit(f"label member: expected {SIZE} bytes, got {len(data)}")
    MEMBER.write_bytes(data)


def load_labels() -> pd.DataFrame:
    """Decompress the zip member and check its CRC. Columns event_id, true_risk."""
    require_frozen()
    fetch()
    raw = MEMBER.read_bytes()
    h = struct.unpack_from("<4s5H3I2H", raw, 0)
    if h[0] != b"PK\x03\x04" or h[3] != 8:
        sys.exit("invalid zip member")
    start = 30 + h[-2] + h[-1]
    payload = zlib.decompress(raw[start:start + h[7]], -15)
    if zlib.crc32(payload) & 0xFFFFFFFF != CRC:
        sys.exit("released-label CRC mismatch")
    lab = pd.read_csv(io.BytesIO(payload), usecols=["event_id", "true_risk"])
    if lab.event_id.duplicated().any():
        sys.exit("duplicate label events")
    return lab


if __name__ == "__main__":
    fetch()
    print("label member stored at", MEMBER, "(not opened)")
