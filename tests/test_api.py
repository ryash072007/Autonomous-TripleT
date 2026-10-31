import pytest
from fastapi.testclient import TestClient

from ca_triage import api, storage

pytestmark = pytest.mark.skipif(not (api.ART / "scored" / "test_events.json").exists(), reason="no scored events")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "store", storage.JsonlAuditStore(tmp_path / "audit.jsonl"))
    return TestClient(api.app)


def test_summary_and_events(client):
    s = client.get("/api/summary").json()
    assert s["total"] == sum(s["counts"].values()) > 0
    ev = client.get("/api/events").json()["events"]
    assert len(ev) == s["total"] and "cdms" not in ev[0]
    assert ev[0]["tier"] >= ev[-1]["tier"]
    assert client.get(f"/api/events/{ev[0]['event_id']}").json()["cdms"]
    live = client.get("/api/events?dataset=live").json()["events"]
    assert all("rule_only" in e["flags"] for e in live)  # live is tiered by the rule only (empty without a snapshot)


def test_score_and_window(client):
    r = client.post("/api/score", json={"miss_distance": 500, "max_risk_estimate": -9}).json()
    assert r["tier_name"] == "Critical"
    r = client.post("/api/score", json={"miss_distance": 50000, "max_risk_estimate": -9}).json()
    assert r["tier_name"] == "Safe"
    w = client.get("/api/window?elapsed_days=1.5").json()
    assert all(0 <= e["remaining_days"] <= 1 for e in w["events"])


def test_audit_chain_and_demo(client):
    client.post("/api/audit", json={"event_id": 1, "action": "Accept", "note": "ok"})
    client.post("/api/audit", json={"event_id": 1, "action": "Escalate", "note": ""})
    a = client.get("/api/audit").json()
    assert len(a["records"]) == 2 and a["chain_ok"]
    assert a["records"][1]["prev_hash"] == a["records"][0]["hash"]
    assert client.get("/api/demo").json()["items"]
