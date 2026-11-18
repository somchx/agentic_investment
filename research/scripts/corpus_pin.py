"""Pin the SEC files an experiment reads (incident 2026-11-18, docs/a3v2_2/11_gold150_incident_recovery_analysis.md).

datasets/corpus_manifest.json pins filing documents by raw sha256, but EDGAR appends a random
`<script src="/...">` tag to every download, so a re-downloaded document never matches it byte for byte;
and the filing lists (submissions_CIK*.json) and XBRL company facts (CIK*.json) that decide which filings
and figures are used are not pinned at all. This records, for every such file the Gold / smoke / dev claims
read: the raw sha256 and a content sha256 (raw bytes with EDGAR's script tag removed; equal to raw for
JSON). `verify` fails if any file is missing or its content hash changed.

    research/.venv/bin/python research/scripts/corpus_pin.py write  [--out datasets/corpus_pin_a3v2.2.json]
    research/.venv/bin/python research/scripts/corpus_pin.py verify [--pin datasets/corpus_pin_a3v2.2.json]
"""
import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.corpus import RetrievalConfig, build_corpus, document_path, facts_path, submissions_path  # noqa: E402
from engine.datasets import load_claims  # noqa: E402

PIN = os.path.join(RESEARCH_ROOT, "datasets", "corpus_pin_a3v2.2.json")
CLAIM_SETS = {"gold": "datasets/gold_claims.jsonl", "smoke": "datasets/smoke_cases_a3v2.2.jsonl",
              "dev-v0.2": "datasets/development_cases_dev-v0.2.jsonl"}
CONFIG = "configs/a3v2_2_gold150.json"
_EDGAR_SCRIPT = re.compile(rb'<script type="text/javascript"\s+src="/[^"]*"></script>')


def _hashes(path: str) -> dict:
    b = open(path, "rb").read()
    return {"raw_sha256": hashlib.sha256(b).hexdigest(), "content_sha256": hashlib.sha256(_EDGAR_SCRIPT.sub(b"", b)).hexdigest(),
            "bytes": len(b)}


def files() -> dict:
    """relative path -> what it is, for every SEC file the claim sets read."""
    retrieval = json.load(open(os.path.join(RESEARCH_ROOT, CONFIG)))["common"]["retrieval"]
    rc = RetrievalConfig(**{k: v for k, v in retrieval.items() if k in RetrievalConfig.__dataclass_fields__})
    out = {}
    for name, path in CLAIM_SETS.items():
        claims = [c.to_input() for c in load_claims(os.path.join(RESEARCH_ROOT, path))]
        for c in {c.company for c in claims}:
            for kind, p in (("submissions", submissions_path(c)), ("company_facts", facts_path(c))):
                out.setdefault(os.path.relpath(p, RESEARCH_ROOT), {"kind": kind, "company": c, "sets": []})["sets"].append(name)
        for f in build_corpus(claims, rc):
            p = document_path(f["accession_number"], f["primary_document"])
            e = out.setdefault(os.path.relpath(p, RESEARCH_ROOT), {"kind": "document", "company": f["company"],
                                                                    "accession_number": f["accession_number"], "sets": []})
            if name not in e["sets"]:
                e["sets"].append(name)
    return out


def write(out: str) -> dict:
    entries = {}
    for rel, meta in sorted(files().items()):
        p = os.path.join(RESEARCH_ROOT, rel)
        if not os.path.exists(p):
            raise SystemExit(f"missing {rel}; download it before pinning")
        entries[rel] = {**meta, **_hashes(p)}
    pin = {"version": "corpus-pin-1.0", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "claim_sets": CLAIM_SETS, "retrieval_config": CONFIG, "files": entries}
    json.dump(pin, open(out, "w"), indent=1)
    return pin


def verify(pin_path: str) -> list[str]:
    pin = json.load(open(pin_path))
    problems = []
    for rel, e in pin["files"].items():
        p = os.path.join(RESEARCH_ROOT, rel)
        if not os.path.exists(p):
            problems.append(f"missing {rel}")
        elif _hashes(p)["content_sha256"] != e["content_sha256"]:
            problems.append(f"content changed {rel}")
    extra = set(files()) - set(pin["files"])
    problems += [f"read but not pinned {r}" for r in sorted(extra)]
    return problems


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("write", "verify"))
    ap.add_argument("--pin", default=PIN)
    a = ap.parse_args()
    if a.cmd == "write":
        if os.path.exists(a.pin):
            raise SystemExit(f"{a.pin} exists; not overwritten")
        pin = write(a.pin)
        kinds = {}
        for e in pin["files"].values():
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        print(json.dumps({"wrote": os.path.relpath(a.pin, RESEARCH_ROOT), "files": kinds}))
    else:
        probs = verify(a.pin)
        print("corpus pin: PASS" if not probs else "corpus pin: FAIL\n  " + "\n  ".join(probs))
        sys.exit(1 if probs else 0)
