# DECISIONS

1. **Source data:** `data/raw/ad_nprm.xlsx` copied from Downloads; SHA-256 `3bc255f5f790b3adf41b8b70525dd1867310820801ac960fedf9b3ddc2fb1fd0`. Original untouched.
2. **UI: FastAPI + static HTML instead of Streamlit.** Streamlit needs `pyarrow`, which has no wheel for this ARM64 Python 3.13 (build failed); a binary-only install pulled streamlit 0.8, which is broken. FastAPI and uvicorn already work.
3. **LLM:** Anthropic (`claude-haiku-5-5` verified working). Used only for (a) query-parser fallback, (b) the LLM-only baseline. Never for applicability, revision status or answer facts. Ramith approved use.
4. **Dev dependencies installed:** bm25s, anthropic, uvicorn.

5. **Test set v1 FROZEN 2026-10-31 11:12 SGT.** `eval/testset_v1.jsonl`, 40 questions (10 lookup, 12 applicability, 6 revision, 12 refuse; 10 dev / 30 test). SHA-256 `3097beda9d7118d0cfbaf90ffb50f4945287fc1705cc426b56fa2f8ff9ed609b`. No edits after this; any change becomes v2 and v1 results are still reported.
   - **Authorship caveat (must appear in README):** written by the AI coding assistant that also builds the system, not by an independent person, because the team is one human with three hours. Mitigations: labels were derived from the spreadsheet and the Federal Register full text (not from system output), written before any system code existed; the 30 `test` questions are never used for tuning; Ramith spot-checks a sample of labels (target 10) before submission. Single annotator, 40 questions: too small for tight confidence intervals.
   - **Doc ID convention:** FR document number (e.g. `2026-20543`); rows with no resolved FR doc number use `docket@YYYY-MM-DD`.
   - **Reason-code semantics:** `CERT_DATE_BEFORE_CUTOFF` = CofA on or before the cutoff (in scope); `CERT_DATE_AFTER_CUTOFF` = after (out of scope).
   - **Codes added beyond the control prompt:** `EXCLUSION_UNVERIFIABLE` (AD excludes airplanes meeting a maintenance-programme condition the user didn't state), `INSUFFICIENT_EVIDENCE` as a refusal code.
   - **Refusal scoring:** refusal precision/recall count any refusal; refusal-code accuracy is reported separately.
   - Where a model appears in several NPRMs, questions are anchored by docket, superseded AD number, or bulletin so the gold doc is unique. The gold doc for a revised docket is the **latest** entry.

6. **Doc-number resolution widened.** Link regex now handles `/documents/YYYY/MM/DD/N`, `/documents/N`, `/d/N`, `/a/N` and `R1-YYYY-N` forms: 237 rows resolve (229 unique FR documents), up from 216 in scoping. All 229 fetched, 0 errors.
7. **Embedded text discovered.** 169 rows (the ones without a URL) carry the notice's own regulatory text in the spreadsheet's `Link for Submitting Public Comment` column. Used as text source `embedded` (some cells had literal `\n`/`\t`, normalised once). Full-text coverage: fr_text 237 + embedded 169 = **406/431 (94.2%)**; 25 rows summary_only.
8. **Three source formats parsed** (modern lettered, old lettered, oldest unlettered/inline "Applicability:"). Applicability section found in 304 rows; 65 are withdrawal notices; 37 full-text rows lack an applicability section (extension/correction notices or partial text).
9. **Full-corpus applicability patterns** (regex hits on 304 parsed sections, see `data/processed/coverage_report.md`): model list 96%, "all" 35%, EASA/TCCA/ANAC AD 11%, "as identified in" 24%, part number 10%, serial number 18% (includes "all serial numbers" phrasing), "except" 3%, CofA date cutoff 1%. These correct the 30-document sample from scoping (serial 3%).
10. `data/processed/docs.jsonl` (full text) is git-ignored; regenerate with `python src/ingest.py && python src/build_corpus.py && python src/coverage_patterns.py`.
