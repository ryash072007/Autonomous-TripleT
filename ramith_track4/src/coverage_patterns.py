"""Phase 1A step 7: measure applicability patterns over the FULL corpus and append them to coverage_report.md.

Replaces the 30-document sample estimates from scoping with whole-corpus counts.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_sections import get_section  # noqa: E402

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"

PATTERNS = {
    "all_models ('all ... Model')": re.compile(r"\ball\b", re.I),
    "model list": re.compile(r"\bModels?\b", re.I),
    "CofA / date cutoff": re.compile(r"(?:original|certificate of airworthiness|export certificate).{0,120}(?:on or before|before|after|on or after)\s+[A-Z][a-z]+ \d{1,2}, \d{4}", re.I | re.S),
    "part number condition": re.compile(r"part number|\bP/N\b", re.I),
    "serial number condition": re.compile(r"serial number|\bS/N\b|\bMSN\b", re.I),
    "exclusion ('except')": re.compile(r"\bexcept\b", re.I),
    "external: EASA/TCCA/ANAC/CASA AD": re.compile(r"(?:EASA|Transport Canada|TCCA|ANAC|CASA|European Union Aviation Safety Agency)[^.]{0,40}\bAD\b", re.I),
    "external: 'as identified in' bulletin/AD": re.compile(r"as identified in", re.I),
    "group paragraphs (c)(1)...": re.compile(r"\(c\)\(1\)|paragraphs \(c\)\(1\)|\(1\)[^\n]{0,80}\n?\s*\(2\)", re.I),
}


def main():
    R = [json.loads(l) for l in open(PROCESSED / "docs.jsonl", encoding="utf-8")]
    cats = Counter()
    pat = Counter()
    n_app = 0
    for r in R:
        key, s = get_section(r["sections"], "Applicability")
        if r["source"] == "summary":
            cats["summary_only"] += 1
        elif s:
            cats["applicability_section_parsed"] += 1
            n_app += 1
            for name, rx in PATTERNS.items():
                if rx.search(s["text"]):
                    pat[name] += 1
        elif r["is_withdrawal"]:
            cats["withdrawal_notice"] += 1
        else:
            cats["full_text_but_no_applicability_section"] += 1
    lines = ["", "## Applicability section outcome (all 431 rows)", ""]
    lines += [f"- {k}: **{v}**" for k, v in cats.most_common()]
    lines += ["", f"## Applicability patterns over the {n_app} parsed Applicability sections (full corpus, not a sample)", ""]
    lines += [f"- {k}: **{pat[k]}** ({100 * pat[k] / n_app:.0f}%)" for k in PATTERNS]
    lines += ["", "Pattern flags are regex hits on the Applicability paragraph; a hit is a candidate for the rule extractor, not a verified label."]
    rep = PROCESSED / "coverage_report.md"
    txt = rep.read_text(encoding="utf-8")
    txt = txt.split("\n## Applicability section outcome")[0].rstrip("\n") + "\n" + "\n".join(lines) + "\n"
    rep.write_text(txt, encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
