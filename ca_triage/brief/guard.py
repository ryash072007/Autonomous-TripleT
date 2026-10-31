"""Numeric guard: every number in the LLM text must equal a computed fact within the rounding it was written at."""

from __future__ import annotations

import re

from .facts import numeric_values

NUM = re.compile(r"(?<![\w.])[-−]?\d[\d,]*(?:\.\d+)?(?:e[-−]?\d+)?", re.I)


def extract_numbers(text: str) -> list[tuple[str, float, int]]:
    """(token, value, decimals written) for each number in the text."""
    out = []
    for m in NUM.finditer(text):
        tok = m.group(0)
        s = tok.replace("−", "-").replace(",", "")
        try:
            v = float(s)
        except ValueError:
            continue
        mant = s.lower().split("e")[0]
        dec = len(mant.split(".")[1]) if "." in mant else 0
        out.append((tok, v, dec))
    return out


def check(text: str, facts: dict) -> list[str]:
    """Return the numbers in `text` that match no fact. Empty list means the text passes."""
    allowed = numeric_values(facts)
    bad = []
    for tok, v, dec in extract_numbers(text):
        tol = 0.5 * 10 ** (-dec) + 1e-9
        if "e" in tok.lower():
            ok = any(a != 0 and abs(abs(v) - abs(a)) <= 1e-12 + 1e-6 * abs(a) for a in allowed)
        else:
            ok = any(abs(abs(v) - abs(a)) <= tol for a in allowed)
        if not ok:
            bad.append(tok)
    return bad
