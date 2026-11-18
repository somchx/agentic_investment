"""Paired evaluation of A2, A3v2.1.1_R and A3v2.1.1_RG on dev-v0.2, run only
against APPROVED reference labels (after second annotation and adjudication).

    research/.venv/bin/python research/scripts/a3v2_dev_evaluate.py \
        --labels datasets/annotations_dev/dev-v0.2_reference_labels.approved.jsonl

Reference-label file: one JSON object per claim
    {"claim_id", "final_label", "label_status": "AGREED" | "ADJUDICATED",
     "approved_by", "approved_at", "source"}
Reviewer files (rev_*.jsonl) and design intent are refused: they are not
reference labels. Every dev-v0.2 claim must have an approved label unless
--allow-partial is given (then coverage is reported first and every result is
marked PARTIAL).

Metrics: accuracy and macro-F1 with bootstrap CIs; accuracy by claim type;
McNemar (exact) + paired bootstrap for A2 vs R, A2 vs RG, R vs RG; correction
and regression rates against A2 with Wilson CIs; guard helpful / harmful
decisions (overall and by reason code); vote patterns (agreement of A2, R and
RG, optionally an external pattern file) with Fisher exact tests. Writes
results/dev_v0_2/evaluation_<labels sha8>/ and never overwrites it.
"""
import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.metrics import classification_metrics  # noqa: E402
from engine.schema import LABELS  # noqa: E402
from engine.stats import bootstrap_ci, bootstrap_diff, mcnemar  # noqa: E402

CLAIMS_FILE = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2")
ARMS = {"A2": "pred_A2", "R": "pred_R", "RG": "pred_RG"}
APPROVED = ("AGREED", "ADJUDICATED")
REPORT_VERSION = "1.1"  # 1.1: guard effect split into RG−R and RG−A2 (1.0 reported their sum as net_helpful)
TYPES = ("ambiguous", "interpretive", "numerical")


class NotApproved(ValueError):
    pass


# ---------------------------------------------------------------- inputs

def load_reference(path: str, claim_ids: set[str], allow_partial: bool = False) -> tuple[dict, dict]:
    name = os.path.basename(path)
    if name.startswith("rev_") or "design_intent" in name or "llm_annotations" in path:
        raise NotApproved(f"{name} is a reviewer / design-intent / LLM file, not an approved reference-label file")
    labels, problems = {}, []
    for i, line in enumerate(open(path, encoding="utf-8"), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        cid = r.get("claim_id")
        if r.get("final_label") not in LABELS:
            problems.append(f"line {i} {cid}: final_label {r.get('final_label')!r}")
        elif r.get("label_status") not in APPROVED:
            problems.append(f"line {i} {cid}: label_status {r.get('label_status')!r} is not approved")
        elif not r.get("approved_by") or not r.get("approved_at"):
            problems.append(f"line {i} {cid}: approved_by / approved_at missing")
        elif cid in labels:
            problems.append(f"line {i} {cid}: duplicate")
        elif cid not in claim_ids:
            problems.append(f"line {i} {cid}: not a dev-v0.2 claim")
        else:
            labels[cid] = r
    if problems:
        raise NotApproved("reference labels refused:\n  " + "\n  ".join(problems))
    missing = sorted(claim_ids - set(labels))
    if missing and not allow_partial:
        raise NotApproved(f"{len(missing)} claims have no approved label (e.g. {missing[:5]}); finish adjudication or pass --allow-partial")
    cov = {"labelled": len(labels), "total": len(claim_ids), "missing": missing, "partial": bool(missing),
           "labels_sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
           "label_status": dict(Counter(r["label_status"] for r in labels.values()))}
    return labels, cov


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int, z: float = 1.959964) -> dict:
    if n == 0:
        return {"k": 0, "n": 0, "rate": None, "ci_low": None, "ci_high": None}
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "rate": p, "ci_low": max(0.0, c - h), "ci_high": min(1.0, c + h)}


def fisher_exact(a: int, b: int, c: int, d: int) -> dict:
    """Two-sided Fisher exact test of [[a, b], [c, d]] (sum of tables no more likely than the observed)."""
    r1, c1, n = a + b, a + c, a + b + c + d

    def pr(x):
        return math.comb(r1, x) * math.comb(n - r1, c1 - x) / math.comb(n, c1)
    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    p_obs = pr(a)
    p = sum(pr(x) for x in range(lo, hi + 1) if pr(x) <= p_obs * (1 + 1e-9))
    odds = ((a + .5) * (d + .5)) / ((b + .5) * (c + .5))
    return {"table": [[a, b], [c, d]], "p_value": min(1.0, p), "odds_ratio_haldane": odds}


# ---------------------------------------------------------------- metrics

def evaluate(rows: list[dict], labels: dict, n_boot: int = 5000, seed: int = 20261118, votes: dict | None = None) -> dict:
    rows = [r for r in rows if r["claim_id"] in labels]
    y = [labels[r["claim_id"]]["final_label"] for r in rows]
    pred = {a: [r[c] for r in rows] for a, c in ARMS.items()}
    right = {a: [p == t for p, t in zip(pred[a], y)] for a in ARMS}
    out = {"n": len(rows)}
    out["overall"] = {a: {**{k: classification_metrics(y, pred[a])[k] for k in ("accuracy", "macro_f1", "confusion_matrix")},
                          "ci": bootstrap_ci(y, pred[a], n_boot=n_boot, seed=seed)} for a in ARMS}
    out["by_claim_type"] = {}
    for t in TYPES:
        idx = [i for i, r in enumerate(rows) if r["claim_type"] == t]
        yt = [y[i] for i in idx]
        out["by_claim_type"][t] = {"n": len(idx), **{a: {"accuracy": classification_metrics(yt, [pred[a][i] for i in idx])["accuracy"] if idx else None,
                                                         **({"ci": bootstrap_ci(yt, [pred[a][i] for i in idx], n_boot=n_boot, seed=seed)["accuracy"]} if idx else {})}
                                                     for a in ARMS}}
    out["paired"] = {f"{a}_vs_{b}": {"mcnemar": mcnemar(y, pred[a], pred[b]),
                                     "bootstrap": bootstrap_diff(y, pred[a], pred[b], n_boot=n_boot, seed=seed)}
                     for a, b in (("A2", "R"), ("A2", "RG"), ("R", "RG"))}
    # corrections / regressions against A2
    a2_wrong = [i for i in range(len(rows)) if not right["A2"][i]]
    a2_right = [i for i in range(len(rows)) if right["A2"][i]]
    out["vs_A2"] = {a: {"correction": wilson(sum(right[a][i] for i in a2_wrong), len(a2_wrong)),
                        "regression": wilson(sum(not right[a][i] for i in a2_right), len(a2_right)),
                        "changed": sum(pred[a][i] != pred["A2"][i] for i in range(len(rows)))} for a in ("R", "RG")}
    # guard decisions on the claims where R moved away from A2
    g, by_reason = Counter(), defaultdict(Counter)
    for i, r in enumerate(rows):
        if pred["R"][i] == pred["A2"][i]:
            continue
        kept_a2 = pred["RG"][i] == pred["A2"][i]
        if kept_a2:
            kind = "helpful_block" if right["A2"][i] and not right["R"][i] else ("harmful_block" if right["R"][i] and not right["A2"][i] else "neutral_block")
        else:
            kind = "helpful_accept" if right["R"][i] and not right["A2"][i] else ("harmful_accept" if right["A2"][i] and not right["R"][i] else "neutral_accept")
        g[kind] += 1
        by_reason[r["guard_reason"]][kind] += 1
    # two different baselines, reported separately (report 1.1): blocks are RG vs R, accepts are RG vs A2
    out["guard"] = {"r_changes": sum(g.values()), "decisions": dict(g), "by_reason_code": {k: dict(v) for k, v in by_reason.items()},
                    "rg_minus_r": g["helpful_block"] - g["harmful_block"],
                    "rg_minus_a2": g["helpful_accept"] - g["harmful_accept"],
                    "accepted_change_precision": wilson(g["helpful_accept"], g["helpful_accept"] + g["harmful_accept"] + g["neutral_accept"]),
                    "net_helpful_legacy": g["helpful_block"] + g["helpful_accept"] - g["harmful_block"] - g["harmful_accept"]}
    out["vote_patterns"] = vote_patterns(rows, right, votes)
    return out


def pattern_of(r: dict) -> str:
    a2, rr, rg = r["pred_A2"], r["pred_R"], r["pred_RG"]
    if a2 == rr == rg:
        return "UNANIMOUS"
    if a2 == rg != rr:
        return "RG_KEPT_A2"
    if rr == rg != a2:
        return "RG_FOLLOWED_R"
    if a2 == rr != rg:
        return "RG_ONLY_DIFFERS"
    return "ALL_DIFFER"


def vote_patterns(rows: list[dict], right: dict, external: dict | None = None) -> dict:
    out = {}
    for name, key in (("approach_agreement", pattern_of), *((("external", lambda r: external.get(r["claim_id"], "NONE")),) if external else ())):
        groups = defaultdict(list)
        for i, r in enumerate(rows):
            groups[key(r)].append(i)
        out[name] = {p: {"n": len(ix), **{a: wilson(sum(right[a][i] for i in ix), len(ix)) for a in ARMS}} for p, ix in sorted(groups.items())}
    # does RG correctness depend on whether the three approaches agree?
    una = [i for i, r in enumerate(rows) if pattern_of(r) == "UNANIMOUS"]
    split = [i for i, r in enumerate(rows) if pattern_of(r) != "UNANIMOUS"]
    out["rg_correct_by_unanimity"] = fisher_exact(sum(right["RG"][i] for i in una), sum(not right["RG"][i] for i in una),
                                                  sum(right["RG"][i] for i in split), sum(not right["RG"][i] for i in split))
    return out


# ---------------------------------------------------------------- report

def render(res: dict, cov: dict) -> str:
    pct = lambda x: "—" if x is None else f"{100 * x:.1f}%"
    tag = " (PARTIAL: not all claims have approved labels)" if cov["partial"] else ""
    L = [f"# A3 v2.1.1 dev-v0.2 evaluation{tag}", "",
         f"Labels: {cov['labelled']}/{cov['total']} approved ({cov['label_status']}), sha256 {cov['labels_sha256'][:12]}", "",
         "| Approach | Accuracy | 95% CI | Macro-F1 |", "|---|---|---|---|"]
    for a, m in res["overall"].items():
        L.append(f"| {a} | {pct(m['accuracy'])} | {pct(m['ci']['accuracy']['ci_low'])}–{pct(m['ci']['accuracy']['ci_high'])} | {m['macro_f1']:.3f} |")
    L += ["", "| Claim type | n | A2 | R | RG |", "|---|---|---|---|---|"]
    for t, m in res["by_claim_type"].items():
        L.append(f"| {t} | {m['n']} | " + " | ".join(pct(m[a]["accuracy"]) for a in ARMS) + " |")
    L += ["", "| Pair | Acc diff (2nd − 1st) | 95% CI | McNemar exact p | discordant |", "|---|---|---|---|---|"]
    for k, v in res["paired"].items():
        b = v["bootstrap"]["accuracy"]
        L.append(f"| {k} | {pct(b['diff_b_minus_a'])} | {pct(b['ci_low'])}–{pct(b['ci_high'])} | {v['mcnemar']['p_value_exact']:.3f} | {v['mcnemar']['discordant']} |")
    L += ["", "| vs A2 | Correction (A2 wrong → right) | Regression (A2 right → wrong) | Changed |", "|---|---|---|---|"]
    for a, v in res["vs_A2"].items():
        L.append(f"| {a} | {v['correction']['k']}/{v['correction']['n']} ({pct(v['correction']['rate'])}) | "
                 f"{v['regression']['k']}/{v['regression']['n']} ({pct(v['regression']['rate'])}) | {v['changed']} |")
    g = res["guard"]
    ap = g["accepted_change_precision"]
    L += ["", f"Guard on {g['r_changes']} R changes: {g['decisions']}",
          f"- RG − R (blocks: helpful − harmful): {g['rg_minus_r']:+d} claims",
          f"- RG − A2 (accepts: helpful − harmful): {g['rg_minus_a2']:+d} claims",
          f"- Accepted-change precision: {ap['k']}/{ap['n']} ({pct(ap['rate'])})",
          f"- (legacy sum of both, not a single comparison: {g['net_helpful_legacy']:+d})", "",
          f"RG correct vs unanimity (Fisher exact): {res['vote_patterns']['rg_correct_by_unanimity']}"]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--claims", default=CLAIMS_FILE)
    ap.add_argument("--allow-partial", action="store_true")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--votes", help="optional jsonl {claim_id, pattern}: an external grouping (e.g. label agreement status)")
    args = ap.parse_args(argv)
    if not os.path.exists(args.labels):
        raise SystemExit(f"{args.labels}: no approved reference-label file yet. Finish second annotation and adjudication "
                         "(results/dev_v0_2/label_status.md), then write the approved file; nothing is scored before that.")
    import importlib.util
    spec = importlib.util.spec_from_file_location("hw", os.path.join(os.path.dirname(__file__), "dev_v0_2_human_workflow.py"))
    hw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hw)
    probs = hw.validate(args.labels)  # every approved label must trace to human sources (manifest written by `approve`)
    if probs:
        raise SystemExit("reference labels refused (provenance):\n  " + "\n  ".join(probs))
    rows = [json.loads(x) for x in open(args.claims, encoding="utf-8")]
    try:
        labels, cov = load_reference(args.labels, {r["claim_id"] for r in rows}, args.allow_partial)
    except NotApproved as e:
        raise SystemExit(str(e))
    votes = {json.loads(x)["claim_id"]: json.loads(x)["pattern"] for x in open(args.votes)} if args.votes else None
    res = evaluate(rows, labels, n_boot=args.n_boot, votes=votes)
    d = os.path.join(args.out_dir, f"evaluation_{cov['labels_sha256'][:8]}_r{REPORT_VERSION}{'_PARTIAL' if cov['partial'] else ''}")
    if os.path.exists(d):
        raise SystemExit(f"{d} exists; an evaluation is not overwritten")
    os.makedirs(d)
    json.dump({"report_version": REPORT_VERSION, "coverage": cov, "claims_file": os.path.relpath(args.claims, RESEARCH_ROOT),
               "claims_sha256": hashlib.sha256(open(args.claims, "rb").read()).hexdigest(), "results": res},
              open(os.path.join(d, "evaluation.json"), "w"), indent=1, default=str)
    open(os.path.join(d, "evaluation.md"), "w").write(render(res, cov))
    print(f"wrote {d}")


if __name__ == "__main__":
    main()
