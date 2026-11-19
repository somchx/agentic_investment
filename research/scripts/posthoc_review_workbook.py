"""POST-HOC EXPLORATORY: blind human-review workbook for evidence-grounded correctness (Task 3B), and its scorer.

build:  stratified random sample of 50 Gold claims (seed 20261119; 16 numerical, 17 interpretive, 17 ambiguous,
        drawn from the sorted claim ids of each category with random.Random(seed).sample; reference labels are not
        read when sampling), 2 rows per claim (A2_rag_numeric, A3v2_2e) = 100 rows in a seeded random order.
        The reviewer workbook has no arm name and no reference label; the mapping is a separate file.
score:  reads the filled reviewer workbook + mapping; refuses to report EGC while judgments are missing.

    research/.venv/bin/python research/scripts/posthoc_review_workbook.py build
    research/.venv/bin/python research/scripts/posthoc_review_workbook.py score
"""
import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine import RESEARCH_ROOT  # noqa: E402
from engine.corpus import doc_url, eligible_filings  # noqa: E402

SEED = 20261119
QUOTA = {"numerical": 16, "interpretive": 17, "ambiguous": 17}
ARMS = ("A2_rag_numeric", "A3v2_2e")
JUDGMENTS = ("SUPPORTED_BY_EVIDENCE", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED", "UNABLE_TO_ASSESS")
RUN = os.path.join(RESEARCH_ROOT, "results", "runs", "a3v2.2-gold150-20261118T112814Z")
OUT = os.path.join(RESEARCH_ROOT, "results", "posthoc_20261119", "human_review")
REVIEW = os.path.join(OUT, "evidence_review_blind.xlsx")
MAPPING = os.path.join(OUT, "mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx")
FONT = "Arial"


def sha(path: str) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def cite_text(c: dict, i: int) -> str:
    head = f"[{i}] {c.get('form') or c.get('kind') or '?'} {c.get('accession_number') or ''} (filed {c.get('filed') or '?'}, period end {c.get('period_end') or '?'})"
    body = (c.get("quote") or "").strip() or f"(computed from XBRL: {c.get('locator') or ''})"
    return f"{head}\n\"{body}\""


def build() -> None:
    if os.path.exists(REVIEW) or os.path.exists(MAPPING):
        raise SystemExit("workbook exists; not overwritten")
    os.makedirs(OUT, exist_ok=True)
    claims = {r["claim_id"]: r for r in map(json.loads, open(os.path.join(RESEARCH_ROOT, "datasets", "gold_claims.jsonl")))}
    rng = random.Random(SEED)
    sample = []
    for cat, k in QUOTA.items():
        sample += rng.sample(sorted(c for c, r in claims.items() if r["claim_category"] == cat), k)
    P = {}
    for r in map(json.loads, open(os.path.join(RUN, "predictions.jsonl"))):
        if r["approach"] in ARMS:
            P[(r["approach"], r["claim_id"])] = r
    rows = [(cid, arm) for cid in sample for arm in ARMS]
    rng.shuffle(rows)

    wb = Workbook()
    guide = wb.active
    guide.title = "คู่มือผู้ตรวจ"
    lines = [
        ("คู่มือผู้ตรวจ: Evidence Review (POST-HOC EXPLORATORY)", True),
        ("", False),
        ("เป้าหมาย: ตัดสินว่า หลักฐานที่ระบบอ้าง รองรับ 'คำตอบของระบบ' ในแต่ละแถวจริงหรือไม่", True),
        ("ไม่ต้องตัดสินว่าคำตอบถูกหรือผิดเมื่อเทียบเฉลย และไม่ต้องเดาว่าแถวไหนมาจากระบบใด", False),
        ("", False),
        ("ขั้นตอน (ราว 2–3 นาทีต่อแถว, 100 แถว)", True),
        ("1. อ่าน claim, วันตัดข้อมูล (as_of_date) และคำตอบของระบบ (system_answer)", False),
        ("2. อ่านหลักฐานที่ระบบอ้าง (cited_evidence) ถ้าจำเป็นเปิดเอกสาร SEC จากลิงก์ใน source_links หรือ filings_available_at_as_of_date (เอกสารทั้งหมดที่ระบบใช้ได้สำหรับ claim นั้น)", False),
        ("3. เลือก judgment จาก dropdown หนึ่งค่า", False),
        ("4. เขียนเหตุผลสั้นๆ ใน reviewer_reason และระบุ citation ที่ใช้ตัดสิน (เช่น [1] หรือ accession + ข้อความ) ใน reviewer_citation", False),
        ("", False),
        ("ความหมายของ judgment", True),
        ("SUPPORTED_BY_EVIDENCE: หลักฐานที่อ้างรองรับคำตอบครบถ้วน ทั้งตัวเลข งวด และขอบเขต (บริษัท/segment) ตรงกับ claim", False),
        ("PARTIALLY_SUPPORTED: หลักฐานรองรับบางส่วน เช่น ครอบคลุมเพียงบางส่วนของ claim หรือต้องอนุมานเพิ่ม", False),
        ("NOT_SUPPORTED: หลักฐานไม่รองรับคำตอบ ผิดงวด ผิดขอบเขต หรือขัดกับคำตอบ", False),
        ("UNABLE_TO_ASSESS: ตัดสินไม่ได้ เช่น ไม่มีหลักฐานที่อ้าง หรือเปิดเอกสารไม่ได้ (ระบุเหตุผล)", False),
        ("", False),
        ("กรณี system_answer = INSUFFICIENT_EVIDENCE", True),
        ("ให้ตัดสินว่าเหตุผลและหลักฐานที่อ้างแสดงอย่างสมเหตุสมผลหรือไม่ว่า เอกสารที่ยื่นภายใน as_of_date ไม่พอจะยืนยันหรือแย้ง claim", False),
        ("ถ้าผู้ตรวจพบหลักฐานชัดเจนในเอกสารที่ตัดสิน claim ได้ ให้เลือก NOT_SUPPORTED และอ้างหลักฐานนั้น", False),
        ("", False),
        ("ข้อห้าม", True),
        ("ห้ามเปิดไฟล์ mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx จนกว่าจะตรวจครบทุกแถว", False),
        ("ห้ามใช้หลักฐานที่ยื่นหลัง as_of_date", False),
        ("ห้ามแก้คอลัมน์อื่นนอกจาก judgment, reviewer_reason, reviewer_citation (ช่องสีเหลือง)", False),
        ("", False),
        (f"สุ่ม 50 claims จาก Gold 150 แบบแบ่งชั้นตามหมวด (seed {SEED}: ตัวเลข 16, ตีความ 17, กำกวม 17) × 2 ระบบ = 100 แถว เรียงแบบสุ่ม", False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        guide.cell(i, 1, t).font = Font(name=FONT, bold=bold, size=12 if i == 1 else 11)
    guide.column_dimensions["A"].width = 130

    ws = wb.create_sheet("review")
    head = ["review_id", "company", "as_of_date", "claim", "system_answer", "system_reasoning", "cited_evidence", "source_links",
            "filings_available_at_as_of_date", "judgment", "reviewer_reason", "reviewer_citation"]
    widths = [10, 9, 11, 50, 18, 55, 70, 45, 55, 24, 40, 30]
    for j, (h, w) in enumerate(zip(head, widths), 1):
        c = ws.cell(1, j, h)
        c.font = Font(name=FONT, bold=True)
        ws.column_dimensions[c.column_letter].width = w
    yellow = PatternFill("solid", fgColor="FFFF00")
    dv = DataValidation(type="list", formula1='"' + ",".join(JUDGMENTS) + '"', allow_blank=True)
    ws.add_data_validation(dv)
    mapping = []
    for i, (cid, arm) in enumerate(rows, 1):
        p, cl = P[(arm, cid)], claims[cid]
        cites = p.get("citations") or []
        rid = f"R{i:03d}"
        vals = [rid, cl["company"], cl["as_of_date"], cl["claim"], p["predicted_label"], (p.get("reasoning_summary") or "").strip(),
                "\n\n".join(cite_text(c, k) for k, c in enumerate(cites, 1)) or "(no citation)",
                "\n".join(sorted({c["source_url"] for c in cites if c.get("source_url")})),
                "\n".join(f"{f['form']} filed {f['filed']} (period end {f['report_date']}): {doc_url(f)}"
                          for f in eligible_filings(cl["company"], cl["as_of_date"], {"10-K", "10-Q"}, {"10-K": 1, "10-Q": 2})),
                None, None, None]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i + 1, j, v)
            c.font = Font(name=FONT)
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if j >= 10:
                c.fill = yellow
        dv.add(f"J{i + 1}")
        mapping.append([rid, cid, arm, cl["claim_category"], p["predicted_label"]])
    ws.freeze_panes = "B2"
    wb.save(REVIEW)

    from engine.reference import load_reference
    ref = load_reference()["labels"]
    mb = Workbook()
    m = mb.active
    m.title = "mapping"
    m.append(["review_id", "claim_id", "arm", "claim_category", "predicted_label", "reference_label", "label_correct"])
    for r in mapping:
        m.append(r + [ref[r[1]]["label"], r[4] == ref[r[1]]["label"]])
    for row in m.iter_rows():
        for c in row:
            c.font = Font(name=FONT, bold=c.row == 1)
    mb.save(MAPPING)
    json.dump({"status": "POST-HOC EXPLORATORY", "seed": SEED, "quota": QUOTA, "arms": ARMS, "sample_claims": sample,
               "row_order": [f"{a}|{c}" for c, a in rows], "script_sha256": sha(__file__),
               "inputs_sha256": {"predictions": sha(os.path.join(RUN, "predictions.jsonl")),
                                 "gold_claims": sha(os.path.join(RESEARCH_ROOT, "datasets", "gold_claims.jsonl"))},
               "outputs_sha256": {"review_workbook_as_built": sha(REVIEW), "mapping": sha(MAPPING)}},
              open(os.path.join(OUT, "sample_manifest.json"), "w"), indent=1)


def score() -> dict:
    rv = load_workbook(REVIEW, data_only=True)["review"]
    hdr = [c.value for c in rv[1]]
    J = {r[0]: (r[hdr.index("judgment")] or "").strip() for r in rv.iter_rows(min_row=2, values_only=True) if r[0]}
    mp = load_workbook(MAPPING, data_only=True)["mapping"]
    M = {r[0]: r for r in mp.iter_rows(min_row=2, values_only=True)}
    bad = {k: v for k, v in J.items() if v and v not in JUDGMENTS}
    missing = [k for k, v in J.items() if not v]
    res = {"status": "POST-HOC EXPLORATORY", "rows": len(J), "judged": len(J) - len(missing), "missing": len(missing),
           "invalid_values": bad}
    if missing or bad:
        res["note"] = "review incomplete: EGC is not computed"
        return res
    for arm in ARMS:
        ids = [k for k in J if M[k][2] == arm]
        unable = [k for k in ids if J[k] == "UNABLE_TO_ASSESS"]
        assessed = [k for k in ids if J[k] != "UNABLE_TO_ASSESS"]
        res[arm] = {"rows": len(ids), "unable_to_assess": len(unable), "assessed": len(assessed),
                    "judgments": dict(Counter(J[k] for k in ids)),
                    "label_correct_assessed": sum(bool(M[k][6]) for k in assessed),
                    "EGC_strict": sum(bool(M[k][6]) and J[k] == "SUPPORTED_BY_EVIDENCE" for k in assessed),
                    "EGC_lenient": sum(bool(M[k][6]) and J[k] in ("SUPPORTED_BY_EVIDENCE", "PARTIALLY_SUPPORTED") for k in assessed)}
        for key in ("EGC_strict", "EGC_lenient", "label_correct_assessed"):
            res[arm][key + "_rate"] = round(res[arm][key] / len(assessed), 4) if assessed else None
    json.dump(res, open(os.path.join(OUT, "egc_result.json"), "w"), indent=1)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "score"))
    a = ap.parse_args()
    if a.cmd == "build":
        build()
        print("wrote", os.path.relpath(OUT, RESEARCH_ROOT))
    else:
        print(json.dumps(score(), indent=1, ensure_ascii=False))
