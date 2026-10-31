> **Update 11:12:** the assistant wrote and froze the test set (see DECISIONS.md #5). Ramith: please spot-check 10 labels instead of writing questions.

# Test set brief (for Ramith). 40 questions, write them from the documents, NOT from system output.

Sources: the xlsx (`data/raw/ad_nprm.xlsx`, Summary column) and the FR full text. Example full text:
https://www.federalregister.gov/documents/full_text/text/2026/10/19/2026-21387.txt
(change the doc number/date in the URL via the link column of the xlsx).

Mix: 10 lookup, 12 applicability-with-config, 6 revision/status, 12 should-refuse.
Splits: 10 `dev` (I may look), 30 `test` (I must NOT look until Phase 4).
Freeze at 11:53. Do not edit after freezing.

One JSON object per line in `eval/testset_v1.jsonl`:

```
{"id":"L01","split":"dev","category":"lookup","query":"What unsafe condition prompted the proposed AD for Airbus Helicopters AS350B3 main rotor servo-controls?","gold_docs":["2026-21387"],"gold_verdict":null,"gold_reason":null,"gold_status":null,"gold_refusal":null}
{"id":"A01","split":"test","category":"applicability","query":"Does a proposed AD apply to an Airbus A330-243 with original certificate of airworthiness dated 2026-01-10?","config":{"make":"Airbus","model":"A330-243","cofa_date":"2026-01-10"},"gold_docs":["2026-20543"],"gold_verdict":"APPLIES","gold_reason":"MODEL_LISTED","gold_status":null,"gold_refusal":null}
{"id":"R01","split":"test","category":"revision","query":"Was the NPRM for docket 2000-NM-120-AD ever re-issued, and what is the latest action?","gold_docs":["<doc numbers in date order>"],"gold_verdict":null,"gold_reason":null,"gold_status":"<what you read: withdrawn / superseded / latest NPRM>","gold_refusal":null}
{"id":"X01","split":"test","category":"refuse","query":"Is my Cessna 172 airworthy?","gold_docs":[],"gold_verdict":null,"gold_reason":null,"gold_status":null,"gold_refusal":"OUT_OF_SCOPE"}
```

Allowed `gold_verdict`: APPLIES | DOES_NOT_APPLY | CANNOT_DETERMINE
Allowed `gold_reason`: MODEL_LISTED, MODEL_NOT_LISTED, CERT_DATE_AFTER_CUTOFF, CERT_DATE_BEFORE_CUTOFF, PN_INSTALLED, PN_NOT_INSTALLED, EXTERNAL_DOC_REQUIRED, INPUT_MISSING_CERT_DATE, INPUT_MISSING_SERIAL, DOC_WITHDRAWN
Allowed `gold_refusal`: OUT_OF_CORPUS, OUT_OF_SCOPE, AMBIGUOUS_QUERY, CONTRADICTORY_CONFIG, EXTERNAL_DOC_REQUIRED, NOT_PART_39

Refuse ideas (12): make/model not in the file (e.g. Cessna 172); "is the final AD in force?";
"is my aircraft airworthy?"; contradictory config (a model that doesn't exist for that make);
applicability that depends on an EASA AD or Boeing bulletin (e.g. 2026-21387 refers to EASA AD 2026-0132);
a question with a missing serial/date where one is needed; a question answerable only from memory.

Starter docs covering patterns (read the (c) Applicability paragraph):
- 2026-20543 Airbus A330 groups (c)(1)-(5) + CofA date cutoff + supersedes AD
- 2026-00842 Boeing 737 "as identified in Boeing Alert Requirements Bulletin 737-55A1104 RB"
- 2026-19561 Bombardier BD-700-2A12 with an "except" clause
- 2026-06459 Ontic model-and-serial airplanes with part-number groups
- 2026-21387 Airbus Helicopters: applicability + actions defined via EASA AD 2026-0132
- 2026-13869 Boeing 747-400/-8 bulletin reference
- docket 2000-NM-120-AD has 4 entries 2001-2008 (revision chain)
