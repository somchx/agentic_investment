"""Dataset loading, split separation and gold-label assembly.

Files (research/datasets/):
- development_cases.jsonl  claims used while building prompts/pipelines
- gold_claims.jsonl        held-out claims; never used for tuning
- annotations/<reviewer>.jsonl  one file per independent human reviewer
- adjudications.jsonl      final decisions on disagreements (append-only)

Claims and labels are kept in different files on purpose: approaches load
claims only, and ClaimInput refuses records that carry label fields.
Gold labels are assembled here, read-only; nothing in this module writes a
label except `append_adjudication`, which refuses to replace an existing one.
"""

import glob
import hashlib
import json
import os
import re
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone

from . import RESEARCH_ROOT
from .schema import Adjudication, Annotation, DatasetClaim, SchemaError

DATASET_DIR = os.path.join(RESEARCH_ROOT, "datasets")
DEV_PATH = os.path.join(DATASET_DIR, "development_cases.jsonl")
GOLD_PATH = os.path.join(DATASET_DIR, "gold_claims.jsonl")
ANNOTATION_DIR = os.path.join(DATASET_DIR, "annotations")
ADJUDICATION_PATH = os.path.join(DATASET_DIR, "adjudications.jsonl")

# Adjudication status of one claim, derived from its annotations.
PENDING, SINGLE, AGREED, DISAGREED, ADJUDICATED = (
    "PENDING_ANNOTATION", "SINGLE_REVIEW", "AGREED", "DISAGREED", "ADJUDICATED")
FINAL_STATUSES = (AGREED, ADJUDICATED)
MIN_REVIEWERS = 2


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SchemaError(f"{os.path.basename(path)} line {n}: {e}") from e
    return rows


def file_sha256(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def load_claims(path: str, expected_split: str | None = None) -> list[DatasetClaim]:
    claims, seen = [], set()
    for row in read_jsonl(path):
        c = DatasetClaim(**row)
        if c.claim_id in seen:
            raise SchemaError(f"duplicate claim_id {c.claim_id} in {os.path.basename(path)}")
        if expected_split and c.split != expected_split:
            raise SchemaError(f"{c.claim_id}: split {c.split!r} in a {expected_split} file")
        seen.add(c.claim_id)
        claims.append(c)
    return claims


def _norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9%]+", " ", s.lower()).strip()


def check_split_separation(dev: list[DatasetClaim], gold: list[DatasetClaim]) -> list[str]:
    """Problems that would let development work leak into the held-out set."""
    problems = []
    shared = {c.claim_id for c in dev} & {c.claim_id for c in gold}
    if shared:
        problems.append(f"claim ids in both splits: {sorted(shared)}")
    dev_texts = {(c.company, _norm_text(c.claim)): c.claim_id for c in dev}
    for g in gold:
        key = (g.company, _norm_text(g.claim))
        if key in dev_texts:
            problems.append(f"gold {g.claim_id} duplicates development {dev_texts[key]} text")
    return problems


def load_split(split: str, path: str | None = None) -> list[DatasetClaim]:
    if split not in ("development", "gold"):
        raise SchemaError("split must be 'development' or 'gold'")
    return load_claims(path or (DEV_PATH if split == "development" else GOLD_PATH), expected_split=split)


def dataset_fingerprint(paths: list[str]) -> dict:
    return {os.path.relpath(p, RESEARCH_ROOT): file_sha256(p) for p in paths}


# ------------------------------------------------------------ annotations

def load_annotations(annotation_dir: str = ANNOTATION_DIR) -> list[Annotation]:
    out, seen = [], set()
    for path in sorted(glob.glob(os.path.join(annotation_dir, "*.jsonl"))):
        for row in read_jsonl(path):
            a = Annotation(**row)
            key = (a.claim_id, a.reviewer_id)
            if key in seen:
                raise SchemaError(f"reviewer {a.reviewer_id} annotated {a.claim_id} twice")
            seen.add(key)
            out.append(a)
    return out


def load_adjudications(path: str = ADJUDICATION_PATH) -> dict[str, Adjudication]:
    out = {}
    for row in read_jsonl(path):
        a = Adjudication(**row)
        if a.claim_id in out:
            raise SchemaError(f"two adjudications for {a.claim_id}; adjudications are append-once")
        out[a.claim_id] = a
    return out


def gold_status(claims: list[DatasetClaim], annotations: list[Annotation],
                adjudications: dict[str, Adjudication]) -> list[dict]:
    """Per-claim review state. A label is final only when at least two
    independent human reviewers agree, or an adjudicator decided."""
    by_claim = defaultdict(list)
    for a in annotations:
        by_claim[a.claim_id].append(a)
    rows = []
    for c in claims:
        anns = by_claim.get(c.claim_id, [])
        labels = sorted({a.gold_label for a in anns})
        adj = adjudications.get(c.claim_id)
        if adj:
            status, final = ADJUDICATED, adj.final_label
        elif not anns:
            status, final = PENDING, None
        elif len(anns) < MIN_REVIEWERS:
            status, final = SINGLE, None
        elif len(labels) == 1:
            status, final = AGREED, labels[0]
        else:
            status, final = DISAGREED, None
        missing_evidence = [a.reviewer_id for a in anns
                            if a.gold_label != "INSUFFICIENT_EVIDENCE" and not (a.supporting_evidence or a.contradictory_evidence)]
        rows.append({
            "claim_id": c.claim_id, "company": c.company, "claim_category": c.claim_category, "difficulty": c.difficulty,
            "n_reviewers": len(anns), "reviewer_labels": {a.reviewer_id: a.gold_label for a in anns},
            "adjudication_status": status, "final_label": final,
            "reviewers_missing_evidence": missing_evidence,
        })
    return rows


def finalized_gold(claims: list[DatasetClaim], annotations: list[Annotation],
                   adjudications: dict[str, Adjudication]) -> dict[str, dict]:
    """claim_id -> {label, supporting_evidence, contradictory_evidence} for
    finalized claims only. Evidence is the union over reviewers whose label
    equals the final label."""
    status = {r["claim_id"]: r for r in gold_status(claims, annotations, adjudications)}
    out = {}
    for cid, r in status.items():
        if r["adjudication_status"] not in FINAL_STATUSES:
            continue
        agreeing = [a for a in annotations if a.claim_id == cid and a.gold_label == r["final_label"]]
        out[cid] = {
            "label": r["final_label"], "status": r["adjudication_status"],
            "supporting_evidence": [e for a in agreeing for e in a.supporting_evidence],
            "contradictory_evidence": [e for a in agreeing for e in a.contradictory_evidence],
        }
    return out


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Agreement between two reviewers over the claims both labelled."""
    if not pairs:
        return None
    n = len(pairs)
    labels = sorted({x for p in pairs for x in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum((sum(1 for a, _ in pairs if a == lab) / n) * (sum(1 for _, b in pairs if b == lab) / n) for lab in labels)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def append_adjudication(adj: Adjudication, path: str = ADJUDICATION_PATH) -> None:
    """Append-only: an existing decision is never replaced."""
    existing = load_adjudications(path)
    if adj.claim_id in existing:
        raise SchemaError(f"{adj.claim_id} is already adjudicated; record a new dataset version instead of overwriting")
    row = asdict(adj)
    row["adjudicated_at"] = row["adjudicated_at"] or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
