# Extraction audit (rule-based applicability extractor)

Method: random sample of parsed Applicability sections (seeded), source paragraph read by hand and compared with the extracted fields
(model coverage, part-number condition, certificate-date cutoff, exclusion, external document reference, serial condition, other
configuration clauses). A record counts as correct if the verdict the engine would give is not misleading (a "cannot determine" on a
hard record counts as correct restraint; a plain "applies" when the paragraph carries an unchecked condition counts as wrong).
Single reviewer (the assistant that wrote the extractor). Not independent. Sample sizes are small.

| Round | Seed | n | Correct | What was wrong | Fix made |
|---|---|---:|---:|---|---|
| A | 7  | 10 | 6 (pre-fix)  | "as listed in <bulletin>" not read as external (2); "all manufacturer serial numbers" flagged as a serial condition; "Model 747 series" did not match 747-400 | wider external pattern; serial scrub; series match |
| B | 11 | 15 | 13 (after A fixes) | a range plus an extra single S/N (`...through F406-0089 and serial number F406-0091`) read as a range only; condition clause "that are required by 14 CFR 135 ..." ignored | any serial wording beyond a clean range -> cannot determine; residual-condition detector |
| C | 23 | 15 | 11-12 (after B fixes) | P/N clause without the word "installed" missed (plus composite P/N tokens); "with STC ... installed" missed; "that were delivered before <date>" missed; "serial \nnumbers" line-wrap and engine ESN not counted | any P/N mention = condition, composite/wrapped P/N lists -> cannot determine; residual keyword detector for unparsed configuration clauses; `\s+` and ESN in serial detection |
| **D** | **31** | **15** | **15 (after C fixes, never used for tuning)** | none found | none |

**Headline:** 15/15 on the last untouched sample (round D). That is a small sample (95% Wilson lower bound about 80%), and rounds A-C
were used to fix the extractor, so their pre-fix numbers (60%, 87%, ~75%) show how the extractor behaved before each fix, not its final accuracy.

## Cost of the restraint (all 304 parsed Applicability sections, regex flags)
- plain model list, no other condition: 113
- external document defines applicability ("as identified/listed/specified in ..."): 82
- configuration clause the tool does not evaluate: 59
- serial wording not a clean range: 25
- part-number condition: 29 (2 with unreadable composite lists)
- certificate-date cutoff: 3
- exclusion clause: 7

Roughly 37% of documents (113/304) can get a definite answer from model alone; the rest need user inputs the tool asks for, or end in
"cannot determine" with the clause quoted. That is deliberate: a wrong "does not apply" is worse than a cautious one.

## Known limitations
- Model matching is textual (list expansion + a "<base> series" rule); unusual model naming can give a false "model not listed".
- Part-number and serial lists are only evaluated when they are clean tokens/ranges; everything else is routed to cannot determine.
- Applicability text for the 169 embedded-text rows comes from the spreadsheet cell, not re-fetched from the Federal Register.
- Only the Applicability paragraph is read; conditions stated elsewhere in the notice are not.
