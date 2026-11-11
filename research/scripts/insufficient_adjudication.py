"""Blind adjudication of decisive answers on INSUFFICIENT_EVIDENCE claims.

The reference labels some claims INSUFFICIENT_EVIDENCE although a careful
reader could defend SUPPORTED or CONTRADICTED when the filing gives evidence
and the claim's wording has a reasonable, unambiguous reading. Whether an
approach's decisive answer is such a defensible reading cannot be checked
automatically (a citation can be real yet not support the answer), so a
person decides, case by case, without knowing which approach gave it.

    # 1) workbook for the adjudicator + a separate key (approach names)
    research/.venv/bin/python research/scripts/insufficient_adjudication.py export --run <run_id>
    # 2) after the workbook is filled in; --variant names the scoring it defines
    research/.venv/bin/python research/scripts/insufficient_adjudication.py import <filled.xlsx> --run <run_id> \
        --variant adjudicated      # case-by-case decisions
    #   --variant lenient          # every decisive answer accepted (upper bound)

Each row is one distinct answer (label + cited evidence) to one claim; the
model's own reasoning is left out because its wording reveals the approach;
approaches that gave the identical answer share a row. Answers are lettered
in a seeded random order per claim. The key mapping letters to approaches is
written next to, not inside, the workbook.
"""
import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import DATASET_DIR, load_split  # noqa: E402
from engine.reference import load_reference  # noqa: E402
from engine.runner import load_run, load_trace  # noqa: E402
from engine.schema import SchemaError  # noqa: E402

ADJ_DIR = os.path.join(DATASET_DIR, "adjudication")
DECISIONS = ("ACCEPTABLE", "NOT_ACCEPTABLE", "UNSURE")
DECISIVE = ("SUPPORTED", "CONTRADICTED")
FONT = "Arial"
H_DECISION, H_NOTE = "Decision [EDIT]", "Note [EDIT]"
COLUMNS = ["Case ID", "Claim ID", "Company", "Category", "Claim", "Evidence cutoff", "Reference label",
           "Reference rationale", "Answer", "Answer label", "Cited evidence",
           "SEC links", H_DECISION, H_NOTE]


def key_path(run_id: str) -> str:
    return os.path.join(ADJ_DIR, f"insufficient_alternatives_key__{run_id}.json")


VARIANT_NAME = __import__("re").compile(r"^[a-z][a-z0-9_]{0,31}$")


def result_path(run_id: str, variant: str) -> str:
    if not VARIANT_NAME.match(variant or ""):
        raise SchemaError(f"variant must be a short lower-case name, got {variant!r}")
    return os.path.join(ADJ_DIR, f"insufficient_alternatives__{run_id}__{variant}.jsonl")


def _fmt_values(u: dict) -> str:
    vals = u.get("values") or []
    unit = u.get("unit") or ""
    out = []
    for v in vals:
        if unit == "USD" and abs(v) >= 1e6:
            out.append(f"${v / 1e6:,.0f}M")
        elif unit in ("ratio", "ratio_points"):
            out.append(f"{v:.2%}" if unit == "ratio" else f"{v * 100:+.2f} pp")
        else:
            out.append(f"{v:,.4g} {unit}".strip())
    return ", ".join(out)


def evidence_lines(pred: dict, trace: dict) -> tuple[str, list[str]]:
    units = {u["evidence_id"]: u for u in trace.get("evidence", [])}
    items = pred["supporting_evidence"] if pred["predicted_label"] == "SUPPORTED" else pred["contradicting_evidence"]
    lines, links = [], []
    for c in items:
        u = units.get(c["evidence_id"], {})
        where = f"{u.get('form', c.get('form'))} filed {u.get('filed', c.get('filed'))}"
        if u.get("kind") == "filing_passage":
            lines.append(f"[{where}] \"{c.get('quote', '').strip()}\"")
        else:
            lines.append(f"[{where}, {'computed' if u.get('kind') == 'derived_metric' else 'XBRL'}] "
                         f"{u.get('locator', '')} = {_fmt_values(u)}")
        if u.get("source_url") and u["source_url"] not in links:
            links.append(u["source_url"])
    return "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines)) or "(none)", links


def build_cases(run: dict, reference: dict, seed: int = 20261111) -> list[dict]:
    claims = {c.claim_id: c for c in load_split("gold")}
    by_claim = {}
    for p in run["predictions"]:
        by_claim.setdefault(p["claim_id"], []).append(p)
    rng = random.Random(seed)
    cases = []
    for cid in sorted(by_claim):
        ref = reference["labels"].get(cid)
        if not ref or ref["label"] != "INSUFFICIENT_EVIDENCE":
            continue
        groups = {}
        for p in sorted(by_claim[cid], key=lambda p: p["approach"]):
            if p.get("predicted_label") not in DECISIVE:
                continue
            ev, links = evidence_lines(p, load_trace(run, p))
            g = groups.setdefault((p["predicted_label"], ev), {"label": p["predicted_label"], "evidence": ev, "links": links,
                                                               "approaches": []})
            g["approaches"].append(p["approach"])
        answers = list(groups.values())
        rng.shuffle(answers)
        c = claims[cid]
        for i, a in enumerate(answers):
            cases.append({"case_id": f"{cid}-{chr(65 + i)}", "claim_id": cid, "company": c.company, "category": c.claim_category,
                          "claim": c.claim, "cutoff": c.as_of_date, "reference_label": ref["label"],
                          "reference_rationale": ref["rationale"] or "", "answer": chr(65 + i), **a})
    return cases


def export(run_id: str, out: str, seed: int = 20261111) -> tuple[str, str]:
    run, reference = load_run(run_id), load_reference()
    cases = build_cases(run, reference, seed)
    kp = key_path(run_id)
    if os.path.exists(kp):
        raise SchemaError(f"{kp} exists; an adjudication for this run was already exported")
    os.makedirs(ADJ_DIR, exist_ok=True)
    with open(kp, "w") as f:
        json.dump({"run_id": run_id, "reference": reference["provenance"]["dataset_version"],
                   "reference_sha256": reference["provenance"]["sha256"], "seed": seed,
                   "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "cases": {c["case_id"]: {"claim_id": c["claim_id"], "label": c["label"], "approaches": c["approaches"]}
                             for c in cases}}, f, indent=1)

    wb = Workbook()
    ins = wb.active
    ins.title = "คำแนะนำ"
    _instructions(ins, len(cases), len({c["claim_id"] for c in cases}))
    ws = wb.create_sheet("Cases")
    head = Font(name=FONT, bold=True, color="FFFFFF", size=10)
    body = Font(name=FONT, size=10)
    edit = PatternFill("solid", fgColor="FFF2CC")
    thin = Side(style="thin", color="D9D9D9")
    for j, h in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=j, value=h)
        cell.font, cell.alignment = head, Alignment(wrap_text=True, vertical="center")
        cell.fill = PatternFill("solid", fgColor="C00000" if h in (H_DECISION, H_NOTE) else "1F4E78")
    for i, c in enumerate(cases, 2):
        vals = [c["case_id"], c["claim_id"], c["company"], c["category"], c["claim"], c["cutoff"], c["reference_label"],
                c["reference_rationale"], c["answer"], c["label"], c["evidence"],
                "\n".join(c["links"]), None, None]
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=j, value=v)
            cell.font, cell.alignment = body, Alignment(wrap_text=True, vertical="top")
            cell.border = Border(bottom=thin)
            if COLUMNS[j - 1] in (H_DECISION, H_NOTE):
                cell.fill = edit
    for j, w in enumerate([16, 15, 8, 11, 40, 11, 14, 45, 7, 14, 80, 40, 18, 30], 1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
    dv = DataValidation(type="list", formula1='"' + ",".join(DECISIONS) + '"', allow_blank=True,
                        error="เลือก ACCEPTABLE, NOT_ACCEPTABLE หรือ UNSURE", showErrorMessage=True)
    ws.add_data_validation(dv)
    dcol = ws.cell(row=1, column=COLUMNS.index(H_DECISION) + 1).column_letter
    dv.add(f"{dcol}2:{dcol}{len(cases) + 1}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(COLUMNS)).column_letter}{len(cases) + 1}"
    wb.save(out)
    return out, kp


def _instructions(ws, n_cases: int, n_claims: int) -> None:
    title, bold, body = Font(name=FONT, bold=True, size=14), Font(name=FONT, bold=True, size=11), Font(name=FONT, size=10.5)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110
    rows = [
        ("ตัดสินคำตอบที่ฟันธงในข้อที่เฉลยเป็น INSUFFICIENT_EVIDENCE", None),
        ("", None),
        ("งานนี้คืออะไร", f"มี {n_cases} คำตอบ จาก {n_claims} claim ที่เฉลย (Final Gold) เป็น INSUFFICIENT_EVIDENCE แต่ระบบตรวจสอบตอบ "
                          "SUPPORTED หรือ CONTRADICTED ให้ตัดสินว่าคำตอบนั้น 'รับได้' หรือไม่"),
        ("รับได้ (ACCEPTABLE)", "หลักฐานที่อ้างมีอยู่จริงในรายงาน และสนับสนุนคำตอบนั้นจริง โดยตีความถ้อยคำของ claim "
                                "ได้ชัดเจนไม่กำกวม (เช่น 'offset' = ชดเชยบางส่วนก็นับ) จนผู้เชี่ยวชาญที่รอบคอบจะเห็นด้วย"),
        ("รับไม่ได้ (NOT_ACCEPTABLE)", "หลักฐานไม่สนับสนุนคำตอบ, อ้างสาเหตุที่รายงานไม่ได้ระบุ, ใช้งวด/ตัวเลขผิด, "
                                      "หรือต้องตั้งเกณฑ์เองโดยไม่มีเหตุผลรองรับ (เช่น 'heavily' โดยไม่มีมาตรวัด)"),
        ("ไม่แน่ใจ (UNSURE)", "ใช้เมื่อตัดสินไม่ได้จริงๆ — จะรายงานแยก ไม่นับเป็นถูก"),
        ("ตัดสินที่อะไร", "ตัดสินที่ 'คำตอบ + หลักฐานที่อ้าง' เท่านั้น ไม่ใช่ว่าเฉลยผิด ถ้าคิดว่าเฉลยควรเปลี่ยน ให้เขียนใน Note"),
        ("ปิดชื่อระบบ", "คำตอบแต่ละข้อติดป้าย A, B, C แบบสุ่ม ไม่บอกว่ามาจากแนวทางไหน — โปรดอย่าเปิดไฟล์ key (.json) "
                        "ที่อยู่ในโฟลเดอร์เดียวกันจนกว่าจะตัดสินครบ"),
        ("ช่องที่ต้องกรอก", f"เฉพาะคอลัมน์สีเหลือง '{H_DECISION}' (เลือกจาก dropdown) และ '{H_NOTE}' (ไม่บังคับ)"),
        ("หลักฐาน", "คอลัมน์ 'Cited evidence' แสดงข้อความที่คัดลอกจากรายงาน หรือค่า XBRL/ค่าที่คำนวณ พร้อมแบบฟอร์มและวันยื่น; "
                    "'SEC links' เปิดรายงานต้นฉบับได้ ทุกฉบับยื่นก่อนวันตัดหลักฐานของ claim"),
        ("ตัวอย่าง (ไม่อยู่ในรายการ)", "GOLD-AMZN-14: \"Amazon's growth in advertising services in the quarter ended September 30, 2026 "
                     "offset slower growth in online stores.\" — หลักฐาน: Advertising services 17,703 → 19,637 ล้านดอลลาร์ (+10.9%) "
                     "ขณะที่ Online stores +1.6% → ACCEPTABLE เพราะ 'offset' ไม่จำเป็นต้องชดเชยทั้งหมด (ข้อนี้ v3 เปลี่ยนเฉลยเป็น SUPPORTED แล้ว)"),
    ]
    for i, (a, b) in enumerate(rows, 1):
        ws.cell(row=i, column=1, value=a).font = title if i == 1 else bold
        if b:
            c = ws.cell(row=i, column=2, value=b)
            c.font, c.alignment = body, Alignment(wrap_text=True, vertical="top")
    ws.sheet_view.showGridLines = False


def import_workbook(path: str, run_id: str, adjudicator: str, variant: str) -> str:
    key = json.load(open(key_path(run_id)))
    out = result_path(run_id, variant)
    if os.path.exists(out):
        raise SchemaError(f"{out} exists; adjudications are recorded once per run")
    ws = load_workbook(path, data_only=True)["Cases"]
    head = [c.value for c in ws[1]]
    col = {h: head.index(h) for h in ("Case ID", "Answer label", H_DECISION, H_NOTE)}
    rows, missing = [], []
    for r in ws.iter_rows(min_row=2, values_only=True):
        cid = r[col["Case ID"]]
        if not cid:
            continue
        if cid not in key["cases"]:
            raise SchemaError(f"unknown case {cid}")
        decision = (r[col[H_DECISION]] or "").strip().upper()
        if decision not in DECISIONS:
            missing.append(cid)
            continue
        k = key["cases"][cid]
        if r[col["Answer label"]] != k["label"]:
            raise SchemaError(f"{cid}: answer label edited in the workbook")
        rows.append({"case_id": cid, "claim_id": k["claim_id"], "label": k["label"], "approaches": k["approaches"],
                     "decision": decision, "note": r[col[H_NOTE]], "adjudicator": adjudicator, "variant": variant,
                     "source_workbook": os.path.basename(path),
                     "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    if missing:
        raise SchemaError(f"{len(missing)} case(s) without a decision: {missing[:10]}")
    if set(key["cases"]) - {r["case_id"] for r in rows}:
        raise SchemaError("workbook is missing cases from the key")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--run", required=True)
    e.add_argument("--out", default=None)
    i = sub.add_parser("import")
    i.add_argument("workbook")
    i.add_argument("--run", required=True)
    i.add_argument("--adjudicator", default="researcher")
    i.add_argument("--variant", required=True, help="name of the scoring these decisions define, e.g. adjudicated / lenient")
    a = ap.parse_args()
    if a.cmd == "export":
        out = a.out or os.path.join(ADJ_DIR, f"INSUFFICIENT_adjudication__{a.run}.xlsx")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        wb, kp = export(a.run, out)
        print("workbook:", wb, "\nkey (do not open before deciding):", kp)
    else:
        print("recorded:", import_workbook(a.workbook, a.run, a.adjudicator, a.variant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
