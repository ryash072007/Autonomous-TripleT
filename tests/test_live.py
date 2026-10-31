import json
from datetime import datetime, timezone
from pathlib import Path

from ca_triage.live import map_cdms

FIX = Path(__file__).parent / "fixtures" / "cdm_public_sample.json"


def test_map_cdms_rule_only():
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
    d = map_cdms(json.loads(FIX.read_text()), now)
    by = {e["names"]["t"]: e for e in d["events"]}
    assert len(d["events"]) == 4 and d["dataset"] == "live"
    a = by["SAT-A"]
    assert a["n_cdms"] == 2 and a["tier_name"] == "Critical" and a["cdm_id"] == "9002"
    assert "emergency_reportable" in a["flags"] and a["p_tier"] is None
    assert abs(a["latest"]["miss_distance"] - 380.0) < 1e-6 and 1.9 < a["latest"]["time_to_tca"] < 2.1
    assert by["SAT-C"]["tier_name"] == "Elevated" and by["SAT-E"]["tier_name"] == "Safe"
    g = by["SAT-G"]
    assert "pc_missing" in g["flags"] and g["tier_name"] == "Safe" and "Pc not published" in g["rule"]
    assert d["events"][0]["tier"] == 2  # sorted tier desc
