"""Evaluation metrics over stored predictions (pure Python, no LLM).

Classification: accuracy, per-class precision / recall / F1, macro-F1 and
the confusion matrix over the three labels. A missing prediction (error,
no verdict) counts as wrong and appears in the confusion matrix as
NO_PREDICTION -- it is never dropped, which would flatter an approach.

Evidence: a cited unit matches a gold evidence reference when it is the
same filing and contains the annotator's quote (>= 80% of the quote's
tokens), or, for XBRL references, the same filing and period. Evidence
precision = matched valid citations / valid citations; evidence recall =
gold references matched / gold references. Both are None (not 0) when
undefined.

Unsupported conclusion: a SUPPORTED / CONTRADICTED label with no valid
citation backing it (computed at prediction time; see
experiments/pipeline.build_prediction).

Efficiency figures are averaged only over rows that actually measured
them; the count is reported so a missing measurement is never invented.
"""

import re
from collections import defaultdict

from .schema import LABELS

NO_PRED = "NO_PREDICTION"


def _safe_div(a, b):
    return a / b if b else None


def classification_metrics(y_true: list[str], y_pred: list[str | None]) -> dict:
    n = len(y_true)
    pred = [p if p in LABELS else NO_PRED for p in y_pred]
    cm = {t: {p: 0 for p in (*LABELS, NO_PRED)} for t in LABELS}
    for t, p in zip(y_true, pred):
        cm[t][p] += 1
    per_class = {}
    for lab in LABELS:
        tp = cm[lab][lab]
        fp = sum(cm[t][lab] for t in LABELS if t != lab)
        fn = sum(cm[lab][p] for p in (*LABELS, NO_PRED) if p != lab)
        precision, recall = _safe_div(tp, tp + fp), _safe_div(tp, tp + fn)
        f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if (tp + fp) or (tp + fn) else None)
        per_class[lab] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    present = [lab for lab in LABELS if per_class[lab]["support"] > 0]
    macro_f1 = sum((per_class[lab]["f1"] or 0.0) for lab in present) / len(present) if present else None
    return {"n": n, "accuracy": _safe_div(sum(1 for t, p in zip(y_true, pred) if t == p), n), "macro_f1": macro_f1,
            "macro_f1_labels": present, "per_class": per_class, "confusion_matrix": cm,
            "no_prediction": sum(1 for p in pred if p == NO_PRED)}


# ---------------------------------------------------------------- evidence

def _tokens(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def citation_matches_ref(cite: dict, unit: dict | None, ref: dict) -> bool:
    if cite.get("accession_number") != ref.get("accession_number"):
        return False
    if ref.get("kind", "filing_passage") == "xbrl_fact":
        if cite.get("kind") not in ("xbrl_fact", "derived_metric"):
            return False
        return not ref.get("period_end") or ref["period_end"] == cite.get("period_end") or ref["period_end"] in (cite.get("locator") or "")
    if cite.get("kind") != "filing_passage":
        return False
    quote = _tokens(ref.get("quote"))
    if not quote:
        return True  # reference names only the filing
    text = set(_tokens((unit or {}).get("excerpt")))
    return sum(1 for t in quote if t in text) / len(quote) >= 0.8


def evidence_scores(pred: dict, trace: dict | None, gold_entry: dict) -> dict:
    units = {u["evidence_id"]: u for u in (trace or {}).get("evidence", [])}
    cites = [c for c in (pred.get("supporting_evidence") or []) + (pred.get("contradicting_evidence") or []) if c.get("valid", True)]
    refs = list(gold_entry.get("supporting_evidence") or []) + list(gold_entry.get("contradictory_evidence") or [])
    matched_cites = [c for c in cites if any(citation_matches_ref(c, units.get(c["evidence_id"]), r) for r in refs)]
    matched_refs = [r for r in refs if any(citation_matches_ref(c, units.get(c["evidence_id"]), r) for c in cites)]
    return {"cited": len(cites), "gold_refs": len(refs),
            "evidence_precision": _safe_div(len(matched_cites), len(cites)) if refs else None,
            "evidence_recall": _safe_div(len(matched_refs), len(refs))}


# ------------------------------------------------------------- aggregation

def _mean(values: list) -> tuple[float | None, int]:
    vals = [v for v in values if isinstance(v, (int, float))]
    return (sum(vals) / len(vals) if vals else None), len(vals)


def efficiency(preds: list[dict]) -> dict:
    lat, n_lat = _mean([p.get("latency_ms") for p in preds])
    tin, n_tok = _mean([(p.get("token_usage") or {}).get("input") for p in preds])
    tout, _ = _mean([(p.get("token_usage") or {}).get("output") for p in preds])
    cost, n_cost = _mean([p.get("estimated_cost_usd") for p in preds])
    return {"avg_latency_ms": lat, "avg_input_tokens": tin, "avg_output_tokens": tout, "avg_cost_usd": cost,
            "total_cost_usd": sum(p.get("estimated_cost_usd") or 0 for p in preds),
            "n_latency": n_lat, "n_tokens": n_tok, "n_cost": n_cost,
            "avg_llm_calls": _mean([p.get("llm_calls") for p in preds])[0]}


def unsupported_rate(preds: list[dict]) -> dict:
    decisive = [p for p in preds if p.get("predicted_label") in ("SUPPORTED", "CONTRADICTED")]
    bad = [p for p in decisive if p.get("unsupported_conclusion")]
    return {"decisive": len(decisive), "unsupported": len(bad), "unsupported_conclusion_rate": _safe_div(len(bad), len(decisive)),
            "invalid_citations": sum(len(p.get("invalid_citations") or []) for p in preds)}


def evaluate(preds: list[dict], gold: dict[str, dict], traces: dict | None = None, group_by: tuple[str, ...] = ("approach",)) -> list[dict]:
    """One row per group. Classification and evidence metrics use only claims
    with a finalized gold label; efficiency and unsupported-conclusion use
    every prediction in the group."""
    groups = defaultdict(list)
    for p in preds:
        groups[tuple(p.get(k) for k in group_by)].append(p)
    rows = []
    for key, ps in sorted(groups.items(), key=lambda kv: [str(x) for x in kv[0]]):
        labelled = [p for p in ps if p["claim_id"] in gold]
        cls = classification_metrics([gold[p["claim_id"]]["label"] for p in labelled], [p.get("predicted_label") for p in labelled]) \
            if labelled else None
        ev = [evidence_scores(p, (traces or {}).get((p["approach"], p["claim_id"])), gold[p["claim_id"]]) for p in labelled]
        row = {**dict(zip(group_by, key)), "n_predictions": len(ps), "n_labelled": len(labelled),
               "accuracy": cls["accuracy"] if cls else None, "macro_f1": cls["macro_f1"] if cls else None,
               "evidence_precision": _mean([e["evidence_precision"] for e in ev])[0],
               "evidence_recall": _mean([e["evidence_recall"] for e in ev])[0],
               "n_evidence_scored": sum(1 for e in ev if e["evidence_recall"] is not None),
               **unsupported_rate(ps), **efficiency(ps), "is_mock": any(p.get("is_mock") for p in ps)}
        if cls:
            for lab in LABELS:
                row[f"precision_{lab}"] = cls["per_class"][lab]["precision"]
                row[f"recall_{lab}"] = cls["per_class"][lab]["recall"]
                row[f"f1_{lab}"] = cls["per_class"][lab]["f1"]
        rows.append(row)
    return rows
