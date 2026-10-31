"""Answer-layer tests: every returned quote is a verbatim slice of the stored source; refusals are typed; no crashes on odd input.
Queries here are NOT taken from the frozen test split.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from answer import answer, verify_quote, _vocab  # noqa: E402
from retrieve import Corpus  # noqa: E402


@pytest.fixture(scope="module")
def C():
    c = Corpus()
    _vocab(c)
    return c


ANSWER_QUERIES = [
    "which proposal replaces AD 2023-12-16?",
    "Falcon 7X spoiler unit replacement proposed rule",
    "Does the proposal for the Vulcanair P.68 cover serial number 200?",
    "Is the RB211 Trent 772B-60 LPC blade NPRM still alive?",
    "What did the FAA propose for the Dowty R212 propeller assemblies?",
    "Does the latest proposed AD in docket FAA-2025-2277 apply to my Bombardier BD-700-2A12?",
]


@pytest.mark.parametrize("q", ANSWER_QUERIES)
def test_every_quote_is_a_verbatim_slice_of_the_source(C, q):
    a = answer(C, q)
    assert a["type"] == "answer"
    for card in a["cards"]:
        assert card["banner"].startswith(("PROPOSED RULE", "WITHDRAWAL NOTICE"))
        assert card["quotes"] or card["verdict"]
        for qt in card["quotes"]:
            assert verify_quote(C.rec[card["doc_id"]], qt), (card["doc_id"], qt["label"])
        if card["verdict"]:
            for e in card["verdict"]["evidence"]:
                assert C.rec[card["doc_id"]]["text"][e["char_start"]:e["char_end"]] == e["quote"]


@pytest.mark.parametrize("q,code", [
    ("How do I renew my pilot licence?", "OUT_OF_SCOPE"),
    ("Is my Piper Cherokee airworthy?", "OUT_OF_SCOPE"),
    ("Is there a proposed AD for the Cirrus SR22?", "OUT_OF_CORPUS"),
    ("Is there an AD for it?", "AMBIGUOUS_QUERY"),
    ("What is docket FAA-1999-9999 about?", "OUT_OF_CORPUS"),
    ("What does EASA AD 2025-0183 say about the A350?", "EXTERNAL_DOC_REQUIRED"),
])
def test_typed_refusals(C, q, code):
    a = answer(C, q)
    assert a["type"] == "refusal" and a["refusal"]["code"] == code
    assert a["refusal"]["message"] and a["refusal"]["what_would_resolve_it"]
    assert a["cards"] == []


@pytest.mark.parametrize("q", ["", "   ", "!!!???", "A" * 5000, "'; DROP TABLE ads; --", "737-800 " * 200])
def test_odd_input_never_crashes(C, q):
    a = answer(C, q)
    assert a["type"] in ("answer", "refusal")


def test_latency_budget(C):
    a = answer(C, "Which proposed AD addresses a fire extinguisher bottle problem?")
    assert a["latency_ms"]["retrieval"] < 3000
