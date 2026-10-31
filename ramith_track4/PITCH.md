# 3-minute pitch (target 2:50). Run: `python -m uvicorn api:app --app-dir src --port 8000`, open http://127.0.0.1:8000

**0:00–0:20 — user and problem**
"A CAMO engineer has to find which proposed airworthiness directives could affect one aircraft, read the exact applicability rule, and check whether it was revised or withdrawn. Today that is manual Federal Register searching. Generic AI chat gets this wrong by blending models and inventing citations. Ours has no language model in the answer path: quotes and deterministic rules only."

**0:20–1:50 — live (3 queries, paste from README "Demo queries")**
1. Query 1 → green **APPLIES**. Click the quote: "this is the exact sentence in the notice, page and character span; the verdict was computed by code, not a language model."
2. Query 2 → red **DOES NOT APPLY, certificate date after cutoff**. Point at the right panel: the docket has two versions, the latest has a different cutoff; the older one would have given the opposite answer.
3. Query 3 → amber **CANNOT DETERMINE: applicability is defined in a Transport Canada AD that is not in the corpus.** "We refuse to guess."
(If time: `Is my Cessna 172 airworthy?` → typed refusal.)

**1:50–2:40 — evidence and an honest failure**
- "Frozen test sets, independent annotator, first-pass numbers, never tuned on." Show the Results tab / `REPORT.md`.
- "On notices the rules had never seen: 82.7% verdict accuracy pooled over five fresh sets (CI 74–89), 89.5% on the last untouched set. The builder-written test said 100%: that gap is overfitting, and we report the blind number."
- "Plain BM25 matches us on lookup but gets 44–57% on applicability and never refuses. An LLM forced to answer cites document numbers that do not exist, about 76% of the time."
- **Failure:** "Once the system said 'applies' when a certificate-date limit applied: the Federal Register text wraps lines mid-phrase and our regex missed it. Fixed, found on blind data, and the card always shows the applicability paragraph so a qualified person can read the real condition."

**2:40–3:00 — limits and next**
"Proposed rules only; we cannot say if a final AD exists. Too cautious in some cases: it says 'cannot determine' where a human would decide. Next: per-model serial ranges, wildcard part numbers, linking final rules. The engineer decides; the tool shows its evidence."

Do NOT say: any time-saved figure, "zero hallucination" as a guarantee (say: no generated text, 0% unsupported quotes in our checks), or that the 100% held-out score is accuracy.
