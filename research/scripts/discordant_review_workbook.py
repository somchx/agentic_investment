"""Researcher confirmation of the A2/A3 discordant-case review (offline).

The review CSV (datasets/error_analysis/discordant_case_review__<run>.csv)
holds an AI analyst's error classification of each claim where A2 and A3
disagree. `export` builds a workbook with everything needed to check it --
claim, reference label and rationale, A2 / A3 verdicts, A3's initial and
final verdict, the contradiction trace, the citations and their audit
flags -- and two editable columns. `import` copies only those two columns
(researcher_confirmed, researcher_note) back into the CSV.

    research/.venv/bin/python research/scripts/discordant_review_workbook.py export --run <run_id>
    research/.venv/bin/python research/scripts/discordant_review_workbook.py import <filled.xlsx> --run <run_id>
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import DATASET_DIR  # noqa: E402
from engine.error_analysis import MECHANISMS, citation_audit  # noqa: E402
from engine.reference import load_reference  # noqa: E402
from engine.runner import RUNS_DIR, load_run, load_trace  # noqa: E402
from engine.schema import SchemaError  # noqa: E402

REVIEW_DIR = os.path.join(DATASET_DIR, "error_analysis")
A, B = "A2_rag_numeric", "A3_contradiction_aware"
DECISIONS = ("CONFIRMED", "PARTIALLY_CONFIRMED", "REJECTED", "UNSURE")
ANALYST = ("mechanism", "counterevidence_genuine", "interpretation_correct", "final_citations_entail_verdict")
H_CONFIRM, H_NOTE = "researcher_confirmed [EDIT]", "researcher_note [EDIT]"
FONT = "Arial"
COLUMNS = [("Review flag", 16), ("Claim ID", 15), ("Company", 8), ("Category", 11), ("Claim", 42), ("Evidence cutoff", 11),
           ("Reference label", 14), ("Reference rationale", 48), ("A2 final", 14), ("A3 initial", 14), ("A3 final", 14),
           ("Outcome", 13), ("A3 change reason", 60), ("Contradiction trace", 90), ("A3 final citations", 70),
           ("A2 final citations", 60), ("Citation audit", 30), ("Proposed mechanism", 24), ("Mechanism definition", 36),
           ("Counter-evidence genuine?", 11), ("Interpretation correct?", 11), ("Final citations entail verdict?", 11),
           ("Analyst note", 50), (H_CONFIRM, 18), (H_NOTE, 40)]


def review_path(run_id: str) -> str:
    return os.path.join(REVIEW_DIR, f"discordant_case_review__{run_id}.csv")


def read_review(run_id: str) -> list[dict]:
    with open(review_path(run_id), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def flag(row: dict) -> str | None:
    """Cases the analyst could not call cleanly get a closer look."""
    return "CLOSER REVIEW" if row["interpretation_correct"] == "DEBATABLE" else None


def _cite(c: dict) -> str:
    v = "valid" if c.get("valid") else f"INVALID {','.join(c.get('issues') or [])}"
    return (f"[{c.get('evidence_id')}] {c.get('kind') or '?'} {c.get('form') or ''} filed {c.get('filed') or '?'} "
            f"period {c.get('period_end') or '?'} ({v}): {(c.get('quote') or '(no quote: figure attached by the numeric check)')[:300]}")


def contradiction_text(pred: dict) -> str:
    info = pred.get("contradiction") or {}
    out = []
    assessments = {a.get("item_id"): a for a in info.get("assessments") or [] if isinstance(a, dict)}
    queries = {q.get("hypothesis_id"): q for q in info.get("queries") or [] if isinstance(q, dict)}
    for h in info.get("hypotheses") or []:
        hid = h.get("hypothesis_id")
        a = assessments.get(hid, {})
        out.append(f"{hid}: {h.get('challenge')}\n  query: {queries.get(hid, {}).get('query') or h.get('search_query')}\n"
                   f"  -> {a.get('assessment') or 'NO ASSESSMENT'}")
        out += [f"     {_cite(e)}" for e in a.get("evidence") or [] if isinstance(e, dict)]
    if info.get("assessments") is None:
        out.append("Reconciliation produced no final verdict (A3 kept its initial verdict).")
    if info.get("guard_reverted"):
        out.append(f"Guard reverted the model's change: {info['guard_reverted']}")
    return "\n".join(out)


def audit_text(pred: dict, trace: dict | None) -> str:
    notes = []
    for r in citation_audit(pred, trace):
        if r["xbrl_value_in_quote"] is False:
            notes.append(f"{r['evidence_id']}: quote does not contain the cited XBRL figure")
        if r["period_matches_claim"] is False:
            notes.append(f"{r['evidence_id']}: period {r['period_end']} ≠ claim period {r['stated_period_end']}")
        if r["after_cutoff"]:
            notes.append(f"{r['evidence_id']}: filed after the cutoff")
    return "\n".join(notes) or "no automatic flag"


def build_rows(run_id: str, runs_dir: str = RUNS_DIR) -> list[dict]:
    run, ref = load_run(run_id, runs_dir), load_reference()["labels"]
    idx = {(p["approach"], p["claim_id"]): p for p in run["predictions"]}
    rows = []
    for r in read_review(run_id):
        cid = r["claim_id"]
        a2, a3 = idx[(A, cid)], idx[(B, cid)]
        g = ref[cid]
        outcome = "A2 only correct" if a2["predicted_label"] == g["label"] else "A3 only correct"
        trace = load_trace(run, a3)
        rows.append({"Review flag": flag(r), "Claim ID": cid, "Company": a3.get("company"), "Category": a3.get("claim_category"),
                     "Claim": g["claim"], "Evidence cutoff": a3.get("as_of_date"), "Reference label": g["label"],
                     "Reference rationale": g.get("rationale"), "A2 final": a2["predicted_label"],
                     "A3 initial": a3.get("initial_label"), "A3 final": a3["predicted_label"], "Outcome": outcome,
                     "A3 change reason": (a3.get("contradiction") or {}).get("change_reason"),
                     "Contradiction trace": contradiction_text(a3),
                     "A3 final citations": "\n".join(_cite(c) for c in a3.get("citations") or []) or "(none)",
                     "A2 final citations": "\n".join(_cite(c) for c in a2.get("citations") or []) or "(none)",
                     "Citation audit": audit_text(a3, trace),
                     "Proposed mechanism": r["mechanism"], "Mechanism definition": MECHANISMS.get(r["mechanism"], ""),
                     "Counter-evidence genuine?": r["counterevidence_genuine"],
                     "Interpretation correct?": r["interpretation_correct"],
                     "Final citations entail verdict?": r["final_citations_entail_verdict"],
                     "Analyst note": r["note"], H_CONFIRM: r.get("researcher_confirmed") or None,
                     H_NOTE: r.get("researcher_note") or None})
    rows.sort(key=lambda x: (x["Review flag"] is None, x["Outcome"], x["Claim ID"]))
    return rows


def export(run_id: str, out: str | None = None, runs_dir: str = RUNS_DIR) -> str:
    rows = build_rows(run_id, runs_dir)
    out = out or os.path.join(REVIEW_DIR, f"discordant_case_review__{run_id}.xlsx")
    wb = Workbook()
    _instructions(wb.active, rows)
    ws = wb.create_sheet("Cases")
    head = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    body, bold = Font(name=FONT, size=10), Font(name=FONT, size=10, bold=True)
    edit, flagged = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="FCE4D6")
    thin = Side(style="thin", color="D9D9D9")
    names = [c for c, _ in COLUMNS]
    for j, (h, w) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=j, value=h)
        cell.font, cell.alignment = head, Alignment(wrap_text=True, vertical="center")
        cell.fill = PatternFill("solid", fgColor="C00000" if h in (H_CONFIRM, H_NOTE) else "1F4E78")
        ws.column_dimensions[cell.column_letter].width = w
    for i, r in enumerate(rows, 2):
        for j, h in enumerate(names, 1):
            cell = ws.cell(row=i, column=j, value=r[h])
            cell.font = bold if h in ("Review flag", "Claim ID") else body
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(bottom=thin)
            if h in (H_CONFIRM, H_NOTE):
                cell.fill = edit
            elif r["Review flag"] and h in ("Review flag", "Claim ID"):
                cell.fill = flagged
        ws.row_dimensions[i].height = 260
    dv = DataValidation(type="list", formula1='"' + ",".join(DECISIONS) + '"', allow_blank=True,
                        error="Choose " + ", ".join(DECISIONS), showErrorMessage=True)
    ws.add_data_validation(dv)
    col = ws.cell(row=1, column=names.index(H_CONFIRM) + 1).column_letter
    dv.add(f"{col}2:{col}{len(rows) + 1}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(names)).column_letter}{len(rows) + 1}"
    defs = wb.create_sheet("Error classes")
    for j, (h, w) in enumerate((("Code", 38), ("Definition", 100)), 1):
        c = defs.cell(row=1, column=j, value=h)
        c.font, c.fill = head, PatternFill("solid", fgColor="1F4E78")
        defs.column_dimensions[c.column_letter].width = w
    for i, (k, v) in enumerate(MECHANISMS.items(), 2):
        defs.cell(row=i, column=1, value=k).font = bold
        c = defs.cell(row=i, column=2, value=v)
        c.font, c.alignment = body, Alignment(wrap_text=True)
    wb.save(out)
    return out


def _instructions(ws, rows: list[dict]) -> None:
    ws.title = "คำแนะนำ"
    title, bold, body = Font(name=FONT, bold=True, size=14), Font(name=FONT, bold=True, size=11), Font(name=FONT, size=10.5)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110
    flagged = [r["Claim ID"] for r in rows if r["Review flag"]]
    lines = [
        ("ยืนยันการจำแนกสาเหตุข้อผิดพลาด: A2 กับ A3 ตอบต่างกัน", None),
        ("", None),
        ("งานนี้คืออะไร", f"{len(rows)} claim ที่ A2 และ A3 ตอบต่างกัน ผู้ช่วยวิเคราะห์ AI (Claude Opus 5.5) อ่าน trace "
                          "แล้วเสนอสาเหตุ (Proposed mechanism) และประเมินว่าหลักฐานแย้งมีจริงไหม ตีความถูกไหม และ citation "
                          "สุดท้ายรองรับคำตอบไหม — ขอให้ผู้วิจัยตรวจแต่ละข้ออย่างอิสระ"),
        ("ช่องที่ต้องกรอก", f"เฉพาะคอลัมน์สีเหลือง '{H_CONFIRM}' (dropdown) และ '{H_NOTE}' ช่องอื่นห้ามแก้"),
        ("CONFIRMED", "เห็นด้วยกับการจำแนกสาเหตุและการประเมินทั้ง 3 ช่อง"),
        ("PARTIALLY_CONFIRMED", "เห็นด้วยบางส่วน — ระบุใน note ว่าช่องไหนควรเป็นอะไร (เช่น 'mechanism ควรเป็น TEMPORAL_MISMATCH')"),
        ("REJECTED", "ไม่เห็นด้วยกับการจำแนก — ระบุเหตุผลใน note"),
        ("UNSURE", "ตัดสินไม่ได้ — รายงานแยก"),
        ("ข้อที่ต้องดูละเอียด", f"{', '.join(flagged)} (แถบสีส้ม, เรียงไว้บนสุด) — ผู้วิเคราะห์ประเมินการตีความเป็น "
                               "DEBATABLE คือเฉลยเองอาจโต้แย้งได้ ถ้าคิดว่าเฉลยควรเปลี่ยนให้เขียนใน note "
                               "(การยืนยันนี้ไม่เปลี่ยนเฉลยหรือผลหลัก)"),
        ("อ่านคอลัมน์", "Contradiction trace = สมมติฐานที่ A3 ตั้ง, คำค้น, ผลประเมิน และหลักฐานที่อ้างทีละข้อ; "
                        "Citation audit = ธงอัตโนมัติ (ตัวเลข XBRL ไม่ตรง quote, งวดไม่ตรง claim, ยื่นหลัง cutoff); "
                        "trace เต็มอยู่ที่ results/runs/<run>/traces/A3_contradiction_aware/<claim>.json"),
        ("ตัวอย่างการกรอก (ไม่อยู่ในรายการ)", "researcher_confirmed = PARTIALLY_CONFIRMED; researcher_note = "
                                             "\"หลักฐานแย้งมีจริง แต่สาเหตุหลักคือใช้ข้อมูลข้ามงวด ไม่ใช่ predicate กำกวม\""),
        ("หลังกรอกเสร็จ", "research/.venv/bin/python research/scripts/discordant_review_workbook.py import <ไฟล์> --run <run_id> "
                          "— คัดลอกเฉพาะ 2 คอลัมน์นี้กลับเข้า CSV"),
    ]
    for i, (a, b) in enumerate(lines, 1):
        ws.cell(row=i, column=1, value=a).font = title if i == 1 else bold
        if b:
            c = ws.cell(row=i, column=2, value=b)
            c.font, c.alignment = body, Alignment(wrap_text=True, vertical="top")
    ws.sheet_view.showGridLines = False


def import_workbook(path: str, run_id: str) -> str:
    """Copy researcher_confirmed / researcher_note into the review CSV.
    Refuses edited analyst columns, unknown or missing claims, values
    outside DECISIONS, and overwriting decisions already recorded."""
    review = read_review(run_id)
    by = {r["claim_id"]: r for r in review}
    ws = load_workbook(path, data_only=True)["Cases"]
    head = [c.value for c in ws[1]]
    col = {h: head.index(h) for h in ("Claim ID", "Proposed mechanism", "Counter-evidence genuine?", "Interpretation correct?",
                                      "Final citations entail verdict?", H_CONFIRM, H_NOTE)}
    seen = set()
    for row in ws.iter_rows(min_row=2, values_only=True):
        cid = row[col["Claim ID"]]
        if not cid:
            continue
        if cid not in by:
            raise SchemaError(f"unknown claim {cid}")
        r = by[cid]
        for key, h in zip(ANALYST, ("Proposed mechanism", "Counter-evidence genuine?", "Interpretation correct?",
                                    "Final citations entail verdict?")):
            if (row[col[h]] or "") != r[key]:
                raise SchemaError(f"{cid}: analyst column '{h}' was edited in the workbook")
        decision = (row[col[H_CONFIRM]] or "").strip().upper()
        if decision and decision not in DECISIONS:
            raise SchemaError(f"{cid}: '{decision}' is not one of {DECISIONS}")
        if decision and r.get("researcher_confirmed") and r["researcher_confirmed"] != decision:
            raise SchemaError(f"{cid}: a researcher decision is already recorded")
        r["researcher_confirmed"], r["researcher_note"] = decision, row[col[H_NOTE]] or r.get("researcher_note") or ""
        seen.add(cid)
    if set(by) - seen:
        raise SchemaError(f"workbook is missing claims: {sorted(set(by) - seen)}")
    with open(review_path(run_id), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(review[0]))
        w.writeheader()
        w.writerows(review)
    return review_path(run_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--run", required=True)
    e.add_argument("--out")
    i = sub.add_parser("import")
    i.add_argument("workbook")
    i.add_argument("--run", required=True)
    args = ap.parse_args()
    if args.cmd == "export":
        print("wrote", export(args.run, args.out))
    else:
        print("updated", import_workbook(args.workbook, args.run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
