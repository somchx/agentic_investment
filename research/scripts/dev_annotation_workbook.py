"""Development-split annotation workbook (A3 v2 development).

    # blank workbook for the 24 development claims
    research/.venv/bin/python research/scripts/dev_annotation_workbook.py export \
        --out research/datasets/workbooks/dev_annotation_workbook.xlsx

    # blind second-review workbook for selected claims (blank, like any export)
    research/.venv/bin/python research/scripts/dev_annotation_workbook.py export \
        --ids DEV-AAPL-05 DEV-MSFT-07 --out research/datasets/workbooks/dev_blind_review.xlsx

    # a reviewer's filled workbook -> datasets/annotations_dev/<reviewer_id>.jsonl
    research/.venv/bin/python research/scripts/dev_annotation_workbook.py import filled.xlsx

A thin layer over scripts/annotation_workbook.py (gold workflow, unchanged):
the same Claims / Evidence / Filings sheets, label rules, cutoff and company
checks, plus

- uncertainty columns (confidence, uncertainty type, note, second review
  requested), appended after the gold columns so the gold import still reads
  the workbook;
- a development addendum sheet (docs/dev_annotation_guidelines.md);
- a separate output directory, so development labels never mix with gold
  annotations;
- a wider evidence rule on import: any same-company filing of an allowed form
  filed on or before the cutoff (gold guideline §1.3), not only the filings in
  the system's retrieval set. The gold tool keeps its narrower rule. Evidence
  from outside the system's set is listed per claim
  (`evidence_outside_system_corpus`) so evidence-recall metrics can exclude it.

The workbook carries claims and filing links only: no label, no model output,
and no passages chosen by the system's retriever (they would anchor the
reviewer on what the system under evaluation already sees).
"""
import argparse
import contextlib
import importlib.util
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import load_workbook  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import DATASET_DIR, DEV_PATH, load_claims  # noqa: E402
from engine.schema import SOURCE_FORMS, SchemaError  # noqa: E402

_spec = importlib.util.spec_from_file_location("annotation_workbook", os.path.join(os.path.dirname(__file__), "annotation_workbook.py"))
aw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aw)
_spec = importlib.util.spec_from_file_location("dev_corpus", os.path.join(os.path.dirname(__file__), "dev_corpus.py"))
dev_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dev_corpus)
aw.load_manifest = dev_corpus.load_manifest  # frozen manifest + development manifests (new companies)

DEV_ADDENDUM_VERSION = "dev-addendum-1.1"
DEV_ANNOTATION_DIR = os.path.join(DATASET_DIR, "annotations_dev")
H_CONF = "✎ ความมั่นใจ\nConfidence"
H_UTYPE = "✎ ประเภทความไม่แน่ใจ\nUncertainty type"
H_UNOTE = "✎ อธิบายความไม่แน่ใจ\nUncertainty note"
H_SECOND = "✎ ขอผู้ตรวจคนที่ 2\nSecond review requested"
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
UNCERTAINTY_TYPES = {
    "NONE": "ไม่มีความไม่แน่ใจที่สำคัญ",
    "UNDEFINED_PREDICATE": "claim ใช้คำประเมินที่ไม่มีเกณฑ์ (strong, resilient, fully under control, adequate)",
    "CAUSE_NOT_STATED": "ตัวเลขถูก แต่รายงานไม่ได้บอกสาเหตุ/ตัวขับที่ claim อ้าง",
    "PERIOD_OR_BASIS_UNCLEAR": "ไม่ชัดว่า claim หมายถึงงวดหรือฐานเปรียบเทียบใด (ไตรมาส / สะสม / ปี / ณ วันที่)",
    "DEFINITION_CHANGE": "นิยาม segment หรือตัวชี้วัดในรายงานต่างจากที่ claim ใช้ (เปลี่ยนชื่อ, องค์ประกอบเปลี่ยน)",
    "CONFLICTING_DISCLOSURES": "รายงานมีข้อมูลสองด้านที่ชี้ไปคนละทาง",
    "THRESHOLD_OR_ROUNDING_EDGE": "ตัวเลขใกล้เกณฑ์มากจนการปัดเศษมีผล",
    "FIGURE_NOT_FOUND": "หาตัวเลขที่ต้องใช้ไม่พบในรายงานที่ใช้ได้",
    "NEGATIVE_CLAIM": "claim เชิงปฏิเสธ (ไม่ได้รับผลกระทบ / ไม่มีแรงกดดัน) ที่รายงานไม่ได้ระบุชัดว่าไม่มีผลหรือไม่มีสาระสำคัญ",
    "OTHER": "อื่น ๆ (อธิบายในช่องถัดไป)",
}
DEV_COLUMNS = [(H_CONF, 13), (H_UTYPE, 26), (H_UNOTE, 40), (H_SECOND, 14)]


def _addendum_sheet(wb):
    ws = wb.create_sheet("เกณฑ์ Dev", 1)
    rows = [
        ("ชุด Development (ไม่ใช่ Gold)", ""),
        ("Guideline", f"gold-guidelines-1.0 (ทุกกฎในชีต คำแนะนำ) + {DEV_ADDENDUM_VERSION} (ด้านล่าง); รายละเอียด: research/docs/dev_annotation_guidelines.md"),
        ("ใช้ทำอะไร", "พัฒนาและเลือก architecture ของ A3 v2 เท่านั้น ไม่ใช่ผลการทดลองสุดท้าย และไม่รวมกับ Gold 150"),
        ("ความเป็นอิสระ", "ห้ามเปิดผลของระบบ (v1 traces, ผล v2, notebooks) และห้ามถาม AI ใด ๆ; ไฟล์นี้ไม่มีข้อความที่ระบบดึงมาโดยตั้งใจ"),
        ("Label", "ใช้กฎเดียวกับ Gold: แยก claim เป็นส่วนสำคัญ → มีส่วนใดเท็จ = CONTRADICTED → ทุกส่วนจริง = SUPPORTED → อื่น ๆ = INSUFFICIENT_EVIDENCE"),
        ("ความมั่นใจ", "HIGH = ผู้ตรวจอีกคนน่าจะได้ label เดียวกัน; MEDIUM = มีจุดตีความแต่เลือกได้มีเหตุผล; LOW = อาจได้ label อื่นอย่างสมเหตุผล"),
        ("ประเภทความไม่แน่ใจ", "เลือก 1 ค่าที่เป็นต้นเหตุหลัก (ถ้า NONE ให้ความมั่นใจเป็น HIGH ได้)"),
        *[(f"  {k}", v) for k, v in UNCERTAINTY_TYPES.items()],
        ("ขอผู้ตรวจคนที่ 2", "ใส่ \"ใช่\" เมื่อความมั่นใจ LOW หรือ claim ควรได้ความเห็นที่สอง (ผู้ตรวจคนที่ 2 ต้องทำแบบอิสระ)"),
        ("คำประเมินที่ไม่มีเกณฑ์", "ถ้ารายงานไม่ได้ระบุเกณฑ์และตีความได้หลายทาง → INSUFFICIENT_EVIDENCE (ตาม gold guideline §2); ถ้าส่วนข้อเท็จจริงของ claim ถูกหักล้าง → CONTRADICTED"),
        ("งวดเวลา", "ใช้งวดที่ claim ระบุ; ตัวเลขของงวดอื่นใช้ได้เฉพาะเป็นฐานเปรียบเทียบ (เช่นไตรมาสเดียวกันปีก่อน)"),
        ("ตัวเลขที่ต้องคำนวณ", "ถ้าต้องคำนวณ (เช่น FCF = OCF − capex, สัดส่วนของการเปลี่ยนแปลง) ให้ใส่สูตรและตัวเลขที่ใช้ในช่องเหตุผล และใส่หลักฐานของตัวเลขต้นทางในชีต Evidence"),
    ]
    for a, b in rows:
        ws.append([a, b])
    for row in ws.iter_rows():
        for c in row:
            c.font, c.alignment = aw.Font(name=aw.FONT, size=10, bold=c.column == 1 and c.row == 1), aw.WRAP
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 28, 120


def _subset_file(claim_paths, ids: list[str], tmp: str) -> str:
    """Claim records of `ids` only (same fields), so a blind second-review
    workbook carries just those claims. Order follows `ids`."""
    rows = {}
    for p in claim_paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    rows[r["claim_id"]] = line if line.endswith("\n") else line + "\n"
    unknown = [i for i in ids if i not in rows]
    if unknown:
        raise SystemExit(f"unknown claim ids: {unknown}")
    path = os.path.join(tmp, "subset.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(rows[i] for i in ids)
    return path


def export(out: str, claim_paths=(DEV_PATH,), ids: list[str] | None = None) -> int:
    if ids:
        with tempfile.TemporaryDirectory() as tmp:
            return export(out, (_subset_file(claim_paths, ids, tmp),))
    claims = [c for p in claim_paths for c in load_claims(p)]
    if any(c.split != "development" for c in claims):
        raise SystemExit("dev workbook: only development claims")
    n = aw.export(list(claim_paths), out)
    wb = load_workbook(out)
    wb["คำแนะนำ"]["A1"].value = "แบบฟอร์มติด label ชุด Development (A3 v2) — ไม่ใช่ Gold; ดูชีต “เกณฑ์ Dev”"
    cs = wb["Claims"]
    start = cs.max_column + 1
    for i, (head, width) in enumerate(DEV_COLUMNS):
        col = start + i
        cs.cell(row=1, column=col, value=head)
        cs.column_dimensions[get_column_letter(col)].width = width
        for r in range(2, n + 2):
            aw._style_cell(cs.cell(row=r, column=col), "input")
    aw._style_header(cs, [(cs.cell(row=1, column=c).value, cs.column_dimensions[get_column_letter(c)].width, "")
                          for c in range(1, cs.max_column + 1)])
    letters = [get_column_letter(start + i) for i in range(len(DEV_COLUMNS))]
    for values, col in ((CONFIDENCE, letters[0]), (tuple(UNCERTAINTY_TYPES), letters[1]), (("ใช่",), letters[3])):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True,
                            error="เลือกจากรายการเท่านั้น")
        cs.add_data_validation(dv)
        dv.add(f"{col}2:{col}{n + 1}")
    cs.auto_filter.ref = f"A1:{letters[-1]}{n + 1}"
    _addendum_sheet(wb)
    wb.calculation.fullCalcOnLoad = True
    wb.save(out)
    return n


def dev_eligible_filings(claim, filings: list[dict]) -> list[dict]:
    """Development evidence rule: same company, allowed form, filed on or before
    the cutoff -- e.g. the prior-year 10-Q a year-over-year balance comparison
    needs, which the system's retrieval set (latest 10-K + 2 latest 10-Qs)
    leaves out."""
    forms = {form for src in claim.allowed_sources for form in SOURCE_FORMS.get(src, ())}
    return sorted((f for f in filings if f["company"] == claim.company and f["form"] in forms and f["filed"] <= claim.as_of_date),
                  key=lambda f: f["filed"])


@contextlib.contextmanager
def _dev_evidence_rule():
    gold_rule = aw.eligible_filings
    aw.eligible_filings = dev_eligible_filings
    try:
        yield gold_rule
    finally:
        aw.eligible_filings = gold_rule


def read_dev(path: str, claim_paths=(DEV_PATH,)) -> list[dict]:
    with _dev_evidence_rule() as system_rule:
        annotations = aw.read_workbook(path, list(claim_paths))  # all gold-workflow validation, wider evidence rule
    claims = {c.claim_id: c for p in claim_paths for c in load_claims(p)}
    manifest = aw.load_manifest()
    outside = {}
    for a in annotations:
        system_set = {f["accession_number"] for f in system_rule(claims[a.claim_id], manifest)}
        cited = [e["accession_number"] for e in a.supporting_evidence + a.contradictory_evidence]
        outside[a.claim_id] = sorted({x for x in cited if x not in system_set})
    wb = load_workbook(path, data_only=False)
    cs = wb["Claims"]
    col = {cell.value: cell.column - 1 for cell in cs[1]}
    missing = [h for h, _ in DEV_COLUMNS if h not in col]
    if missing:
        raise SchemaError(f"Claims sheet is missing development columns {missing}; was it made by dev_annotation_workbook.py export?")
    extra, errors = {}, []
    for r, row in enumerate(cs.iter_rows(min_row=2, values_only=True), start=2):
        cid = aw._text(row[0])
        if not cid:
            continue
        conf, utype, unote, second = (aw._text(row[col[h]]) for h, _ in DEV_COLUMNS)
        if conf is not None and conf not in CONFIDENCE:
            errors.append(f"Claims row {r}: confidence must be one of {CONFIDENCE}")
        if utype is not None and utype not in UNCERTAINTY_TYPES:
            errors.append(f"Claims row {r}: uncertainty type must be one of {list(UNCERTAINTY_TYPES)}")
        if utype == "OTHER" and not unote:
            errors.append(f"Claims row {r}: uncertainty type OTHER needs a note")
        extra[cid] = {"confidence": conf, "uncertainty_type": utype, "uncertainty_note": unote, "second_review_requested": second == "ใช่"}
    labelled = {a.claim_id for a in annotations}
    errors += [f"{cid}: confidence is required for a labelled claim" for cid in sorted(labelled) if not extra[cid]["confidence"]]
    if errors:
        raise SchemaError("workbook has problems; nothing was written:\n  " + "\n  ".join(errors))
    return [{**vars(a), "split": "development", "dev_addendum_version": DEV_ADDENDUM_VERSION, **extra[a.claim_id],
             "evidence_outside_system_corpus": outside[a.claim_id]} for a in annotations]


def import_dev(path: str, annotation_dir: str = DEV_ANNOTATION_DIR, claim_paths=(DEV_PATH,), version: str | None = None) -> str:
    """`version` (e.g. "v2") writes <reviewer>.<version>.jsonl next to the
    earlier file, which is never replaced, and records the version and the
    source workbook's sha256 in every row."""
    rows = read_dev(path, claim_paths)
    if not rows:
        raise SchemaError("no labelled claims in the workbook")
    if version is not None:
        if not version.replace("-", "").replace("_", "").isalnum():
            raise SchemaError(f"version {version!r}: letters, digits, - and _ only")
        import hashlib
        with open(path, "rb") as f:
            src = hashlib.sha256(f.read()).hexdigest()
        rows = [{**r, "annotation_version": version, "source_workbook_sha256": src} for r in rows]
    name = rows[0]["reviewer_id"] + (f".{version}" if version else "")
    target = os.path.join(annotation_dir, f"{name}.jsonl")
    if os.path.exists(target):
        raise SchemaError(f"{target} already exists; annotations are not overwritten")
    os.makedirs(annotation_dir, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return target


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export")
    ex.add_argument("--out", default=os.path.join(DATASET_DIR, "workbooks", "dev_annotation_workbook.xlsx"))
    ex.add_argument("--ids", nargs="+", help="export only these development claim ids (blind second review)")
    im = sub.add_parser("import")
    im.add_argument("workbook")
    im.add_argument("--version", help="write <reviewer>.<version>.jsonl beside earlier versions (e.g. v2)")
    for p in (ex, im):
        p.add_argument("--claims", default=DEV_PATH, help="development claims file (e.g. datasets/development_cases_dev-v0.2.jsonl)")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "export":
            if os.path.exists(args.out):
                raise SystemExit(f"{args.out} exists; choose another --out (a filled copy may be there)")
            print(f"wrote {export(args.out, (args.claims,), ids=args.ids)} claims to {args.out}")
        else:
            print(f"wrote {import_dev(args.workbook, claim_paths=(args.claims,), version=args.version)}")
    except SchemaError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
