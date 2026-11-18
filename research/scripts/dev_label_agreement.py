"""Compare two reviewers' development labels and compute Cohen's kappa.

    research/.venv/bin/python research/scripts/dev_label_agreement.py \
        datasets/annotations_dev/rev_som.jsonl datasets/annotations_dev/<second>.jsonl \
        --out results/dev_agreement/<first>__<second>.json

Read-only on both annotation files. Agreement is computed on the claims both
reviewers labelled. With few overlapping claims (e.g. 8), kappa is unstable:
the bootstrap interval is reported so that is visible. Disagreements are listed
for adjudication (engine.datasets.append_adjudication); nothing is decided here.
"""
import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.datasets import bootstrap_agreement, cohen_kappa  # noqa: E402


def load(path: str) -> dict[str, dict]:
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r["claim_id"] in rows:
                    raise SystemExit(f"{path}: duplicate claim {r['claim_id']}")
                rows[r["claim_id"]] = r
    reviewers = {r["reviewer_id"] for r in rows.values()}
    if len(reviewers) != 1:
        raise SystemExit(f"{path}: expected one reviewer, found {sorted(reviewers)}")
    return rows


def compare(a: dict[str, dict], b: dict[str, dict], n_boot: int = 2000) -> dict:
    ra, rb = next(iter(a.values()))["reviewer_id"], next(iter(b.values()))["reviewer_id"]
    if ra == rb:
        raise SystemExit("both files come from the same reviewer")
    shared = sorted(set(a) & set(b))
    pairs = [(a[c]["gold_label"], b[c]["gold_label"]) for c in shared]
    lo, hi = bootstrap_agreement(pairs, cohen_kappa, n_boot=n_boot) if pairs else (None, None)
    rows = [{"claim_id": c, "label_a": a[c]["gold_label"], "label_b": b[c]["gold_label"], "agree": a[c]["gold_label"] == b[c]["gold_label"],
             "confidence_a": a[c].get("confidence"), "confidence_b": b[c].get("confidence"),
             "uncertainty_a": a[c].get("uncertainty_type"), "uncertainty_b": b[c].get("uncertainty_type")} for c in shared]
    return {"reviewer_a": ra, "reviewer_b": rb, "n_shared": len(shared), "only_a": sorted(set(a) - set(b)), "only_b": sorted(set(b) - set(a)),
            "raw_agreement": sum(r["agree"] for r in rows) / len(rows) if rows else None,
            "cohen_kappa": cohen_kappa(pairs), "kappa_ci95_bootstrap": [lo, hi],
            "confusion": {f"{x}|{y}": n for (x, y), n in sorted(Counter(pairs).items())},
            "label_counts_a": dict(Counter(p[0] for p in pairs)), "label_counts_b": dict(Counter(p[1] for p in pairs)),
            "disagreements": [r for r in rows if not r["agree"]], "rows": rows,
            "note": "Few shared claims make kappa unstable; read it with the interval and the disagreement list."
                    if len(shared) < 30 else None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("first")
    ap.add_argument("second")
    ap.add_argument("--out", help="write the result as JSON (refuses to overwrite)")
    args = ap.parse_args(argv)
    res = compare(load(args.first), load(args.second))
    if args.out:
        if os.path.exists(args.out):
            raise SystemExit(f"{args.out} exists")
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"{res['reviewer_a']} vs {res['reviewer_b']}: {res['n_shared']} shared claims, raw agreement "
          f"{res['raw_agreement']}, kappa {res['cohen_kappa']} (bootstrap 95% {res['kappa_ci95_bootstrap']})")
    for d in res["disagreements"]:
        print(f"  DISAGREE {d['claim_id']}: {d['label_a']} ({d['confidence_a']}) vs {d['label_b']} ({d['confidence_b']})")


if __name__ == "__main__":
    main()
