"""Post-experiment error analysis over a completed run: paired outcomes,
second-look transitions, INSUFFICIENT_EVIDENCE errors, counter-evidence and
citation audits, and per-claim cost / latency. Pure functions over
predictions, traces and reference labels -- nothing here calls a model or
writes into a run directory."""

import glob
import json
import os
import re
from collections import Counter, defaultdict

from .metrics import transition
from .reference import correct, stated_period_end

INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
DECISIVE = ("SUPPORTED", "CONTRADICTED")
SHORT = {"SUPPORTED": "S", "CONTRADICTED": "C", INSUFFICIENT: "I"}
QUADRANTS = ("both_correct", "only_a", "only_b", "both_wrong")
ERROR_TYPES = ("correct", "overconfident_supported", "overconfident_contradicted", "over_abstention",
               "polarity_error", "no_prediction")
# quotes the pipeline checks verbatim; xbrl_fact / derived_metric quotes are not checked (see citation_audit)
QUOTE_CHECKED_KINDS = ("filing_passage",)
# codes of the discordant-case review (datasets/error_analysis/discordant_case_review__<run>.csv)
MECHANISMS = {
    "OVER_RESOLUTION_UNDEFINED_PREDICATE": "Decisive answer to a claim whose key term has no criterion in the filings "
                                           "(e.g. 'resilient', 'adequate returns', 'fully under control').",
    "ASPIRATIONAL_TEXT_AS_EVIDENCE": "Management intent or strategy language taken as proof of an outcome.",
    "TERM_MISREADING": "An accounting or reporting term read wrongly (line-item definitions, what a total includes).",
    "ARGUMENT_FROM_SILENCE": "Absence of a disclosure taken as evidence that the effect did not happen.",
    "ARITHMETIC_NOT_DONE": "The figures needed were retrieved but the decisive calculation was not made.",
    "LEVEL_VS_CHANGE": "A level (or one period's effect) compared with a change, ignoring the comparison period.",
    "OVER_SKEPTICISM_CAUSAL": "An explicit causal sentence demanded where the accounting relation already settles it.",
    "PREMISE_OVER_LITERAL": "A premise the claim does not make is attacked and the claim judged on it.",
    "TEMPORAL_MISMATCH": "Evidence from another fiscal period used as if it described the claim's period.",
    "GENUINE_MISSING_EVIDENCE_FOUND": "The investigation retrieved decisive evidence the initial retrieval lacked.",
    "SCOPE_CORRECTION": "The investigation showed the evidence used initially did not cover the claim's scope.",
    "RE_REASONING_SAME_EVIDENCE": "No new evidence; the verdict changed on re-reading evidence already in hand.",
    "THRESHOLD_REINTERPRETATION": "A vague threshold in the claim (e.g. 'meaningful') re-judged on the same figures.",
}


def _index(preds: list[dict]) -> dict[tuple[str, str], dict]:
    return {(p["approach"], p["claim_id"]): p for p in preds}


# ------------------------------------------------------- paired outcomes

def quadrant(correct_a: bool, correct_b: bool) -> str:
    return {(True, True): "both_correct", (True, False): "only_a", (False, True): "only_b",
            (False, False): "both_wrong"}[(bool(correct_a), bool(correct_b))]


def paired_outcomes(preds: list[dict], gold: dict[str, dict], a: str, b: str,
                    alternatives: dict | None = None) -> list[dict]:
    """One row per claim scored for both approaches: labels, correctness and
    the 2x2 cell (only_a = a correct, b wrong). `alternatives` switches to the
    adjudicated / lenient scoring of engine.reference.correct."""
    idx = _index(preds)
    rows = []
    for (name, cid), pa in sorted(idx.items()):
        if name != a or cid not in gold or (b, cid) not in idx:
            continue
        pb = idx[(b, cid)]
        ca, cb = correct(pa, gold, alternatives), correct(pb, gold, alternatives)
        rows.append({"claim_id": cid, "company": pa.get("company"), "category": pa.get("claim_category"),
                     "difficulty": pa.get("difficulty"), "gold": gold[cid]["label"],
                     "label_a": pa.get("predicted_label"), "label_b": pb.get("predicted_label"),
                     "correct_a": ca, "correct_b": cb, "quadrant": quadrant(ca, cb)})
    return rows


# --------------------------------------------------- second-look changes

def label_shift(initial: str | None, final: str | None) -> str:
    if initial == final:
        return "unchanged"
    if initial == INSUFFICIENT and final in DECISIVE:
        return "insufficient_to_decisive"
    if initial in DECISIVE and final == INSUFFICIENT:
        return "decisive_to_insufficient"
    if initial in DECISIVE and final in DECISIVE:
        return "polarity_flip"
    return "other"


def second_look_rows(preds: list[dict], gold: dict[str, dict], kind: str = "contradiction_aware") -> list[dict]:
    """Per labelled claim of the second-look approach: initial (= A2 final)
    vs final verdict, the transition against the reference, and what the
    investigation recorded."""
    rows = []
    for p in preds:
        if p.get("approach_kind") != kind or p["claim_id"] not in gold:
            continue
        info = p.get("contradiction") or {}
        g = gold[p["claim_id"]]["label"]
        assessments = [x for x in (info.get("assessments") or []) if isinstance(x, dict)]
        counts = Counter(x.get("assessment") for x in assessments)
        ini, fin = p.get("initial_label"), p.get("predicted_label")
        rows.append({"claim_id": p["claim_id"], "company": p.get("company"), "category": p.get("claim_category"),
                     "gold": g, "initial": ini, "final": fin, "model_final": info.get("model_final_label"),
                     "shift": label_shift(ini, fin), "path": f"{SHORT.get(ini, '?')}→{SHORT.get(fin, '?')}",
                     "transition": transition(ini, fin, g) if ini else None,
                     "completed": info.get("assessments") is not None,
                     "guard_reverted": info.get("guard_reverted"),
                     "n_hypotheses": len(info.get("hypotheses") or []),
                     "challenges_supported": counts.get("CHALLENGE_SUPPORTED", 0),
                     "challenges_refuted": counts.get("CHALLENGE_REFUTED", 0),
                     "no_relevant_evidence": counts.get("NO_RELEVANT_EVIDENCE", 0),
                     "stop_reason": p.get("stop_reason")})
    return rows


# --------------------------------------------- INSUFFICIENT_EVIDENCE errors

def error_type(pred: str | None, ref: str) -> str:
    """How a final label relates to the reference. Overconfident = a decisive
    answer where the reference says the filings cannot decide the claim;
    over-abstention = INSUFFICIENT_EVIDENCE where the reference is decisive."""
    if pred == ref:
        return "correct"
    if pred not in DECISIVE and pred != INSUFFICIENT:
        return "no_prediction"
    if ref == INSUFFICIENT:
        return "overconfident_supported" if pred == "SUPPORTED" else "overconfident_contradicted"
    return "over_abstention" if pred == INSUFFICIENT else "polarity_error"


def error_rows(preds: list[dict], gold: dict[str, dict]) -> list[dict]:
    return [{"approach": p["approach"], "claim_id": p["claim_id"], "category": p.get("claim_category"),
             "gold": gold[p["claim_id"]]["label"], "pred": p.get("predicted_label"),
             "error_type": error_type(p.get("predicted_label"), gold[p["claim_id"]]["label"])}
            for p in preds if p["claim_id"] in gold]


# ------------------------------------------------------- citation audit

_NUM = re.compile(r"\(?-?\$?\s?\d[\d,]*(?:\.\d+)?\s?%?\)?")


def quote_numbers(text: str) -> list[tuple[float, bool]]:
    """Numbers in a quote as (value, is_percent); '(1,234)' is negative."""
    out = []
    for m in _NUM.finditer(text or ""):
        s = m.group(0)
        neg = s.startswith("(") and s.endswith(")") or "-" in s
        pct = "%" in s
        digits = re.sub(r"[^\d.]", "", s)
        if not digits or digits == ".":
            continue
        try:
            v = float(digits)
        except ValueError:
            continue
        out.append((-v if neg else v, pct))
    return out


def value_in_quote(value: float, quote: str, rel_tol: float = 0.006) -> bool:
    """Whether a reported figure appears in a quote at any usual scale
    (units, thousands, millions, billions; ratios as percentages)."""
    if value is None:
        return False
    for n, pct in quote_numbers(quote):
        scales = (0.01,) if pct else (1, 1e3, 1e6, 1e9)
        for s in scales:
            x = n * s
            if value == 0:
                if x == 0:
                    return True
            elif abs(abs(x) - abs(value)) <= rel_tol * abs(value) + (0.0005 if pct else 0):
                return True
    return False


def citation_audit(pred: dict, trace: dict | None) -> list[dict]:
    """Each final citation re-checked independently of the pipeline's
    `valid` flag: filed on or before the claim's cutoff (from the trace's
    evidence ledger), period alignment with the claim's stated period, and
    -- for XBRL / derived-metric citations, whose quotes the pipeline does
    not check -- whether the quoted numbers contain the cited fact's value.
    A citation passing every check is provenance-valid; it is not thereby
    evidence that entails the verdict."""
    ledger = {e.get("evidence_id"): e for e in (trace or {}).get("evidence", []) if isinstance(e, dict)}
    claim = (trace or {}).get("claim") or {}
    stated = stated_period_end(claim.get("claim", ""))
    cutoff = pred.get("as_of_date") or claim.get("as_of_date")
    rows = []
    for c in pred.get("citations") or []:
        unit = ledger.get(c.get("evidence_id")) or {}
        kind = c.get("kind") or unit.get("kind")
        filed = unit.get("filed") or c.get("filed")
        values = unit.get("values") or []
        fidelity = None  # None: not applicable (passage, or an unquoted figure attached by the numeric verifier)
        if kind in ("xbrl_fact", "derived_metric") and values and (c.get("quote") or "").strip():
            fidelity = any(value_in_quote(v, c["quote"]) for v in values if isinstance(v, (int, float)))
        period_end = unit.get("period_end") or c.get("period_end")
        rows.append({"approach": pred["approach"], "claim_id": pred["claim_id"], "evidence_id": c.get("evidence_id"),
                     "kind": kind, "form": c.get("form"), "filed": filed, "period_end": period_end,
                     "cutoff": cutoff, "pipeline_valid": bool(c.get("valid")), "issues": ";".join(c.get("issues") or []),
                     "quote_checked_by_pipeline": kind in QUOTE_CHECKED_KINDS,
                     "after_cutoff": bool(filed and cutoff and filed > cutoff),
                     "stated_period_end": stated,
                     "period_matches_claim": (period_end == stated) if stated and period_end else None,
                     "xbrl_value_in_quote": fidelity})
    return rows


def citation_summary(rows: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["approach"]].append(r)
    out = []
    for a, rs in sorted(by.items()):
        unchecked = [r for r in rs if not r["quote_checked_by_pipeline"]]
        fid = [r for r in unchecked if r["xbrl_value_in_quote"] is not None]
        per = [r for r in rs if r["period_matches_claim"] is not None]
        out.append({"approach": a, "citations": len(rs),
                    "pipeline_valid_rate": sum(r["pipeline_valid"] for r in rs) / len(rs),
                    "after_cutoff": sum(r["after_cutoff"] for r in rs),
                    "quote_not_checked": len(unchecked),
                    "xbrl_quote_value_mismatch": sum(1 for r in fid if not r["xbrl_value_in_quote"]),
                    "xbrl_quotes_checked": len(fid),
                    "stated_period_citations": len(per),
                    "period_mismatch_rate": (sum(1 for r in per if not r["period_matches_claim"]) / len(per)) if per else None})
    return out


# ------------------------------------------------- counter-evidence audit

def counter_evidence_audit(pred: dict, trace: dict | None) -> dict:
    """What A3's investigation actually brought in for one claim: new
    filings beyond the initial retrieval, challenges judged supported with
    at least one valid citation, and whether the final citations draw on
    the counter-evidence."""
    info = pred.get("contradiction") or {}
    trace = trace or {}
    ledger = {e.get("evidence_id"): e for e in trace.get("evidence", []) if isinstance(e, dict)}
    initial_ids, counter_ids = set(), set()
    for tc in trace.get("tool_calls", []):
        if tc.get("tool") != "retrieve_passages":
            continue
        (initial_ids if tc.get("purpose") == "initial" else counter_ids).update(tc.get("results") or [])
    counter_ids |= set(info.get("counter_evidence_ids") or [])
    acc = lambda ids: {ledger[i].get("accession_number") for i in ids if i in ledger}  # noqa: E731
    assessments = [x for x in (info.get("assessments") or []) if isinstance(x, dict)]
    supported = [x for x in assessments if x.get("assessment") == "CHALLENGE_SUPPORTED"]
    supported_valid = [x for x in supported
                       if any(isinstance(e, dict) and e.get("valid") for e in x.get("evidence") or [])]
    final_ids = {c.get("evidence_id") for c in pred.get("citations") or []}
    return {"claim_id": pred["claim_id"], "category": pred.get("claim_category"),
            "initial": pred.get("initial_label"), "final": pred.get("predicted_label"),
            "changed": bool(pred.get("verdict_changed")), "completed": info.get("assessments") is not None,
            "hypotheses": len(info.get("hypotheses") or []), "counter_queries": len(info.get("queries") or []),
            "counter_passages": len(counter_ids),
            "new_filings": len(acc(counter_ids) - acc(initial_ids)),
            "challenges_supported": len(supported), "supported_with_valid_citation": len(supported_valid),
            "final_cites_counter_evidence": bool(final_ids & counter_ids),
            "changed_without_supported_challenge": bool(pred.get("verdict_changed")) and not supported,
            "guard_reverted": info.get("guard_reverted")}


# ------------------------------------------------------ cost and latency

def live_latency_index(run_dirs: list[str]) -> dict[str, int]:
    """request_key -> latency (ms) of the call that actually reached the
    API. Offline replays record 0 ms, so latency comes from the live runs."""
    out = {}
    for d in run_dirs:
        for path in glob.glob(os.path.join(d, "traces", "*", "*.json")):
            with open(path) as f:
                t = json.load(f)
            for c in t.get("llm_calls") or []:
                if c.get("source") == "live" and c.get("request_key"):
                    out[c["request_key"]] = c.get("latency_ms") or 0
    return out


def efficiency_rows(preds: list[dict], traces: dict, live_latency: dict[str, int]) -> list[dict]:
    """Per (approach, claim): calls, tool use, tokens, cost and estimated
    wall-clock latency = live latency of each model request it makes (an
    identical request shared across approaches counts for each) + the
    replay's non-model node time. `latency_complete` is False when any
    request has no live measurement."""
    rows = []
    for p in preds:
        t = traces.get((p["approach"], p["claim_id"])) or {}
        calls = t.get("llm_calls") or []
        lat = [live_latency.get(c.get("request_key")) for c in calls]
        node_ms = sum(n.get("duration_ms") or 0 for n in (t.get("graph") or {}).get("execution_trace", []))
        tu = p.get("token_usage") or {}
        rows.append({"approach": p["approach"], "claim_id": p["claim_id"], "category": p.get("claim_category"),
                     "llm_calls": p.get("llm_calls"), "retrieval_queries": p.get("retrieval_queries"),
                     "numeric_checks": p.get("numeric_checks"), "tool_calls": len(t.get("tool_calls") or []),
                     "input_tokens": tu.get("input"), "output_tokens": tu.get("output"),
                     "cost_usd": p.get("estimated_cost_usd"),
                     "latency_s": (sum(x for x in lat if x is not None) + node_ms) / 1000 if calls else None,
                     "latency_complete": bool(calls) and all(x is not None for x in lat)})
    return rows


# ------------------------------------------------------ scoring summary

def scoring_summary(preds: list[dict], gold: dict[str, dict], scorings: dict[str, dict | None],
                    comparisons: list[tuple[str, str]], n_boot: int = 5000) -> dict:
    """Accuracy per approach and paired tests (McNemar exact, bootstrap CI)
    under each scoring: {"strict": None, "adjudicated": alternatives, ...}."""
    from .stats import compare_correctness
    idx = _index(preds)
    approaches = sorted({p["approach"] for p in preds})
    ids = sorted({cid for (a, cid) in idx if cid in gold and all((x, cid) in idx for x in approaches)})
    out = {"n_claims": len(ids), "accuracy": {}, "comparisons": {}}
    for name, alt in scorings.items():
        corr = {a: [correct(idx[(a, c)], gold, alt) for c in ids] for a in approaches}
        out["accuracy"][name] = {a: round(sum(v) / len(v), 6) if v else None for a, v in corr.items()}
        for a, b in comparisons:
            if a in corr and b in corr and ids:
                r = compare_correctness(corr[a], corr[b], n_boot=n_boot)
                d = r["accuracy_diff"] or {}
                m = r["mcnemar"]
                out["comparisons"][f"{a} -> {b} ({name})"] = {
                    "diff": round(d["diff_b_minus_a"], 6), "ci_low": round(d["ci_low"], 6), "ci_high": round(d["ci_high"], 6),
                    "only_a_correct": m["a_right_b_wrong"], "only_b_correct": m["b_right_a_wrong"],
                    "mcnemar_p": round(m["p_value_exact"], 6)}
    return out


def adjudication_matches_workbook(jsonl_path: str, workbook_path: str) -> dict:
    """Re-read the source workbook and compare its decisions, case by case,
    with the recorded variant (sheet `Cases`, columns `Case ID` and
    `Decision [EDIT]`)."""
    from openpyxl import load_workbook
    recorded = {}
    for line in open(jsonl_path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            recorded[r["case_id"]] = r["decision"]
    ws = load_workbook(workbook_path, read_only=True, data_only=True)["Cases"]
    rows = ws.iter_rows(values_only=True)
    head = list(next(rows))
    ci, di = head.index("Case ID"), head.index("Decision [EDIT]")
    book = {r[ci]: str(r[di] or "").strip().upper() for r in rows if r[ci]}
    mismatched = sorted(c for c in recorded.keys() & book.keys() if recorded[c] != book[c])
    return {"cases_recorded": len(recorded), "cases_in_workbook": len(book), "mismatched": mismatched,
            "missing_from_workbook": sorted(recorded.keys() - book.keys()),
            "acceptable_recorded": sum(v == "ACCEPTABLE" for v in recorded.values()),
            "acceptable_in_workbook": sum(v == "ACCEPTABLE" for v in book.values()),
            "consistent": not mismatched and recorded.keys() == book.keys()}
