# AD Applicability Desk
**Autonomous SG 2026, AI & Aerospace Track, Challenge #4** — a traceable, applicability-aware search over FAA Airworthiness Directive proposed rules (NPRMs).

## The user and the problem
A CAMO airworthiness / technical-records engineer (or a B1 technician) has to answer: *"which proposed ADs could affect this aircraft, what exactly do they say, and what is their latest status?"*
Today that means searching the Federal Register / FAA DRS by hand, reading each notice's applicability paragraph, and cross-checking revisions and withdrawals. Time and error cost has **not** been measured here; nothing below claims a time saving.

## What it does
- Searches 431 AD NPRMs (hybrid index over section-aware chunks), answers with **verbatim quotes** and their source (document, docket, FR citation, section, page, character span).
- Decides **APPLIES / DOES_NOT_APPLY / CANNOT_DETERMINE** for a stated aircraft configuration with **deterministic code** (model, certificate date, part number, serial range, exclusions, references to outside documents), with a reason code and the rule that fired.
- Shows the **revision trail** of a docket and its latest status (revised, withdrawn, comment period extended).
- **Refuses**, with a typed code and "what would resolve it", when it should (out of scope, not in the corpus, depends on an outside document, ambiguous, contradictory, no evidence).
- Every answer carries a **"PROPOSED RULE (NPRM): not legally binding"** banner. The engineer decides; the tool never says "compliant" or "safe to fly".

### LLM / non-LLM split
**No language model is in the answer path.** Answers are quotes plus fixed labels; applicability, dates and revision status are plain code, so there is nothing to hallucinate. An Anthropic model is used only to *evaluate* the system (independent test-set annotator and the "LLM only" baselines).

## Quick start
```bash
pip install -r requirements.txt
python src/ingest.py            # fetches full text for the notices that have a Federal Register link (cached; ~2 min)
python src/build_corpus.py      # merges fetched text + text embedded in the spreadsheet
python src/coverage_patterns.py # coverage report -> data/processed/coverage_report.md
python src/build_records.py     # structured applicability + revision graph
python -m uvicorn api:app --app-dir src --port 8000      # open http://127.0.0.1:8000
python -m pytest tests -q       # 46 tests
```
Source data: `data/raw/ad_nprm.xlsx` (the organisers' spreadsheet, copied unchanged). Full text comes from the public Federal Register API (no key needed).

## Demo queries (all verified)
1. `I have a Dassault Falcon 7X. Does the proposed AD superseding AD 2025-13-11 apply to it?` → **APPLIES** (model listed), quoted from the applicability paragraph.
2. `Does the latest proposed AD in docket FAA-2026-1338 apply to my Airbus A330-243, original certificate of airworthiness issued 2026-03-01?` → **DOES NOT APPLY** (certificate after the 2025-12-19 cutoff), and the trail shows the earlier NPRM had a different cutoff.
3. `Does the proposed AD that references Transport Canada AD CF-2026-20R1 apply to my Bell 505 helicopter?` → **CANNOT DETERMINE**: applicability is defined by a document that is not in the corpus.
4. `Is the NPRM on RB211 Trent 768-60 low-pressure compressor blades (docket FAA-2025-2541) still active?` → **WITHDRAWN**.
5. `Is my Cessna 172 airworthy?` → refusal (out of scope). `...Beechcraft King Air 350...` → refusal (not in the corpus).

## Architecture
```
xlsx index + Federal Register full text ─► section parser (3 historic formats) ─► rule-based applicability extraction (every value keeps its character span)
        │                                                                                   │
        └─► section-aware chunks ─► BM25 + metadata filters                                 ▼
query ─► rule parser (make, model, serial, dates, P/N, docket, AD no.) ─► candidate notices ─► deterministic engine ─► verdict + quotes
                                                  └─► typed refusals                       └─► revision graph ─► latest status
quote verifier: every quote must equal a slice of the stored source, else it is dropped
```

## Data coverage (generated: `data/processed/coverage_report.md`)
431 rows → **406 (94.2%) have full text** (237 from the Federal Register, 169 from regulatory text embedded in the spreadsheet), 25 summary-only. Applicability paragraph parsed for 304 notices; 65 are withdrawal notices. Only about 37% of notices (113 of 304) can be decided from the aircraft model alone; the rest need more input or end in CANNOT_DETERMINE with the clause quoted.

## Evaluation (generated: `eval/results/REPORT.md`; read it, including its caveats)
Honest summary:

| | Result |
|---|---|
| Held-out test written by the builder (30 q, run once) | 100% in every category — **optimistic, do not quote** |
| **Blind**: fresh Federal Register notices not in the spreadsheet, labels from an independent annotator, 5 sets pooled (first pass of each system version) | engine verdict accuracy **86/104 = 82.7%** (95% CI 74.3–88.8) |
| Blind free-text applicability questions, pooled | 25/42 = 59.5% (CI 44.5–73.0) |
| Blind lookup / revision / refusal recall / refusal precision, pooled | 59/60 / 29/30 / 41/50 (82.0%) / 41/46 (89.1%) |
| Final system on the last untouched set (e) | engine 17/19 = 89.5%; applicability 8/9; lookup 12/12; revision 5/6; refusal recall and precision 90% |
| Unsupported quotes | 0% (quote verifier) · latency p50 101 ms / p95 469 ms |

Baselines on the same questions: plain BM25 ties on lookup/revision (those questions reuse the notice's wording) but scores 44–57% on applicability (system 86–89% on sets c and e) and never refuses. An LLM with no documents mostly declines; forced to answer it cites document numbers that do not exist about 76% of the time.

### Hardening round after the first submission (read with the caveats)
- **Synthetic stress tests, no API cost:** `eval/synthetic_fuzz.py` runs about 65,000 random configurations against every notice and checks oracles that do not use the extractor (for example: a model whose name appears nowhere in a notice never gets APPLIES). It found one real silent error (King Air 350 matched inside `PC-6/350`), now fixed; the only flags left are oracle false alarms. `eval/parser_fuzz.py` builds 2,400 questions from known values: serial, part number, date, docket and model are recovered 100%.
- **Further fixes from re-reading every blind-set mismatch:** serial ranges tied to their model group, conjunctive evaluation (a failed condition beats an unreadable one), outside-document references always give CANNOT_DETERMINE, scoped exclusions, explanatory notes ignored, own-aircraft model preferred, cost / 'cleared to fly' / 'what does the bulletin say' questions refuse. See `DECISIONS.md` #33-34.
- **Fresh blind documents after these fixes:** set f (first pass, before the last two fixes) engine 20/23 = 87.0%; set g (frozen before it was run, system `b75633c`) engine **20/20**, reason codes 19/20. That is 20 documents: a small sample, not proof of perfection, and the annotator is itself inconsistent on 'as identified in an EASA AD' notices. Numbers on the older sets (B1-B2e) after these fixes are contaminated and are not reported as accuracy.
- **Not re-measured on blind data:** the free-text path (lookup / free-text applicability / revision / refusals). The API budget ran out before new question sets could be written, so the earlier first-pass figures in the table above still stand for that path.

### Where it fails, and how the user would know
- **Over-caution (most common):** says CANNOT_DETERMINE where the annotator said APPLIES (a note under (c) that mentions "with ...", an exclusion scoped to a different model, "-XX" wildcard part numbers). The reason code and quoted clause are shown.
- **Silent wrong "applies" (rare, most dangerous):** found once on blind data — a certificate-date condition missed because the Federal Register text wraps lines mid-phrase (fixed afterwards). Nothing on the card flags such a miss; the quoted applicability paragraph is always displayed beside the verdict so a qualified person can read the real condition.
- **Not handled:** serial ranges are stored per notice, not per model group; informal model names that differ from the notice; applicability defined in outside documents (by design: CANNOT_DETERMINE/refusal).
- First-pass accuracy on fresh documents did **not** trend upward while fixes were made (82.6, 87.0, 81.0, 72.2, 89.5%), so per-failure fixing is not proof of better generalisation.

## Evaluation integrity and authorship (please read)
- The 40-question test set was written by the AI assistant that built the system (not an independent person), from the documents, before any system code existed; it is frozen by SHA-256 (`DECISIONS.md` #5). The held-out part was run once (`eval/run_eval.py` refuses the test split without `--final` and logs every run).
- The **blind sets** were written by a separate Claude model that saw only the notices. Its labels can be wrong, and it is the same model family as some baselines. Each blind set was frozen by hash before the system ran on it; first-pass results are saved untouched (`eval/results/FIRSTPASS_*`). Numbers measured after fixing the system on a set are labelled contaminated and are not reported as accuracy.
- The extraction audit (hand-checked, four rounds incl. failures) has a single reviewer: `eval/results/extraction_audit.md`.
- Corpus = proposed rules (NPRMs) only; it cannot say whether a final AD exists.

## Layout
`src/` system · `ui/` single-page UI · `tests/` 46 tests · `eval/` test sets, blind-set generators, baselines, runners, results · `DECISIONS.md` every decision incl. failures · `STATUS.md` gate log · `CONTROL_PROMPT.md` build plan.
