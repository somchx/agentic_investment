"""Report, and with --download fetch from SEC EDGAR, every filing the claims'
cutoffs make eligible. SEC EDGAR is free (no API key); downloads land in the
application's SEC cache (backend/app/data/cache). Writes
datasets/corpus_manifest.json with each document's sha256.

    research/.venv/bin/python research/scripts/build_corpus.py            # report only (offline)
    research/.venv/bin/python research/scripts/build_corpus.py --download
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.corpus import build_corpus  # noqa: E402
from engine.datasets import DEV_PATH, GOLD_PATH, load_claims  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="fetch missing documents from SEC EDGAR (free)")
    args = ap.parse_args()
    claims = [c.to_input() for c in load_claims(DEV_PATH) + load_claims(GOLD_PATH)]
    rows = build_corpus(claims, allow_network=args.download)
    out = os.path.join(RESEARCH_ROOT, "datasets", "corpus_manifest.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)
    for r in rows:
        print(f"{r['company']:5} {r['form']:5} filed {r['filed']} period {r['report_date']} {r['accession_number']} {'cached' if r['cached'] else 'MISSING'}")
    missing = sum(1 for r in rows if not r["cached"])
    print(f"{len(rows)} documents, {missing} missing -> {out}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
