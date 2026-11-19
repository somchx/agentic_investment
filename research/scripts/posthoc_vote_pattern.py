"""POST-HOC EXPLORATORY: accuracy of every Gold 150 arm by the annotator vote pattern (advisor question, 2026-11-16).

The vote pattern is the three initial LLM annotations (Claude Opus 5.5 | Gemini 4 Argon | GPT-6.0 Astra) recorded
in the Gold workbook before adjudication; it is not the gold label. Reads the frozen predictions and the frozen
reference only; nothing is re-run or re-labelled. No API call.

    research/.venv/bin/python research/scripts/posthoc_vote_pattern.py
"""
import hashlib
import json
import math
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.reference import REFERENCE_PATH, load_reference  # noqa: E402
from engine.stats import mcnemar  # noqa: E402

PRED = os.path.join(RESEARCH_ROOT, "results", "runs", "a3v2.2-gold150-20261118T112814Z", "predictions.jsonl")
V1_PRED = os.path.join(RESEARCH_ROOT, "results", "runs", "claimverif-main-v1-20261110T104207Z", "predictions.jsonl")  # same as the evaluator's V1_RUN
OUT = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "vote_pattern")
ARMS = ["A1_conventional_rag", "A2_rag_numeric", "SR_self_reflection", "V1:A3_contradiction_aware", "A3v2_1_1_R", "A3v2_1_1_RG", "A3v2_2e"]
A2, A3 = "A2_rag_numeric", "A3v2_2e"
GROUPS = ["unanimous", "majority_2_1", "three_way_split"]


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def wilson(k: int, n: int, z: float = 1.959964) -> list:
    if not n:
        return [None, None]
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def classify(gold: dict) -> dict:
    votes = [v.strip() for v in gold["vote_pattern"].split("|")]
    assert len(votes) == 3, gold["vote_pattern"]
    top, n = Counter(votes).most_common(1)[0]
    group = {3: "unanimous", 2: "majority_2_1", 1: "three_way_split"}[n]
    return {"votes": votes, "group": group, "majority": top if n >= 2 else None,
            "gold_vs_majority": None if n == 1 else ("gold_is_majority" if gold["label"] == top else "gold_overturned_majority")}


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": round(k / n, 4) if n else None, "wilson_95": wilson(k, n)}


def main() -> dict:
    os.makedirs(OUT, exist_ok=True)
    ref = load_reference()["labels"]
    meta = {c: {**classify(g), "gold": g["label"], "category": g["claim_category"]} for c, g in ref.items()}
    P = {}
    for r in map(json.loads, open(PRED)):
        if r["approach"] in ARMS:
            P.setdefault(r["approach"], {})[r["claim_id"]] = r["predicted_label"]
    for r in map(json.loads, open(V1_PRED)):
        if r["approach"] == "A3_contradiction_aware" and r["claim_id"] in meta:
            P.setdefault("V1:A3_contradiction_aware", {})[r["claim_id"]] = r["predicted_label"]
    assert all(set(P[a]) == set(meta) for a in ARMS)
    ok = {a: {c: P[a][c] == meta[c]["gold"] for c in meta} for a in ARMS}

    def acc(arm: str, keep) -> dict:
        ids = [c for c in meta if keep(meta[c])]
        return rate(sum(ok[arm][c] for c in ids), len(ids))

    res = {"status": "POST-HOC EXPLORATORY",
           "vote_pattern_source": "three initial LLM annotations (Claude Opus 5.5 | Gemini 4 Argon | GPT-6.0 Astra), before AI-assisted adjudication and researcher review; not the gold label",
           "n_claims": len(meta),
           "group_counts": dict(Counter(m["group"] for m in meta.values())),
           "group_by_category": {g: dict(Counter(m["category"] for m in meta.values() if m["group"] == g)) for g in GROUPS},
           "gold_vs_majority_in_2_1": dict(Counter(m["gold_vs_majority"] for m in meta.values() if m["group"] == "majority_2_1")),
           "accuracy_by_group": {a: {g: acc(a, lambda m, g=g: m["group"] == g) for g in GROUPS} for a in ARMS},
           "accuracy_split_combined": {a: acc(a, lambda m: m["group"] != "unanimous") for a in ARMS},
           "accuracy_by_gold_vs_annotator_majority_incl_unanimous": {a: {k: acc(a, lambda m, k=k: m["gold_vs_majority"] == k)
                                                    for k in ("gold_is_majority", "gold_overturned_majority")} for a in ARMS},
           "accuracy_by_group_and_category": {a: {g: {cat: acc(a, lambda m, g=g, cat=cat: m["group"] == g and m["category"] == cat)
                                                     for cat in ("numerical", "interpretive", "ambiguous")} for g in GROUPS} for a in (A2, A3)},
           # a wrong answer that at least one annotator also gave: a defensible reading, not an arbitrary error
           "wrong_but_matches_some_annotator": {a: {g: rate(sum(P[a][c] in meta[c]["votes"] for c in meta if meta[c]["group"] == g and not ok[a][c]),
                                                            sum(1 for c in meta if meta[c]["group"] == g and not ok[a][c])) for g in GROUPS} for a in ARMS},
           "paired_A2_vs_A3v2_2e": {}}
    for g in GROUPS + ["not_unanimous"]:
        ids = sorted(c for c in meta if (meta[c]["group"] != "unanimous" if g == "not_unanimous" else meta[c]["group"] == g))
        m = mcnemar([meta[c]["gold"] for c in ids], [P[A2][c] for c in ids], [P[A3][c] for c in ids])
        res["paired_A2_vs_A3v2_2e"][g] = {"n": len(ids), "A2_right_A3_wrong": m["a_right_b_wrong"], "A3_right_A2_wrong": m["b_right_a_wrong"],
                                          "both_right": m["both_right"], "exploratory_mcnemar_exact_p": round(m["p_value_exact"], 4),
                                          "discordant": [{"claim_id": c, "category": meta[c]["category"], "votes": " | ".join(meta[c]["votes"]),
                                                          "gold": meta[c]["gold"], "A2": P[A2][c], "A3v2_2e": P[A3][c]}
                                                         for c in ids if ok[A2][c] != ok[A3][c]]}
    res["inputs_sha256"] = {os.path.relpath(p, RESEARCH_ROOT): sha(p) for p in (PRED, V1_PRED, REFERENCE_PATH)}
    res["script_sha256"] = sha(__file__)
    json.dump(res, open(os.path.join(OUT, "vote_pattern_summary.json"), "w"), indent=1, ensure_ascii=False)
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("group_counts", "group_by_category", "gold_vs_majority_in_2_1")}, ensure_ascii=False))
    for a in ARMS:
        print(a, {g: f'{v["k"]}/{v["n"]}' for g, v in r["accuracy_by_group"][a].items()}, "split:", f'{r["accuracy_split_combined"][a]["k"]}/{r["accuracy_split_combined"][a]["n"]}',
              "wrong~annot:", {g: f'{v["k"]}/{v["n"]}' for g, v in r["wrong_but_matches_some_annotator"][a].items()})
    for g, v in r["paired_A2_vs_A3v2_2e"].items():
        print(g, {k: v[k] for k in v if k != "discordant"})
    print(json.dumps(r["accuracy_by_group_and_category"], ensure_ascii=False))
