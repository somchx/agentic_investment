"""Reference-label status of every dev-v0.2 claim (read-only).

    research/.venv/bin/python research/scripts/dev_v0_2_label_status.py

Reads the human annotation files and the development adjudication log; writes
results/dev_v0_2/label_status.{jsonl,md}. It creates no label. A claim counts
as having an approved final label only when it appears in an approved
reference-label file (see scripts/a3v2_dev_evaluate.py); none exists yet.

Status per claim:
    DISAGREED           two independent labels differ, no adjudication yet
    AGREED              two independent labels agree (awaits approval into the reference file)
    ADJUDICATED         an adjudication is recorded (awaits approval into the reference file)
    SINGLE              one labeller only
Second annotation is required for SINGLE ambiguous / interpretive claims
(plan §2b); numerical claims are listed as optional.
"""
import importlib.util
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import load_adjudications, load_claims  # noqa: E402

D = os.path.join(RESEARCH_ROOT, "datasets", "annotations_dev")
DATASET = os.path.join(RESEARCH_ROOT, "datasets", "development_cases_dev-v0.2.jsonl")
OLD_FIRST, OLD_SECOND = os.path.join(D, "rev_som.v4.jsonl"), os.path.join(D, "rev_reviewer2.jsonl")
OLD_PRE_REVIEW = os.path.join(D, "rev_som.v3.jsonl")
NEW_FIRST = os.path.join(D, "rev_person2.dev-v0_2.jsonl")
ADJ = os.path.join(D, "adjudications.jsonl")
APPROVED = os.path.join(D, "dev-v0.2_reference_labels.approved.jsonl")
OUT = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2")
NOT_INDEPENDENT = {
    "rev_person3": "dev_blind_review_dev-v0.2_40_{filled,reviewed}.xlsx: content identical to the Codex-filled workbook; not imported, not usable for κ",
    "ai_codex_dev48": "AI-filled workbook; not a human label",
}

_spec = importlib.util.spec_from_file_location("agr", os.path.join(os.path.dirname(__file__), "dev_label_agreement.py"))
agr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agr)


def status_rows() -> list[dict]:
    claims = load_claims(DATASET)
    first = {**agr.load(OLD_FIRST), **agr.load(NEW_FIRST)}
    pre = agr.load(OLD_PRE_REVIEW)
    second = agr.load(OLD_SECOND)
    adj = load_adjudications(ADJ) if os.path.exists(ADJ) else {}
    approved = {json.loads(x)["claim_id"] for x in open(APPROVED)} if os.path.exists(APPROVED) else set()
    rows = []
    for c in claims:
        f, s = first.get(c.claim_id), second.get(c.claim_id)
        if c.claim_id in adj:
            st = "ADJUDICATED"
        elif f and s:
            st = "AGREED" if f["gold_label"] == s["gold_label"] else "DISAGREED"
        elif f:
            st = "SINGLE"
        else:
            st = "NONE"
        needs_second = st == "SINGLE" and c.claim_category in ("ambiguous", "interpretive")
        rows.append({"claim_id": c.claim_id, "claim_type": c.claim_category, "dataset_version": "dev-v0.1" if c.claim_id in pre else "dev-v0.2-new",
                     "first_labeller": f and f["reviewer_id"], "first_label": f and f["gold_label"],
                     "first_label_ai_assisted": bool(f and f["reviewer_id"] == "rev_som" and pre.get(c.claim_id, {}).get("gold_label") != f["gold_label"]),
                     "second_labeller": s and s["reviewer_id"], "second_label": s and s["gold_label"], "status": st,
                     "adjudicated_label": adj[c.claim_id].final_label if c.claim_id in adj else None,
                     "needs_second_annotation": needs_second, "second_annotation_optional": st == "SINGLE" and not needs_second,
                     "needs_adjudication": st == "DISAGREED", "approved_final_label": c.claim_id in approved})
    return rows


def render(rows: list[dict]) -> str:
    from collections import Counter
    n = len(rows)
    st = Counter(r["status"] for r in rows)
    need2 = [r["claim_id"] for r in rows if r["needs_second_annotation"]]
    opt2 = [r["claim_id"] for r in rows if r["second_annotation_optional"]]
    dis = [r for r in rows if r["needs_adjudication"]]
    ai = [r["claim_id"] for r in rows if r["first_label_ai_assisted"]]
    unapproved = [r["claim_id"] for r in rows if not r["approved_final_label"]]
    L = ["# dev-v0.2 reference-label status", "",
         f"Claims: {n}. Status: " + ", ".join(f"{k} {v}" for k, v in sorted(st.items())) + f". Approved final labels: {n - len(unapproved)}/{n}.", "",
         "## Disagreements requiring adjudication", ""]
    L += [f"- {r['claim_id']} ({r['claim_type']}): {r['first_labeller']} {r['first_label']} vs {r['second_labeller']} {r['second_label']}"
          for r in dis] or ["- none"]
    L += ["", f"## Independent second annotation required ({len(need2)}: SINGLE ambiguous / interpretive)", "", ", ".join(need2), "",
          f"## Second annotation optional ({len(opt2)}: SINGLE numerical)", "", ", ".join(opt2), "",
          f"## First labels decided after the AI-prepared label review (v4 differs from v3; not independent of AI assistance) ({len(ai)})", "",
          ", ".join(ai) or "none", "",
          "## Second-review files that are not usable", ""]
    L += [f"- {k}: {v}" for k, v in NOT_INDEPENDENT.items()]
    L += ["", f"## Claims without an approved final label ({len(unapproved)})", "",
          "All of them: no approved reference-label file exists yet "
          f"(`{os.path.relpath(APPROVED, RESEARCH_ROOT)}`). AGREED / ADJUDICATED labels still need to be approved into that file.", "",
          "| claim | type | status | first | second | needs |", "|---|---|---|---|---|---|"]
    for r in rows:
        need = "adjudication" if r["needs_adjudication"] else ("2nd annotation" if r["needs_second_annotation"] else
                                                                ("2nd (optional)" if r["second_annotation_optional"] else "approval"))
        L.append(f"| {r['claim_id']} | {r['claim_type']} | {r['status']} | {r['first_labeller']}: {r['first_label']} | "
                 f"{r['second_labeller'] or '—'}: {r['second_label'] or '—'} | {need} |")
    return "\n".join(L) + "\n"


def main():
    rows = status_rows()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "label_status.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    open(os.path.join(OUT, "label_status.md"), "w", encoding="utf-8").write(render(rows))
    print(render(rows).split("\n## Claims without")[0])


if __name__ == "__main__":
    main()
