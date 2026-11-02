"""SYNTHETIC data for self-checks of the analysis code -- NOT research data.

Notebooks 02, 05 and 06 need labelled data to show that the review,
metric and statistics code works. Until independent reviewers have labelled
real claims, they run on what this module generates: made-up claim ids
(prefix SYN-), made-up reviewers, and predictions drawn at random with a
fixed seed. Nothing here is derived from SEC data or from any model, and
every object carries `synthetic: True`; notebooks print a banner whenever
they use it.
"""

import random

from .schema import Adjudication, Annotation, DatasetClaim, LABELS

SYN_PREFIX = "SYN-"


def synthetic_claims(n: int = 30, seed: int = 7) -> list[DatasetClaim]:
    rng = random.Random(seed)
    cats = ["numerical", "interpretive", "ambiguous"]
    return [DatasetClaim(claim_id=f"{SYN_PREFIX}{i:03d}", company=rng.choice(["AAPL", "MSFT", "AMZN"]),
                         claim=f"Synthetic placeholder claim {i}", as_of_date="2026-08-15", claim_category=cats[i % 3],
                         split="gold", difficulty=["easy", "medium", "hard"][i % 3], notes="SYNTHETIC")
            for i in range(n)]


def synthetic_annotations(claims: list[DatasetClaim], seed: int = 7) -> tuple[list[Annotation], dict[str, Adjudication]]:
    """Two reviewers on most claims, a third of disagreements adjudicated,
    a few claims single-reviewed or untouched -- every review state appears."""
    rng = random.Random(seed)
    anns, adjs = [], {}
    for i, c in enumerate(claims):
        if i % 10 == 9:
            continue  # pending
        truth = rng.choice(LABELS)
        ev = [{"accession_number": "0000000000-00-000000", "quote": "synthetic quote text"}] if truth != "INSUFFICIENT_EVIDENCE" else []
        anns.append(Annotation(c.claim_id, "rev_A", truth, supporting_evidence=ev if truth == "SUPPORTED" else [],
                               contradictory_evidence=ev if truth == "CONTRADICTED" else [], review_notes="SYNTHETIC"))
        if i % 10 == 8:
            continue  # single review
        second = truth if rng.random() < 0.8 else rng.choice([x for x in LABELS if x != truth])
        anns.append(Annotation(c.claim_id, "rev_B", second, review_notes="SYNTHETIC",
                               supporting_evidence=[] if i % 7 == 0 else (ev if second == "SUPPORTED" else []),
                               contradictory_evidence=ev if second == "CONTRADICTED" else []))
        if second != truth and i % 3 == 0:
            adjs[c.claim_id] = Adjudication(c.claim_id, "adj_1", truth, "SYNTHETIC adjudication", considered_reviewers=["rev_A", "rev_B"])
    return anns, adjs


def synthetic_predictions(gold: dict[str, dict], accuracies: dict[str, float], seed: int = 11) -> list[dict]:
    """Per-approach predictions that are right with the given probability."""
    rng = random.Random(seed)
    out = []
    for name, acc in accuracies.items():
        for cid, g in sorted(gold.items()):
            right = rng.random() < acc
            label = g["label"] if right else rng.choice([x for x in LABELS if x != g["label"]])
            out.append({"claim_id": cid, "approach": name, "predicted_label": label, "initial_label": label,
                        "claim_category": ["numerical", "interpretive", "ambiguous"][int(cid[-3:]) % 3],
                        "company": "SYN", "difficulty": None, "latency_ms": None, "token_usage": None,
                        "estimated_cost_usd": None, "unsupported_conclusion": False, "synthetic": True, "is_mock": True})
    return out
