"""Unit tests for the deterministic applicability engine and revision logic.

Expected values were read by hand from the source notices (spreadsheet + Federal Register text), not from system output.
Run: python -m pytest tests -q   (needs data/processed/ad_records.jsonl: python src/build_records.py)
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from applicability import AircraftConfig, build_model_index, config_contradiction, verdict  # noqa: E402
from build_records import load_records  # noqa: E402
from revisions import build_graph, latest_status  # noqa: E402

PAIRS = load_records()
REC = {r["doc_id"]: (r, a) for r, a in PAIRS}
GRAPH = build_graph([r for r, _ in PAIRS])


def run(doc, **cfg):
    r, a = REC[doc]
    return verdict(r, a, AircraftConfig(**cfg))


CASES = [
    # (doc, config, verdict, main_reason)
    ("2026-16961", dict(make="Dassault Aviation", model="Falcon 7X"), "APPLIES", "MODEL_LISTED"),                 # "all ... FALCON 7X"
    ("2026-16961", dict(make="Dassault Aviation", model="Falcon 900"), "DOES_NOT_APPLY", "MODEL_NOT_LISTED"),
    ("2026-20543", dict(make="Airbus", model="A330-243", cofa_date="2025-06-01"), "APPLIES", "CERT_DATE_BEFORE_CUTOFF"),   # list expansion + date
    ("2026-20543", dict(make="Airbus", model="A330-243", cofa_date="2025-12-19"), "APPLIES", "CERT_DATE_BEFORE_CUTOFF"),   # "on or before" is inclusive
    ("2026-20543", dict(make="Airbus", model="A330-243", cofa_date="2025-12-20"), "DOES_NOT_APPLY", "CERT_DATE_AFTER_CUTOFF"),
    ("2026-20543", dict(make="Airbus", model="A330-243"), "CANNOT_DETERMINE", "INPUT_MISSING_CERT_DATE"),
    ("2026-03747", dict(make="Airbus", model="A330-941", cofa_date="2025-06-01"), "DOES_NOT_APPLY", "CERT_DATE_AFTER_CUTOFF"),  # older NPRM, cutoff 2024-10-01
    ("2026-00842", dict(make="Boeing", model="737-800"), "CANNOT_DETERMINE", "EXTERNAL_DOC_REQUIRED"),            # "as identified in ... Bulletin"
    ("2026-00842", dict(make="Boeing", model="737-300"), "DOES_NOT_APPLY", "MODEL_NOT_LISTED"),
    ("2026-08385", dict(make="Boeing", model="757-300"), "APPLIES", "MODEL_LISTED"),                              # "-200, -200PF, -200CB, and -300"
    ("2026-06459", dict(make="Ontic", model="SA227-AC", part_numbers=["DL5040M5"]), "APPLIES", "PN_INSTALLED"),
    ("2026-06459", dict(make="Ontic", model="SA227-AC", part_numbers=["DL5040M7"]), "DOES_NOT_APPLY", "PN_NOT_INSTALLED"),
    ("2026-06459", dict(make="Ontic", model="SA227-AC"), "CANNOT_DETERMINE", "INPUT_MISSING_PN"),
    ("2026-19561", dict(make="Bombardier", model="BD-700-2A12"), "CANNOT_DETERMINE", "EXCLUSION_UNVERIFIABLE"),
    ("2026-10781", dict(make="Rolls-Royce", model="RB211 Trent 768-60"), "DOES_NOT_APPLY", "DOC_WITHDRAWN"),
    ("FAA-2009-1028@2009-10-28", dict(make="Gulfstream", model="Gulfstream G150", serial="210"), "APPLIES", "SERIAL_IN_RANGE"),
    ("FAA-2009-1028@2009-10-28", dict(make="Gulfstream", model="Gulfstream G150", serial="300"), "DOES_NOT_APPLY", "SERIAL_OUT_OF_RANGE"),
    ("FAA-2009-1028@2009-10-28", dict(make="Gulfstream", model="Gulfstream G150"), "CANNOT_DETERMINE", "INPUT_MISSING_SERIAL"),
    ("FAA-2006-26691@2007-02-15", dict(make="Reims", model="F406", serial="F406-0091"), "CANNOT_DETERMINE", "AMBIGUOUS_SCOPE"),   # range + extra S/N: restraint
    ("2000-NM-120-AD@2005-01-21", dict(make="Embraer", model="EMB-120"), "CANNOT_DETERMINE", "AMBIGUOUS_SCOPE"),                    # "that are required by 14 CFR 135 ..."
    ("2001-NM-40-AD@2002-01-02", dict(make="Boeing", model="747-400"), "CANNOT_DETERMINE", "EXTERNAL_DOC_REQUIRED"),                 # "747 series" + "as listed in" bulletin
    ("FAA-2002-13744@2008-07-30", dict(make="Robinson", model="R22"), "CANNOT_DETERMINE", "NOT_PART_39"),
]


@pytest.mark.parametrize("doc,cfg,expected,reason", CASES)
def test_verdict(doc, cfg, expected, reason):
    v = run(doc, **cfg)
    assert (v.verdict, v.main_reason) == (expected, reason), v.detail


def test_every_verdict_has_verifiable_evidence_spans():
    for doc, cfg, _, _ in CASES:
        v = run(doc, **cfg)
        r, _ = REC[doc]
        for e in v.evidence:
            assert r["text"][e["char_start"]:e["char_end"]] == e["quote"]
            assert e["quote"].strip()


def test_contradictory_make_model():
    idx = build_model_index(PAIRS)
    assert config_contradiction(AircraftConfig(make="Boeing", model="A330-243"), idx)
    assert not config_contradiction(AircraftConfig(make="Airbus", model="A330-243"), idx)


def test_revision_latest_status():
    s = latest_status(GRAPH, "FAA-2026-1338")
    assert s["status"].startswith("REVISED_NPRM") and s["latest"]["doc_id"] == "2026-20543" and s["multiple_versions"]
    assert latest_status(GRAPH, "FAA-2025-2541")["status"] == "WITHDRAWN"


def test_comment_extension_does_not_replace_the_proposal():
    s = latest_status(GRAPH, "FAA-2024-2142")
    assert s["latest"]["doc_id"] == "2024-21652" and s["last_entry"]["doc_id"] == "2024-25883"


def test_r1_docket_folds_into_base():
    assert "FAA-2022-1308" in GRAPH and len(GRAPH["FAA-2022-1308"]) >= 1
