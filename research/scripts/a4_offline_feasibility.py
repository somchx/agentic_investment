"""A4 offline feasibility study on dev-v0.2 (EXPLORATORY; not a confirmatory result).

A4 = A2's answer by default; A3v2_2e (the proposer) may change it only through one of three gates,
each built from a researcher-stated principle (2026-11-18):

  P3 numeric lock   A2's numeric verdict stands when every A2 check is complete (status TRUE/FALSE,
                    no issues, unit, period equal to the asserted period, no conflicting versions) and
                    A3's deterministic checks raise no validity flag. A flagged check (SCOPE_MISMATCH,
                    PERIOD_MISMATCH, FUTURE_PERIOD) or an A2 check that is not complete re-opens the claim
                    to A3's deterministic re-check (N1 / N2).
  P1 abstention     a change to INSUFFICIENT_EVIDENCE is never accepted on the decidability (D-sup) or
                    coverage (E1) signal alone. It also needs: the claim is not numeric-locked, A3's own
                    review validated no decisive finding for A2's label (else abstaining discards real
                    evidence), and, for D-sup, an evaluative term with no stated criterion.
                    E1 additionally needs the independent proposer R not to repeat A2's label.
  P2 decisive       a change to SUPPORTED / CONTRADICTED needs evidence scope and assertion coverage,
                    not agreement: the deciding findings must be VALID, quote VERIFIED, period EXACT_MATCH
                    or COMPATIBLE_AFTER_VERIFIED_DERIVATION, no definition mismatch, not forward-looking /
                    intent; the claim must be DECIDABLE with no undefined evaluative criterion; for
                    SUPPORTED every claim assertion (A0, N*) must be entailed, for CONTRADICTED one assertion
                    contradicted with no qualifying entailment of it; a causal claim needs a CAUSE finding
                    (CHANGE suffices to contradict its measurable premise).

Inputs: run a3v2.2-dev-v0.2-20261118T052512Z (rebuilt offline from the LLM cache) and dev reference
labels v2 (7dccc43a). No API call, no gold file, no change to frozen code. Every number this writes is
dev-only and exploratory: dev-v0.2 was used to develop A3v2_2e, and the gates were written after
looking at the dev traces. Ablations drop one safeguard at a time.

    research/.venv/bin/python research/scripts/a4_offline_feasibility.py
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402

RUN = "a3v2.2-dev-v0.2-20261118T052512Z"
TRACES = os.path.join(RESEARCH_ROOT, "results", "runs", RUN, "traces")
LABELS = os.path.join(RESEARCH_ROOT, "datasets", "annotations_dev", "dev-v0.2_reference_labels.v2.approved.jsonl")
CLAIMS = os.path.join(RESEARCH_ROOT, "datasets", "development_cases_dev-v0.2.jsonl")
OUT = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a4_feasibility")
S, C, I = "SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"
GOOD_PERIOD = {"EXACT_MATCH", "COMPATIBLE_AFTER_VERIFIED_DERIVATION"}
WEAK_TYPES = {"FORWARD_LOOKING_OR_RISK", "MANAGEMENT_INTENT"}
VARIANTS = {
    "A4": set(),
    "A4 -numeric_lock": {"numeric_lock"},
    "A4 -abstain_guard": {"abstain_guard"},
    "A4 -scope_coverage": {"scope_coverage"},
    "A4 -criterion": {"criterion"},
    "A4 +R_agrees": {"+r_agrees"},
}


def stage(t: dict, name: str) -> dict:
    return next((s for s in t["stages"] if s["stage"] == name), {})


def a2_numeric_complete(a2: dict) -> bool:
    nv = stage(a2, "numeric_verification")
    if nv.get("rule") not in ("NUMERIC_ALL_TRUE", "NUMERIC_FALSE") or not nv.get("checks"):
        return False
    for c in nv["checks"]:
        comp = c.get("computed") or {}
        if c.get("status") not in ("TRUE", "FALSE") or c.get("issues") or not comp.get("unit") \
                or comp.get("period_end") != c["assertion"].get("period_end") or comp.get("conflicting_versions"):
            return False
    return True


def qualifying(f: dict) -> bool:
    return (f["validation_status"] == "VALID" and not f["definition_mismatch"] and f["evidence_type"] not in WEAK_TYPES
            and all(c.get("quote_status") == "VERIFIED" and c.get("period_status") in GOOD_PERIOD for c in f["checks"]))


def features(cid: str) -> dict:
    t = {a: json.load(open(os.path.join(TRACES, a, f"{cid}.json"))) for a in os.listdir(TRACES)}
    a2, e = t["A2_rag_numeric"], t["A3v2_2e"]
    g, er = stage(e, "reconciliation_guard"), stage(e, "evidence_review")
    rec = (g.get("decidability_gate") or {}).get("record") or {}
    findings = er.get("findings") or []
    assertions = [a["assertion_id"] for a in er.get("assertions") or []] or ["A0"]
    return {"a2": a2["final_label"], "e": e["final_label"], "R": t["A3v2_1_1_R"]["final_label"],
            "RG": t["A3v2_1_1_RG"]["final_label"], "a2_rule": stage(a2, "numeric_verification").get("rule"),
            "a2_numeric_complete": a2_numeric_complete(a2),
            "validity": (g.get("numeric_checks") or {}).get("validity") or [],
            "numeric_label_after": (g.get("numeric_checks") or {}).get("label_after"),
            "numeric_reason": (g.get("numeric_checks") or {}).get("reason"),
            "fcf": ((g.get("numeric_checks") or {}).get("fcf") or {}).get("status"),
            "dec_status": rec.get("status"), "dec_reason": (g.get("decidability_gate") or {}).get("reason"),
            "predicate": rec.get("predicate_type"), "criterion_source": rec.get("criterion_source"),
            "evaluative_terms": rec.get("evaluative_terms") or [], "dec_issues": rec.get("issues") or [],
            "contribution": (rec.get("contribution") or {}).get("type"),
            "coverage_reason": (g.get("coverage") or {}).get("reason"),
            "guard_reason": g.get("reason_code"), "findings": findings, "assertions": assertions}


def decide(x: dict, drop: set) -> tuple[str, str]:
    """(A4 label, gate) for one claim."""
    base, prop = x["a2"], x["e"]
    if prop == base:
        return base, "same"
    flagged = bool(x["validity"])
    locked = x["a2_numeric_complete"] and not flagged
    if locked and "numeric_lock" not in drop:
        return base, "P3 numeric lock"
    # P3 re-check: A3's deterministic checks (N1 validity flag, N2 FCF) produced the proposal
    if (flagged or x["fcf"] in ("TRUE", "FALSE")) and x["numeric_label_after"] == prop:
        return prop, "P3 numeric re-check"
    valid_for = lambda lab: [f for f in x["findings"] if qualifying(f) and
                             f["relation"] == {S: "ENTAILS", C: "CONTRADICTS"}.get(lab)]
    undefined_criterion = bool(x["evaluative_terms"]) and x["criterion_source"] in (None, "NONE")
    if prop == I:
        dsup = "NO_CRITERION" in (x["dec_reason"] or "")
        e1 = x["coverage_reason"] == "E1_NO_VALIDATED_BASIS" or "NOT_DECIDED_BY_VALID_EVIDENCE" in (x["guard_reason"] or "")
        if "abstain_guard" in drop:
            return (prop, "P1 abstain (unguarded)") if (dsup or e1) else (base, "P1 no abstain signal")
        if valid_for(base):
            return base, "P1 blocked: A3 validated evidence for A2's label"
        if dsup:
            return (prop, "P1 D-sup + undefined criterion") if undefined_criterion else (base, "P1 blocked: D-sup without evaluative term")
        if e1:
            return (prop, "P1 E1 + R does not repeat A2") if x["R"] != base else (base, "P1 blocked: E1 but R repeats A2")
        return base, "P1 no abstain signal"
    # P2 decisive change
    if "+r_agrees" in drop and x["R"] != prop:
        return base, "P2 blocked: R disagrees"
    if "criterion" not in drop:
        if x["dec_status"] != "DECIDABLE" or "SCOPE_NOT_COVERED" in str(x["dec_issues"]):
            return base, "P2 blocked: not decidable"
        if undefined_criterion:
            return base, "P2 blocked: undefined evaluative criterion"
    if "scope_coverage" in drop:
        return prop, "P2 accepted (no scope/coverage check)"
    fs = valid_for(prop)
    if not fs:
        return base, "P2 blocked: no qualifying finding"
    if prop == S:
        covered = all(any(f["assertion_id"] == a for f in fs) for a in x["assertions"])
    else:
        ent = {f["assertion_id"] for f in valid_for(S)}
        covered = any(f["assertion_id"] not in ent for f in fs)
    if not covered:
        return base, "P2 blocked: assertion coverage"
    if x["contribution"] == "PRIMARY_DRIVER" or x["predicate"] == "CAUSAL":
        ok = {"CAUSE"} | ({"CHANGE"} if prop == C else set())
        if not any(f["addresses"] in ok for f in fs):
            return base, "P2 blocked: causal claim without CAUSE evidence"
    return prop, "P2 accepted"


def score(pred: dict, ref: dict, a2: dict, cat: dict) -> dict:
    ids = sorted(ref)
    changed = [c for c in ids if pred[c] != a2[c]]
    out = {"correct": sum(pred[c] == ref[c] for c in ids), "n": len(ids),
           "corrections": sum(a2[c] != ref[c] and pred[c] == ref[c] for c in ids),
           "regressions": sum(a2[c] == ref[c] and pred[c] != ref[c] for c in ids),
           "changes": len(changed), "changes_correct": sum(pred[c] == ref[c] for c in changed),
           "insufficient_recall": f"{sum(pred[c] == I for c in ids if ref[c] == I)}/{sum(ref[c] == I for c in ids)}"}
    out["accuracy"] = round(out["correct"] / out["n"], 4)
    out["accepted_change_precision"] = round(out["changes_correct"] / out["changes"], 3) if out["changes"] else None
    out["by_category"] = {k: f"{sum(pred[c] == ref[c] for c in ids if cat[c] == k)}/{sum(cat[c] == k for c in ids)}"
                          for k in ("numerical", "interpretive", "ambiguous")}
    return out


def main() -> dict:
    ref = {r["claim_id"]: r["final_label"] for r in map(json.loads, open(LABELS))}
    cat = {r["claim_id"]: r["claim_category"] for r in map(json.loads, open(CLAIMS))}
    X = {c: features(c) for c in sorted(ref)}
    a2 = {c: x["a2"] for c, x in X.items()}
    arms = {"A2": a2, "R": {c: x["R"] for c, x in X.items()}, "RG": {c: x["RG"] for c, x in X.items()},
            "A3v2_2e": {c: x["e"] for c, x in X.items()}}
    gates = {}
    for name, drop in VARIANTS.items():
        res = {c: decide(x, drop) for c, x in X.items()}
        arms[name] = {c: r[0] for c, r in res.items()}
        gates[name] = {c: r[1] for c, r in res.items()}
    report = {"status": "EXPLORATORY (dev-v0.2 only; gates written after seeing dev traces; not confirmatory)",
              "run": RUN, "labels": os.path.relpath(LABELS, RESEARCH_ROOT), "paid_api_calls": 0, "gold_used": False,
              "arms": {k: score(v, ref, a2, cat) for k, v in arms.items()},
              "proposals": [{"claim_id": c, "category": cat[c], "reference": ref[c], "A2": a2[c], "proposal_2e": X[c]["e"],
                             "R": X[c]["R"], "A4": arms["A4"][c], "gate": gates["A4"][c],
                             "outcome": ("correction" if arms["A4"][c] == ref[c] != a2[c] else
                                         "regression" if a2[c] == ref[c] != arms["A4"][c] else
                                         "kept A2" if arms["A4"][c] == a2[c] else "wrong->wrong")}
                            for c in sorted(ref) if X[c]["e"] != a2[c]],
              "gate_counts": dict(Counter(gates["A4"].values()))}
    os.makedirs(OUT, exist_ok=True)
    json.dump(report, open(os.path.join(OUT, "a4_feasibility.json"), "w"), indent=1)
    return report


if __name__ == "__main__":
    r = main()
    for k, v in r["arms"].items():
        print(f"{k:20s} {v['correct']}/{v['n']} corr {v['corrections']} regr {v['regressions']} "
              f"changes {v['changes']} prec {v['accepted_change_precision']} INSUF {v['insufficient_recall']} {v['by_category']}")
    for p in r["proposals"]:
        print(f"  {p['claim_id']:12s} {p['category'][:4]} ref {p['reference'][:4]} A2 {p['A2'][:4]} -> 2e {p['proposal_2e'][:4]} "
              f"R {p['R'][:4]} | A4 {p['A4'][:4]} {p['outcome']:12s} {p['gate']}")
