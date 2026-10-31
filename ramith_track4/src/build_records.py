"""Phase 2: build data/processed/ad_records.jsonl (record + extracted applicability) and revisions.json."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract import extract_applicability  # noqa: E402
from revisions import build_graph, classify  # noqa: E402

PROCESSED = Path(__file__).resolve().parent.parent / "data" / "processed"


def load_docs():
    return [json.loads(l) for l in open(PROCESSED / "docs.jsonl", encoding="utf-8")]


def load_records():
    """Return list of (record, applicability) pairs, reading the processed files."""
    out = []
    for l in open(PROCESSED / "ad_records.jsonl", encoding="utf-8"):
        d = json.loads(l)
        out.append((d["rec"], d["appl"]))
    return out


def main():
    docs = load_docs()
    n_app = 0
    with open(PROCESSED / "ad_records.jsonl", "w", encoding="utf-8") as f:
        for r in docs:
            r["event"] = classify(r)
            appl = extract_applicability(r)
            n_app += appl["scope"] != "none"
            f.write(json.dumps({"rec": r, "appl": appl}, ensure_ascii=False) + "\n")
    graph = build_graph(docs)
    (PROCESSED / "revisions.json").write_text(json.dumps(graph, indent=1), encoding="utf-8")
    multi = sum(1 for v in graph.values() if len(v) > 1)
    print(f"records {len(docs)}, with applicability {n_app}, dockets {len(graph)}, multi-entry dockets {multi}")


if __name__ == "__main__":
    main()
