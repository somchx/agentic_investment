"""POST-HOC EXPLORATORY: rule-based baseline (no LLM) and majority-class baseline.

Rule set RB-1.0. A claim is parsed with regular expressions into at most one numeric assertion of
engine.numeric (metric, measure, basis, comparison, threshold, period) and checked against SEC XBRL facts
filed on or before the claim's as_of_date with the existing deterministic verifier. Inputs are the claim
text, company, reporting_period and as_of_date only; reference labels are never read by `run`.

Rules (fixed before the Gold run; see LOCK.json):
  R1 metric    the metric phrase must follow the company's possessive ("Apple's total net sales") or the word
               "total"/"consolidated"; anything else (segment, product, region: "iPhone sales", "Data Center
               revenue") is out of scope -> no assertion
  R2 measure   "% year over year / grew N% / increased by more than N%" -> yoy_growth;
               "exceeded / above / below / more than / less than N% (margin) or $N billion" -> level;
               "increased / grew / rose / higher / improved / expanded ... (year over year | than a year earlier)"
               and "decreased / declined / fell / lower" -> yoy direction
  R3 period    a date in the claim wins; else FY label -> latest 10-K report date in that year
               (a3v2.checks.claim_period); else "quarter" -> latest reported quarter at the cutoff;
               balance-sheet metrics -> instant; year-to-date / half-year / multi-period wording -> out of scope
  R4 FCF       "free cash flow" level vs a $ threshold = OperatingCashFlow - CapitalExpenditure (same period)
  R5 decision  no parsable assertion -> INSUFFICIENT_EVIDENCE; check FALSE -> CONTRADICTED;
               check TRUE and the claim has no causal / evaluative wording -> SUPPORTED;
               check TRUE with such wording, or UNVERIFIABLE -> INSUFFICIENT_EVIDENCE
  Majority     SUPPORTED for every claim

    research/.venv/bin/python research/scripts/posthoc_rule_baseline.py run --split dev
    research/.venv/bin/python research/scripts/posthoc_rule_baseline.py lock
    research/.venv/bin/python research/scripts/posthoc_rule_baseline.py run --split gold     # once, after lock
    research/.venv/bin/python research/scripts/posthoc_rule_baseline.py score --split gold
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.corpus import eligible_filings  # noqa: E402
from engine.datasets import load_claims  # noqa: E402
from engine.numeric import EvidenceLedger, verify_assertion  # noqa: E402
from a3v2.checks import claim_period  # noqa: E402

VERSION = "RB-1.0"
OUT = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "rule_baseline")
LOCK = os.path.join(OUT, "LOCK.json")
SPLITS = {"dev": "datasets/development_cases_dev-v0.2.jsonl", "gold": "datasets/gold_claims.jsonl"}
DEV_LABELS = "datasets/annotations_dev/dev-v0.2_reference_labels.v2.approved.jsonl"
S, C, I = "SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"

METRICS = [  # longest phrases first
    (r"total net sales|net sales|total revenues?|net revenues?|revenues?|total sales and revenues|sales and revenues", "Revenue"),
    (r"operating margin", "OperatingMargin"), (r"gross margin percentage|gross margin", "GrossMargin"),
    (r"net (?:profit )?margin", "NetMargin"), (r"operating income", "OperatingIncome"), (r"net income", "NetIncome"),
    (r"gross profit", "GrossProfit"),
    (r"operating cash flows?|cash (?:flows? )?(?:provided by|generated (?:by|from)) operating activities|cash from operations", "OperatingCashFlow"),
    (r"capital expenditures?|capex", "CapitalExpenditure"), (r"long-term debt|term debt", "LongTermDebt"),
    (r"cash and cash equivalents", "CashAndEquivalents"), (r"free cash flow", "FCF"),
]
INSTANT = {"LongTermDebt", "CashAndEquivalents"}
RATIO = {"OperatingMargin", "GrossMargin", "NetMargin"}
OUT_OF_SCOPE = re.compile(r"year[- ]to[- ]date|through the end of|first half|second half|first nine months|nine months|six months|"
                          r"trailing|cumulative|combined|together|per share|\beps\b|segment|non-gaap|adjusted", re.I)
QUALITATIVE = re.compile(r"driven|due to|because|primarily|mainly|largely|main reason|reflect|despite|offset|led by|"
                         r"attribut|result of|thanks to|strong|solid|robust|healthy|resilien|significant|material|"
                         r"well positioned|affected|impact|pressure|benefit|efficien|headwind|tailwind|sustain|"
                         r"rather than|instead of|while|whereas|alongside|even as|outpac|faster than|slower than|"
                         r"used to|in order to|to fund|to finance|purpose|so that", re.I)
UP = r"increas\w*|grew|grow\w*|rose|ris\w*|higher|improv\w*|expand\w*|up"
DOWN = r"decreas\w*|declin\w*|fell|fall\w*|lower|contract\w*|shrank|down"
PCT = r"(\d+(?:\.\d+)?)\s?%"
USD = r"\$\s?(\d+(?:\.\d+)?)\s?(billion|million)"


def sha256(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def find_metric(text: str, company_names: list[str]) -> tuple[str | None, str | None]:
    t = text.lower()
    for pat, metric in METRICS:
        for m in re.finditer(rf"\b({pat})\b", t):
            before = t[:m.start()].rstrip()
            if re.search(r"(?:'s|’s)$", before) or re.search(r"\b(?:total|consolidated)$", before) or \
                    any(before.endswith(n.lower()) for n in company_names):
                return metric, m.group(1)
            if re.search(r"(?:'s|’s)\s+(?:total |consolidated |quarterly |annual )?$", before + " "):
                return metric, m.group(1)
    return None, None


def parse(claim) -> dict:
    """claim -> {"assertion": dict | None, "why": str} (no reference label involved)."""
    text = claim.claim
    if OUT_OF_SCOPE.search(text):
        return {"assertion": None, "why": "OUT_OF_SCOPE_WORDING"}
    metric, phrase = find_metric(text, [claim.company])
    if metric is None:
        return {"assertion": None, "why": "NO_COMPANY_LEVEL_METRIC"}
    t = text.lower()
    a = {"metric": metric, "threshold": None, "stated_value": None}
    yoy = re.search(r"year[- ]over[- ]year|than a year (?:earlier|ago|before)|from (?:a|the) year|compared (?:with|to) (?:the )?(?:prior|previous|fiscal|same)|prior[- ]year", t)
    pct = re.search(PCT, t)
    usd = re.search(USD, t)
    grow_pct = re.search(rf"(?:{UP}|{DOWN})\w*(?: by)?(?: (more|less) than| at least| over| about| approximately| roughly)? {PCT}", t)
    if grow_pct and metric not in RATIO:
        dirn = -1 if re.match(DOWN, grow_pct.group(0)) else 1
        q, v = grow_pct.group(1), float(grow_pct.group(2)) / 100 * dirn
        a["measure"] = "yoy_growth"
        if q == "more" or " over" in grow_pct.group(0):
            a["comparison"] = ">" if dirn > 0 else "<"
        elif q == "less":
            a["comparison"] = "<" if dirn > 0 else ">"
        elif "at least" in grow_pct.group(0):
            a["comparison"] = ">=" if dirn > 0 else "<="
        else:
            a["comparison"], a["stated_value"] = "approximately", v
        if a["comparison"] != "approximately":
            a["threshold"] = v
    elif re.search(r"exceed\w*|above|more than|greater than|over|at least|below|under|less than", t) and (pct or usd):
        comp_word = re.search(r"exceed\w*|above|more than|greater than|over|at least|below|under|less than", t).group(0)
        a["measure"] = "level"
        a["comparison"] = ">=" if comp_word == "at least" else "<" if comp_word in ("below", "under", "less than") else ">"
        if metric in RATIO:
            if not pct:
                return {"assertion": None, "why": "RATIO_WITHOUT_PERCENT"}
            a["threshold"] = float(pct.group(1)) / 100
        else:
            if not usd:
                return {"assertion": None, "why": "AMOUNT_WITHOUT_USD"}
            a["threshold"] = float(usd.group(1)) * (1e9 if usd.group(2) == "billion" else 1e6)
    elif re.search(rf"\b(?:{UP})\b", t) and (yoy or metric in INSTANT or re.search(r"\bthan\b", t)):
        a["measure"], a["comparison"] = "level", "increase"
    elif re.search(rf"\b(?:{DOWN})\b", t) and (yoy or metric in INSTANT or re.search(r"\bthan\b", t)):
        a["measure"], a["comparison"] = "level", "decrease"
    else:
        return {"assertion": None, "why": "NO_COMPARISON"}
    if metric in RATIO and a["measure"] == "yoy_growth":
        return {"assertion": None, "why": "MARGIN_GROWTH_PERCENT_AMBIGUOUS"}
    return {"assertion": a, "why": "PARSED"}


def resolve_period(claim, a: dict) -> tuple[str | None, str | None]:
    """(basis, period_end) per R3."""
    if a["metric"] in INSTANT:
        filings = eligible_filings(claim.company, claim.as_of_date, {"10-K", "10-Q"})
        return "instant", claim_period(claim, filings)["period_end"]
    t = claim.claim.lower()
    filings = eligible_filings(claim.company, claim.as_of_date, {"10-K", "10-Q"})
    p = claim_period(claim, filings)
    quarterly = re.search(r"quarter|three months|\bq[1-4]\b", t) is not None
    if p["source"] == "stated_date":
        return ("quarter" if quarterly else "annual"), p["period_end"]
    if quarterly or re.search(r"\bQ[1-4]\b", claim.reporting_period or ""):
        return "quarter", None
    if p["source"] == "fiscal_year_10k":
        return "annual", p["period_end"]
    m = re.fullmatch(r"(\d{4})", (claim.reporting_period or "").strip())
    if m:
        tenk = [f for f in filings if f.get("form", "").startswith("10-K") and (f.get("report_date") or "")[:4] == m.group(1)]
        if tenk:
            return "annual", max(f["report_date"] for f in tenk)
    return None, None


def check(claim, a: dict) -> dict:
    basis, end = resolve_period(claim, a)
    if basis is None:
        return {"status": "UNVERIFIABLE", "issues": ["PERIOD_UNRESOLVED"], "basis": None, "period_end": None}
    ledger = EvidenceLedger()
    if a["metric"] == "FCF":
        if a["measure"] != "level" or a["comparison"] not in (">", ">=", "<", "<="):
            return {"status": "UNVERIFIABLE", "issues": ["FCF_ONLY_LEVEL_THRESHOLD"], "basis": basis, "period_end": end}
        parts = {}
        for m in ("OperatingCashFlow", "CapitalExpenditure"):
            r = verify_assertion(claim.company, claim.as_of_date, {"metric": m, "measure": "level", "period_basis": basis,
                                 "period_end": end, "comparison": ">", "threshold": 0}, ledger)
            if not r["computed"]:
                return {"status": "UNVERIFIABLE", "issues": [f"FCF_PART_MISSING:{m}"] + r["issues"], "basis": basis, "period_end": end}
            parts[m] = r["computed"]["level"]
        fcf = parts["OperatingCashFlow"] - parts["CapitalExpenditure"]
        th = a["threshold"]
        ok = {">": fcf > th, ">=": fcf >= th, "<": fcf < th, "<=": fcf <= th}[a["comparison"]]
        return {"status": "TRUE" if ok else "FALSE", "issues": [], "basis": basis, "period_end": end, "computed": {"fcf": fcf, **parts}}
    r = verify_assertion(claim.company, claim.as_of_date, {**a, "period_basis": basis, "period_end": end}, ledger)
    return {"status": r["status"], "issues": r["issues"], "basis": basis, "period_end": end,
            "computed": {k: r["computed"].get(k) for k in ("period_end", "level", "prior_level", "yoy_change")} if r["computed"] else None}


def decide(claim) -> dict:
    p = parse(claim)
    row = {"claim_id": claim.claim_id, "approach": "RB_rule_based", "rule_version": VERSION, "parse": p}
    if p["assertion"] is None:
        return {**row, "predicted_label": I, "rule": "R5_NO_ASSERTION"}
    c = check(claim, p["assertion"])
    row["check"] = c
    qualitative = bool(QUALITATIVE.search(claim.claim))
    if c["status"] == "FALSE":
        return {**row, "predicted_label": C, "rule": "R5_NUMERIC_FALSE"}
    if c["status"] == "TRUE" and not qualitative:
        return {**row, "predicted_label": S, "rule": "R5_NUMERIC_TRUE"}
    return {**row, "predicted_label": I, "rule": "R5_TRUE_BUT_QUALITATIVE" if c["status"] == "TRUE" else "R5_UNVERIFIABLE"}


def run(split: str) -> str:
    out = os.path.join(OUT, f"predictions_{split}.jsonl")
    if split == "gold":
        if not os.path.exists(LOCK):
            raise SystemExit("rules are not locked; run `lock` first")
        lock = json.load(open(LOCK))
        if lock["script_sha256"] != sha256(__file__):
            raise SystemExit("script changed after lock; the Gold run is refused")
        if os.path.exists(out):
            raise SystemExit(f"{out} exists; the Gold run is one-time")
    os.makedirs(OUT, exist_ok=True)
    claims = load_claims(os.path.join(RESEARCH_ROOT, SPLITS[split]))
    with open(out, "w") as f:
        for c in claims:
            f.write(json.dumps(decide(c)) + "\n")
            f.write(json.dumps({"claim_id": c.claim_id, "approach": "MAJ_majority_supported", "predicted_label": S}) + "\n")
    meta = {"split": split, "input_sha256": sha256(os.path.join(RESEARCH_ROOT, SPLITS[split])), "script_sha256": sha256(__file__),
            "output_sha256": sha256(out), "rule_version": VERSION, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    json.dump(meta, open(os.path.join(OUT, f"run_{split}.json"), "w"), indent=1)
    return out


def labels(split: str) -> dict:
    if split == "dev":
        return {r["claim_id"]: r["final_label"] for r in map(json.loads, open(os.path.join(RESEARCH_ROOT, DEV_LABELS)))}
    from engine.reference import load_reference
    return {k: v["label"] for k, v in load_reference()["labels"].items()}


def score(split: str) -> dict:
    from engine.metrics import classification_metrics
    ref = labels(split)
    cats = {c.claim_id: c.claim_category for c in load_claims(os.path.join(RESEARCH_ROOT, SPLITS[split]))}
    preds = [json.loads(x) for x in open(os.path.join(OUT, f"predictions_{split}.jsonl"))]
    res = {}
    for arm in ("RB_rule_based", "MAJ_majority_supported"):
        P = {p["claim_id"]: p["predicted_label"] for p in preds if p["approach"] == arm}
        ids = sorted(ref)
        m = classification_metrics([ref[i] for i in ids], [P[i] for i in ids])
        res[arm] = {"correct": sum(P[i] == ref[i] for i in ids), "n": len(ids), "accuracy": round(m["accuracy"], 4),
                    "macro_f1": round(m["macro_f1"], 4),
                    "by_category": {k: f"{sum(P[i] == ref[i] for i in ids if cats[i] == k)}/{sum(cats[i] == k for i in ids)}"
                                    for k in ("numerical", "interpretive", "ambiguous")},
                    "confusion": {f"{g}>{p}": n for (g, p), n in sorted(Counter((ref[i], P[i]) for i in ids).items())},
                    "predicted": dict(Counter(P.values()))}
        if arm == "RB_rule_based":
            res[arm]["rules_fired"] = dict(Counter(p["rule"] for p in preds if p["approach"] == arm))
            res[arm]["decisive_correct"] = f"{sum(P[i] == ref[i] for i in ids if P[i] != I)}/{sum(P[i] != I for i in ids)}"
    res["status"] = "POST-HOC EXPLORATORY"
    json.dump(res, open(os.path.join(OUT, f"score_{split}.json"), "w"), indent=1)
    return res


def lock() -> None:
    if os.path.exists(LOCK):
        raise SystemExit("already locked")
    os.makedirs(OUT, exist_ok=True)
    json.dump({"rule_version": VERSION, "script": os.path.relpath(__file__, RESEARCH_ROOT), "script_sha256": sha256(__file__),
               "locked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "developed_on": "dev-v0.2 only", "status": "POST-HOC EXPLORATORY",
               "known_limitations": ["one numeric assertion per claim", "company-level metrics only (no segment)",
                                     "quarter without a stated date -> latest reported quarter at the cutoff",
                                     "no causal / evaluative reasoning: such claims become INSUFFICIENT_EVIDENCE unless a number is false",
                                     "author had seen some Gold claim texts earlier in the project (exposed set)"]},
              open(LOCK, "w"), indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("run", "lock", "score"))
    ap.add_argument("--split", choices=tuple(SPLITS), default="dev")
    a = ap.parse_args()
    if a.cmd == "run":
        print("wrote", run(a.split))
    elif a.cmd == "lock":
        lock()
        print("locked", sha256(__file__))
    else:
        print(json.dumps(score(a.split), indent=1))
