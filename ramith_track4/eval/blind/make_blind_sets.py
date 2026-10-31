"""Blind sets, step 2: an INDEPENDENT annotator (a separate Claude call that sees only the source documents, never the
system's code, rules or outputs) writes questions and gold labels.

  B1 (fresh documents): 30 AD NPRMs NOT in the spreadsheet -> config + gold applicability verdict. Tests extractor + engine on
      documents the rules have never seen.
  B2 (fresh questions on the corpus): 12 lookup, 10 applicability (free text), 6 revision, 10 refuse, phrased by the annotator.

All prompts and raw outputs are saved under eval/blind/raw/. The generated files are hashed (freeze) BEFORE the system is run on them.
Target verdicts / refusal categories are assigned by a seeded RNG, not chosen by anyone who knows the system.
"""
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from build_records import load_records  # noqa: E402
from revisions import build_graph, latest_status  # noqa: E402

MODEL = "claude-sonnet-5-5"
TAG = sys.argv[2] if len(sys.argv) > 2 else ""
SEED = 20261031 + 1 + (1000 if TAG else 0)
RAW = ROOT / "eval" / "blind" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
client = anthropic.Anthropic()
REASONS = ("MODEL_LISTED, MODEL_NOT_LISTED, CERT_DATE_BEFORE_CUTOFF, CERT_DATE_AFTER_CUTOFF, PN_INSTALLED, PN_NOT_INSTALLED, SERIAL_IN_RANGE, "
           "SERIAL_OUT_OF_RANGE, EXCLUSION_UNVERIFIABLE, EXTERNAL_DOC_REQUIRED, INPUT_MISSING_CERT_DATE, INPUT_MISSING_SERIAL, INPUT_MISSING_PN, AMBIGUOUS_SCOPE")
SYSTEM = ("You are an independent aviation-records annotator building an evaluation set. You see only the notice text given to you. "
          "You know nothing about any software being evaluated. Output a single JSON object and nothing else.")
VERDICT_DEF = ("Verdict definitions, judged ONLY from the notice's applicability paragraph(s): APPLIES = every stated applicability condition is "
               "satisfied by the configuration; DOES_NOT_APPLY = at least one condition clearly fails (model not listed, date outside the stated limit, "
               "part number not in the list, serial outside the range); CANNOT_DETERMINE = applicability depends on something the configuration does not "
               "state (e.g. original certificate date, part number, serial number, engine/STC fit) or is defined in a document not provided "
               "(a manufacturer bulletin, a foreign-authority AD), or has an exclusion that needs maintenance-programme information.")
CORPUS_DESC = "a collection of FAA proposed airworthiness directive notices (NPRMs, 14 CFR Part 39) issued between 2001 and 2026"


def call(tag, user, retries=2):
    (RAW / f"{tag}.prompt.txt").write_text(user, encoding="utf-8")
    for i in range(retries + 1):
        r = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, messages=[{"role": "user", "content": user}])
        txt = "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
        (RAW / f"{tag}.out{i}.txt").write_text(txt, encoding="utf-8")
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        time.sleep(1)
    return None


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def b1():
    docs = [json.loads(l) for l in open(ROOT / "eval" / "blind" / f"fresh_docs{TAG}.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)
    targets = (["APPLIES"] * 10 + ["DOES_NOT_APPLY"] * 10 + ["CANNOT_DETERMINE"] * 10)[: len(docs)]
    rng.shuffle(targets)
    out = []
    for d, tgt in zip(docs, targets):
        u = (f"Below is the full text of one FAA proposed airworthiness directive notice.\n\n{VERDICT_DEF}\n\n"
             f"TASK: invent a realistic aircraft configuration so that, according ONLY to this notice, the correct determination is {tgt}. "
             "Config fields: make, model, cofa_date (original certificate of airworthiness date, YYYY-MM-DD, or null), serial (or null), "
             "part_numbers (list, possibly empty). Only include values a real owner would know. If it is impossible to build such a configuration "
             "from this notice, set feasible=false.\n"
             f"Reason codes you may use: {REASONS}.\n"
             'Return JSON: {"feasible": bool, "config": {"make":..., "model":..., "cofa_date":..., "serial":..., "part_numbers":[...]}, '
             '"gold_verdict": "APPLIES|DOES_NOT_APPLY|CANNOT_DETERMINE", "gold_reason": "<code>", "evidence_quote": "<verbatim sentence from the notice>", "notes": "<one line>"}\n\n'
             f"NOTICE TEXT:\n{d['text'][:32000]}")
        a = call(f"B1{TAG}_{d['doc_id']}", u)
        out.append({"id": f"B1{TAG}-{len(out)+1:02d}", "doc_id": d["doc_id"], "target": tgt, "annotation": a})
        print("B1", d["doc_id"], tgt, "->", (a or {}).get("gold_verdict"), (a or {}).get("gold_reason"), "feasible" if (a or {}).get("feasible") else "INFEASIBLE")
    p = ROOT / "eval" / "blind" / f"blind_B1{TAG}.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in out) + "\n", encoding="utf-8", newline="\n")
    return p


def b2():
    pairs = load_records()
    graph = build_graph([r for r, _ in pairs])
    gold_v1 = {d for l in open(ROOT / "eval" / "testset_v1.jsonl", encoding="utf-8") for d in json.loads(l)["gold_docs"]}
    for pf in (ROOT / "eval" / "blind").glob("blind_B2*.jsonl"):       # never reuse documents from earlier blind sets
        if pf.name != f"blind_B2{TAG}.jsonl":
            gold_v1 |= {d for l in open(pf, encoding="utf-8") for d in json.loads(l).get("gold_docs", [])}
    rng = random.Random(SEED + 7)

    def is_latest(r):
        st = latest_status(graph, r["docket"])
        return st.get("latest") and st["latest"]["doc_id"] == r["doc_id"]

    elig = [(r, a) for r, a in pairs if r["source"] != "summary" and r["summary"] and not r["is_withdrawal"] and is_latest(r) and r["doc_id"] not in gold_v1]
    rng.shuffle(elig)
    items = []
    # ---- lookup 12
    for r, a in elig[:12]:
        u = (f"Below is one FAA proposed AD notice from {CORPUS_DESC}.\nTASK: write ONE natural question an engineer might type to find THIS notice by "
             "what it is about (the aircraft/engine type and the problem or action). Do NOT mention its docket number, Federal Register number or AD number. "
             'Return JSON: {"question": "..."}\n\n'
             f"TITLE: {r['subject']}\nSUMMARY: {r['summary']}\n")
        a_ = call(f"B2{TAG}_lookup_{r['doc_id']}", u)
        if a_:
            items.append({"id": f"B2{TAG}-L{len(items)+1:02d}", "category": "lookup", "query": a_["question"], "gold_docs": [r["doc_id"]], "config": None})
    # ---- applicability 10
    app_pool = [(r, a) for r, a in elig[12:] if a["scope"] != "none"][:10]
    tg = ["APPLIES"] * 4 + ["DOES_NOT_APPLY"] * 3 + ["CANNOT_DETERMINE"] * 3
    rng.shuffle(tg)
    n_app = 0
    for (r, a), tgt in zip(app_pool, tg):
        sec = a["section"]
        app_txt = r["text"][sec["char_start"]:sec["char_end"]].strip()
        u = (f"Below is the applicability paragraph of one FAA proposed AD notice from {CORPUS_DESC}.\n\n{VERDICT_DEF}\n\n"
             f"TASK: write a natural question from an aircraft owner/engineer asking whether a proposed AD applies to their aircraft, with the configuration "
             f"stated inside the question text, so that the correct determination for THIS notice is {tgt}. Identify the notice by describing what it is about "
             "(the problem or the AD it supersedes), NOT by docket, Federal Register or AD number. If impossible, set feasible=false.\n"
             f"Reason codes you may use: {REASONS}.\n"
             'Return JSON: {"feasible": bool, "question": "...", "config": {"make":..., "model":..., "cofa_date":..., "serial":..., "part_numbers":[...]}, '
             '"gold_verdict": "...", "gold_reason": "<code>"}\n\n'
             f"TITLE: {r['subject']}\nSUMMARY: {r['summary']}\nAPPLICABILITY PARAGRAPH:\n{app_txt[:3500]}")
        a_ = call(f"B2{TAG}_app_{r['doc_id']}", u)
        if a_ and a_.get("feasible"):
            n_app += 1
            items.append({"id": f"B2{TAG}-A{n_app:02d}", "category": "applicability", "query": a_["question"], "gold_docs": [r["doc_id"]],
                          "config": None, "annotator_config": a_["config"], "gold_verdict": a_["gold_verdict"], "gold_reason": a_["gold_reason"], "target": tgt})
    # ---- revision 6
    multi = [k for k, ev in graph.items() if len(ev) >= 2 and not k.startswith(("FAA-2002", "2000", "2001"))]
    rng.shuffle(multi)
    wd = [r for r, _ in pairs if r["is_withdrawal"] and r["doc_number"] and r["doc_id"] not in gold_v1]
    rng.shuffle(wd)
    rev_cases = [("multi", k) for k in multi[:3]] + [("withdrawn", r["docket"]) for r in wd[:3]]
    for n, (kind, k) in enumerate(rev_cases, 1):
        evs = graph[k.split(",")[0].strip()] if kind == "multi" else graph.get(k.split(",")[0].strip(), [])
        recs = {}
        for pr, _ in pairs:
            recs[pr["doc_id"]] = pr
        lines = "\n".join(f"- doc {e['doc_id']} issued {e['date']}: {(recs[e['doc_id']]['summary'] or '')[:420]} | spreadsheet note: {recs[e['doc_id']].get('comments')}" for e in evs)
        u = (f"Below are all entries for one rulemaking docket {k} in {CORPUS_DESC}.\nTASK: write ONE natural question about the status of this proposal "
             "(for example: is it still active, was it revised or withdrawn, which is the latest version, what is the current comment deadline). "
             "You may mention the docket number. Then state the correct answer from the entries.\n"
             'Return JSON: {"question": "...", "gold_status": "<plain-language correct answer>", "gold_latest_doc": "<doc id of the latest entry>", "withdrawn": bool}\n\n' + lines)
        a_ = call(f"B2{TAG}_rev_{n}", u)
        if a_:
            items.append({"id": f"B2{TAG}-R{n:02d}", "category": "revision", "query": a_["question"], "gold_docs": [e["doc_id"] for e in evs],
                          "gold_status": a_["gold_status"], "gold_latest_doc": a_.get("gold_latest_doc"), "withdrawn": bool(a_.get("withdrawn")), "config": None})
    # ---- refuse 10
    makes = sorted({r["make_norm"] for r, _ in pairs if r["make_norm"]})
    ext_pool = [(r, a) for r, a in pairs if a.get("external_refs") and r["source"] == "fr_text" and not r["is_withdrawal"]]
    rng.shuffle(ext_pool)
    ins_pool = elig[40:60]
    cats = ["OUT_OF_SCOPE_judgement", "OUT_OF_SCOPE_offtopic", "OUT_OF_CORPUS_entity", "OUT_OF_CORPUS_final", "EXTERNAL_DOC_REQUIRED",
            "AMBIGUOUS_QUERY", "CONTRADICTORY_CONFIG", "INSUFFICIENT_EVIDENCE", "OUT_OF_CORPUS_old_date", "OUT_OF_SCOPE_judgement"]
    rng.shuffle(cats)
    descr = {
        "OUT_OF_SCOPE_judgement": "asks the tool to decide airworthiness, safety, legality to fly/dispatch, or compliance for the user's aircraft",
        "OUT_OF_SCOPE_offtopic": "is a general question unrelated to airworthiness directives (e.g. about airlines, travel, weather, careers)",
        "OUT_OF_CORPUS_entity": "asks about an aircraft or engine manufacturer/model that has no entry in the collection (the manufacturers present are: " + ", ".join(makes[:60]) + "); pick one NOT in this list",
        "OUT_OF_CORPUS_final": "asks whether a final airworthiness directive has been issued or is in force (the collection only has proposed rules)",
        "EXTERNAL_DOC_REQUIRED": "asks for the content of the foreign-authority AD or manufacturer bulletin that the context notice refers to, which is not in the collection",
        "AMBIGUOUS_QUERY": "is too vague to answer because it does not say which aircraft, engine or notice it means",
        "CONTRADICTORY_CONFIG": "states an aircraft make and model that contradict each other (a real model attributed to the wrong manufacturer)",
        "INSUFFICIENT_EVIDENCE": "asks for a specific numeric value or detail about the context notice that the notice does not actually state",
        "OUT_OF_CORPUS_old_date": "asks about an airworthiness directive from before the year 2000",
    }
    for n, c in enumerate(cats, 1):
        ctx = ""
        if c == "EXTERNAL_DOC_REQUIRED":
            r, a = ext_pool[n]
            ctx = f"\nCONTEXT NOTICE TITLE: {r['subject']}\nCONTEXT APPLICABILITY: {r['text'][a['section']['char_start']:a['section']['char_end']].strip()[:1200]}"
        if c == "INSUFFICIENT_EVIDENCE":
            r, a = ins_pool[n]
            ctx = f"\nCONTEXT NOTICE TITLE: {r['subject']}\nCONTEXT SUMMARY: {r['summary']}\n(The summary is only part of the notice; ask for a specific number or detail that is not in the summary and is unlikely to be in a short notice.)"
        u = (f"We are testing a question-answering tool over {CORPUS_DESC}. The tool should REFUSE to answer some questions.\n"
             f"TASK: write ONE realistic question that {descr[c]}.{ctx}\n"
             'Return JSON: {"question": "...", "config": {"make": null, "model": null, "cofa_date": null, "serial": null, "part_numbers": []}}')
        a_ = call(f"B2{TAG}_refuse_{n}_{c}", u)
        if a_:
            items.append({"id": f"B2{TAG}-X{n:02d}", "category": "refuse", "query": a_["question"], "gold_docs": [], "config": None,
                          "annotator_config": a_.get("config"), "refusal_category": c})
    p = ROOT / "eval" / "blind" / f"blind_B2{TAG}.jsonl"
    p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in items) + "\n", encoding="utf-8", newline="\n")
    return p


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    paths = []
    if which in ("b1", "both"):
        paths.append(b1())
    if which in ("b2", "both"):
        paths.append(b2())
    for p in paths:
        print("FROZEN", p.name, "sha256", sha(p), "lines", sum(1 for _ in open(p, encoding="utf-8")))
