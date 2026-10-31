"""Phase 1A: split FR / embedded AD text into sections with page numbers and char offsets.

Offsets index into the text stored in data/processed/docs.jsonl (fr_text: identical to the cached FR file),
so every span can be re-checked verbatim. Three source formats are handled:
  1. modern   : "(a) Comments Due Date ... (c) Applicability" (lettered, page markers [[Page N]])
  2. old      : "(a) Applicability ..." lettered, no Comments Due Date paragraph
  3. oldest   : unlettered title lines ("Applicability" alone) or inline "Applicability: Model ..."
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "fr"

PAGE_RE = re.compile(r"\[\[Page (\d+)\]\]")
HEAD_RE = re.compile(r"^[ \t]*\(([a-z])\)\s+([A-Z][^\n]{2,80})$", re.M)
WITHDRAW_RE = re.compile(r"\b(is withdrawing|withdraws? the (?:NPRM|notice)|the NPRM is withdrawn)\b", re.I)
UNLETTERED_RE = re.compile(
    r"^(Comments Due Date|Affected ADs|Applicability|Subject|Unsafe Condition|Compliance|Required Actions|"
    r"Alternative Methods of Compliance \(AMOCs\)|Related Information|Material Incorporated by Reference)[ \t]*$",
    re.M,
)
INLINE_APP_RE = re.compile(r"Applicability:?[ \t]*\n*[ \t]*(.+?)(?:\n[ \t]*\n|\Z)", re.S)


def page_at(text: str, pos: int, start_page):
    """Page containing char offset `pos`: last [[Page N]] marker before it, else the document's start page."""
    last = None
    for m in PAGE_RE.finditer(text, 0, pos):
        last = int(m.group(1))
    return last if last is not None else start_page


def _section(text, title, body_start, end, head_pos, start_page):
    return {
        "title": title,
        "text": text[body_start:end].strip(),
        "page": page_at(text, head_pos, start_page),
        "char_start": body_start,
        "char_end": end,
    }


def _parse_lettered(text: str, start_page, out: dict) -> bool:
    m = None
    for m in re.finditer(r"^\s*\(a\)\s+Comments Due Date", text, re.M):
        pass
    first = "a"
    if m is None:
        m = re.search(r"^\s*\(a\)\s+(?:Applicability|Affected ADs|Unsafe Condition)\b", text, re.M)
    if m is None:
        m = re.search(r"^\s*\(([ab])\)\s+Affected ADs\b", text, re.M)
        if m is not None:
            first = m.group(1)
    if m is None:
        return False
    seq, expect = [], ord(first)
    for h in HEAD_RE.finditer(text, m.start()):  # keep a,b,c... order to skip sub-list false positives
        if ord(h.group(1)) == expect:
            seq.append(h)
            expect += 1
    for i, h in enumerate(seq):
        end = seq[i + 1].start() if i + 1 < len(seq) else len(text)
        out["sections"][h.group(1)] = _section(text, h.group(2).strip(), h.end(), end, h.start(), start_page)
    return bool(seq)


def _parse_unlettered(text: str, start_page, out: dict) -> bool:
    heads = list(UNLETTERED_RE.finditer(text))
    if not any(h.group(1) == "Applicability" for h in heads):
        return False
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        key = re.sub(r"\W+", "_", h.group(1).lower()).strip("_")
        out["sections"][key] = _section(text, h.group(1), h.end(), end, h.start(), start_page)
    return True


def _inline_applicability(text: str, start_page, out: dict) -> None:
    """Old NPRMs print 'Applicability: Model ...' inline; synthesise an 'applicability' section from that paragraph."""
    if get_section(out["sections"], "Applicability")[1] is not None:
        return
    m = INLINE_APP_RE.search(text)
    if m and len(m.group(1)) > 20:
        out["sections"]["applicability_inline"] = _section(text, "Applicability", m.start(1), m.end(1), m.start(), start_page)


def parse_document(text: str, start_page=None) -> dict:
    """Return {'sections': {key: {title, text, page, char_start, char_end}}, 'is_withdrawal', 'has_reg_text'}."""
    out = {"sections": {}, "is_withdrawal": bool(WITHDRAW_RE.search(text[:6000])), "has_reg_text": False}
    if not _parse_lettered(text, start_page, out):
        _parse_unlettered(text, start_page, out)
    _inline_applicability(text, start_page, out)
    out["has_reg_text"] = bool(out["sections"])
    return out


def load_doc(doc: str):
    p = CACHE / f"{doc}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else None


def get_section(sections: dict, title_prefix: str):
    """(key, section) whose title starts with `title_prefix` (case-insensitive); letters differ between formats."""
    for key, s in sections.items():
        if s["title"].lower().startswith(title_prefix.lower()):
            return key, s
    return None, None
