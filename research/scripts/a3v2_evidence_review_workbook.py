"""Human evidence-error review of the A3 v2.1.1 development runs.

    # workbook for an independent reviewer (no predicted or reference labels)
    research/.venv/bin/python research/scripts/a3v2_evidence_review_workbook.py export \
        --out datasets/workbooks/a3v2.1.1_evidence_review.xlsx
    # filled workbook -> results/dev_v0_2/evidence_review/<reviewer>.jsonl (never overwritten)
    research/.venv/bin/python research/scripts/a3v2_evidence_review_workbook.py import filled.xlsx

Rows: every finding that the Evidence Reviewer declared ENTAILS or CONTRADICTS
(sheet Findings), and every claim (sheet Claims, for claim-level questions).
Shown: the claim, its normalised period, the evidence text or figure, the
model reviewer's relation, the deterministic checks (period, statement time,
quote) and whether the guard used the finding. Not shown: A2 / R / RG
predicted labels and any reference label, so the review is about evidence
quality, not about agreeing with a verdict. P1 rows belong to the claims where
R changed A2's label or the guard decided.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import load_claims  # noqa: E402

CLAIMS_FILE = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
DATASET = os.path.join(RESEARCH_ROOT, "datasets", "development_cases_dev-v0.2.jsonl")
OUT_DIR = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "evidence_review")
FILL = PatternFill("solid", start_color="FFF2CC")

FINDING_INPUTS = {
    "✎ Evidence relevance": ("RELEVANT", "PARTIALLY_RELEVANT", "IRRELEVANT"),
    "✎ Correct relation": ("ENTAILS", "CONTRADICTS", "RELATED_NOT_DECIDING", "IRRELEVANT", "CANNOT_TELL"),
    "✎ Temporal compatibility": ("SAME_PERIOD", "COMPARISON_PERIOD", "DIFFERENT_DURATION", "DIFFERENT_PERIOD", "CANNOT_TELL"),
    "✎ Statement time": ("HISTORICAL", "FORWARD_LOOKING", "MIXED", "CANNOT_TELL"),
    "✎ Causal attribution": ("NOT_CAUSAL", "STATED_IN_EVIDENCE", "UNSUPPORTED_INFERENCE"),
    "✎ Segment / geography scope": ("NOT_APPLICABLE", "SAME_SCOPE", "DIFFERENT_SCOPE"),
    "✎ Numerical derivation": ("NOT_NUMERIC", "COMPLETE", "INCOMPLETE", "WRONG"),
    "✎ Quote validation": ("OK", "QUOTE_NOT_VERBATIM", "LABEL_INSTEAD_OF_VALUE", "SYSTEM_CHECK_WRONG"),
}
CLAIM_INPUTS = {
    "✎ Subjective-claim decidability": ("NOT_SUBJECTIVE", "CRITERION_IN_CLAIM", "CRITERION_IN_FILING", "NO_CRITERION"),
    "✎ Claim has a causal part": ("NO", "YES"),
    "✎ Claim has a segment / geography scope": ("NO", "YES"),
    "✎ Composite figure needed (e.g. FCF)": ("NO", "YES_AVAILABLE_IN_FILING", "YES_NOT_AVAILABLE"),
}
FINDING_INFO = ["Review item", "Priority", "Claim ID", "Claim", "Claim type", "Claim period", "Finding", "Assertion", "Evidence ID", "Kind",
                "Form / filed", "Evidence period", "System period status", "System statement time", "Key quote", "Evidence text / figure",
                "Model reviewer relation (declared → effective)", "Downgrade reason", "Used by guard to decide", "Model justification"]
CLAIM_INFO = ["Claim ID", "Claim", "Claim type", "Claim period", "Guard decision", "Guard reason", "Findings declared deciding"]
NOTE = "✎ Notes"


def _stage(t, name):
    return next((s for s in t.get("stages") or [] if s.get("stage") == name), {})


def _evidence_text(t: dict, eid: str) -> tuple[dict, str]:
    unit = next((e for e in (t.get("evidence") or []) if e.get("evidence_id") == eid), {})
    if unit.get("kind") == "filing_passage":
        return unit, (unit.get("excerpt") or "")[:1500]
    return unit, f"{unit.get('locator')} | values {unit.get('values')} {unit.get('unit') or ''} | {(unit.get('excerpt') or '')[:600]}"


def build_rows(claims_file: str = CLAIMS_FILE) -> tuple[list[list], list[list]]:
    texts = {c.claim_id: c.claim for c in load_claims(DATASET)}
    findings, claims = [], []
    for r in (json.loads(x) for x in open(claims_file, encoding="utf-8")):
        t = json.load(open(os.path.join(RESEARCH_ROOT, r["trace_RG"])))
        rv, g, an = _stage(t, "evidence_review"), _stage(t, "reconciliation_guard"), _stage(t, "analyze_claim")
        p = (an.get("analysis") or {}).get("claim_period") or {}
        period = f"{p.get('label')} ({p.get('start')}..{p.get('end')}, {p.get('kind')}, source {p.get('source')})"
        assertions = {a["assertion_id"]: a.get("text") for a in (an.get("analysis") or {}).get("assertions") or []}
        prio = "P1" if r["R_changed_vs_A2"] or r["guard_outcome"] != "NO_CHANGE" else "P2"
        dec = [f for f in rv.get("findings") or [] if f.get("declared_relation") in ("ENTAILS", "CONTRADICTS")]
        claims.append([r["claim_id"], texts[r["claim_id"]], r["claim_type"], period, r["guard_outcome"], r["guard_reason"], len(dec)])
        for f in dec:
            for k, eid in enumerate(f["evidence_ids"]):
                unit, text = _evidence_text(t, eid)
                chk = (f.get("checks") or [{}])[min(k, len(f.get("checks") or [{}]) - 1)]
                pc = chk.get("period_compatibility") or {}
                ev = pc.get("evidence_period") or {}
                findings.append([f"{r['claim_id']}:{f['finding_id']}:{eid}", prio, r["claim_id"], texts[r["claim_id"]], r["claim_type"], period,
                                 f["finding_id"], f"{f['assertion_id']}: {assertions.get(f['assertion_id'])}", eid, unit.get("kind"),
                                 f"{unit.get('form')} filed {unit.get('filed')} ({unit.get('accession_number')})",
                                 f"{ev.get('start')}..{ev.get('end')} months {ev.get('months')} ({ev.get('source')})",
                                 f"{pc.get('status')} / {pc.get('reason')}", ";".join(str(x) for x in f.get("statement_time") or []),
                                 f.get("key_quote"), text, f"{f['declared_relation']} → {f['relation']}", f.get("downgraded_reason") or "",
                                 "YES" if f["finding_id"] in (g.get("deciding_findings") or []) else "NO", f.get("justification")])
    findings.sort(key=lambda x: (x[1], x[0]))
    return findings, claims


def _sheet(wb, title, info, inputs, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(info + list(inputs) + [NOTE])
    for r in rows:
        ws.append(list(r) + [None] * (len(inputs) + 1))
    lists = wb["Lists"]
    for j, (name, values) in enumerate(inputs.items()):
        col = lists.max_column + 1 if lists.max_row > 1 or lists["A1"].value else 1
        lists.cell(1, col, name)
        for i, v in enumerate(values, 2):
            lists.cell(i, col, v)
        letter = lists.cell(1, col).column_letter
        dv = DataValidation(type="list", formula1=f"Lists!${letter}$2:${letter}${len(values) + 1}", allow_blank=True, showErrorMessage=True)
        ws.add_data_validation(dv)
        target = ws.cell(1, len(info) + j + 1).column_letter
        dv.add(f"{target}2:{target}{len(rows) + 1}")
    for row in ws.iter_rows():
        for c in row:
            c.font, c.alignment = Font(name="Arial", size=10, bold=c.row == 1), Alignment(wrap_text=True, vertical="top")
            if c.row > 1 and c.column > len(info):
                c.fill = FILL
    for i, w in enumerate(widths + [22] * len(inputs) + [40], 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = ws.cell(2, 4)


def export(out: str, claims_file: str = CLAIMS_FILE) -> dict:
    if os.path.exists(out):
        raise SystemExit(f"{out} exists")
    findings, claims = build_rows(claims_file)
    wb = Workbook()
    rd = wb.active
    rd.title = "คำแนะนำ"
    for line in ["ตรวจคุณภาพหลักฐานของ A3 v2.1.1 (dev-v0.2) — ผู้ตรวจต้องเป็นคน ห้ามใช้ AI ช่วยตอบ",
                 "ไฟล์นี้ไม่แสดงคำตอบของระบบ (A2/R/RG) และไม่มี reference label: ตัดสินเฉพาะว่า 'หลักฐานชิ้นนี้พิสูจน์ assertion นี้ได้จริงไหม'",
                 "ชีต Findings: หนึ่งแถว = หลักฐานหนึ่งชิ้นที่ model reviewer บอกว่า ENTAILS/CONTRADICTS — ทำ P1 ก่อน (claim ที่ R เปลี่ยนคำตอบหรือ guard ตัดสิน)",
                 "ชีต Claims: คำถามระดับ claim (คำประเมินมีเกณฑ์ไหม, มีส่วนเหตุผล/ขอบเขต segment ไหม, ต้องคำนวณตัวเลขผสมไหม)",
                 "กรอกเฉพาะช่องสีเหลือง เลือกจาก dropdown; เปิด filing จากเลข accession ได้ที่ sec.gov; ใส่ Reviewer ID ที่เซลล์ B8",
                 "ความหมาย: DIFFERENT_DURATION = วันสิ้นงวดเดียวกันแต่ความยาวต่างกัน (เช่น 9 เดือน vs ไตรมาส); LABEL_INSTEAD_OF_VALUE = quote เป็นชื่อ metric ไม่ใช่ตัวเลข",
                 ""]:
        rd.append([line])
    rd.append(["✎ Reviewer ID", None])
    rd["B8"].fill = FILL
    rd.column_dimensions["A"].width = 150
    wb.create_sheet("Lists")
    _sheet(wb, "Findings", FINDING_INFO, FINDING_INPUTS, findings, [26, 6, 12, 40, 11, 26, 7, 30, 7, 12, 22, 24, 26, 14, 40, 60, 22, 18, 8, 40])
    _sheet(wb, "Claims", CLAIM_INFO, CLAIM_INPUTS, claims, [12, 50, 11, 30, 11, 28, 8])
    wb.move_sheet("Lists", offset=2)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return {"findings": len(findings), "p1": sum(1 for f in findings if f[1] == "P1"), "claims": len(claims)}


def import_review(path: str, out_dir: str = OUT_DIR) -> str:
    wb = load_workbook(path)
    rid = str(wb["คำแนะนำ"]["B8"].value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", rid):
        raise SystemExit("Reviewer ID (คำแนะนำ!B8) required: letters, digits, _ . - only")
    if re.match(r"(?i)^(claude|gpt|llm|model|ai|codex)[-_:]?", rid):
        raise SystemExit(f"reviewer id {rid!r} looks like a model; this review must be done by a person")
    out, problems = [], []
    for sheet, info, inputs in (("Findings", FINDING_INFO, FINDING_INPUTS), ("Claims", CLAIM_INFO, CLAIM_INPUTS)):
        ws = wb[sheet]
        head = [c.value for c in ws[1]]
        if head != info + list(inputs) + [NOTE]:
            raise SystemExit(f"{sheet}: headers differ from the exported workbook")
        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            answers = dict(zip(inputs, row[len(info):len(info) + len(inputs)]))
            if not any(answers.values()):
                continue
            for k, v in answers.items():
                if v is not None and v not in inputs[k]:
                    problems.append(f"{sheet} row {i}: {k} = {v!r}")
            out.append({"sheet": sheet, "item": row[0], "claim_id": row[2] if sheet == "Findings" else row[0], "reviewer_id": rid,
                        **{k.lstrip("✎ ").strip(): v for k, v in answers.items()}, "notes": row[len(info) + len(inputs)]})
    if problems:
        raise SystemExit("workbook has problems; nothing was written:\n  " + "\n  ".join(problems[:30]))
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, f"{rid}.jsonl")
    if os.path.exists(target):
        raise SystemExit(f"{target} exists; reviews are not overwritten")
    with open(target, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in out)
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--out", default=os.path.join(RESEARCH_ROOT, "datasets", "workbooks", "a3v2.1.1_evidence_review.xlsx"))
    im = sub.add_parser("import")
    im.add_argument("workbook")
    args = ap.parse_args(argv)
    if args.cmd == "export":
        print(json.dumps(export(args.out)))
    else:
        print("wrote", import_review(args.workbook))


if __name__ == "__main__":
    main()
