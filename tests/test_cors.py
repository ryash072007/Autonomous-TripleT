import importlib

import pytest
from fastapi.testclient import TestClient

from ca_triage import api


@pytest.fixture()
def cors_app(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://orbitguard.example.com, https://app.example.org/")
    mod = importlib.reload(api)
    yield mod
    monkeypatch.delenv("ALLOWED_ORIGINS")
    importlib.reload(api)


def test_allowed_and_disallowed_origin(cors_app):
    c = TestClient(cors_app.app)
    ok = c.get("/api/health", headers={"Origin": "https://orbitguard.example.com"})
    assert ok.headers.get("access-control-allow-origin") == "https://orbitguard.example.com"
    bad = c.get("/api/health", headers={"Origin": "https://evil.example.net"})
    assert "access-control-allow-origin" not in bad.headers
    pre = c.options("/api/audit", headers={"Origin": "https://app.example.org", "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type"})
    assert pre.status_code == 200 and pre.headers["access-control-allow-origin"] == "https://app.example.org"


def test_default_is_same_origin_only():
    c = TestClient(api.app)
    r = c.get("/api/health", headers={"Origin": "https://anything.example.com"})
    assert "access-control-allow-origin" not in r.headers
    assert set(r.json()) == {"ok", "dataset_generated_utc", "model_version"}
