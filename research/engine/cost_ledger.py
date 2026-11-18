"""Aggregate spending cap shared by every process and every resume.

A per-process BudgetGuard forgets its spend when the process ends, so N
batches each approved for $X could spend N*X. A ledger is one append-only
JSONL file (results/cost_ledger/<name>.jsonl) whose first line fixes the cap:

    {"type": "open", "cap_usd": 15.0, ...}
    {"type": "reserve", "id": ..., "request_key": ..., "worst_usd": ...}   before a paid call
    {"type": "settle",  "id": ..., "actual_usd": ..., "usage": {...}}       after it returns
    {"type": "fail",    "id": ..., "error": ...}                            the call raised
    {"type": "release", "id": ..., "reason": ...}                           the request was never sent

Committed spend = settled actual + every reservation not yet settled, at its
worst case. A failed call keeps its reservation: whether the API billed it is
unknown, so it is counted as spent (conservative). `reconcile()` settles an
open reservation whose response did reach the cache (a process killed between
the API reply and the settle line).

Every read-check-write happens under an exclusive flock on the file, so two
processes cannot both reserve the last dollars. Cache hits never touch the
ledger: only new paid calls count, and spend before the ledger was opened is
never included."""

import fcntl
import json
import os
import time
import uuid
from contextlib import contextmanager

from . import RESEARCH_ROOT

LEDGER_DIR = os.environ.get("RC_COST_LEDGER_DIR") or os.path.join(RESEARCH_ROOT, "results", "cost_ledger")


class LedgerExceeded(RuntimeError):
    pass


def ledger_path(name: str, ledger_dir: str = LEDGER_DIR) -> str:
    if not name or any(ch in name for ch in "/\\") or name.startswith("."):
        raise ValueError(f"bad ledger name {name!r}")
    return os.path.join(ledger_dir, f"{name}.jsonl")


class CostLedger:
    def __init__(self, name: str, cap_usd: float | None = None, ledger_dir: str = LEDGER_DIR):
        self.name, self.path = name, ledger_path(name, ledger_dir)
        os.makedirs(ledger_dir, exist_ok=True)
        with self._locked() as rows:
            if not rows:
                if cap_usd is None or cap_usd <= 0:
                    raise ValueError(f"ledger {name} does not exist; open it with a positive cap_usd")
                self._append({"type": "open", "cap_usd": round(float(cap_usd), 2), "at": _now()})
            elif cap_usd is not None and round(float(cap_usd), 2) != rows[0]["cap_usd"]:
                raise ValueError(f"ledger {name} was opened with cap ${rows[0]['cap_usd']:.2f}; it cannot be changed "
                                 f"(asked ${cap_usd:.2f})")

    # ------------------------------------------------------------ file
    @contextmanager
    def _locked(self):
        with open(self.path, "a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                self._f = f
                yield [json.loads(line) for line in f if line.strip()]
            finally:
                self._f = None
                fcntl.flock(f, fcntl.LOCK_UN)

    def _append(self, row: dict) -> None:
        self._f.write(json.dumps(row) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    # ------------------------------------------------------------ state
    @staticmethod
    def summarize(rows: list[dict]) -> dict:
        cap = rows[0]["cap_usd"] if rows else 0.0
        open_, settled, failed = {}, 0.0, 0.0
        n_settled = n_failed = 0
        for r in rows[1:]:
            if r["type"] == "reserve":
                open_[r["id"]] = r
            elif r["type"] == "settle" and r["id"] in open_:
                settled += r["actual_usd"]
                n_settled += 1
                open_.pop(r["id"])
            elif r["type"] == "release" and r["id"] in open_:
                open_.pop(r["id"])
            elif r["type"] == "fail" and r["id"] in open_:
                failed += open_[r["id"]]["worst_usd"]
                n_failed += 1
                open_.pop(r["id"])
        reserved = sum(r["worst_usd"] for r in open_.values())
        committed = settled + failed + reserved
        return {"cap_usd": cap, "settled_usd": round(settled, 6), "failed_reserved_usd": round(failed, 6),
                "open_reserved_usd": round(reserved, 6), "committed_usd": round(committed, 6),
                "remaining_usd": round(cap - committed, 6), "paid_calls": n_settled, "failed_calls": n_failed,
                "open_reservations": [r["id"] for r in open_.values()]}

    def status(self) -> dict:
        with self._locked() as rows:
            return {"ledger": self.name, "path": self.path, **self.summarize(rows)}

    def remaining(self) -> float:
        return self.status()["remaining_usd"]

    # ------------------------------------------------------------ calls
    def reserve(self, worst_usd: float, request_key: str | None = None, run_id: str | None = None) -> str:
        with self._locked() as rows:
            s = self.summarize(rows)
            if s["committed_usd"] + worst_usd > s["cap_usd"] + 1e-9:
                raise LedgerExceeded(f"ledger {self.name}: next call could cost ${worst_usd:.4f} but only "
                                     f"${s['remaining_usd']:.4f} of the ${s['cap_usd']:.2f} cap remains")
            rid = uuid.uuid4().hex
            self._append({"type": "reserve", "id": rid, "request_key": request_key, "worst_usd": round(worst_usd, 6),
                          "run_id": run_id, "pid": os.getpid(), "at": _now()})
            return rid

    def settle(self, rid: str, actual_usd: float, usage: dict | None = None) -> None:
        with self._locked():
            self._append({"type": "settle", "id": rid, "actual_usd": round(actual_usd, 6), "usage": usage or {}, "at": _now()})

    def fail(self, rid: str, error: str) -> None:
        with self._locked():
            self._append({"type": "fail", "id": rid, "error": error[:300], "at": _now()})

    def release(self, rid: str, reason: str) -> None:
        """Only for a reservation whose request provably never left the
        process (e.g. the API client could not be built). Anything that may
        have reached the API is `fail`, which stays counted."""
        with self._locked():
            self._append({"type": "release", "id": rid, "reason": reason[:300], "at": _now()})

    def audit(self, ids: list[str], result: str, evidence: str) -> None:
        """Append an audit record about earlier entries (e.g. a billing check of
        failed calls). It changes no amount; only `release` / `settle` do."""
        with self._locked():
            self._append({"type": "audit", "ids": ids, "result": result[:300], "evidence": evidence[:1000], "at": _now()})

    def reconcile(self, cache_dir: str, pricing) -> list[str]:
        """Settle open reservations whose response reached the cache."""
        done = []
        with self._locked() as rows:
            s = self.summarize(rows)
            res = {r["id"]: r for r in rows if r["type"] == "reserve" and r["id"] in s["open_reservations"]}
            for rid, r in res.items():
                key = r.get("request_key")
                p = os.path.join(cache_dir, key[:2], f"{key}.json") if key else None
                if p and os.path.exists(p):
                    usage = (json.load(open(p))["response"].get("usage") or {})
                    self._append({"type": "settle", "id": rid, "usage": usage, "at": _now(), "reconciled": True,
                                  "actual_usd": round(pricing.cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0)), 6)})
                    done.append(rid)
        return done


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
