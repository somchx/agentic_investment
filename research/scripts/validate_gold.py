"""Validate the Final Gold reference against the gold claims and the SEC corpus
(offline, read-only). Exits non-zero on any error.

    research/.venv/bin/python research/scripts/validate_gold.py [--out results/metrics/gold_validation.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import DEV_PATH, GOLD_PATH, check_split_separation, file_sha256, load_split  # noqa: E402
from engine.reference import load_reference, validate_reference  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join("results", "metrics", "gold_validation.json"))
    args = ap.parse_args()
    dev, gold = load_split("development"), load_split("gold")
    ref = load_reference()
    report = validate_reference(gold, ref)
    report["errors"] += check_split_separation(dev, gold)
    report["provenance"] = ref["provenance"]
    report["claims_files"] = {os.path.relpath(p, RESEARCH_ROOT): file_sha256(p) for p in (GOLD_PATH, DEV_PATH)}
    out = args.out if os.path.isabs(args.out) else os.path.join(RESEARCH_ROOT, args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"{len(gold)} gold claims, {ref['provenance']['n_labels']} reference labels {report['label_counts']}")
    print("future-period claims:", ", ".join(report["future_period_claims"]) or "none")
    for w in report["warnings"]:
        print("warning:", w)
    for e in report["errors"]:
        print("ERROR:", e)
    print(f"{len(report['errors'])} error(s) -> {out}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
