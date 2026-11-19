"""POST-HOC EXPLORATORY: citation validity / unsupported conclusions (Task 1) and automated evidence proxies (Task 3A).

Reads only frozen files: Gold 150 run a3v2.2-gold150-20261118T112814Z (predictions, traces, corpus.json), the v1 run
(A3 v1 predictions), the Gold reference (engine.reference) and the cached SEC documents. Nothing frozen is written.

Task 1 measures what the pipeline itself recorded (experiments/pipeline.py build_prediction):
  unsupported_conclusion = label is SUPPORTED/CONTRADICTED and no cited item backing that label passed
  ClaimRun.validate (evidence id issued in the run, same company, filed on/before as_of_date, passage quote verbatim).
  This is CITATION VALIDITY (form), not whether the evidence means what the label says (semantic support).
Task 3A adds proxies computed here, each a necessary-but-not-sufficient condition for correct evidence:
  temporal_ok, in_run_corpus, span_in_source_document, same_filing_as_reference, reference_number_overlap.

    research/.venv/bin/python research/scripts/posthoc_citation_evidence.py
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.corpus import document_text  # noqa: E402
from engine.metrics import unsupported_rate  # noqa: E402
from engine.reference import load_reference  # noqa: E402
from a3v2.checks import qnorm, tolerant_quote_status  # noqa: E402

RUN = os.path.join(RESEARCH_ROOT, "results", "runs", "a3v2.2-gold150-20261118T112814Z")
V1 = os.path.join(RESEARCH_ROOT, "results", "runs", "claimverif-main-v1-20261110T104207Z")
OUT = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "citation_evidence")
ARMS = ["A1_conventional_rag", "A2_rag_numeric", "SR_self_reflection", "A3v2_1_1_R", "A3v2_1_1_RG", "A3v2_2e", "V1:A3_contradiction_aware"]
DECISIVE = ("SUPPORTED", "CONTRADICTED")
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d{3,}")


def sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def load() -> tuple[dict, dict]:
    P = defaultdict(dict)
    for r in map(json.loads, open(os.path.join(RUN, "predictions.jsonl"))):
        P[r["approach"]][r["claim_id"]] = r
    for r in map(json.loads, open(os.path.join(V1, "predictions.jsonl"))):
        if r["approach"] == "A3_contradiction_aware":
            P["V1:A3_contradiction_aware"][r["claim_id"]] = r
    return P, load_reference()["labels"]


def task1(P: dict, ref: dict) -> dict:
    out = {}
    for arm in ARMS:
        preds = list(P[arm].values())
        u = unsupported_rate(preds)                      # the project's own function, unchanged
        recount = [p for p in preds if p["predicted_label"] in DECISIVE and p["unsupported_conclusion"]]
        assert len(recount) == u["unsupported"]
        invalid = [c for p in preds for c in (p.get("invalid_citations") or [])]
        reasons = Counter(i for c in invalid for i in (c.get("issues") or ["NO_ISSUE_RECORDED"]))
        excluded = 0
        if arm.startswith("A3v2"):                       # A3v2 drops guard-excluded citations before validation
            for cid in P[arm]:
                t = json.load(open(os.path.join(RUN, "traces", arm, f"{cid}.json")))
                g = next((s for s in t["stages"] if s["stage"] == "reconciliation_guard"), {})
                excluded += len(g.get("excluded_citations") or [])
        out[arm] = {"decisive_predictions": u["decisive"], "unsupported_conclusions": u["unsupported"],
                    "unsupported_rate": round(u["unsupported_conclusion_rate"] or 0, 4),
                    "unsupported_and_wrong": sum(ref[p["claim_id"]]["label"] != p["predicted_label"] for p in recount),
                    "citations_total": sum(len(p.get("citations") or []) for p in preds),
                    "invalid_citations": len(invalid), "claims_with_invalid_citation": sum(bool(p.get("invalid_citations")) for p in preds),
                    "invalid_reasons": dict(reasons), "guard_excluded_before_validation": excluded if arm.startswith("A3v2") else None,
                    "unsupported_claims": sorted(p["claim_id"] for p in recount)}
    return out


def task3a(P: dict, ref: dict) -> dict:
    corpus = json.load(open(os.path.join(RUN, "corpus.json")))
    docs = {}

    def doc(acc):
        if acc not in docs:
            e = corpus.get(acc)
            docs[acc] = qnorm(document_text(acc, e["primary_document"])) if e else None
        return docs[acc]

    out = {}
    for arm in ARMS:
        rows = []
        for cid, p in P[arm].items():
            if p["predicted_label"] not in DECISIVE:
                continue
            r = ref[cid]
            backing = [c for c in (p["supporting_evidence"] if p["predicted_label"] == "SUPPORTED" else p["contradicting_evidence"]) if c.get("valid")]
            cites = [c for c in p.get("citations") or [] if c.get("accession_number")]
            asof = p.get("as_of_date")
            accs = {c["accession_number"] for c in cites}
            passages = [c for c in cites if c.get("kind") == "filing_passage" and c.get("quote")]
            spans = [tolerant_quote_status(c["quote"], doc(c["accession_number"]) or "") != "NOT_IN_PASSAGE"
                     if doc(c["accession_number"]) is not None else False for c in passages]
            ref_nums = {n.replace(",", "") for n in _NUM.findall(r.get("evidence_text") or "")}
            cited_nums = {n.replace(",", "") for c in cites for n in _NUM.findall(c.get("quote") or "")}
            for c in cites:
                for v in (c.get("values") or []):
                    cited_nums.add(str(v))
            rows.append({
                "claim_id": cid, "correct": p["predicted_label"] == r["label"], "has_valid_backing": bool(backing),
                "temporal_ok": all((c.get("filed") or "") <= (asof or "9999") for c in cites) if cites else None,
                "in_run_corpus": all(a in corpus and corpus[a]["company"] == r["company"] for a in accs) if accs else None,
                "span_in_source": all(spans) if spans else None,
                "same_filing_as_reference": bool(accs & set(r.get("reference_accessions") or [])) if r.get("reference_accessions") else None,
                "reference_number_overlap": bool(ref_nums & cited_nums) if ref_nums else None})

        def rate(key, subset):
            vals = [x[key] for x in subset if x[key] is not None]
            return {"k": sum(vals), "n": len(vals), "rate": round(sum(vals) / len(vals), 4) if vals else None}

        keys = ["has_valid_backing", "temporal_ok", "in_run_corpus", "span_in_source", "same_filing_as_reference", "reference_number_overlap"]
        out[arm] = {"decisive": len(rows), "correct_decisive": sum(x["correct"] for x in rows),
                    "all_decisive": {k: rate(k, rows) for k in keys},
                    "correct_decisive_only": {k: rate(k, [x for x in rows if x["correct"]]) for k in keys}}
        json.dump(rows, open(os.path.join(OUT, f"proxy_rows_{arm.replace(':', '_')}.json"), "w"), indent=0)
    return out


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    P, ref = load()
    t1, t3 = task1(P, ref), task3a(P, ref)
    inputs = {p: sha(os.path.join(RESEARCH_ROOT, p)) for p in (
        "results/runs/a3v2.2-gold150-20261118T112814Z/predictions.jsonl", "results/runs/a3v2.2-gold150-20261118T112814Z/corpus.json",
        "results/runs/claimverif-main-v1-20261110T104207Z/predictions.jsonl", "datasets/workbooks/Final_Gold_v3_approved.xlsx",
        "results/gold150/a3v2.2-gold150-20261118T112814Z/evaluation.json")}
    json.dump({"status": "POST-HOC EXPLORATORY", "script_sha256": sha(__file__), "inputs_sha256": inputs,
               "task1_citation_validity": t1, "task3a_evidence_proxies": t3},
              open(os.path.join(OUT, "citation_evidence.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
    print("wrote", os.path.relpath(OUT, RESEARCH_ROOT))
