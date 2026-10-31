"""Audit-log storage behind a tiny interface so it can move from a local JSONL file to a hosted store."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

ROOT = Path(__file__).resolve().parents[1]
GENESIS = "0" * 64


class AuditStore(Protocol):
    def append(self, event_id: int, action: str, note: str, tier_name: str | None, model: str | None) -> dict: ...
    def read(self, event_id: int | None = None) -> list[dict]: ...
    def verify(self) -> bool: ...


def _digest(prev: str, rec: dict) -> str:
    body = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev + body).encode()).hexdigest()


class JsonlAuditStore:
    def __init__(self, path: Path | None = None):
        self.path = path or ROOT / "artifacts" / "audit.jsonl"
        self._lock = threading.Lock()

    def _all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def append(self, event_id, action, note, tier_name=None, model=None) -> dict:
        with self._lock:
            rows = self._all()
            prev = rows[-1]["hash"] if rows else GENESIS
            rec = {
                "seq": len(rows) + 1,
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "event_id": event_id,
                "action": action,
                "note": note,
                "tier_name": tier_name,
                "model": model,
            }
            rec["prev_hash"] = prev
            rec["hash"] = _digest(prev, {k: v for k, v in rec.items() if k not in ("hash", "prev_hash")})
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            return rec

    def read(self, event_id=None) -> list[dict]:
        return [r for r in self._all() if event_id is None or r["event_id"] == event_id]

    def verify(self) -> bool:
        prev = GENESIS
        for r in self._all():
            body = {k: v for k, v in r.items() if k not in ("hash", "prev_hash")}
            if r["prev_hash"] != prev or r["hash"] != _digest(prev, body):
                return False
            prev = r["hash"]
        return True


store: AuditStore = JsonlAuditStore()
