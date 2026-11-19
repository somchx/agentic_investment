"""POST-HOC EXPLORATORY: paired evidence-grounded correctness (EGC) of A2 vs A3v2_2e on the 50 sampled claims.

Reads the filled review workbook, the private mapping (review_id -> claim, arm; never written to the output),
the frozen Gold run predictions and the Gold reference, and cross-checks them. Judgments are used as entered;
nothing is re-judged. Output is claim-level only (no review_id), so the summary does not reveal the blind mapping.

    research/.venv/bin/python research/scripts/posthoc_paired_egc.py
"""
import hashlib
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import load_workbook  # noqa: E402

from engine import RESEARCH_ROOT  # noqa: E402
from engine.reference import load_reference  # noqa: E402
from engine.stats import mcnemar  # noqa: E402

REVIEW = os.path.join(RESEARCH_ROOT, "datasets", "workbooks", "evidence_review_blind.xlsx")
MAPPING = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "human_review", "mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx")
PRED = os.path.join(RESEARCH_ROOT, "results", "runs", "a3v2.2-gold150-20261118T112814Z", "predictions.jsonl")
EGC = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "human_review", "egc_result.json")
OUT = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "paired_egc")
A2, A3 = "A2_rag_numeric", "A3v2_2e"
SUP, PAR, NOT, UNA = "SUPPORTED_BY_EVIDENCE", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "UNABLE_TO_ASSESS"
RANK = {SUP: 2, PAR: 1, NOT: 0}
I = "INSUFFICIENT_EVIDENCE"


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def load() -> dict:
    ws = load_workbook(REVIEW, data_only=True)["review"]
    hd = [c.value for c in ws[1]]
    J = {r[0]: r[hd.index("judgment")] for r in ws.iter_rows(min_row=2, values_only=True) if r[0]}
    mp = load_workbook(MAPPING, data_only=True)["mapping"]
    mh = [c.value for c in mp[1]]
    M = {r[0]: dict(zip(mh, r)) for r in mp.iter_rows(min_row=2, values_only=True)}
    ref = {k: v["label"] for k, v in load_reference()["labels"].items()}
    P = {}
    for r in map(json.loads, open(PRED)):
        if r["approach"] in (A2, A3):
            P[(r["approach"], r["claim_id"])] = r["predicted_label"]
    rows = {}
    for rid, m in M.items():
        assert P[(m["arm"], m["claim_id"])] == m["predicted_label"], rid      # mapping agrees with frozen predictions
        assert ref[m["claim_id"]] == m["reference_label"], rid                # and with the frozen Gold reference
        rows.setdefault(m["claim_id"], {"category": m["claim_category"], "gold": ref[m["claim_id"]]})[m["arm"]] = {
            "pred": m["predicted_label"], "correct": m["predicted_label"] == ref[m["claim_id"]], "judgment": J[rid]}
    assert len(rows) == 50 and all(A2 in v and A3 in v for v in rows.values())
    return rows


def egc_counts(rows: dict, arm: str, lenient: bool) -> dict:
    ok = (SUP, PAR) if lenient else (SUP,)
    s = sum(1 for v in rows.values() if v[arm]["judgment"] != UNA and v[arm]["correct"] and v[arm]["judgment"] in ok)
    u = sum(1 for v in rows.values() if v[arm]["judgment"] == UNA)
    f = len(rows) - s - u
    assert s + f + u == len(rows)
    return {"success": s, "failure_assessed": f, "unable_to_assess": u, "assessable": s + f,
            "egc_rate_assessable": round(s / (s + f), 4), "observed_success_over_50": round(s / len(rows), 4),
            "bound_low_if_unable_all_fail": round(s / len(rows), 4), "bound_high_if_unable_all_success": round((s + u) / len(rows), 4)}


def support_among_correct(rows: dict, arm: str) -> dict:
    out = {}
    for name, keep in (("all_correct", lambda p: True), ("correct_decisive", lambda p: p != I), ("correct_insufficient", lambda p: p == I)):
        sel = [v[arm] for v in rows.values() if v[arm]["correct"] and keep(v[arm]["pred"])]
        c = Counter(x["judgment"] for x in sel)
        assessed = len(sel) - c[UNA]
        out[name] = {"n_correct": len(sel), "judgments": {k: c[k] for k in (SUP, PAR, NOT, UNA)}, "assessable": assessed,
                     "strict_support_rate": round(c[SUP] / assessed, 4) if assessed else None,
                     "lenient_support_rate": round((c[SUP] + c[PAR]) / assessed, 4) if assessed else None,
                     "correct_but_not_fully_supported": c[PAR] + c[NOT]}
    return out


def paired(rows: dict, lenient: bool) -> dict:
    ok = (SUP, PAR) if lenient else (SUP,)
    both = {c: v for c, v in rows.items() if v[A2]["judgment"] != UNA and v[A3]["judgment"] != UNA}
    succ = {c: (v[A2]["correct"] and v[A2]["judgment"] in ok, v[A3]["correct"] and v[A3]["judgment"] in ok) for c, v in both.items()}
    n11 = sum(a and b for a, b in succ.values())
    n10 = sum(a and not b for a, b in succ.values())
    n01 = sum(b and not a for a, b in succ.values())
    n00 = sum(not a and not b for a, b in succ.values())
    m = mcnemar([True] * len(succ), [a for a, _ in succ.values()], [b for _, b in succ.values()])
    disc = []
    for c in sorted(succ):
        a, b = succ[c]
        if a != b:
            v = rows[c]
            disc.append({"claim_id": c, "category": v["category"], "gold": v["gold"],
                         "A2": {"pred": v[A2]["pred"], "judgment": v[A2]["judgment"]},
                         "A3v2_2e": {"pred": v[A3]["pred"], "judgment": v[A3]["judgment"]},
                         "egc_success_by": "A2 only" if a else "A3v2_2e only"})
    return {"pairs_both_assessable": len(succ), "n11_both_success": n11, "n10_A2_only": n10, "n01_A3_only": n01,
            "n00_both_failure": n00, "A2_rate": round((n11 + n10) / len(succ), 4), "A3_rate": round((n11 + n01) / len(succ), 4),
            "paired_difference_A3_minus_A2": round((n01 - n10) / len(succ), 4),
            "exploratory_mcnemar_exact_p": round(m["p_value_exact"], 4), "discordant": disc}


def support_ordering(rows: dict) -> dict:
    both = [v for v in rows.values() if v[A2]["judgment"] != UNA and v[A3]["judgment"] != UNA]
    cmp = Counter("A3 better" if RANK[v[A3]["judgment"]] > RANK[v[A2]["judgment"]] else
                  "A3 worse" if RANK[v[A3]["judgment"]] < RANK[v[A2]["judgment"]] else "equal" for v in both)
    same_answer = Counter((v[A2]["pred"] == v[A3]["pred"]) for v in both)
    return {"pairs": len(both), "A3_better": cmp["A3 better"], "equal": cmp["equal"], "A3_worse": cmp["A3 worse"],
            "pairs_with_same_prediction": same_answer[True],
            "cross_table_A2_by_A3": {f"{a}|{b}": n for (a, b), n in sorted(Counter((v[A2]["judgment"], v[A3]["judgment"]) for v in both).items())}}


def missingness(rows: dict) -> dict:
    pat = lambda v: ("both_assessable" if v[A2]["judgment"] != UNA and v[A3]["judgment"] != UNA else
                     "A2_only_assessable" if v[A2]["judgment"] != UNA else
                     "A3_only_assessable" if v[A3]["judgment"] != UNA else "both_unable")
    by_cat = {}
    for v in rows.values():
        by_cat.setdefault(v["category"], Counter())[pat(v)] += 1
    vs_pred = {arm: {f"unable={u}|pred_insufficient={p}": n for (u, p), n in sorted(
        Counter((v[arm]["judgment"] == UNA, v[arm]["pred"] == I) for v in rows.values()).items())} for arm in (A2, A3)}
    unable_correct = {arm: Counter(v[arm]["correct"] for v in rows.values() if v[arm]["judgment"] == UNA) for arm in (A2, A3)}
    return {"patterns": dict(Counter(pat(v) for v in rows.values())), "by_category": {k: dict(c) for k, c in by_cat.items()},
            "unable_vs_insufficient_prediction": vs_pred,
            "unable_rows_label_correct": {arm: {"correct": c[True], "incorrect": c[False]} for arm, c in unable_correct.items()}}


def main() -> dict:
    os.makedirs(OUT, exist_ok=True)
    rows = load()
    old = json.load(open(EGC))
    res = {"status": "POST-HOC EXPLORATORY",
           "judgment_provenance": "HUMAN-ASSESSED: all 100 judgments by the researcher (rev_som), blind to arm and reference label; self-reported; single, non-independent assessor",
           "n_claims": len(rows),
           "egc_strict": {arm: egc_counts(rows, arm, False) for arm in (A2, A3)},
           "egc_lenient": {arm: egc_counts(rows, arm, True) for arm in (A2, A3)},
           "support_among_correct": {arm: support_among_correct(rows, arm) for arm in (A2, A3)},
           "paired_strict": paired(rows, False), "paired_lenient": paired(rows, True),
           "support_ordering": support_ordering(rows), "missingness": missingness(rows),
           "category_counts": dict(Counter(v["category"] for v in rows.values()))}
    for arm in (A2, A3):   # consistency with the committed egc_result.json
        assert res["egc_strict"][arm]["success"] == old[arm]["EGC_strict"] and res["egc_strict"][arm]["assessable"] == old[arm]["assessed"]
        assert res["egc_lenient"][arm]["success"] == old[arm]["EGC_lenient"]
    out = os.path.join(OUT, "paired_egc_summary.json")
    res["inputs_sha256"] = {os.path.relpath(p, RESEARCH_ROOT): sha(p) for p in (REVIEW, MAPPING, PRED, EGC)}
    res["script_sha256"] = sha(__file__)
    json.dump(res, open(out, "w"), indent=1, ensure_ascii=False)
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in r if k not in ("inputs_sha256",)}, indent=1, ensure_ascii=False))
