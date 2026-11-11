"""Excel workbook for independent human reviewers (gold annotation).

    # build a blank workbook from the claim files (default: held-out gold claims only)
    research/.venv/bin/python research/scripts/annotation_workbook.py export \
        --out research/datasets/workbooks/annotation_workbook.xlsx

    # convert one reviewer's filled workbook into datasets/annotations/<reviewer_id>.jsonl
    research/.venv/bin/python research/scripts/annotation_workbook.py import filled.xlsx

Each reviewer gets their own copy and types their reviewer id on the instructions
sheet. The workbook carries claims and filing metadata only -- never a label,
a model output or a run -- so it can be sent to reviewers as is. Import
validates every row with engine.schema.Annotation plus the evidence-cutoff and
company checks, and refuses to overwrite an existing reviewer file.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.formatting.rule import FormulaRule  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.workbook.defined_name import DefinedName  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import ANNOTATION_DIR, DATASET_DIR, GOLD_PATH, load_claims  # noqa: E402
from engine.schema import LABELS, SOURCE_FORMS, Annotation, EvidenceRef, SchemaError  # noqa: E402
from engine.corpus import RetrievalConfig, _cik, select_filings  # noqa: E402

GUIDELINE_VERSION = "gold-guidelines-1.0"
MANIFEST_PATH = os.path.join(DATASET_DIR, "corpus_manifest.json")
EVIDENCE_ROWS = 600
SIDES = {"supporting": "supporting_evidence", "contradicting": "contradictory_evidence"}
KINDS = ("filing_passage", "xbrl_fact")
UNUSABLE_PREFIX = "UNUSABLE: "

FONT = "Arial"
INPUT_FILL = PatternFill("solid", start_color="FFF2CC")
FIXED_FILL = PatternFill("solid", start_color="F2F2F2")
HEAD_FILL = PatternFill("solid", start_color="1F3864")
THIN = Border(*(Side(style="thin", color="BFBFBF"),) * 4)
WRAP = Alignment(wrap_text=True, vertical="top")

# Claims sheet: (header, width, kind) -- kind "fixed" = claim data, "input" = reviewer fills, "check" = formula.
# One link column per eligible filing sits between the claim data and the inputs, so import
# finds input columns by header, not position.
CLAIM_FIXED = [
    ("Claim ID", 15, "fixed"), ("บริษัท\nCompany", 9, "fixed"), ("ข้อความ Claim\nClaim text", 60, "fixed"),
    ("หมวด\nCategory", 13, "fixed"), ("ความยาก\nDifficulty", 10, "fixed"),
    ("งวดที่อ้างถึง\nReporting period", 13, "fixed"), ("วันตัดหลักฐาน\nEvidence cutoff", 13, "fixed"),
    ("แหล่งที่อนุญาต\nAllowed sources", 14, "fixed"),
    ("รายงานที่ใช้ได้ (ยื่นก่อนหรือในวันตัด)\nEligible filings", 40, "fixed"),
]
LINK_HEADER = "🔗 เปิดรายงาน SEC {i}\nOpen filing {i}"
H_LABEL, H_NOTES = "✎ Label", "✎ เหตุผล / หมายเหตุ\nReview notes"
H_UNUSABLE, H_MINUTES = "✎ ใช้ไม่ได้ (UNUSABLE)\nใส่ \"ใช่\" ถ้า claim ใช้ไม่ได้", "✎ เวลาที่ใช้ (นาที)\nMinutes spent"
CLAIM_INPUT = [(H_LABEL, 24, "input"), (H_NOTES, 45, "input"), (H_UNUSABLE, 16, "input"), (H_MINUTES, 11, "input")]
CLAIM_CHECK = [("จำนวนหลักฐาน\nEvidence rows", 11, "check"), ("สถานะ\nStatus", 30, "check")]
LINK_FONT = Font(name=FONT, size=10, color="0563C1", underline="single")
EVIDENCE_COLS = [
    ("✎ Claim ID", 15, "input"), ("✎ ฝั่ง\nSide", 14, "input"), ("✎ ประเภท\nKind", 15, "input"),
    ("✎ Accession number", 24, "input"), ("✎ ตำแหน่งในเอกสาร\nLocator (section / table)", 30, "input"),
    ("✎ ข้อความคัดลอกคำต่อคำ\nVerbatim quote", 70, "input"),
    ("✎ XBRL concept\n(เฉพาะ xbrl_fact)", 26, "input"), ("✎ Period end\n(เฉพาะ xbrl_fact)", 13, "input"),
    ("แบบฟอร์ม\nForm", 9, "check"), ("วันที่ยื่น\nFiled", 12, "check"), ("ตรวจสอบ\nCheck", 30, "check"),
    ("🔗 เปิดรายงาน SEC\nOpen filing", 16, "check"),
]
FILING_COLS = [("บริษัท\nCompany", 9), ("แบบฟอร์ม\nForm", 9), ("วันที่ยื่น\nFiled", 12),
               ("สิ้นงวด\nPeriod end", 12), ("Accession number", 24), ("ลิงก์ SEC\nSEC link", 70)]


def _style_header(ws, cols):
    for i, col in enumerate(cols, start=1):
        cell = ws.cell(row=1, column=i, value=col[0])
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        cell.border = THIN
        ws.column_dimensions[cell.column_letter].width = col[1]
    ws.row_dimensions[1].height = 48
    ws.freeze_panes = "B2"


def _style_cell(cell, kind):
    cell.font = Font(name=FONT, size=10)
    cell.alignment = WRAP
    cell.border = THIN
    if kind == "input":
        cell.fill = INPUT_FILL
    elif kind in ("fixed", "check"):
        cell.fill = FIXED_FILL


def _as_date(value) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def load_manifest() -> list[dict]:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    return sorted(rows, key=lambda r: (r["company"], r["filed"]))


def filing_url(f: dict) -> str:
    return (f"https://www.sec.gov/Archives/edgar/data/{int(_cik(f['company']))}/"
            f"{f['accession_number'].replace('-', '')}/{f['primary_document']}")


def eligible_filings(claim, filings: list[dict]) -> list[dict]:
    """Same documents the approaches retrieve from: the most recent filings per
    form (RetrievalConfig.max_filings_per_form) filed on or before the cutoff,
    so gold evidence never cites a filing no approach can see."""
    forms = {form for src in claim.allowed_sources for form in SOURCE_FORMS.get(src, ())}
    own = [f for f in filings if f["company"] == claim.company]
    picked = select_filings(own, claim.as_of_date, forms, RetrievalConfig().max_filings_per_form)
    return sorted(picked, key=lambda f: f["filed"])


# ------------------------------------------------------------------ export

def _instructions(ws, claims):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 95
    bold = Font(name=FONT, bold=True, size=11)
    body = Font(name=FONT, size=10)
    row = 1

    def put(a, b="", font=body, fill=None, height=None):
        nonlocal row
        ca, cb = ws.cell(row=row, column=1, value=a), ws.cell(row=row, column=2, value=b)
        for c in (ca, cb):
            c.font, c.alignment = font, WRAP
            if fill:
                c.fill = fill
        if height:
            ws.row_dimensions[row].height = height
        row += 1
        return cb

    put("แบบฟอร์มให้ผู้เชี่ยวชาญติดป้ายกำกับ (Gold annotation)",
        "Financial claim verification — ReasonCheck research", font=Font(name=FONT, bold=True, size=14))
    put("Guideline version", GUIDELINE_VERSION)
    put("จำนวน claim ทั้งหมด", f"=COUNTA(Claims!$A$2:$A${len(claims) + 1})")
    for company in dict.fromkeys(c.company for c in claims):
        put(f"    {company}", f'=COUNTIF(Claims!$B$2:$B${len(claims) + 1},"{company}")').alignment = Alignment(horizontal="left")
    put("", "กรองดูทีละบริษัทได้จากปุ่มลูกศรที่หัวคอลัมน์ “บริษัท” ในชีต Claims")
    reviewer = put("✎ Reviewer ID (ภาษาอังกฤษ ไม่มีเว้นวรรค เช่น rev_somchai)", "", font=bold, fill=INPUT_FILL)
    reviewer.border = THIN
    ws.parent.defined_names["ReviewerID"] = DefinedName("ReviewerID", attr_text=f"'{ws.title}'!${reviewer.column_letter}${reviewer.row}")
    put("✎ ชื่อผู้ตรวจ (ไม่บังคับ)", "", fill=INPUT_FILL)
    row += 1

    put("วิธีกรอก", "", font=bold)
    put("ช่องสีเหลือง (✎)", "ช่องที่ให้กรอก ช่องสีเทาเป็นข้อมูลของ claim และสูตรตรวจสอบ ห้ามแก้", fill=INPUT_FILL)
    put("1. ชีต Claims", "กดลิงก์ “🔗 เปิดรายงาน SEC” ในแถวของ claim เพื่อเปิดเอกสารต้นฉบับบนเว็บไซต์ SEC "
        "(มีเฉพาะรายงานที่ยื่นก่อนหรือในวันตัดหลักฐาน) แล้วเลือก Label จาก dropdown และเขียนเหตุผลสั้น ๆ "
        "คอลัมน์ “สถานะ” จะบอกว่า claim ไหนยังขาดอะไร", height=45)
    put("2. ชีต Evidence", "ใส่หลักฐานทีละแถว (หนึ่ง claim มีได้หลายแถว) เลือก Claim ID, ฝั่ง, ประเภท และ Accession "
        "จาก dropdown แล้ววางข้อความที่คัดลอกจากรายงานแบบคำต่อคำ คอลัมน์ “ตรวจสอบ” จะเตือนถ้ารายงานยื่นหลังวันตัด "
        "หรือเป็นของบริษัทอื่น และมีลิงก์ “เปิดรายงาน” กลับไปที่เอกสารที่อ้างถึง", height=45)
    put("3. ชีต Filings", "รายการรายงาน SEC ที่ใช้ได้ พร้อมลิงก์ไปยังเอกสารต้นฉบับ")
    put("4. ส่งกลับ", "บันทึกไฟล์แล้วส่งคืนผู้ดูแลชุดข้อมูล ห้ามส่งให้ผู้ตรวจคนอื่นดูก่อนทั้งสองฝ่ายส่งครบ")
    row += 1

    put("กฎสำคัญ", "", font=bold)
    put("ตรวจคนเดียว", "ห้ามปรึกษาผู้ตรวจคนอื่นเรื่อง claim ใด ๆ ก่อนที่ทั้งสองคนจะส่งผลแล้ว")
    put("ห้ามใช้ AI", "ห้ามถาม ChatGPT, Claude หรือ AI อื่น และห้ามเปิดผลการทดลองของระบบ ผล label ต้องมาจากผู้เชี่ยวชาญเท่านั้น")
    put("วันตัดหลักฐาน", "ใช้เฉพาะรายงานที่ยื่นก่อนหรือในวัน “วันตัดหลักฐาน” ของ claim นั้น ห้ามใช้รายงานที่ยื่นทีหลัง ข่าว "
        "หรือสิ่งที่รู้ว่าเกิดขึ้นภายหลัง แม้จะรู้ว่าผลจริงออกมาเป็นอย่างไร", height=30)
    put("ตัดสินตามข้อความ", "ตัดสินทุกส่วนสำคัญของ claim ตามที่เขียน ทั้งตัวเลข ทิศทาง งวด และสาเหตุที่ claim อ้าง")
    row += 1

    put("ความหมายของ Label", "", font=bold)
    put("SUPPORTED", "รายงานยืนยันได้ว่า “ทุก” ส่วนสำคัญของ claim เป็นจริง (ตัวเลข/ทิศทาง/เกณฑ์ถูกต้องในงวดนั้น "
        "และถ้า claim อ้างสาเหตุ รายงานต้องระบุสาเหตุนั้นเอง เช่นใน MD&A)", height=30)
    put("CONTRADICTED", "รายงานแสดงว่าอย่างน้อยหนึ่งส่วนสำคัญเป็นเท็จ (ตัวเลขไปคนละทาง ไม่ถึงเกณฑ์ "
        "หรือรายงานบอกสาเหตุอื่นที่ต่างจาก claim)", height=30)
    put("INSUFFICIENT_EVIDENCE", "รายงานไม่ได้ยืนยันหรือหักล้างส่วนสำคัญบางส่วน (ตัวเลขถูกแต่รายงานไม่ได้บอกสาเหตุที่ claim อ้าง, "
        "งวดนั้นยังไม่ได้รายงาน ณ วันตัด, หรือ claim กำกวมจนตีความได้หลายแบบ)", height=30)
    put("ลำดับการตัดสิน", "1) แยก claim เป็นส่วนสำคัญ  2) มีส่วนใดถูกพิสูจน์ว่าเท็จ → CONTRADICTED  "
        "3) ทุกส่วนถูกพิสูจน์ว่าจริง → SUPPORTED  4) นอกนั้น → INSUFFICIENT_EVIDENCE", height=30)
    put("ข้อควรจำ", "• ตัวเลขขยับ ไม่ได้แปลว่ารู้สาเหตุ: margin เพิ่มอย่างเดียว ไม่พอจะยืนยัน “เพราะมีประสิทธิภาพขึ้น”\n"
        "• ตัวเลขที่ใกล้เคียงตามการปัดเศษถือว่าถูก (เช่น “ประมาณ 16%” กับ 16.4%)\n"
        "• เทียบงวดให้ตรงกัน (ไตรมาสกับไตรมาสเดียวกันปีก่อน, ปีงบกับปีงบก่อน)\n"
        "• ถ้ามีการแก้ตัวเลขย้อนหลัง ใช้ฉบับล่าสุดที่ยื่นก่อนวันตัด\n"
        "• claim ที่ใช้ไม่ได้ (เช่น งวดจบหลังวันตัด) ให้ใส่ “ใช่” ในช่อง UNUSABLE และ label เป็น INSUFFICIENT_EVIDENCE",
        height=80)
    row += 1

    put("หลักฐาน (ชีต Evidence)", "", font=bold)
    put("ต้องมีเมื่อไหร่", "SUPPORTED หรือ CONTRADICTED ต้องมีหลักฐานอย่างน้อย 1 แถว ส่วน INSUFFICIENT_EVIDENCE "
        "ใส่หลักฐานที่ตรวจแล้วได้ถ้าช่วยอธิบาย (เช่น ประโยคที่รายงานตัวเลขแต่ไม่บอกสาเหตุ)", height=30)
    put("ฝั่ง (Side)", "supporting = หลักฐานที่สนับสนุน claim, contradicting = หลักฐานที่หักล้าง claim "
        "(เทียบกับ claim ไม่ใช่กับ label ที่เลือก)", height=30)
    put("ข้อความคัดลอก", "เปิดรายงานจากลิงก์ แล้วคัดลอกข้อความ “คำต่อคำ” 1–2 ประโยคที่เฉพาะเจาะจง (Ctrl/Cmd+F "
        "ช่วยหาได้) ห้ามสรุปหรือแปล ระบบให้คะแนนโดยเทียบคำในประโยคนี้กับสิ่งที่โมเดลอ้างอิง", height=30)
    put("xbrl_fact", "ถ้าหลักฐานเป็นตัวเลขจากงบการเงิน เลือกประเภท xbrl_fact แล้วใส่ XBRL concept "
        "(เช่น RevenueFromContractWithCustomerExcludingAssessedTax) และวันสิ้นงวด", height=30)
    row += 1

    put("ตัวอย่างรูปแบบ (ไม่ใช่ claim ในชุดนี้)", "", font=bold)
    put("Claim (ตัวอย่าง)", "Apple's Services net sales grew in the quarter ended December 27, 2025, primarily due to "
        "higher advertising, App Store and cloud services sales.", height=30)
    put("Label", "SUPPORTED")
    put("เหตุผล", "MD&A ระบุสาเหตุตรงกับ claim และยอดขาย Services เพิ่มขึ้นจากไตรมาสเดียวกันปีก่อน")
    put("แถว Evidence", "Claim ID: (ของ claim)  |  Side: supporting  |  Kind: filing_passage  |  "
        "Accession: 0000320193-26-000006  |  Locator: 10-Q MD&A — Services", height=30)
    put("ข้อความคัดลอก", "Services net sales increased during the first quarter of 2026 compared to the same quarter "
        "in 2025 primarily due to higher net sales from advertising, the App Store and cloud services.", height=30)


def export(claim_paths: list[str], out: str) -> int:
    claims = [c for p in claim_paths for c in load_claims(p)]
    if not claims:
        raise SystemExit("no claims to export")
    ids = [c.claim_id for c in claims]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate claim_id across claim files")
    filings = load_manifest()

    wb = Workbook()
    wb.active.title = "คำแนะนำ"
    _instructions(wb.active, claims)

    ws = wb.create_sheet("Claims")
    elig_by_claim = {c.claim_id: eligible_filings(c, filings) for c in claims}
    n_links = max(1, max(len(e) for e in elig_by_claim.values()))
    cols = (CLAIM_FIXED + [(LINK_HEADER.format(i=i), 20, "link") for i in range(1, n_links + 1)]
            + CLAIM_INPUT + CLAIM_CHECK)
    letter = {spec[0]: get_column_letter(i) for i, spec in enumerate(cols, start=1)}
    lab, cnt, status = letter[H_LABEL], letter[CLAIM_CHECK[0][0]], letter[CLAIM_CHECK[1][0]]
    _style_header(ws, cols)
    n = len(claims) + 1
    for r, c in enumerate(claims, start=2):
        elig = elig_by_claim[c.claim_id]
        values = ([c.claim_id, c.company, c.claim, c.claim_category, c.difficulty, c.reporting_period,
                   _as_date(c.as_of_date), ", ".join(c.allowed_sources),
                   "\n".join(f"{f['form']} ยื่น {f['filed']} ({f['accession_number']})" for f in elig)
                   or "ไม่มีรายงานในคลัง — แจ้งผู้ดูแล"]
                  + [f"{f['form']} ยื่น {f['filed']}" for f in elig] + [None] * (n_links - len(elig))
                  + [None] * len(CLAIM_INPUT)
                  + [f'=COUNTIF(Evidence!$A$2:$A${EVIDENCE_ROWS + 1},A{r})',
                     f'=IF({lab}{r}="","ยังไม่ได้เลือก Label",IF(AND({lab}{r}<>"INSUFFICIENT_EVIDENCE",{cnt}{r}=0),'
                     f'"ต้องมีหลักฐานอย่างน้อย 1 แถว","ครบ"))'])
        for col, (value, spec) in enumerate(zip(values, cols), start=1):
            cell = ws.cell(row=r, column=col, value=value)
            _style_cell(cell, "fixed" if spec[2] == "link" else spec[2])
        for i, f in enumerate(elig):
            cell = ws.cell(row=r, column=len(CLAIM_FIXED) + 1 + i)
            cell.hyperlink, cell.font = filing_url(f), LINK_FONT
        ws.cell(row=r, column=7).number_format = "yyyy-mm-dd"
        ws.row_dimensions[r].height = max(45, 15 * max(len(elig), 3))
    label_dv = DataValidation(type="list", formula1=f'"{",".join(LABELS)}"', allow_blank=True,
                              error="เลือกจากรายการเท่านั้น", errorTitle="Label ไม่ถูกต้อง", showErrorMessage=True)
    unusable_dv = DataValidation(type="list", formula1='"ใช่"', allow_blank=True)
    minutes_dv = DataValidation(type="decimal", operator="between", formula1="0", formula2="600", allow_blank=True)
    for dv, col in ((label_dv, lab), (unusable_dv, letter[H_UNUSABLE]), (minutes_dv, letter[H_MINUTES])):
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{n}")
    ws.conditional_formatting.add(f"{status}2:{status}{n}", FormulaRule(formula=[f'${status}2="ครบ"'], fill=PatternFill("solid", start_color="C6EFCE")))
    ws.conditional_formatting.add(f"{status}2:{status}{n}", FormulaRule(formula=[f'${status}2<>"ครบ"'], fill=PatternFill("solid", start_color="FFC7CE")))
    ws.auto_filter.ref = f"A1:{status}{n}"

    fs = wb.create_sheet("Filings")
    _style_header(fs, FILING_COLS)
    for r, f in enumerate(filings, start=2):
        url = filing_url(f)
        values = [f["company"], f["form"], _as_date(f["filed"]), _as_date(f["report_date"]), f["accession_number"], url]
        for col, value in enumerate(values, start=1):
            cell = fs.cell(row=r, column=col, value=value)
            _style_cell(cell, "fixed")
        for col in (3, 4):
            fs.cell(row=r, column=col).number_format = "yyyy-mm-dd"
        link = fs.cell(row=r, column=6)
        link.hyperlink, link.font = url, LINK_FONT
    nf = len(filings) + 1

    es = wb.create_sheet("Evidence")
    _style_header(es, EVIDENCE_COLS)
    find = f"MATCH(D{{r}},Filings!$E$2:$E${nf},0)"
    for r in range(2, EVIDENCE_ROWS + 2):
        m, claim_m = find.format(r=r), f"MATCH(A{r},Claims!$A$2:$A${n},0)"
        checks = [
            f'=IF(D{r}="","",IFERROR(INDEX(Filings!$B$2:$B${nf},{m}),"?"))',
            f'=IF(D{r}="","",IFERROR(INDEX(Filings!$C$2:$C${nf},{m}),"?"))',
            f'=IF(AND(A{r}="",D{r}=""),"",IF(A{r}="","ใส่ Claim ID",IF(ISNA({claim_m}),"ไม่พบ Claim ID",'
            f'IF(D{r}="","ใส่ Accession",IF(ISNA({m}),"Accession ไม่อยู่ในชีต Filings",'
            f'IF(INDEX(Filings!$A$2:$A${nf},{m})<>INDEX(Claims!$B$2:$B${n},{claim_m}),"คนละบริษัทกับ claim",'
            f'IF(INDEX(Filings!$C$2:$C${nf},{m})>INDEX(Claims!$G$2:$G${n},{claim_m}),"ยื่นหลังวันตัด — ห้ามใช้",'
            # column I lists the claim's eligible accessions; an older filing of the same company is not one of them
            f'IF(ISERROR(SEARCH(D{r},INDEX(Claims!$I$2:$I${n},{claim_m}))),"ไม่ใช่รายงานที่ใช้ได้ของ claim นี้ — ใช้ลิงก์ในแถว claim",'
            f'IF(AND(C{r}="filing_passage",F{r}=""),"ใส่ข้อความคัดลอก",'
            f'IF(AND(C{r}="xbrl_fact",OR(G{r}="",H{r}="")),"ใส่ XBRL concept และ period end","OK"))))))))))',
            f'=IF(D{r}="","",IFERROR(HYPERLINK(INDEX(Filings!$F$2:$F${nf},{m}),"เปิดรายงาน"),""))',
        ]
        for col, spec in enumerate(EVIDENCE_COLS, start=1):
            cell = es.cell(row=r, column=col, value=checks[col - 9] if col >= 9 else None)
            _style_cell(cell, spec[2])
        es.cell(row=r, column=8).number_format = "yyyy-mm-dd"
        es.cell(row=r, column=10).number_format = "yyyy-mm-dd"
        es.cell(row=r, column=12).font = LINK_FONT
    last = EVIDENCE_ROWS + 1
    for formula, col in ((f"=Claims!$A$2:$A${n}", "A"), (f'"{",".join(SIDES)}"', "B"), (f'"{",".join(KINDS)}"', "C"),
                         (f"=Filings!$E$2:$E${nf}", "D")):
        dv = DataValidation(type="list", formula1=formula, allow_blank=True, showErrorMessage=True,
                            error="เลือกจากรายการเท่านั้น")
        es.add_data_validation(dv)
        dv.add(f"{col}2:{col}{last}")
    date_dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2000,1,1)", allow_blank=True)
    es.add_data_validation(date_dv)
    date_dv.add(f"H2:H{last}")
    es.conditional_formatting.add(f"K2:K{last}", FormulaRule(formula=['$K2="OK"'], fill=PatternFill("solid", start_color="C6EFCE")))
    es.conditional_formatting.add(f"K2:K{last}", FormulaRule(formula=['AND($K2<>"",$K2<>"OK")'], fill=PatternFill("solid", start_color="FFC7CE")))

    wb.move_sheet("Evidence", offset=-1)  # order: instructions, Claims, Evidence, Filings
    wb.calculation.fullCalcOnLoad = True
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return len(claims)


# ------------------------------------------------------------------ import

def _text(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None


def read_workbook(path: str, claim_paths: list[str]) -> list[Annotation]:
    """Filled workbook -> validated Annotation records (one per labelled claim)."""
    wb = load_workbook(path, data_only=False)
    dn = wb.defined_names.get("ReviewerID")
    if dn is None:
        raise SchemaError("workbook has no ReviewerID cell; was it made by annotation_workbook.py export?")
    sheet, ref = next(dn.destinations)
    reviewer_id = _text(wb[sheet][ref.replace("$", "")].value)
    if not reviewer_id or " " in reviewer_id:
        raise SchemaError("fill in Reviewer ID (no spaces) on the instructions sheet")

    claims = {c.claim_id: c for p in claim_paths for c in load_claims(p)}
    filings = {f["accession_number"]: f for f in load_manifest()}
    errors = []

    evidence = defaultdict(lambda: {v: [] for v in SIDES.values()})
    for r, row in enumerate(wb["Evidence"].iter_rows(min_row=2, max_col=8, values_only=True), start=2):
        cid, side, kind, accn, locator, quote, concept, period_end = (_text(v) for v in row)
        if not any((cid, side, accn, locator, quote, concept)):
            continue
        where = f"Evidence row {r}"
        claim, filing = claims.get(cid), filings.get(accn)
        if claim is None:
            errors.append(f"{where}: unknown claim id {cid!r}"); continue
        if side not in SIDES:
            errors.append(f"{where}: side must be one of {list(SIDES)}"); continue
        if filing is None:
            errors.append(f"{where}: accession {accn!r} is not in the corpus manifest"); continue
        if filing not in eligible_filings(claim, list(filings.values())):
            errors.append(f"{where}: {accn} is not an eligible filing for {cid} "
                          f"(other company, disallowed form, or filed after {claim.as_of_date})"); continue
        kind = kind or "filing_passage"
        if kind == "filing_passage" and not quote:
            errors.append(f"{where}: filing_passage needs a verbatim quote"); continue
        if kind == "xbrl_fact" and not (concept and period_end):
            errors.append(f"{where}: xbrl_fact needs XBRL concept and period end"); continue
        ref = EvidenceRef(accession_number=accn, form=filing["form"], locator=locator, quote=quote, kind=kind,
                          xbrl_concept=concept, period_end=period_end)
        evidence[cid][SIDES[side]].append({k: v for k, v in vars(ref).items() if v is not None})

    out = []
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    cs = wb["Claims"]
    col = {cell.value: cell.column - 1 for cell in cs[1]}
    missing = [h for h in (H_LABEL, H_NOTES, H_UNUSABLE) if h not in col]  # minutes spent is optional
    if missing:
        raise SchemaError(f"Claims sheet is missing columns {missing}; were headers edited?")
    for r, row in enumerate(cs.iter_rows(min_row=2, values_only=True), start=2):
        cid, label, notes = _text(row[0]), _text(row[col[H_LABEL]]), _text(row[col[H_NOTES]])
        unusable, minutes = _text(row[col[H_UNUSABLE]]), row[col[H_MINUTES]] if H_MINUTES in col else None
        if not cid:
            continue
        if cid not in claims:
            errors.append(f"Claims row {r}: claim {cid} is not in the claim files"); continue
        if not label:
            if evidence.get(cid):
                errors.append(f"Claims row {r}: {cid} has evidence rows but no label")
            continue
        ev = evidence.get(cid, {v: [] for v in SIDES.values()})
        if label != "INSUFFICIENT_EVIDENCE" and not any(ev.values()):
            errors.append(f"Claims row {r}: {cid} is {label} but has no evidence row"); continue
        if unusable == "ใช่":
            notes = UNUSABLE_PREFIX + (notes or "")
        try:
            out.append(Annotation(claim_id=cid, reviewer_id=reviewer_id, gold_label=label, review_notes=notes,
                                  annotated_at=now, guideline_version=GUIDELINE_VERSION,
                                  time_spent_minutes=float(minutes) if minutes not in (None, "") else None, **ev))
        except (SchemaError, TypeError, ValueError) as e:
            errors.append(f"Claims row {r}: {e}")
    if errors:
        raise SchemaError("workbook has problems; nothing was written:\n  " + "\n  ".join(errors))
    return out


def import_workbook(path: str, claim_paths: list[str], annotation_dir: str = ANNOTATION_DIR) -> str:
    annotations = read_workbook(path, claim_paths)
    if not annotations:
        raise SchemaError("no labelled claims in the workbook")
    target = os.path.join(annotation_dir, f"{annotations[0].reviewer_id}.jsonl")
    if os.path.exists(target):
        raise SchemaError(f"{target} already exists; annotations are not overwritten. "
                          "Move it aside deliberately if this is a corrected resubmission.")
    os.makedirs(annotation_dir, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        for a in annotations:
            f.write(json.dumps(vars(a), ensure_ascii=False) + "\n")
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--claims", nargs="+", default=[GOLD_PATH])
    ex.add_argument("--out", default=os.path.join(DATASET_DIR, "workbooks", "annotation_workbook.xlsx"))
    im = sub.add_parser("import")
    im.add_argument("workbook")
    im.add_argument("--claims", nargs="+", default=[GOLD_PATH])
    args = ap.parse_args(argv)
    try:
        if args.cmd == "export":
            print(f"wrote {export(args.claims, args.out)} claims to {args.out}")
        else:
            print(f"wrote {import_workbook(args.workbook, args.claims)}")
    except SchemaError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
