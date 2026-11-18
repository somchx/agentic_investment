"""Development-split adjudication and label status.

    # packet for the claims two reviewers disagree on (adjudicator fills it)
    research/.venv/bin/python research/scripts/dev_adjudication.py export \
        datasets/annotations_dev/rev_som.v4.jsonl datasets/annotations_dev/rev_reviewer2.jsonl \
        --out datasets/workbooks/dev_adjudication_packet.xlsx

    # filled packet -> datasets/annotations_dev/adjudications.jsonl (append-only)
    research/.venv/bin/python research/scripts/dev_adjudication.py record filled.xlsx

    # per-claim status of the development labels (AGREED / ADJUDICATED / SINGLE / DISAGREED)
    research/.venv/bin/python research/scripts/dev_adjudication.py status \
        datasets/annotations_dev/rev_som.v4.jsonl datasets/annotations_dev/rev_reviewer2.jsonl

The packet shows both annotations (label, notes, confidence, uncertainty,
evidence) and the claim's filing links, as gold guideline §5 requires, and
nothing else: no AI-prepared review and no model output. The adjudicator must
not be one of the reviewers and must be a person. Decisions use
engine.datasets.append_adjudication (append-only) on a development file that is
separate from the gold adjudications.
"""
import argparse
import importlib.util
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import DATASET_DIR, DEV_PATH, append_adjudication, load_adjudications, load_claims  # noqa: E402
from engine.schema import LABELS, Adjudication, SchemaError  # noqa: E402

_spec = importlib.util.spec_from_file_location("dev_label_agreement", os.path.join(os.path.dirname(__file__), "dev_label_agreement.py"))
agr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agr)
_spec = importlib.util.spec_from_file_location("annotation_workbook", os.path.join(os.path.dirname(__file__), "annotation_workbook.py"))
aw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aw)

DEV_ADJUDICATION_PATH = os.path.join(DATASET_DIR, "annotations_dev", "adjudications.jsonl")
HEAD = ["Claim ID", "Claim", "Reporting period", "Evidence cutoff", "Filings (links in Filings sheet)",
        "Reviewer A", "A: label", "A: notes", "A: confidence / uncertainty", "A: evidence",
        "Reviewer B", "B: label", "B: notes", "B: confidence / uncertainty", "B: evidence",
        "✎ Adjudicator ID", "✎ Final label", "✎ Decision notes (why)"]
INPUT_FILL = PatternFill("solid", start_color="FFF2CC")


def _evidence(r: dict) -> str:
    out = []
    for side, key in (("supporting", "supporting_evidence"), ("contradicting", "contradictory_evidence")):
        for e in r.get(key) or []:
            out.append(f"[{side}] {e.get('kind')} {e['accession_number']} | {e.get('locator') or ''} | {e.get('quote') or ''}"
                       + (f" | {e['xbrl_concept']} {e.get('period_end')}" if e.get("xbrl_concept") else ""))
    return "\n".join(out) or "(none)"


def export(first: str, second: str, out: str) -> list[str]:
    a, b = agr.load(first), agr.load(second)
    res = agr.compare(a, b, n_boot=10)
    ids = [d["claim_id"] for d in res["disagreements"]]
    if not ids:
        raise SystemExit("no disagreements to adjudicate")
    claims = {c.claim_id: c for c in load_claims(DEV_PATH)}
    manifest = aw.load_manifest()
    wb = Workbook()
    ws = wb.active
    ws.title = "Adjudication"
    ws.append(HEAD)
    for cid in ids:
        c, x, y = claims[cid], a[cid], b[cid]
        filings = "\n".join(f"{f['form']} {f['accession_number']} filed {f['filed']}" for f in aw.eligible_filings(c, manifest))
        ws.append([cid, c.claim, c.reporting_period, c.as_of_date, filings,
                   x["reviewer_id"], x["gold_label"], x.get("review_notes"), f"{x.get('confidence')} / {x.get('uncertainty_type')}", _evidence(x),
                   y["reviewer_id"], y["gold_label"], y.get("review_notes"), f"{y.get('confidence')} / {y.get('uncertainty_type')}", _evidence(y),
                   None, None, None])
    for row in ws.iter_rows():
        for cell in row:
            cell.font = Font(name="Arial", size=10, bold=cell.row == 1)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if cell.row > 1 and cell.column >= 16:
                cell.fill = INPUT_FILL
    for i, w in enumerate([13, 45, 11, 11, 32, 12, 16, 50, 18, 60, 12, 16, 50, 18, 60, 16, 20, 50], start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    dv = DataValidation(type="list", formula1='"' + ",".join(LABELS) + '"', allow_blank=True, showErrorMessage=True)
    ws.add_data_validation(dv)
    dv.add(f"Q2:Q{len(ids) + 1}")
    fs = wb.create_sheet("Filings")
    fs.append(["Accession", "Company", "Form", "Filed", "SEC link"])
    for f in manifest:
        if any(f["company"] == claims[i].company for i in ids):
            fs.append([f["accession_number"], f["company"], f["form"], f["filed"], aw.filing_url(f)])
            fs.cell(fs.max_row, 5).hyperlink = aw.filing_url(f)
    rd = wb.create_sheet("วิธีใช้", 0)
    for line in ["Adjudication ของชุด Development (ไม่ใช่ Gold)",
                 "ผู้ตัดสินต้องเป็นคน และต้องไม่ใช่ผู้ตรวจคนใดคนหนึ่งในแถวนั้น ห้ามถาม AI และห้ามเปิดผลของระบบหรือรายงานที่ AI เตรียม",
                 "อ่าน claim, คำตอบของผู้ตรวจทั้งสอง และเปิด filing จากชีต Filings แล้วตัดสินตาม annotation_guidelines.md + dev_annotation_guidelines.md",
                 "กรอกช่องสีเหลือง: Adjudicator ID (ภาษาอังกฤษ ไม่มีเว้นวรรค), Final label, เหตุผล (บังคับ)",
                 "การตัดสินบันทึกแบบ append-only: ตัดสินแล้วแก้ทับไม่ได้ ต้องทำ dataset version ใหม่"]:
        rd.append([line])
    rd.column_dimensions["A"].width = 140
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return ids


def record(path: str, adjudication_path: str = DEV_ADJUDICATION_PATH) -> list[str]:
    ws = load_workbook(path)["Adjudication"]
    head = [c.value for c in ws[1]]
    if head != HEAD:
        raise SchemaError("not a packet made by dev_adjudication.py export (headers differ)")
    todo, errors = [], []
    for r, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cid, rev_a, rev_b, adj, label, notes = row[0], row[5], row[10], row[15], row[16], row[17]
        if not cid or not any((adj, label, notes)):
            continue
        adj = (str(adj or "")).strip()
        if not adj or " " in adj:
            errors.append(f"row {r}: adjudicator id required (no spaces)")
        elif adj in (rev_a, rev_b):
            errors.append(f"row {r}: the adjudicator must not be one of the reviewers ({adj})")
        elif re.match(r"(?i)^(claude|gpt|llm|model|ai)[-_:]", adj):
            errors.append(f"row {r}: adjudicator id {adj!r} looks like a model")
        try:
            todo.append(Adjudication(claim_id=cid, adjudicator_id=adj, final_label=label, decision_notes=notes or "",
                                     considered_reviewers=[rev_a, rev_b]))
        except SchemaError as e:
            errors.append(f"row {r}: {e}")
    if errors:
        raise SchemaError("packet has problems; nothing was written:\n  " + "\n  ".join(errors))
    existing = load_adjudications(adjudication_path) if os.path.exists(adjudication_path) else {}
    dup = [a.claim_id for a in todo if a.claim_id in existing]
    if dup:
        raise SchemaError(f"already adjudicated: {dup} (append-only)")
    os.makedirs(os.path.dirname(os.path.abspath(adjudication_path)), exist_ok=True)
    for a in todo:
        append_adjudication(a, adjudication_path)
    return [a.claim_id for a in todo]


def status(first: str, second: str, adjudication_path: str = DEV_ADJUDICATION_PATH) -> list[dict]:
    """Per development claim: the label it would get today and why. Reviewer A's
    file covers every claim; B may cover a subset."""
    a, b = agr.load(first), agr.load(second)
    adj = load_adjudications(adjudication_path) if os.path.exists(adjudication_path) else {}
    rows = []
    for cid in sorted(a):
        if cid in adj:
            rows.append({"claim_id": cid, "status": "ADJUDICATED", "label": adj[cid].final_label})
        elif cid in b and b[cid]["gold_label"] == a[cid]["gold_label"]:
            rows.append({"claim_id": cid, "status": "AGREED", "label": a[cid]["gold_label"]})
        elif cid in b:
            rows.append({"claim_id": cid, "status": "DISAGREED", "label": None})
        else:
            rows.append({"claim_id": cid, "status": "SINGLE", "label": a[cid]["gold_label"]})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("first")
    ex.add_argument("second")
    ex.add_argument("--out", default=os.path.join(DATASET_DIR, "workbooks", "dev_adjudication_packet.xlsx"))
    rc = sub.add_parser("record")
    rc.add_argument("packet")
    st = sub.add_parser("status")
    st.add_argument("first")
    st.add_argument("second")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "export":
            if os.path.exists(args.out):
                raise SystemExit(f"{args.out} exists")
            print(f"wrote {args.out}: {export(args.first, args.second, args.out)}")
        elif args.cmd == "record":
            print(f"recorded {record(args.packet)} in {DEV_ADJUDICATION_PATH}")
        else:
            rows = status(args.first, args.second)
            for s in ("AGREED", "ADJUDICATED", "SINGLE", "DISAGREED"):
                ids = [r["claim_id"] for r in rows if r["status"] == s]
                print(f"{s:12} {len(ids):3}  {' '.join(ids)}")
    except SchemaError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
