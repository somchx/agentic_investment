"""SEC filings for development claims, kept apart from the frozen corpus.

    # report (offline) or, with --download, fetch from SEC EDGAR (free) every
    # filing an authoring workbook's claims make eligible, plus XBRL companyfacts
    research/.venv/bin/python research/scripts/dev_corpus.py dev_claims_filled.xlsx --version dev-v0.2 [--download]

datasets/corpus_manifest.json is part of the frozen v1 experiment and is never
rewritten here. Development filings go to datasets/corpus_manifest_<version>.json;
load_manifest() returns both, so the development tools see the new companies
while the gold workflow and the frozen runs see exactly what they saw before.
"""
import argparse
import glob
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine.corpus import RetrievalConfig, _cik, build_corpus, facts_path  # noqa: E402
from engine.datasets import DATASET_DIR  # noqa: E402
from engine.schema import DatasetClaim  # noqa: E402

FROZEN_MANIFEST = os.path.join(DATASET_DIR, "corpus_manifest.json")


def manifest_path(version: str) -> str:
    return os.path.join(DATASET_DIR, f"corpus_manifest_{version}.json")


def load_manifest() -> list[dict]:
    """The frozen manifest plus every development manifest, one row per document."""
    rows, seen = [], set()
    for path in [FROZEN_MANIFEST, *sorted(glob.glob(os.path.join(DATASET_DIR, "corpus_manifest_*.json")))]:
        with open(path, encoding="utf-8") as f:
            for r in json.load(f):
                if r["accession_number"] not in seen:
                    seen.add(r["accession_number"])
                    rows.append(r)
    return sorted(rows, key=lambda r: (r["company"], r["filed"]))


def _claims(workbook: str) -> list[DatasetClaim]:
    spec = importlib.util.spec_from_file_location("dev_claims_authoring", os.path.join(os.path.dirname(__file__), "dev_claims_authoring.py"))
    auth = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auth)
    return [DatasetClaim(claim_id=d["claim_id"], company=d["company"], claim=d["claim"], as_of_date=d["as_of_date"],
                         claim_category=d["claim_category"], split="development",
                         allowed_sources=[s.strip() for s in str(d["allowed_sources"] or "SEC_10K,SEC_10Q").split(",")],
                         reporting_period=d["reporting_period"], difficulty=d["difficulty"]) for d in auth.read(workbook)]


def build(workbook: str, version: str, download: bool = False) -> tuple[str, list[dict]]:
    claims = [c.to_input() for c in _claims(workbook)]
    rows = build_corpus(claims, RetrievalConfig(), allow_network=download)
    if download:
        from sec_client import get_company_facts
        for t in sorted({c.company for c in claims}):
            if not os.path.exists(facts_path(t)):
                get_company_facts(_cik(t))
    out = manifest_path(version)
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)
    return out, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workbook")
    ap.add_argument("--version", required=True)
    ap.add_argument("--download", action="store_true", help="fetch missing documents from SEC EDGAR (free)")
    args = ap.parse_args(argv)
    out, rows = build(args.workbook, args.version, args.download)
    for r in rows:
        print(f"{r['company']:5} {r['form']:5} filed {r['filed']} period {r['report_date']} {r['accession_number']} {'cached' if r['cached'] else 'MISSING'}")
    missing = sum(1 for r in rows if not r["cached"])
    print(f"{len(rows)} documents, {missing} missing -> {out}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
