"""Reference labels for evaluation: the researcher-reviewed Final Gold set.

Final_Gold_v3_approved.xlsx (datasets/workbooks/; exported from the
researcher's Google Sheet, identical to Final_Gold_v3.xlsx except that all 150
claims are marked human review "Approved") holds the evaluation reference for
the 150 gold claims. v1 (sheet `Final_Gold_150`) is still readable. v3
differs from v1 in 7 labels: five claims whose wording has an unambiguous
reading backed by the figures ("offset", "weighed on", "drag") moved from
INSUFFICIENT_EVIDENCE to SUPPORTED, and two "driven by" claims (read as
"main driver") moved from SUPPORTED to INSUFFICIENT_EVIDENCE. Provenance, recorded with every load: three LLMs
annotated each claim (Claude Opus 5.5, Gemini 4 Argon, GPT-6.0 Astra),
disagreements were adjudicated with AI assistance, and the researcher
reviewed the result. It is therefore NOT independent human gold in the
sense of datasets.finalized_gold (>= 2 human reviewers), and results scored
against it must say so.

Isolation: only evaluation code imports this module. Approaches receive
ClaimInput (schema.py), which carries no label field, and no agent tool can
read datasets/workbooks/. The workbook is opened read-only and never written.

Label values are normalised by trimming whitespace and upper-casing only; a
value that is not then exactly one of LABELS is an error, never guessed.
"""

import os
import re
from collections import Counter
from datetime import date

from . import RESEARCH_ROOT
from .corpus import _cik, eligible_filings, list_filings
from .datasets import DATASET_DIR, file_sha256
from .schema import LABELS, SchemaError

REFERENCE_PATH = os.path.join(DATASET_DIR, "workbooks", "Final_Gold_v3_approved.xlsx")
REFERENCE_SHEET = "Final Gold 150"
LABEL_SOURCE = "llm_annotated_ai_adjudicated_researcher_reviewed"
PROVENANCE = {
    "label_source": LABEL_SOURCE,
    "annotators": ["Claude Opus 5.5", "Gemini 4 Argon", "GPT-6.0 Astra"],
    "adjudication": "AI-assisted, then reviewed by the researcher",
    "independent_human_gold": False,
    "initial_agreement": {"fleiss_kappa": 0.634, "krippendorff_alpha_nominal": 0.634, "n_claims": 150, "n_raters": 3},
}

_COMMON = {"claim_id": "Claim ID", "company": "Company", "category": "Category", "claim": "Claim text",
           "vote_pattern": "Vote pattern (not gold)", "label": "Final Gold Label [EDIT]",
           "rationale": "Decision rationale [EDIT]", "evidence_urls": "SEC evidence URL(s) [EDIT]",
           "evidence_text": "Exact quotation / computation [EDIT]", "review_date": "Review date [EDIT]"}
# sheet name -> columns; the sheet present in the workbook selects the layout
LAYOUTS = {
    "Final Gold 150": {**_COMMON, "qa_status": "Independent SEC quote QA v2", "audit_status": "Additional SEC audit status",
                       "human_review": "Human review status [EDIT]"},
    "Final_Gold_150": {**_COMMON, "qa_status": "Evidence QA status [EDIT]"},
}
# evidence QA statuses meaning a quote was matched in the filing (or no filing exists)
VERBATIM_OK = {"SEC_PROSE_QUOTE_MATCHED_NORMALIZED", "SELECTED_SEC_PASSAGE_CHECKED",
               "NO_ELIGIBLE_FILING_AT_CUTOFF"}

_ACCESSION_URL = re.compile(r"/Archives/edgar/data/(\d+)/(\d{10})(\d{2})(\d{6})/")


def normalize_label(value) -> str:
    v = str(value or "").strip().upper()
    if v not in LABELS:
        raise SchemaError(f"reference label {value!r} is not one of {LABELS}")
    return v


def accessions_in(urls: str | None) -> list[str]:
    """Accession numbers (with dashes) named by SEC Archives URLs."""
    out = []
    for m in _ACCESSION_URL.finditer(urls or ""):
        acc = f"{m.group(2)}-{m.group(3)}-{m.group(4)}"
        if acc not in out:
            out.append(acc)
    return out


def _cell(v):
    if v is None:
        return None
    if hasattr(v, "date"):
        return v.date().isoformat()
    return str(v).strip()


def load_reference(path: str = REFERENCE_PATH) -> dict:
    """{"labels": {claim_id: entry}, "provenance": {...}}. Each entry has
    `label` (so metrics/stats accept it as gold), the researcher's rationale,
    the evidence filings it names and its evidence QA status. Gold evidence
    quotes are not verbatim-verified, so no `supporting_evidence` is exposed
    for passage-level evidence precision / recall."""
    from openpyxl import load_workbook

    if not os.path.exists(path):
        raise FileNotFoundError(f"reference workbook not found: {path}")
    sha = file_sha256(path)
    wb = load_workbook(path, read_only=True, data_only=True)
    sheet = next((name for name in LAYOUTS if name in wb.sheetnames), None)
    if sheet is None:
        raise SchemaError(f"{os.path.basename(path)} has none of the sheets {list(LAYOUTS)}")
    columns = LAYOUTS[sheet]
    rows = list(wb[sheet].iter_rows(values_only=True))
    wb.close()
    header = [str(h or "").strip() for h in rows[0]]
    missing = [c for c in columns.values() if c not in header]
    if missing:
        raise SchemaError(f"{sheet} is missing columns {missing}")
    idx = {k: header.index(c) for k, c in columns.items()}
    labels, normalised = {}, []
    for n, r in enumerate(rows[1:], start=2):
        r = tuple(r) + (None,) * (len(header) - len(r))
        cid = _cell(r[idx["claim_id"]])
        if not cid:
            continue
        if cid in labels:
            raise SchemaError(f"{sheet} row {n}: duplicate claim id {cid}")
        raw = r[idx["label"]]
        label = normalize_label(raw)
        if str(raw) != label:
            normalised.append({"claim_id": cid, "raw": raw, "label": label})
        urls = _cell(r[idx["evidence_urls"]])
        labels[cid] = {"label": label, "status": "REFERENCE", "label_source": LABEL_SOURCE,
                       "company": _cell(r[idx["company"]]), "claim_category": _cell(r[idx["category"]]),
                       "claim": _cell(r[idx["claim"]]), "vote_pattern": _cell(r[idx["vote_pattern"]]),
                       "rationale": _cell(r[idx["rationale"]]), "evidence_urls": urls,
                       "reference_accessions": accessions_in(urls), "evidence_text": _cell(r[idx["evidence_text"]]),
                       "qa_status": _cell(r[idx["qa_status"]]), "review_date": _cell(r[idx["review_date"]]),
                       "audit_status": _cell(r[idx["audit_status"]]) if "audit_status" in idx else None,
                       "human_review": _cell(r[idx["human_review"]]) if "human_review" in idx else None,
                       "supporting_evidence": [], "contradictory_evidence": []}
    version = re.sub(r"[_ ]+", "-", os.path.splitext(os.path.basename(path))[0]).lower()
    return {"labels": labels, "provenance": {"dataset_version": version, **PROVENANCE,
                                             "path": os.path.relpath(path, RESEARCH_ROOT), "sha256": sha,
                                             "sheet": sheet, "n_labels": len(labels), "label_normalisations": normalised}}


# ------------------------------------------------------------- validation

_QUARTER_ENDED = re.compile(r"(?:quarter|period|year) ended ([A-Z][a-z]+ \d{1,2}, \d{4})")


def stated_period_end(claim_text: str) -> str | None:
    """'... for the quarter ended June 27, 2026 ...' -> '2026-06-27'."""
    from datetime import datetime
    m = _QUARTER_ENDED.search(claim_text or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def validate_reference(claims, reference: dict, max_per_form: dict | None = None) -> dict:
    """Checks the reference against the claims file and the SEC corpus.
    Returns {"errors": [...], "warnings": [...], "claims": [per-claim rows]}.
    Errors block evaluation; warnings are reported limitations."""
    max_per_form = max_per_form or {"10-K": 1, "10-Q": 2, "8-K": 2}
    labels = reference["labels"]
    errors, warnings, rows = [], [], []
    by_id = {c.claim_id: c for c in claims}
    if len(by_id) != len(claims):
        errors.append("duplicate claim ids in the claims file")
    for cid in sorted(set(by_id) - set(labels)):
        errors.append(f"{cid}: claim has no reference label")
    for cid in sorted(set(labels) - set(by_id)):
        errors.append(f"{cid}: reference label for a claim not in the claims file")
    filed_by_acc = {}
    for c in claims:
        if c.company not in filed_by_acc:
            filed_by_acc[c.company] = {f["accession_number"]: f for f in list_filings(c.company)}
    for cid in sorted(set(by_id) & set(labels)):
        c, ref = by_id[cid], labels[cid]
        issues = []
        if (ref["claim"] or "").strip() != c.claim.strip():
            errors.append(f"{cid}: claim text differs between the claims file and the reference")
        if ref["company"] != c.company:
            errors.append(f"{cid}: company differs ({ref['company']} vs {c.company})")
        if (ref["claim_category"] or "").lower() != c.claim_category:
            errors.append(f"{cid}: category differs ({ref['claim_category']} vs {c.claim_category})")
        try:
            date.fromisoformat(c.as_of_date)
        except ValueError:
            errors.append(f"{cid}: invalid evidence cutoff {c.as_of_date!r}")
            continue
        eligible = eligible_filings(c.company, c.as_of_date, c.to_input().allowed_forms(), max_per_form)
        eligible_acc = {f["accession_number"] for f in eligible}
        period_end = stated_period_end(c.claim)
        future_period = bool(period_end and period_end > c.as_of_date)
        covered = bool(period_end) and any((f.get("report_date") or "") >= period_end for f in eligible)
        if future_period:
            issues.append("PERIOD_ENDS_AFTER_CUTOFF")
        elif period_end and not covered:
            issues.append("NO_ELIGIBLE_FILING_COVERS_PERIOD")
        for acc in ref["reference_accessions"]:
            f = filed_by_acc[c.company].get(acc)
            if f is None:
                issues.append(f"EVIDENCE_FILING_NOT_THIS_COMPANY:{acc}")
            elif f["filed"] > c.as_of_date:
                issues.append(f"EVIDENCE_FILED_AFTER_CUTOFF:{acc}")
            elif acc not in eligible_acc:
                issues.append(f"EVIDENCE_FILING_OUTSIDE_RETRIEVAL_WINDOW:{acc}")
        cik = str(int(_cik(c.company)))
        for m in _ACCESSION_URL.finditer(ref["evidence_urls"] or ""):
            if m.group(1) != cik:
                issues.append(f"EVIDENCE_URL_OTHER_CIK:{m.group(1)}")
        if not ref["reference_accessions"] and ref["label"] != "INSUFFICIENT_EVIDENCE":
            issues.append("DECISIVE_LABEL_WITHOUT_EVIDENCE_URL")
        if (future_period or (period_end and not covered)) and ref["label"] != "INSUFFICIENT_EVIDENCE":
            errors.append(f"{cid}: period not observable at the cutoff but reference label is {ref['label']}")
        for i in issues:
            if i.startswith(("EVIDENCE_FILED_AFTER_CUTOFF", "EVIDENCE_FILING_NOT_THIS_COMPANY", "EVIDENCE_URL_OTHER_CIK")):
                errors.append(f"{cid}: {i}")
        rows.append({"claim_id": cid, "company": c.company, "claim_category": c.claim_category, "as_of_date": c.as_of_date,
                     "stated_period_end": period_end, "future_period": future_period, "label": ref["label"],
                     "qa_status": ref["qa_status"], "eligible_filings": len(eligible),
                     "reference_accessions": len(ref["reference_accessions"]), "issues": issues})
    qa = Counter(r["qa_status"] for r in rows)
    unverified = sum(n for s, n in qa.items() if s not in VERBATIM_OK)
    if unverified:
        warnings.append(f"{unverified}/{len(rows)} reference evidence items are not verbatim-verified quotes (e.g. table "
                        "values corroborated, or quote check pending); passage-level evidence precision/recall are not computed")
    review = Counter(labels[r["claim_id"]].get("human_review") for r in rows)
    not_approved = sum(n for s, n in review.items() if s is not None and s != "Approved")
    if not_approved:
        warnings.append(f"{not_approved}/{len(rows)} claims have a human review status other than Approved in the workbook")
    outside = sum(1 for r in rows if any(i.startswith("EVIDENCE_FILING_OUTSIDE") for i in r["issues"]))
    if outside:
        warnings.append(f"{outside} claims cite a reference filing older than the retrieval window (eligible but not retrieved)")
    if not reference["provenance"]["independent_human_gold"]:
        warnings.append("reference labels are LLM-annotated, AI-adjudicated and researcher-reviewed, not independent human gold")
    return {"errors": errors, "warnings": warnings, "claims": rows,
            "label_counts": dict(Counter(r["label"] for r in rows)), "qa_status_counts": dict(qa),
            "human_review_counts": dict(review),
            "future_period_claims": [r["claim_id"] for r in rows if r["future_period"] or "NO_ELIGIBLE_FILING_COVERS_PERIOD" in r["issues"]]}


# ------------------------------------------------ adjudicated alternatives

ALTERNATIVE_VARIANTS = ("adjudicated", "lenient")  # reporting order; any imported variant is listed


def alternative_variants(run_id: str) -> list[str]:
    """Scorings recorded for a run, e.g. `adjudicated` (case-by-case blind
    decisions) and `lenient` (every decisive answer accepted: an upper bound)."""
    d = os.path.join(DATASET_DIR, "adjudication")
    prefix = f"insufficient_alternatives__{run_id}__"
    found = sorted(f[len(prefix):-6] for f in os.listdir(d) if f.startswith(prefix) and f.endswith(".jsonl")) \
        if os.path.isdir(d) else []
    return [v for v in ALTERNATIVE_VARIANTS if v in found] + [v for v in found if v not in ALTERNATIVE_VARIANTS]


def load_alternatives(run_id: str, variant: str = "adjudicated") -> dict[tuple[str, str], str]:
    """(claim_id, approach) -> ACCEPTABLE / NOT_ACCEPTABLE / UNSURE, from one
    recorded scoring variant of the blind adjudication of decisive answers on
    INSUFFICIENT_EVIDENCE claims (scripts/insufficient_adjudication.py).
    Empty if that variant was not recorded."""
    path = os.path.join(DATASET_DIR, "adjudication", f"insufficient_alternatives__{run_id}__{variant}.jsonl")
    out = {}
    if os.path.exists(path):
        import json
        for line in open(path, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                for a in r["approaches"]:
                    out[(r["claim_id"], a)] = r["decision"]
    return out


def correct(pred: dict, gold: dict, alternatives: dict | None = None) -> bool:
    """Strict match with the reference, or -- when `alternatives` is given --
    a decisive answer on an INSUFFICIENT_EVIDENCE claim that the adjudicator
    marked ACCEPTABLE. UNSURE never counts as correct."""
    ref = gold[pred["claim_id"]]["label"]
    if pred.get("predicted_label") == ref:
        return True
    return bool(alternatives) and ref == "INSUFFICIENT_EVIDENCE" and \
        alternatives.get((pred["claim_id"], pred["approach"])) == "ACCEPTABLE"
