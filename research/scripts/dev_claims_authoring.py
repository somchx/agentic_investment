"""Authoring new development claims (dev set expansion, docs/a3v2_dev_dataset_plan.md §2b).

    # blank authoring workbook (claims are written by people; see the rules sheet)
    research/.venv/bin/python research/scripts/dev_claims_authoring.py template --out dev_claims_authoring.xlsx

    # check a filled workbook: schema, ids, companies, near-duplicates of gold /
    # existing dev claims, filings available at the cutoff, quotas
    research/.venv/bin/python research/scripts/dev_claims_authoring.py validate filled.xlsx

    # write the next dataset version (never overwrites): claims file for annotators
    # + a separate author-only design-intent file that annotators must not see
    research/.venv/bin/python research/scripts/dev_claims_authoring.py build filled.xlsx --version dev-v0.2

Nothing here writes a label. `design_intent` is the author's expectation, kept
out of the claims file and the annotation workbook.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine.datasets import DATASET_DIR, DEV_PATH, GOLD_PATH, load_claims  # noqa: E402
from engine.schema import LABELS, DatasetClaim, SchemaError  # noqa: E402

_spec = importlib.util.spec_from_file_location("annotation_workbook", os.path.join(os.path.dirname(__file__), "annotation_workbook.py"))
aw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aw)
_spec = importlib.util.spec_from_file_location("dev_corpus", os.path.join(os.path.dirname(__file__), "dev_corpus.py"))
dev_corpus = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dev_corpus)
aw.load_manifest = dev_corpus.load_manifest  # frozen manifest + development manifests (new companies)

COLUMNS = ["claim_id", "company", "claim", "claim_category", "reporting_period", "as_of_date", "allowed_sources", "difficulty",
           "pattern_type", "design_intent", "author_id", "author_notes"]
CATEGORIES = ("numerical", "interpretive", "ambiguous")
DIFFICULTY = ("easy", "medium", "hard")
# §2b targets for the 48 new claims
PATTERN_TARGETS = {
    "EVALUATIVE_NO_CRITERION": 12, "EVALUATIVE_FACT_FALSE": 6, "CAUSE_NOT_STATED": 6, "CAUSE_STATED": 8,
    "ABSENCE_NOT_STATED": 4, "ABSENCE_EFFECT_DISCLOSED": 2, "PERIOD_NOT_COVERED": 2, "PERIOD_TRAP": 4,
    "COMPUTATION_OR_DEFINITION": 4, "NUMERIC_CHECK": 0, "OTHER": 0,
}
CATEGORY_TARGETS = {"ambiguous": 25, "interpretive": 15, "numerical": 8}
INTENTS = (*LABELS, "UNSURE")
NEAR_DUPLICATE = 0.6  # token Jaccard similarity that blocks a claim
_ID = re.compile(r"^DEV-[A-Z]{1,5}-\d{2,3}$")
_STOP = {"the", "a", "an", "of", "in", "its", "for", "and", "to", "by", "was", "were", "is", "that", "than", "on", "with", "show", "results"}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in _STOP}


def similarity(a: str, b: str) -> float:
    x, y = tokens(a), tokens(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def template(out: str) -> None:
    wb = Workbook()
    rules = wb.active
    rules.title = "กติกา"
    for line in [
        "เขียน claim ใหม่สำหรับชุด Development (A3 v2) — ผู้เขียนเป็นคน; ห้ามให้ระบบที่ถูกประเมินเขียนหรือติด label",
        "1) ห้ามคัดลอก/ถอดความ claim จาก Gold 150 และห้ามเขียนโดยดูผลของระบบ (validate จะบล็อก claim ที่คล้าย Gold หรือ Dev เดิม)",
        "2) ใช้บริษัทที่ไม่ใช่ 10 บริษัทของ Gold และไม่ใช่บริษัทที่จองไว้สำหรับ holdout (validate บล็อกบริษัท Gold โดยปริยาย)",
        "3) ตั้ง category, difficulty, reporting_period, as_of_date จากข้อความ claim ก่อนให้ใครติด label",
        "4) pattern_type = ประเภทตามแผน §2b; design_intent = สิ่งที่ผู้เขียนคาด (ไม่ใช่ label) — จะถูกแยกไฟล์ ผู้ติด label ไม่เห็น",
        "5) เขียนแบบนักวิเคราะห์ ไม่ใส่คำที่เฉลยคำตอบ; ทุก pattern ที่น่าจะเป็น INSUFFICIENT ต้องมีคู่ที่ตัดสินได้ (ดู Quotas)",
        "6) ผู้เขียนไม่ควรเป็นผู้ติด label คนเดียวของ claim นั้น",
        "7) บริษัทใหม่ต้องดาวน์โหลด filing จาก SEC ก่อน (ฟรี): scripts/build_corpus.py --download; validate จะบอกว่าข้อไหนยังไม่มี filing",
    ]:
        rules.append([line])
    rules.column_dimensions["A"].width = 150
    ws = wb.create_sheet("Claims")
    ws.append(COLUMNS)
    ws.append(["DEV-XXX-01", "XXX", "(ตัวอย่าง — ลบแถวนี้) XXX's results for the quarter ended March 31, 2027 show disciplined cost management.",
               "ambiguous", "2027 Q1", "2027-05-15", "SEC_10K,SEC_10Q", "medium", "EVALUATIVE_NO_CRITERION", "INSUFFICIENT_EVIDENCE",
               "author_id", ""])
    fill = PatternFill("solid", start_color="FFF2CC")
    for i, w in enumerate([14, 9, 70, 13, 13, 12, 18, 10, 28, 22, 14, 30], start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    for row in ws.iter_rows():
        for c in row:
            c.font, c.alignment = Font(name="Arial", size=10, bold=c.row == 1), Alignment(wrap_text=True, vertical="top")
            if c.row > 1:
                c.fill = fill
    for col, values in (("D", CATEGORIES), ("H", DIFFICULTY), ("I", tuple(PATTERN_TARGETS)), ("J", INTENTS)):
        dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True)
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}500")
    q = wb.create_sheet("Quotas")
    q.append(["pattern_type", "target (new claims)"])
    for k, v in PATTERN_TARGETS.items():
        q.append([k, v])
    q.append([])
    q.append(["claim_category", "target (new claims)"])
    for k, v in CATEGORY_TARGETS.items():
        q.append([k, v])
    q.column_dimensions["A"].width = 30
    wb.save(out)


def read(path: str) -> list[dict]:
    ws = load_workbook(path, data_only=True)["Claims"]
    head = [c.value for c in ws[1]]
    if head[:len(COLUMNS)] != COLUMNS:
        raise SchemaError("Claims sheet headers differ from the template")
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not r[0] or str(r[0]).startswith("DEV-XXX"):
            continue
        d = dict(zip(COLUMNS, r))
        d["as_of_date"] = d["as_of_date"].date().isoformat() if hasattr(d["as_of_date"], "date") else d["as_of_date"]
        rows.append(d)
    return rows


def validate(path: str, allow_gold_companies: bool = False) -> dict:
    rows = read(path)
    gold = load_claims(GOLD_PATH)
    dev = load_claims(DEV_PATH)
    gold_companies = {c.company for c in gold}
    manifest = aw.load_manifest()
    errors, warnings, ok = [], [], []
    seen = {c.claim_id for c in dev}
    for d in rows:
        cid = d["claim_id"]
        try:
            if not _ID.match(cid or ""):
                raise SchemaError("claim_id must look like DEV-<TICKER>-NN")
            if cid in seen:
                raise SchemaError("duplicate claim_id")
            seen.add(cid)
            if d["claim_category"] not in CATEGORIES or d["difficulty"] not in DIFFICULTY:
                raise SchemaError("claim_category / difficulty not from the list")
            if d["pattern_type"] not in PATTERN_TARGETS or d["design_intent"] not in INTENTS:
                raise SchemaError("pattern_type / design_intent not from the list")
            if not d.get("author_id"):
                raise SchemaError("author_id required")
            c = DatasetClaim(claim_id=cid, company=d["company"], claim=d["claim"], as_of_date=d["as_of_date"],
                             claim_category=d["claim_category"], split="development",
                             allowed_sources=[s.strip() for s in str(d["allowed_sources"] or "SEC_10K,SEC_10Q").split(",")],
                             reporting_period=d["reporting_period"], difficulty=d["difficulty"])
            c.to_input()
            if c.company in gold_companies and not allow_gold_companies:
                raise SchemaError(f"{c.company} is a gold company")
            near = max(((similarity(c.claim, g.claim), g.claim_id) for g in gold + dev), default=(0, None))
            if near[0] >= NEAR_DUPLICATE:
                raise SchemaError(f"too similar to {near[1]} (similarity {near[0]:.2f})")
            if near[0] >= 0.45:
                warnings.append(f"{cid}: similar to {near[1]} ({near[0]:.2f})")
            if not aw.eligible_filings(c, manifest):
                warnings.append(f"{cid}: NEEDS_DOWNLOAD (no {c.company} filing in the corpus at {c.as_of_date})")
            ok.append(d)
        except (SchemaError, TypeError, ValueError) as e:
            errors.append(f"{cid}: {e}")
    return {"n": len(rows), "valid": len(ok), "errors": errors, "warnings": warnings,
            "categories": dict(Counter(d["claim_category"] for d in ok)), "patterns": dict(Counter(d["pattern_type"] for d in ok)),
            "design_intent": dict(Counter(d["design_intent"] for d in ok)), "companies": dict(Counter(d["company"] for d in ok)), "rows": ok}


def build(path: str, version: str, out_dir: str = DATASET_DIR, allow_gold_companies: bool = False) -> tuple[str, str]:
    res = validate(path, allow_gold_companies)
    if res["errors"]:
        raise SchemaError("validation failed:\n  " + "\n  ".join(res["errors"]))
    claims_out = os.path.join(out_dir, f"development_cases_{version}.jsonl")
    intent_out = os.path.join(out_dir, "annotations_dev", f"design_intent_{version}.jsonl")
    for p in (claims_out, intent_out):
        if os.path.exists(p):
            raise SchemaError(f"{p} exists")
    with open(DEV_PATH, encoding="utf-8") as f:
        existing = [line if line.endswith("\n") else line + "\n" for line in f if line.strip()]
    os.makedirs(os.path.dirname(intent_out), exist_ok=True)
    with open(claims_out, "w", encoding="utf-8") as f:
        f.writelines(existing)
        for d in res["rows"]:
            f.write(json.dumps({"claim_id": d["claim_id"], "company": d["company"], "claim": d["claim"], "claim_category": d["claim_category"],
                                "split": "development", "reporting_period": d["reporting_period"], "as_of_date": d["as_of_date"],
                                "allowed_sources": [s.strip() for s in str(d["allowed_sources"] or "SEC_10K,SEC_10Q").split(",")],
                                "difficulty": d["difficulty"], "relevant_filings": [],
                                "notes": f"development case; drafted by {d['author_id']}; unlabelled until independent review",
                                "dataset_version": version},
                               ensure_ascii=False) + "\n")
    with open(intent_out, "w", encoding="utf-8") as f:
        for d in res["rows"]:
            f.write(json.dumps({k: d[k] for k in ("claim_id", "pattern_type", "design_intent", "author_id", "author_notes")}, ensure_ascii=False) + "\n")
    load_claims(claims_out, expected_split="development")
    return claims_out, intent_out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template")
    t.add_argument("--out", default="dev_claims_authoring.xlsx")
    for name in ("validate", "build"):
        p = sub.add_parser(name)
        p.add_argument("workbook")
        p.add_argument("--allow-gold-companies", action="store_true")
        if name == "build":
            p.add_argument("--version", required=True)
    args = ap.parse_args(argv)
    try:
        if args.cmd == "template":
            if os.path.exists(args.out):
                raise SystemExit(f"{args.out} exists")
            template(args.out)
            print(f"wrote {args.out}")
        elif args.cmd == "validate":
            res = validate(args.workbook, args.allow_gold_companies)
            print(json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False, indent=1))
        else:
            print("wrote", *build(args.workbook, args.version, allow_gold_companies=args.allow_gold_companies))
    except SchemaError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
