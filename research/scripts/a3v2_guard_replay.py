"""Offline replay of the reconciliation guard and change policies on recorded A3 v2.1.1 traces (no LLM, no cost).

    research/.venv/bin/python research/scripts/a3v2_guard_replay.py \
        --labels datasets/annotations_dev/dev-v0.2_reference_labels.approved.jsonl

Every guard input is read back from the traces: the pre-guard state from the
A3v2_1_1_R trace (its final citations), the evidence review, the contradiction
assessments, counter numeric checks and A2's numeric verification. Citation
checks are deterministic and identical in guard 0.1 and 0.2, so the recorded
`excluded_citations` are fed back instead of rebuilding the evidence ledger.
The replay first re-runs guard 0.1 and refuses unless it reproduces every
recorded decision (outcome, reason, final label) on all claims.

Arms: A2, R, RG-0.1 (= recorded RG), RG-G3, RG-G6, RG-0.2 (G3+G6), and the
selective change policy C on top of RG-0.1 / RG-0.2:
  C-system    keep A2's INSUFFICIENT_EVIDENCE unless the claim has a numeric
              assertion parsed by the system or a decisive counter numeric check
              (uses only what the system knows at run time)
  C-category  same, but using the dataset's claim_category (not available at run
              time; diagnostic only)

ALL RESULTS ARE IN-SAMPLE DIAGNOSTICS: the rules were designed after reading
these claims' errors and gold labels. They are not evidence that a rule works.
Writes results/dev_v0_2/offline_ablation/<labels sha8>/ (never overwritten).
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.metrics import classification_metrics  # noqa: E402
from engine.stats import mcnemar  # noqa: E402
from a3v2.checks import revalidate_quotes_v11  # noqa: E402
from a3v2.decidability import apply_phase1  # noqa: E402
from a3v2.numeric_checks import apply_numeric_checks, fcf_direction_check, numeric_validity  # noqa: E402
from a3v2.guard import decide  # noqa: E402

_spec = importlib.util.spec_from_file_location("ev", os.path.join(os.path.dirname(__file__), "a3v2_dev_evaluate.py"))
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

CLAIMS_TABLE = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "offline_ablation")
DECISIVE = ("SUPPORTED", "CONTRADICTED")
REPLAY_VERSION = "1.3"  # 1.1: + guard 0.3 (G3b), quote check 1.1 arms; 1.2: + decidability gate arms (--decidability); 1.3: + N1/N2 numeric checks
BANNER = "IN-SAMPLE DIAGNOSTIC: rules designed after reading these claims' errors and gold labels; not a performance claim."


def _stage(t: dict, name: str) -> dict:
    return next((s for s in t["stages"] if s["stage"] == name), {})


def guard_inputs(row: dict) -> dict:
    rg = json.load(open(os.path.join(RESEARCH_ROOT, row["trace_RG"])))
    r = json.load(open(os.path.join(RESEARCH_ROOT, row["trace_RG"].replace("A3v2_1_1_RG", "A3v2_1_1_R"))))
    rec = _stage(rg, "reconciliation_guard")
    nv, rv, ci = _stage(r, "numeric_verification"), _stage(r, "evidence_review"), _stage(r, "contradiction_investigation")
    excluded = rec.get("excluded_citations") or []
    bad = {e["evidence_id"] for e in excluded}

    def recorded_check(ledger, claim, period, items):
        kept = [{"evidence_id": it.get("evidence_id"), "quote": it.get("quote") or "", "issues": []}
                for it in items if isinstance(it, dict) and it.get("evidence_id") not in bad]
        return kept, excluded

    assertions = (_stage(r, "analyze_claim").get("analysis") or {}).get("assertions") or []
    excerpts = {e["evidence_id"]: e.get("excerpt") or "" for e in r.get("evidence") or []}
    f11, restored = revalidate_quotes_v11(rv.get("findings") or [], excerpts.get, rv.get("claim_period") or {})
    return {"recorded": rec, "findings_q11": f11, "restored_q11": restored, "claim": r["claim"],
            "claim_period": rv.get("claim_period") or {}, "numeric_assertion": any(a.get("type") == "numeric" for a in assertions),
            "kwargs": dict(initial_label=rec["initial_label"], proposed_label=rec["proposed_label"], initial_rule=nv.get("rule"),
                           initial_checks=nv.get("checks") or [], supporting=r.get("citations") or [], contradicting=[],
                           assessments=_stage(r, "reconciliation").get("assessments") or [],
                           counter_numeric=ci.get("counter_numeric") or [], findings=rv.get("findings") or [],
                           ledger=None, claim=None, period=rv.get("claim_period"), citation_check=recorded_check)}


def guard_variant(inp: dict, rules: tuple) -> dict:
    """Guard 0.1 plus a subset of the 0.2 rules (for single-rule ablations)."""
    from a3v2 import guard as g
    g.GUARD_RULES["ablation"], g.GUARD_VERSIONS["ablation"] = rules, "ablation"
    try:
        return decide(**inp["kwargs"], version="ablation")
    finally:
        del g.GUARD_RULES["ablation"], g.GUARD_VERSIONS["ablation"]


def selective(a2: str, rg: str, numeric_ok: bool) -> str:
    """Policy C: A2's INSUFFICIENT_EVIDENCE is kept unless numeric grounds exist."""
    return a2 if a2 == "INSUFFICIENT_EVIDENCE" and rg in DECISIVE and not numeric_ok else rg


def with_decidability(a2, final, record, findings, scope, downgrade):
    return apply_phase1(a2, final, record, findings, scope, downgrade)


def replay(rows: list[dict], decid: dict | None = None) -> tuple[dict, list[str]]:
    preds = {k: {} for k in ("A2", "R", "RG-0.1", "RG-G3", "RG-G6", "RG-0.2", "RG-0.1+C-system", "RG-0.2+C-system",
                             "RG-0.1+C-category", "RG-0.3 (G3b)", "RG-0.3+G6", "RG-0.1+Q1.1", "RG-0.3+Q1.1",
                             "RG-0.3+Q1.1+C-system")}
    if decid:
        for k in ("V22: RG-0.3+Q1.1+G1", "V22: +G1+G4", "V22: +G1+D", "V22: +G1+G4+D", "V22: +G1+G4+D-sup (post hoc)",
                  "V22b: +G1+G4+D-sup+N1+N2"):
            preds[k] = {}
    reasons, mismatches = {}, []
    for row in rows:
        cid, inp = row["claim_id"], guard_inputs(row)
        rec = inp["recorded"]
        d01 = decide(**inp["kwargs"], version="0.1")
        if (d01["outcome"], d01["reason_code"], d01["final_label"]) != (rec["outcome"], rec["reason_code"], rec["final_label"]) \
                or d01["final_label"] != row["pred_RG"]:
            mismatches.append(f"{cid}: replay {d01['outcome']}/{d01['reason_code']}/{d01['final_label']} vs recorded "
                              f"{rec['outcome']}/{rec['reason_code']}/{rec['final_label']}")
        d3, d6, d02 = guard_variant(inp, ("G3",)), guard_variant(inp, ("G6",)), decide(**inp["kwargs"], version="0.2")
        q11 = {**inp, "kwargs": {**inp["kwargs"], "findings": inp["findings_q11"]}}
        d03, d03g6 = decide(**inp["kwargs"], version="0.3"), guard_variant(inp, ("G3b", "G6"))
        d01q, d03q = decide(**q11["kwargs"], version="0.1"), decide(**q11["kwargs"], version="0.3")
        numeric_ok = inp["numeric_assertion"] or any(n.get("status") in ("TRUE", "FALSE") for n in inp["kwargs"]["counter_numeric"])
        a2 = row["pred_A2"]
        for k, v in (("A2", a2), ("R", row["pred_R"]), ("RG-0.1", d01["final_label"]), ("RG-G3", d3["final_label"]),
                     ("RG-G6", d6["final_label"]), ("RG-0.2", d02["final_label"]),
                     ("RG-0.1+C-system", selective(a2, d01["final_label"], numeric_ok)),
                     ("RG-0.2+C-system", selective(a2, d02["final_label"], numeric_ok)),
                     ("RG-0.1+C-category", selective(a2, d01["final_label"], row["claim_type"] == "numerical")),
                     ("RG-0.3 (G3b)", d03["final_label"]), ("RG-0.3+G6", d03g6["final_label"]),
                     ("RG-0.1+Q1.1", d01q["final_label"]), ("RG-0.3+Q1.1", d03q["final_label"]),
                     ("RG-0.3+Q1.1+C-system", selective(a2, d03q["final_label"], numeric_ok))):
            preds[k][cid] = v
        if decid:
            rec = (decid.get(cid) or {}).get("record")
            for k, sc, dg in (("V22: RG-0.3+Q1.1+G1", False, False), ("V22: +G1+G4", True, False),
                              ("V22: +G1+D", False, True), ("V22: +G1+G4+D", True, True),
                              ("V22: +G1+G4+D-sup (post hoc)", True, "supported")):
                lab, why = with_decidability(a2, d03q["final_label"], rec, inp["findings_q11"], sc, dg)
                preds[k][cid] = lab
                if why:
                    reasons.setdefault(cid, {}).setdefault("decidability", {})[k] = why
            kw, cl = inp["kwargs"], inp["claim"]
            validity = numeric_validity(kw["initial_rule"], kw["initial_checks"], inp["claim_period"], cl["as_of_date"], rec)
            fcf = fcf_direction_check(cl["claim"], cl["company"], cl["as_of_date"], inp["claim_period"])
            lab, why = apply_numeric_checks(preds["V22: +G1+G4+D-sup (post hoc)"][cid], kw["initial_rule"], validity, fcf,
                                            inp["findings_q11"], rec)
            preds["V22b: +G1+G4+D-sup+N1+N2"][cid] = lab
            if why or validity or fcf.get("status") not in (None, "NOT_APPLICABLE"):
                reasons.setdefault(cid, {})["numeric_checks"] = {"validity": validity, "fcf": {k: fcf.get(k) for k in ("status", "current", "prior", "change")},
                                                                  "reason": why}
        reasons[cid] = {**reasons.get(cid, {}), "0.1": d01["reason_code"], "0.2": d02["reason_code"], "0.3": d03["reason_code"], "0.3+Q1.1": d03q["reason_code"],
                        "G3_trace": [t for t in d02["rule_trace"] if t.startswith("G3")],
                        "G3b_trace": [t for t in d03["rule_trace"] if t.startswith("G3")],
                        "q11_restored": inp["restored_q11"], "numeric_ok": numeric_ok}
    return {"preds": preds, "reasons": reasons}, mismatches


def metrics(preds: dict, rows: list[dict], labels: dict) -> dict:
    ids = [r["claim_id"] for r in rows]
    y = [labels[c]["final_label"] for c in ids]
    types = {r["claim_id"]: r["claim_type"] for r in rows}
    a2 = [preds["A2"][c] for c in ids]
    out = {}
    for arm, p in preds.items():
        pv = [p[c] for c in ids]
        cm = classification_metrics(y, pv)
        right = [a == b for a, b in zip(pv, y)]
        a2_right = [a == b for a, b in zip(a2, y)]
        changed = [i for i in range(len(ids)) if pv[i] != a2[i]]
        acc_dec = [i for i in changed if pv[i] in DECISIVE]
        ins = [i for i in range(len(ids)) if y[i] == "INSUFFICIENT_EVIDENCE"]
        out[arm] = {
            "correct": sum(right), "accuracy": cm["accuracy"], "macro_f1": cm["macro_f1"],
            "insufficient_recall": ev.wilson(sum(right[i] for i in ins), len(ins)),
            "changed_vs_A2": len(changed),
            "accepted_decisive_change_precision": ev.wilson(sum(right[i] for i in acc_dec), len(acc_dec)),
            "correction_vs_A2": ev.wilson(sum(right[i] for i in range(len(ids)) if not a2_right[i]), sum(not x for x in a2_right)),
            "regression_vs_A2": ev.wilson(sum(not right[i] for i in range(len(ids)) if a2_right[i]), sum(a2_right)),
            "minus_A2": sum(right) - sum(a2_right),
            "minus_R": sum(right) - sum(preds["R"][c] == labels[c]["final_label"] for c in ids),
            "by_type": {t: f"{sum(right[i] for i in range(len(ids)) if types[ids[i]] == t)}/{sum(1 for c in ids if types[c] == t)}"
                        for t in ("numerical", "ambiguous", "interpretive")},
            "mcnemar_vs_RG-0.1": mcnemar(y, [preds["RG-0.1"][c] for c in ids], pv),
            "mcnemar_vs_A2": mcnemar(y, a2, pv),
            "differs_from_RG-0.1": [c for c in ids if p[c] != preds["RG-0.1"][c]],
        }
    return out


def render(m: dict, mismatches: list, labels_sha: str, n: int) -> str:
    pct = lambda x: "—" if x is None else f"{100 * x:.1f}%"  # noqa: E731
    L = ["# Offline guard / policy replay on A3 v2.1.1 dev-v0.2 traces", "", f"> **{BANNER}**", "",
         f"Labels sha256 {labels_sha[:12]}; {n} claims; guard 0.1 replay reproduced the recorded decision on "
         f"{n - len(mismatches)}/{n} claims. No LLM call.", "",
         "| Arm | Correct | Acc | Macro-F1 | INSUFF recall | Accepted decisive precision | Δ vs A2 | Δ vs R | McNemar p vs RG-0.1 | num / amb / int |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for arm, v in m.items():
        ir, ap = v["insufficient_recall"], v["accepted_decisive_change_precision"]
        bt = v["by_type"]
        L.append(f"| {arm} | {v['correct']}/{n} | {pct(v['accuracy'])} | {v['macro_f1']:.3f} | {ir['k']}/{ir['n']} | "
                 f"{ap['k']}/{ap['n']} ({pct(ap['rate'])}) | {v['minus_A2']:+d} | {v['minus_R']:+d} | "
                 f"{v['mcnemar_vs_RG-0.1']['p_value_exact']:.3f} | {bt['numerical']} / {bt['ambiguous']} / {bt['interpretive']} |")
    L += ["", "## Claims whose label differs from RG-0.1", ""]
    L += [f"- **{arm}**: {', '.join(v['differs_from_RG-0.1']) or 'none'}" for arm, v in m.items() if arm not in ("A2", "R", "RG-0.1")]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--decidability", help="classifier output jsonl (scripts/a3v2_decidability_run.py)")
    args = ap.parse_args(argv)
    decid = {json.loads(x)["claim_id"]: json.loads(x) for x in open(args.decidability)} if args.decidability else None
    rows = [json.loads(x) for x in open(CLAIMS_TABLE, encoding="utf-8")]
    labels, cov = ev.load_reference(args.labels, {r["claim_id"] for r in rows})
    res, mismatches = replay(rows, decid)
    if mismatches:
        raise SystemExit("guard 0.1 replay does not reproduce the recorded decisions; nothing written:\n  " + "\n  ".join(mismatches))
    m = metrics(res["preds"], rows, labels)
    d = os.path.join(args.out_dir, cov["labels_sha256"][:8] + f"_r{REPLAY_VERSION}")
    if os.path.exists(d):
        raise SystemExit(f"{d} exists; replays are not overwritten")
    os.makedirs(d)
    json.dump({"banner": BANNER, "decidability_file": args.decidability,
               "decidability_sha256": hashlib.sha256(open(args.decidability, "rb").read()).hexdigest() if args.decidability else None, "labels_sha256": cov["labels_sha256"], "claims_table_sha256": hashlib.sha256(open(CLAIMS_TABLE, "rb").read()).hexdigest(),
               "replay_reproduced": len(rows) - len(mismatches), "metrics": m, "predictions": res["preds"], "reasons": res["reasons"]},
              open(os.path.join(d, "replay.json"), "w"), indent=1, default=str)
    open(os.path.join(d, "replay.md"), "w").write(render(m, mismatches, cov["labels_sha256"], len(rows)))
    print(render(m, mismatches, cov["labels_sha256"], len(rows)))


if __name__ == "__main__":
    main()
