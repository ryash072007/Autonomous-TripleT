from __future__ import annotations

from typing import Callable

from . import guard
from .facts import build_facts
from .llm import call_llm, llm_available
from .template import template_brief


def make_brief(event: dict, llm_fn: Callable[[dict], str] | None = None) -> dict:
    """Brief for one event. llm_fn is injectable for tests; by default the LLM is used only if a key is set."""
    facts = build_facts(event)
    fn = llm_fn
    if fn is None and llm_available():
        fn = call_llm
    if fn is None:
        return {"text": template_brief(facts), "source": "template", "fallback_reason": "no API key", "facts": facts}
    try:
        text = fn(facts)
    except Exception as exc:  # network, auth, rate limit: the app must still work
        return {"text": template_brief(facts), "source": "template",
                "fallback_reason": f"LLM call failed ({type(exc).__name__})", "facts": facts}
    if not text.strip().endswith("Analyst decides."):
        text = text.rstrip() + " Analyst decides."
    bad = guard.check(text, facts)
    if bad:
        return {"text": template_brief(facts), "source": "template",
                "fallback_reason": "numbers not in computed facts: " + ", ".join(bad[:5]), "facts": facts}
    return {"text": text, "source": "llm", "fallback_reason": None, "facts": facts}
