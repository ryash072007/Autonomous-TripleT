from ca_triage.brief import make_brief
from ca_triage.brief.guard import check
from ca_triage.brief.facts import build_facts

EVENT = {
    "event_id": 7, "c_object_type": "DEBRIS", "n_cdms": 3, "tier": 2, "tier_name": "Critical",
    "rule": "Critical: miss distance 0.81 km < 1.0 km", "p_tier": [0.01, 0.09, 0.9], "tier_set": [2],
    "abstain": False, "forecast_tier_at_tca": None, "p_forecast": None, "recommendation": None, "flags": [],
    "latest": {"time_to_tca": 2.13, "miss_distance": 812.0, "relative_speed": 13500.0, "max_risk_estimate": -5.2},
    "cdms": [{"time_to_tca": 6.9, "miss_distance": 2400.0, "max_risk_estimate": -6.0},
             {"time_to_tca": 2.13, "miss_distance": 812.0, "max_risk_estimate": -5.2}],
}


def test_template_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    b = make_brief(EVENT)
    assert b["source"] == "template" and b["text"].endswith("Analyst decides.")
    assert check(b["text"], b["facts"]) == []  # the template itself passes the guard


def test_wrong_number_falls_back():
    b = make_brief(EVENT, llm_fn=lambda f: "Event 7 is Critical with miss distance 0.35 km. Analyst decides.")
    assert b["source"] == "template" and "0.35" in b["fallback_reason"]


def test_correct_llm_text_accepted():
    ok = "Event 7 is Critical: miss distance 0.81 km, 90% Critical probability, 2.13 days out. Analyst decides."
    b = make_brief(EVENT, llm_fn=lambda f: ok)
    assert b["source"] == "llm" and b["fallback_reason"] is None


def test_llm_error_falls_back():
    def boom(f):
        raise RuntimeError("x")
    assert make_brief(EVENT, llm_fn=boom)["source"] == "template"
    assert build_facts(EVENT)["miss_distance_km"] == 0.81
