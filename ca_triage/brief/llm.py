"""Anthropic call. Only turns already computed facts into a short brief; never decides or computes."""

from __future__ import annotations

import json
import os

DEFAULT_MODEL = "claude-haiku-5-5"

SYSTEM = (
    "You write a short brief (at most 120 words) for a satellite conjunction analyst. "
    "Only restate the facts in the JSON you are given. Do not introduce any number that is not in the facts, "
    "do not do arithmetic, do not give a recommendation beyond the tool's own output. "
    "Write plain sentences, no markdown. End with the exact words: Analyst decides."
)


def llm_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def call_llm(facts: dict) -> str:
    import anthropic  # imported lazily: the app must start without it

    client = anthropic.Anthropic()
    kw = dict(model=os.environ.get("BRIEF_MODEL", DEFAULT_MODEL), system=SYSTEM,
              messages=[{"role": "user", "content": json.dumps(facts)}])
    try:  # thinking tokens would eat the budget of a 120-word brief
        r = client.messages.create(max_tokens=400, thinking={"type": "disabled"}, **kw)
    except anthropic.BadRequestError:
        r = client.messages.create(max_tokens=1500, **kw)
    return "".join(b.text for b in r.content if getattr(b, "type", "") == "text").strip()
