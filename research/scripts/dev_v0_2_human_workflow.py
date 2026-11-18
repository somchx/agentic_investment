"""Final human annotation, adjudication and label-approval workflow for dev-v0.2.

    PY=research/.venv/bin/python; S=research/scripts/dev_v0_2_human_workflow.py
    $PY $S blind-package          # blank, blind workbook for the 44 required second annotations + audit
    $PY $S aapl05-packet          # AAPL-05 packet for an independent third reviewer + audit
    $PY $S numeric-checklist      # numerical verification workbook (20 numerical claims), blind
    $PY $S numeric-import FILLED.xlsx
    $PY $S provenance             # per-claim annotation provenance (jsonl + md)
    $PY $S agreement --second datasets/annotations_dev/<rev_X>.jsonl [--numeric datasets/annotations_dev/numcheck_<id>.jsonl]
    $PY $S adjudication-packet --second ... [--numeric ...] --out datasets/workbooks/<packet>.xlsx
    $PY $S approve --second ... [--numeric ...] --approved-by <human id> --out <approved.jsonl>
    $PY $S validate <approved.jsonl>

Nothing here creates or changes a label. Labels come only from human annotation
files under datasets/annotations_dev/ and from the append-only adjudication log
(dev_adjudication.py record). `approve` derives an approved row only where two
independent human labels agree, or a human adjudicator decided; it refuses
AI-produced files, excluded reviewers, model-like ids, design intent, system
outputs (results/), annotations whose notes repeat known AI-produced text or the
first labeller's notes, and it leaves SINGLE / DISAGREED claims unapproved.
No A2 / R / RG output is read by any command except the audits, which read the
consolidated table only to prove its strings are absent from the packets.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.styles import Alignment, Font, PatternFill  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402
from openpyxl.worksheet.datavalidation import DataValidation  # noqa: E402

from engine import RESEARCH_ROOT  # noqa: E402
from engine.datasets import bootstrap_agreement, cohen_kappa, file_sha256, load_adjudications, load_claims  # noqa: E402
from engine.schema import LABELS, SOURCE_FORMS, SchemaError  # noqa: E402


def _module(name: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), f"{name}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


dwb = _module("dev_annotation_workbook")  # its `aw` reads the frozen + development corpus manifests
da = _module("dev_adjudication")
agr = _module("dev_label_agreement")
lst = _module("dev_v0_2_label_status")

TOOL_VERSION = "dev-v0.2-human-workflow-1.0"
DATASET = lst.DATASET
ANN_DIR = lst.D
ADJ = lst.ADJ
WB_DIR = os.path.join(RESEARCH_ROOT, "datasets", "workbooks")
OUT = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "human_workflow")
CONSOLIDATED = os.path.join(RESEARCH_ROOT, "results", "dev_v0_2", "a3v2.1.1_claims.jsonl")
DESIGN_INTENT = os.path.join(ANN_DIR, "design_intent_dev-v0.2.jsonl")
CODEX_WORKBOOK = os.path.join(RESEARCH_ROOT, "datasets", "dev_annotation_workbook_dev-v0.2_new48.xlsx")
PRE_REVIEW = lst.OLD_PRE_REVIEW       # rev_som.v3: dev-v0.1 first labels before the AI-prepared label review
POST_REVIEW = lst.OLD_FIRST           # rev_som.v4: after it (informational)
OLD_SECOND = lst.OLD_SECOND           # rev_reviewer2: 8 dev-v0.1 claims
NEW_FIRST = lst.NEW_FIRST             # rev_person2: 48 dev-v0.2 claims

# First label after the AI-prepared label review (v4 differs from v3), or the
# definition written after it, or a second-review reason that closely matches it.
AI_AFFECTED = {
    "DEV-AAPL-07": "rev_som v4 label changed after the AI-prepared label review (v3 CONTRADICTED -> v4 INSUFFICIENT_EVIDENCE); "
                   "rev_reviewer2's reason closely matches that review's wording",
    "DEV-MSFT-05": "rev_som v4 label changed after the AI-prepared label review (v3 SUPPORTED -> v4 INSUFFICIENT_EVIDENCE)",
    "DEV-MSFT-06": "rev_som label kept but its definition (profitability = gross margin %) was written after the AI-prepared "
                   "label review; rev_reviewer2's reason closely matches that review's wording",
    "DEV-MSFT-07": "rev_som v4 label changed after the AI-prepared label review (v3 SUPPORTED -> v4 INSUFFICIENT_EVIDENCE); "
                   "rev_reviewer2's reason closely matches that review's wording",
}
MUST_ADJUDICATE = {**AI_AFFECTED, "DEV-AAPL-05": "rev_som INSUFFICIENT_EVIDENCE vs rev_reviewer2 SUPPORTED"}
EXCLUDED_REVIEWERS = {**lst.NOT_INDEPENDENT}
MODEL_ID = re.compile(r"(?i)^(claude|gpt|llm|model|ai|codex|gemini|openai|anthropic|bot)([-_:.]|$)")
FORBIDDEN_PATH_PARTS = ("design_intent", "llm_annotations", "dev-v0.2_author", os.sep + "results" + os.sep, "predictions", "trace")
# Strings that only exist in system outputs / AI files; none may appear in a packet sent to a person.
SYSTEM_TOKENS = ("A2_rag_numeric", "A3v2_1_1", "A3v2", "pred_A2", "pred_R", "pred_RG", "predicted_label", "guard_outcome",
                 "DECIDING_EVIDENCE", "CONTEXT_ONLY", "A2_NUMERIC_CONCLUSION", "INITIAL_VERDICT", "reconciliation",
                 "design_intent", "design intent", "author_notes", "ai_codex", "Codex", "ai_draft", "claude-opus",
                 "dev_label_review", "label review", "rev_person3")
FIRST_REVIEWERS = ("rev_som", "rev_person2")
INPUT_FILL = PatternFill("solid", start_color="FFF2CC")
HEAD_FONT = Font(name="Arial", size=10, bold=True)
BODY_FONT = Font(name="Arial", size=10)
WRAP = Alignment(wrap_text=True, vertical="top")


# ---------------------------------------------------------------- shared

def claims() -> dict:
    return {c.claim_id: c for c in load_claims(DATASET)}


def required_second() -> list[str]:
    """The fixed PRIMARY_44 set: ambiguous / interpretive claims without a dev-v0.1 second review (rev_reviewer2).
    Defined from the dataset and the pre-existing second review only, so it does not shrink once later
    annotation or adjudication is recorded."""
    r2 = agr.load(OLD_SECOND)
    return [c.claim_id for c in load_claims(DATASET) if c.claim_category in ("ambiguous", "interpretive") and c.claim_id not in r2]


def numerical_ids() -> list[str]:
    return [c.claim_id for c in claims().values() if c.claim_category == "numerical"]


def first_labels() -> dict[str, dict]:
    """Independent first label per claim: rev_som v3 (pre-review) for dev-v0.1, rev_person2 for the 48 new claims."""
    return {**agr.load(PRE_REVIEW), **agr.load(NEW_FIRST)}


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def known_ai_texts() -> list[str]:
    """Free text produced by AI for these claims: the Codex-filled workbook and the drafter's design intent."""
    out = []
    if os.path.exists(DESIGN_INTENT):
        out += [r.get("author_notes") for r in (json.loads(x) for x in open(DESIGN_INTENT, encoding="utf-8") if x.strip())]
    if os.path.exists(CODEX_WORKBOOK):
        cs = load_workbook(CODEX_WORKBOOK, read_only=True)["Claims"]
        rows = list(cs.iter_rows(values_only=True))
        cols = [i for i, h in enumerate(rows[0]) if h and ("Review notes" in str(h) or "Uncertainty note" in str(h))]
        out += [r[i] for r in rows[1:] for i in cols]
    return [t for t in (_norm(x) for x in out) if len(t) >= 30]


def check_source(path: str, ann_dir: str = ANN_DIR) -> list[str]:
    """Why a file cannot supply labels (empty list = usable)."""
    p = os.path.abspath(path)
    if not p.startswith(os.path.abspath(ann_dir) + os.sep):
        return [f"{path}: label sources must be in {os.path.relpath(ann_dir, RESEARCH_ROOT)}/"]
    bad = [x for x in FORBIDDEN_PATH_PARTS if x in p]
    if bad:
        return [f"{path}: path marks it as {bad} (not a human annotation)"]
    probs = []
    for i, line in enumerate(open(p, encoding="utf-8"), 1):
        if not line.strip():
            continue
        r = json.loads(line)
        rid = str(r.get("reviewer_id") or "")
        if r.get("reviewer_type") != "human":
            probs.append(f"{path}:{i}: reviewer_type {r.get('reviewer_type')!r} is not 'human'")
        if not rid or MODEL_ID.match(rid):
            probs.append(f"{path}:{i}: reviewer id {rid!r} looks like a model")
        if rid in EXCLUDED_REVIEWERS:
            probs.append(f"{path}:{i}: reviewer {rid} is excluded ({EXCLUDED_REVIEWERS[rid]})")
        if r.get("gold_label") not in LABELS:
            probs.append(f"{path}:{i}: label {r.get('gold_label')!r}")
    return probs


def screen_independence(rows: dict[str, dict], first: dict[str, dict], ai_texts: list[str] | None = None) -> list[str]:
    """A second label is not independent if its free text repeats AI-produced text or the first labeller's notes."""
    ai_texts = known_ai_texts() if ai_texts is None else ai_texts
    probs = []
    for cid, r in rows.items():
        for field in ("review_notes", "uncertainty_note"):
            t = _norm(r.get(field))
            if len(t) < 30:
                continue
            if any(t == a or a in t for a in ai_texts):
                probs.append(f"{cid}: {field} repeats AI-produced text (Codex workbook / design intent)")
            f = first.get(cid)
            if f and r["reviewer_id"] != f["reviewer_id"] and t == _norm(f.get(field)):
                probs.append(f"{cid}: {field} is identical to the first labeller's ({f['reviewer_id']})")
        f = first.get(cid)
        if f and r["reviewer_id"] == f["reviewer_id"]:
            probs.append(f"{cid}: {r['reviewer_id']} is the first labeller of this claim")
    return probs


def load_second(path: str, first: dict, ann_dir: str = ANN_DIR, ai_texts=None) -> dict[str, dict]:
    probs = check_source(path, ann_dir)
    rows = agr.load(path) if not probs else {}
    probs += screen_independence(rows, first, ai_texts)
    if probs:
        raise SchemaError("label source refused:\n  " + "\n  ".join(probs))
    return rows


def _sha(path: str) -> str:
    return file_sha256(path)


def _rel(path: str) -> str:
    return os.path.relpath(os.path.abspath(path), RESEARCH_ROOT)


def _no_overwrite(*paths):
    for p in paths:
        if os.path.exists(p):
            raise SystemExit(f"{p} exists; outputs are not overwritten")


def _style_sheet(ws, widths, input_from=None, header=True):
    for row in ws.iter_rows():
        for c in row:
            c.font = HEAD_FONT if header and c.row == 1 else BODY_FONT
            c.alignment = WRAP
            if input_from and c.row > 1 and c.column >= input_from:
                c.fill = INPUT_FILL
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if header:
        ws.freeze_panes = "B2"


def _list_dv(ws, values, rng):
    dv = DataValidation(type="list", formula1='"' + ",".join(values) + '"', allow_blank=True, showErrorMessage=True,
                        error="เลือกจากรายการเท่านั้น")
    ws.add_data_validation(dv)
    dv.add(rng)


# ---------------------------------------------------------------- packet audit

def forbidden_strings() -> list[str]:
    """Text that must never reach an annotator / adjudicator: system-output tokens, AI-produced text, and
    every first-annotation note (they would reveal the first annotator's answer)."""
    out = list(SYSTEM_TOKENS) + known_ai_texts()
    for p in (PRE_REVIEW, POST_REVIEW, NEW_FIRST, OLD_SECOND):
        out += [t for r in agr.load(p).values() for t in (_norm(r.get("review_notes")), _norm(r.get("uncertainty_note"))) if len(t) >= 30]
    return out


def audit_workbook(path: str, expected_ids: list[str], sheet: str = "Claims", allowed=(), forbidden=None) -> dict:
    """Blindness audit of a workbook for a person. `allowed` are strings the packet may legitimately carry
    (e.g. the two annotations an adjudicator must see)."""
    wb = load_workbook(path)
    ws = wb[sheet]
    head = [c.value for c in ws[1]]
    ids = [r[0] for r in ws.iter_rows(min_row=2, values_only=True) if r[0]]
    problems = []
    if sorted(ids) != sorted(expected_ids) or len(ids) != len(set(ids)):
        problems.append(f"{sheet} ids: {len(ids)} rows, {len(set(ids))} unique; missing {sorted(set(expected_ids) - set(ids))}, "
                        f"extra {sorted(set(ids) - set(expected_ids))}")
    forbidden = forbidden_strings() if forbidden is None else forbidden
    allowed_n = {_norm(a) for a in allowed if a}
    hits = []
    for s in wb.worksheets:
        for row in s.iter_rows():
            for c in row:
                if not isinstance(c.value, str) or c.value.startswith("="):
                    continue
                v = _norm(c.value)
                if v in allowed_n:
                    continue
                for f in forbidden:
                    if _norm(f) in v and not any(_norm(f) in a for a in allowed_n):
                        hits.append(f"{s.title}!{c.coordinate}: contains {f[:60]!r}")
                        break
    problems += hits
    return {"workbook": _rel(path), "sha256": _sha(path), "sheet": sheet, "claims": len(ids), "expected": len(expected_ids),
            "header": head, "problems": problems, "blind": not problems}


def audit_blind_annotation(path: str, expected_ids: list[str], forbidden=None) -> dict:
    res = audit_workbook(path, expected_ids, forbidden=forbidden)
    wb = load_workbook(path)
    cs = wb["Claims"]
    head = [c.value for c in cs[1]]
    inputs = [i for i, h in enumerate(head) if h and str(h).startswith("✎")]
    filled = [f"Claims!{get_column_letter(i + 1)}{r}" for r, row in enumerate(cs.iter_rows(min_row=2, values_only=True), 2)
              for i in inputs if row[0] and row[i] not in (None, "")]
    ev = wb["Evidence"]
    ev_head = [c.value for c in ev[1]]
    ev_filled = [f"Evidence!{get_column_letter(i + 1)}{r}" for r, row in enumerate(ev.iter_rows(min_row=2, values_only=True), 2)
                 for i, h in enumerate(ev_head) if h and str(h).startswith("✎") and row[i] not in (None, "") and not str(row[i]).startswith("=")]
    rid = [r[1] for r in wb["คำแนะนำ"].iter_rows(values_only=True) if r[0] and str(r[0]).startswith("✎ Reviewer ID")]
    labels_in_data = [f"Claims row {r}" for r, row in enumerate(cs.iter_rows(min_row=2, values_only=True), 2)
                      if any(isinstance(v, str) and v in LABELS for v in row)]
    res["problems"] += ([f"pre-filled input cells: {filled[:10]}"] if filled else []) + \
                       ([f"pre-filled evidence cells: {ev_filled[:10]}"] if ev_filled else []) + \
                       ([f"reviewer id pre-filled: {rid}"] if any(rid) else []) + \
                       ([f"label values in claim rows: {labels_in_data}"] if labels_in_data else [])
    res["checks"] = {"no_system_predictions": True, "no_ai_labels_or_explanations": True, "no_first_annotator_answers": True,
                     "no_design_intent": True, "inputs_blank": not filled and not ev_filled, "reviewer_id_blank": not any(rid)}
    if res["problems"]:
        res["checks"] = {k: None for k in res["checks"]}
    res["blind"] = not res["problems"]
    return res


# ---------------------------------------------------------------- 1-2 blind second-annotation package

def blind_package(out: str, audit_out: str) -> dict:
    _no_overwrite(out, audit_out)
    ids = required_second()
    if len(ids) != 44:
        raise SystemExit(f"expected 44 claims requiring second annotation, found {len(ids)}: {ids}")
    dwb.export(out, (DATASET,), ids=ids)
    wb = load_workbook(out)
    ws = wb.create_sheet("อ่านก่อน", 0)
    for i, t in enumerate([
            "ผู้ติด label คนที่สอง (อิสระ): ห้ามดู label/เหตุผลของผู้ติด label คนแรก, ผลของระบบ (A2/A3), ไฟล์ที่ AI กรอก หรือถาม AI ใด ๆ",
            "ผู้ติด label ต้องไม่ใช่ rev_som และไม่ใช่ rev_person2 (ผู้ติด label คนแรกของ claim ชุดนี้)",
            f"ชุดนี้มี {len(ids)} claim (ambiguous / interpretive ที่ยังมีผู้ติด label คนเดียว); กรอกครบทุกข้อ",
            "เมื่อเสร็จ ส่งไฟล์คืนผู้วิจัย: import ด้วย scripts/dev_annotation_workbook.py import <file> --claims datasets/development_cases_dev-v0.2.jsonl"], 2):
        ws.cell(i, 1, t).font = Font(name="Arial", size=10, bold=True, color="C00000")
    wb.save(out)
    audit = audit_blind_annotation(out, ids)
    audit.update({"purpose": "independent second annotation (dev-v0.2)", "required_ids": ids,
                  "by_type": dict(Counter(claims()[i].claim_category for i in ids)), "tool": TOOL_VERSION,
                  "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    os.makedirs(os.path.dirname(audit_out), exist_ok=True)
    json.dump(audit, open(audit_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not audit["blind"]:
        raise SystemExit(f"blindness audit failed: {audit['problems']}")
    return audit


# ---------------------------------------------------------------- 3 AAPL-05 packet

def aapl05_packet(out: str, audit_out: str) -> dict:
    _no_overwrite(out, audit_out)
    v3, v4, r2 = agr.load(PRE_REVIEW), agr.load(POST_REVIEW), agr.load(OLD_SECOND)
    cid = "DEV-AAPL-05"
    if (v3[cid]["gold_label"], _norm(v3[cid]["review_notes"])) != (v4[cid]["gold_label"], _norm(v4[cid]["review_notes"])):
        raise SystemExit("AAPL-05 differs between rev_som v3 and v4; the packet would need the pre-review record")
    adj = load_adjudications(ADJ) if os.path.exists(ADJ) else {}
    if cid in adj:
        raise SystemExit(f"{cid} is already adjudicated")
    ids = da.export(POST_REVIEW, OLD_SECOND, out)
    if ids != [cid]:
        raise SystemExit(f"expected only {cid} to disagree, got {ids}")
    fixes = [f for f in json.load(open(os.path.join(ANN_DIR, "rev_reviewer2.fix.json")))["changes"] if f.get("claim_id") == cid] \
        if os.path.exists(os.path.join(ANN_DIR, "rev_reviewer2.fix.json")) else []
    wb = load_workbook(out)
    pv = wb.create_sheet("Provenance")
    pv.append(["Item", "Record"])
    for a, b in [
        ("Claim", f"{cid} (dev-v0.1, interpretive). Status: DISAGREED"),
        ("Reviewer A", f"rev_som; label {v3[cid]['gold_label']}. Pre-review (v3) and post-review (v4) records are identical "
                       "for this claim (label and notes)"),
        ("Reviewer B", f"rev_reviewer2; label {r2[cid]['gold_label']}. Blind second review of 8 dev-v0.1 claims"),
        ("Format fixes to B's evidence", f"{len(fixes)} change(s) recorded in rev_reviewer2.fix.json (value renames / context rows "
                                         "moved out; labels and notes untouched)"),
        ("Not included", "No system output, no AI-prepared material, no AI-filled file, no drafting notes"),
    ]:
        pv.append([a, b])
    _style_sheet(pv, [28, 120])
    dc = wb.create_sheet("Declaration")
    dc.append(["Statement (adjudicator answers ใช่ / ไม่ใช่)", "✎ Answer"])
    for s in ["ฉันไม่ใช่ rev_som และไม่ใช่ rev_reviewer2",
              "ฉันไม่เคยเห็นผลของระบบ (A2 / A3 / RG), workbook ตรวจหลักฐาน หรือรายงานที่ AI เตรียมสำหรับ claim นี้",
              "ฉันไม่ได้ใช้ AI ช่วยตัดสิน",
              "ฉันเปิดรายงาน SEC จากชีต Filings และตัดสินตาม annotation_guidelines.md + dev_annotation_guidelines.md"]:
        dc.append([s, None])
    _style_sheet(dc, [100, 14], input_from=2)
    _list_dv(dc, ("ใช่", "ไม่ใช่"), "B2:B5")
    wb["วิธีใช้"].append(["ก่อนกรอก ให้ตอบชีต Declaration ให้ครบ: ถ้าข้อใดตอบ “ไม่ใช่” ให้คืนไฟล์และหาผู้ตัดสินคนอื่น"])
    wb.save(out)
    allowed = [x for r in (v4[cid], r2[cid]) for x in (r.get("review_notes"), da._evidence(r))]
    audit = audit_workbook(out, [cid], sheet="Adjudication", allowed=allowed)
    audit.update({"tool": TOOL_VERSION, "record_with": "scripts/dev_adjudication.py record <filled packet>",
                  "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    os.makedirs(os.path.dirname(audit_out), exist_ok=True)
    json.dump(audit, open(audit_out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not audit["blind"]:
        raise SystemExit(f"packet audit failed: {audit['problems']}")
    return audit


# ---------------------------------------------------------------- 5 numerical verification checklist

NUM_CLAIM_HEAD = ["Claim ID", "Company", "Claim", "Reporting period", "Evidence cutoff", "Eligible filings",
                  "✎ Metric(s) the claim tests", "✎ Formula (use input refs I1, I2 …)", "✎ Computed result",
                  "✎ Result unit", "✎ Claim threshold / comparison", "✎ Rounding changes the outcome?",
                  "✎ Period check", "✎ Units / scale check", "✎ Sources check", "✎ Calculation done with",
                  "✎ Calculation file / location", "✎ Verifier conclusion", "✎ Confidence", "✎ Notes"]
NUM_INPUT_HEAD = ["Claim ID", "Input ref", "✎ Line item / XBRL concept", "✎ Value as reported", "✎ Scale", "✎ Unit",
                  "✎ Period start", "✎ Period end", "✎ Duration", "✎ Fiscal period label", "✎ Source form",
                  "✎ Accession number", "✎ Location in filing", "✎ Derived from other inputs?", "✎ Notes"]
NUM_LISTS = {
    "✎ Rounding changes the outcome?": ("NO", "YES"),
    "✎ Period check": ("MATCHES_CLAIM_PERIOD", "DERIVED_AND_VERIFIED", "MISMATCH", "UNCLEAR"),
    "✎ Units / scale check": ("CONSISTENT", "CONVERTED_AND_NOTED", "PROBLEM"),
    "✎ Sources check": ("ALL_ELIGIBLE", "SOME_INELIGIBLE"),
    "✎ Calculation done with": ("HAND", "CALCULATOR", "SPREADSHEET", "OTHER"),
    "✎ Verifier conclusion": LABELS,
    "✎ Confidence": ("HIGH", "MEDIUM", "LOW"),
    "✎ Scale": ("UNITS", "THOUSANDS", "MILLIONS", "BILLIONS"),
    "✎ Unit": ("USD", "SHARES", "USD_PER_SHARE", "PERCENT", "RATIO", "OTHER"),
    "✎ Duration": ("QUARTER", "YEAR_TO_DATE", "FISCAL_YEAR", "INSTANT", "DERIVED_PERIOD"),
    "✎ Source form": ("10-K", "10-K/A", "10-Q", "10-Q/A", "8-K"),
    "✎ Derived from other inputs?": ("NO", "YES"),
}
NUM_CHECKLIST = [
    ("1 Formula", "เขียนสูตรที่ claim ต้องการด้วย input ref (เช่น (I1 − I2) / I2 สำหรับการเติบโต YoY, I1 / I2 สำหรับ margin, I1 − I2 สำหรับ FCF = OCF − capex) และสูตรต้องตรงกับนิยามที่ claim ใช้"),
    ("2 Period", "แต่ละ input ระบุ period start/end และ duration: ไตรมาสเดียว / สะสม (YTD) / ทั้งปี / ณ วันที่ (instant). งวดต้องตรงกับที่ claim ระบุ; ถ้าต้องสร้างงวดเอง (เช่น Q4 = FY − 9M YTD, TTM) ให้ใส่ input ทุกตัวที่ใช้และเลือก DERIVED_AND_VERIFIED"),
    ("3 Fiscal calendar", "ใช้ปีบัญชีของบริษัท (เช่น Apple Q3 FY2026 สิ้นสุด 27 มิ.ย. 2026; Microsoft FY สิ้นสุด 30 มิ.ย.); ห้ามเดาจากปีปฏิทิน"),
    ("4 Units and scale", "บันทึกค่าตามที่รายงาน + scale (ล้าน/พันล้าน) + หน่วย; แปลงให้หน่วยเดียวกันก่อนคำนวณ; % ใช้ทศนิยมที่ claim ใช้"),
    ("5 SEC sources", "ทุก input ต้องมาจาก filing ของบริษัทเดียวกันในชีต Filings ที่ยื่นก่อนหรือในวันตัดหลักฐาน และเป็นแบบฟอร์มที่ claim อนุญาต; ใส่ accession และตำแหน่ง (งบ / note / หน้า)"),
    ("6 Calculation provenance", "บอกว่าคำนวณด้วยอะไร และไฟล์/ตำแหน่ง (เช่น calc_DEV-AAPL-01.xlsx!B4) เพื่อให้ตรวจซ้ำได้; ห้ามใช้ AI คำนวณหรือหาเลข"),
    ("7 Rounding", "ถ้าผลอยู่ใกล้เกณฑ์ของ claim จนการปัดเศษเปลี่ยนคำตอบ ให้เลือก YES และอธิบายใน Notes"),
    ("8 Conclusion", "สรุปตามกฎ label ของ gold guideline: ส่วนใดเท็จ = CONTRADICTED; ทุกส่วนจริง = SUPPORTED; หาตัวเลข/งวดไม่ได้หรือไม่ชัด = INSUFFICIENT_EVIDENCE"),
]


def numeric_checklist(out: str, rows_per_claim: int = 6) -> list[str]:
    _no_overwrite(out)
    cs_all = claims()
    ids = numerical_ids()
    manifest = dwb.aw.load_manifest()
    wb = Workbook()
    ins = wb.active
    ins.title = "คำแนะนำ"
    for r in [("ตรวจ claim เชิงตัวเลข ชุด dev-v0.2 (ไม่ใช่ Gold)", ""),
              ("✎ Verifier ID (ภาษาอังกฤษ ไม่มีเว้นวรรค เช่น rev_somchai)", None),
              ("ความเป็นอิสระ", "ผู้ตรวจต้องไม่ใช่ผู้ติด label คนแรกของ claim (rev_som สำหรับ AAPL/MSFT/AMZN, rev_person2 สำหรับ ADBE/INTC/PG/CAT); "
                               "ห้ามดู label ของคนอื่น ผลของระบบ (A2/A3) ไฟล์ที่ AI กรอก และห้ามใช้ AI"),
              ("วิธีกรอก", "ชีต Claims: หนึ่งแถวต่อ claim (ช่องสีเหลือง). ชีต Inputs: หนึ่งแถวต่อตัวเลขที่ใช้ (I1, I2 …); เพิ่มแถวได้ถ้าไม่พอ"),
              ("ตัวอย่างสมมติ (บริษัท ExampleCo ไม่มีอยู่จริง)", "Formula: (I1 − I2) / I2 · I1 = Revenue 1,250 MILLIONS USD, 2030-01-01 → 2030-03-31, QUARTER, 10-Q 0000000000-30-000001, "
                                                 "Income statement · I2 = ไตรมาสเดียวกันปีก่อน 1,000 · Computed result 0.25 RATIO · threshold > 0.20 · Rounding NO · conclusion SUPPORTED"),
              ("", ""), ("Checklist", "ทุก claim ต้องผ่านทุกข้อก่อนเลือก Verifier conclusion")] + NUM_CHECKLIST:
        ins.append(list(r))
    _style_sheet(ins, [34, 130], header=False)
    ins["B2"].fill = INPUT_FILL
    cs = wb.create_sheet("Claims")
    cs.append(NUM_CLAIM_HEAD)
    for cid in ids:
        c = cs_all[cid]
        fl = dwb.dev_eligible_filings(c, manifest)
        cs.append([cid, c.company, c.claim, c.reporting_period, c.as_of_date,
                   "\n".join(f"{f['form']} {f['accession_number']} filed {f['filed']}" for f in fl)] + [None] * (len(NUM_CLAIM_HEAD) - 6))
    _style_sheet(cs, [13, 8, 50, 12, 11, 34, 24, 30, 14, 10, 20, 12, 22, 20, 16, 14, 24, 22, 11, 40], input_from=7)
    n = len(ids) + 1
    for h, vals in NUM_LISTS.items():
        if h in NUM_CLAIM_HEAD:
            col = get_column_letter(NUM_CLAIM_HEAD.index(h) + 1)
            _list_dv(cs, vals, f"{col}2:{col}{n}")
    ip = wb.create_sheet("Inputs")
    ip.append(NUM_INPUT_HEAD)
    for cid in ids:
        for k in range(1, rows_per_claim + 1):
            ip.append([cid, f"I{k}"] + [None] * (len(NUM_INPUT_HEAD) - 2))
    _style_sheet(ip, [13, 8, 34, 16, 12, 14, 12, 12, 16, 14, 10, 24, 30, 12, 34], input_from=3)
    m = ip.max_row + 200
    for h, vals in NUM_LISTS.items():
        if h in NUM_INPUT_HEAD:
            col = get_column_letter(NUM_INPUT_HEAD.index(h) + 1)
            _list_dv(ip, vals, f"{col}2:{col}{m}")
    fs = wb.create_sheet("Filings")
    fs.append(["Accession", "Company", "Form", "Filed", "SEC link"])
    for f in manifest:
        if any(f["company"] == cs_all[i].company for i in ids):
            fs.append([f["accession_number"], f["company"], f["form"], f["filed"], dwb.aw.filing_url(f)])
            fs.cell(fs.max_row, 5).hyperlink = dwb.aw.filing_url(f)
    _style_sheet(fs, [24, 9, 8, 11, 90])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    return ids


def _date(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if v in (None, ""):
        return None
    return date.fromisoformat(str(v).strip()[:10]).isoformat()


def read_numeric(path: str) -> list[dict]:
    wb = load_workbook(path, data_only=True)
    if [c.value for c in wb["Claims"][1]] != NUM_CLAIM_HEAD or [c.value for c in wb["Inputs"][1]] != NUM_INPUT_HEAD:
        raise SchemaError("not a workbook made by numeric-checklist (headers differ)")
    vid = next((r[1] for r in wb["คำแนะนำ"].iter_rows(values_only=True) if r[0] and str(r[0]).startswith("✎ Verifier ID")), None)
    vid = str(vid or "").strip()
    errors = []
    if not vid or " " in vid or MODEL_ID.match(vid) or vid in EXCLUDED_REVIEWERS:
        errors.append(f"verifier id {vid!r}: required, no spaces, not a model id or excluded reviewer")
    cs_all, manifest, first = claims(), dwb.aw.load_manifest(), first_labels()
    inputs = defaultdict(list)
    for r, row in enumerate(wb["Inputs"].iter_rows(min_row=2, values_only=True), 2):
        d = dict(zip(NUM_INPUT_HEAD, row))
        if not d["Claim ID"] or all(d[h] in (None, "") for h in NUM_INPUT_HEAD[2:]):
            continue
        cid = d["Claim ID"]
        if cid not in cs_all:
            errors.append(f"Inputs row {r}: unknown claim {cid}")
            continue
        eligible = {f["accession_number"]: f for f in dwb.dev_eligible_filings(cs_all[cid], manifest)}
        for h in ("✎ Line item / XBRL concept", "✎ Value as reported", "✎ Scale", "✎ Unit", "✎ Period end", "✎ Duration",
                  "✎ Source form", "✎ Accession number", "✎ Location in filing"):
            if d[h] in (None, ""):
                errors.append(f"Inputs row {r} ({cid} {d['Input ref']}): {h[2:]} is required")
        for h, vals in NUM_LISTS.items():
            if h in d and d[h] not in (None, "") and d[h] not in vals:
                errors.append(f"Inputs row {r}: {h[2:]} {d[h]!r} not in {vals}")
        if d["✎ Duration"] == "INSTANT" and str(d["✎ Period start"] or "").strip().upper() in ("N/A", "NA", "-"):
            d["✎ Period start"] = None  # a balance at a date has no start
        try:
            ps, pe = _date(d["✎ Period start"]), _date(d["✎ Period end"])
        except ValueError:
            errors.append(f"Inputs row {r}: period dates must be YYYY-MM-DD")
            ps = pe = None
        acc = str(d["✎ Accession number"] or "").strip()
        if acc and acc not in eligible:
            errors.append(f"Inputs row {r} ({cid}): accession {acc} is not an eligible {cs_all[cid].company} filing filed on or before "
                          f"{cs_all[cid].as_of_date} in an allowed form")
        elif acc and d["✎ Source form"] and eligible[acc]["form"] != d["✎ Source form"]:
            errors.append(f"Inputs row {r}: accession {acc} is a {eligible[acc]['form']}, not {d['✎ Source form']}")
        if pe and pe > cs_all[cid].as_of_date:
            errors.append(f"Inputs row {r}: period end {pe} is after the evidence cutoff")
        inputs[cid].append({"ref": d["Input ref"], "line_item": d["✎ Line item / XBRL concept"], "value": d["✎ Value as reported"],
                            "scale": d["✎ Scale"], "unit": d["✎ Unit"], "period_start": ps, "period_end": pe,
                            "duration": d["✎ Duration"], "fiscal_period": d["✎ Fiscal period label"], "form": d["✎ Source form"],
                            "accession_number": acc, "locator": d["✎ Location in filing"],
                            "derived": d["✎ Derived from other inputs?"] == "YES", "notes": d["✎ Notes"]})
    out, src = [], _sha(path)
    for r, row in enumerate(wb["Claims"].iter_rows(min_row=2, values_only=True), 2):
        d = dict(zip(NUM_CLAIM_HEAD, row))
        cid, label = d["Claim ID"], d["✎ Verifier conclusion"]
        if not cid or label in (None, ""):
            continue
        for h, vals in NUM_LISTS.items():
            if h in d and d[h] not in (None, "") and d[h] not in vals:
                errors.append(f"Claims row {r}: {h[2:]} {d[h]!r} not in {vals}")
        need = ["✎ Formula (use input refs I1, I2 …)", "✎ Computed result", "✎ Period check", "✎ Units / scale check",
                "✎ Sources check", "✎ Calculation done with", "✎ Confidence"]
        if label != "INSUFFICIENT_EVIDENCE":
            need += ["✎ Claim threshold / comparison", "✎ Rounding changes the outcome?"]
        errors += [f"Claims row {r} ({cid}): {h[2:]} is required" for h in need if d[h] in (None, "")]
        if label != "INSUFFICIENT_EVIDENCE" and not inputs.get(cid):
            errors.append(f"Claims row {r} ({cid}): a {label} conclusion needs its inputs in the Inputs sheet")
        if label != "INSUFFICIENT_EVIDENCE" and d["✎ Sources check"] == "SOME_INELIGIBLE":
            errors.append(f"Claims row {r} ({cid}): a decisive conclusion cannot rest on ineligible sources")
        refs = set(re.findall(r"\bI\d+\b", str(d["✎ Formula (use input refs I1, I2 …)"] or "")))
        missing_refs = sorted(refs - {i["ref"] for i in inputs.get(cid, [])})
        if missing_refs:
            errors.append(f"Claims row {r} ({cid}): formula uses {missing_refs} with no matching input row")
        if first.get(cid, {}).get("reviewer_id") == vid:
            errors.append(f"Claims row {r} ({cid}): {vid} is this claim's first labeller; the verifier must be someone else")
        notes = f"[numeric verification] formula: {d['✎ Formula (use input refs I1, I2 …)']}; result: {d['✎ Computed result']} " \
                f"{d['✎ Result unit'] or ''}; threshold: {d['✎ Claim threshold / comparison']}; period: {d['✎ Period check']}; " \
                f"units: {d['✎ Units / scale check']}; sources: {d['✎ Sources check']}" + (f"\n{d['✎ Notes']}" if d["✎ Notes"] else "")
        out.append({"claim_id": cid, "reviewer_id": vid, "gold_label": label, "reviewer_type": "human",
                    "annotation_kind": "numeric_verification", "supporting_evidence": [], "contradictory_evidence": [],
                    "review_notes": notes, "confidence": d["✎ Confidence"], "uncertainty_type": None, "uncertainty_note": d["✎ Notes"],
                    "numeric_check": {k[2:]: d[k] for k in NUM_CLAIM_HEAD[6:]}, "inputs": inputs.get(cid, []),
                    "split": "development", "dataset_version": "dev-v0.2", "source_workbook_sha256": src,
                    "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": TOOL_VERSION})
        if cid not in cs_all or cs_all[cid].claim_category != "numerical":
            errors.append(f"Claims row {r}: {cid} is not a numerical dev-v0.2 claim")
    if errors:
        raise SchemaError("numeric checklist has problems; nothing was written:\n  " + "\n  ".join(errors))
    return out


def numeric_import(path: str, ann_dir: str = ANN_DIR) -> str:
    rows = read_numeric(path)
    if not rows:
        raise SchemaError("no claim has a verifier conclusion")
    target = os.path.join(ann_dir, f"numcheck_{rows[0]['reviewer_id']}.jsonl")
    _no_overwrite(target)
    probs = screen_independence({r["claim_id"]: r for r in rows}, first_labels())
    if probs:
        raise SchemaError("numeric verification refused:\n  " + "\n  ".join(probs))
    with open(target, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows)
    return target


# ---------------------------------------------------------------- 4 provenance

def provenance_rows() -> list[dict]:
    cs_all = claims()
    status = {r["claim_id"]: r for r in lst.status_rows()}
    v3, v4, r2, p2 = agr.load(PRE_REVIEW), agr.load(POST_REVIEW), agr.load(OLD_SECOND), agr.load(NEW_FIRST)
    p2_fix = {f["claim_id"] for f in json.load(open(os.path.join(ANN_DIR, "rev_person2.fix.json")))["changes"]}
    r2_fix = {f["claim_id"] for f in json.load(open(os.path.join(ANN_DIR, "rev_reviewer2.fix.json")))["changes"] if f.get("claim_id")}
    rows, primary = [], set(required_second())
    for cid, c in cs_all.items():
        old = cid in v3
        flags, ai_events = [], []
        if not old:
            ai_events.append("claim text and design intent drafted by AI (ai_draft_claude-opus-5-5); design intent kept from annotators")
            ai_events.append("an AI-filled workbook (ai_codex_dev48) exists for this claim; not a label, excluded")
            if cid in p2_fix:
                ai_events.append("AI analyst corrected evidence cells (concept name / verbatim quote) in rev_person2's workbook; label and notes untouched")
        if cid in AI_AFFECTED:
            flags.append("FIRST_LABEL_AFTER_AI_REVIEW" if v3[cid]["gold_label"] != v4[cid]["gold_label"] else "DEFINITION_AFTER_AI_REVIEW")
            ai_events.append(AI_AFFECTED[cid])
        if cid in r2_fix:
            ai_events.append("AI analyst fixed the format of rev_reviewer2's evidence rows (value renames / context rows moved out)")
        s = status[cid]
        kappa_subset = ("PRIMARY_44" if cid in primary else
                        "HISTORICAL_DEV_V0_1" if cid in r2 else
                        "NUMERICAL_VERIFICATION" if c.claim_category == "numerical" else "NONE")
        route = ("ADJUDICATION (third person)" if cid in MUST_ADJUDICATE else
                 "AGREED with independent second label, else adjudication" if cid in primary or c.claim_category == "numerical"
                 else "AGREED (pending approval)" if s["status"] == "AGREED" else "—")
        rows.append({
            "claim_id": cid, "claim_type": c.claim_category, "dataset_version": "dev-v0.1" if old else "dev-v0.2-new",
            "claim_author": "not recorded (dev-v0.1)" if old else "AI (ai_draft_claude-opus-5-5)",
            "first_labeller": "rev_som" if old else "rev_person2",
            "first_label_for_kappa": (v3 if old else p2)[cid]["gold_label"],
            "first_label_source": "rev_som.v3.jsonl (pre AI review)" if old else "rev_person2.dev-v0_2.jsonl",
            "post_review_label": v4[cid]["gold_label"] if old else None,
            "second_labeller": "rev_reviewer2" if cid in r2 else None, "second_label": r2[cid]["gold_label"] if cid in r2 else None,
            "status": s["status"], "ai_exposure_flags": flags, "ai_involvement": ai_events,
            "kappa_subset": kappa_subset, "approval_route": route,
            "excluded_sources": ["ai_codex_dev48", "rev_person3", "design_intent_dev-v0.2"] if not old else [],
        })
    return rows


def render_provenance(rows: list[dict]) -> str:
    ai = [r for r in rows if r["ai_exposure_flags"]]
    L = ["# dev-v0.2 annotation provenance", "",
         f"- **Generated:** {date.today().isoformat()} by `scripts/dev_v0_2_human_workflow.py provenance` (read-only).",
         "- **Scope:** 72 claims. No label was created or changed.", "",
         "## Sources of labels", "",
         "| Source | Who | Claims | Usable for | Notes |", "|---|---|---|---|---|",
         "| `rev_som.v3.jsonl` | rev_som (researcher) | 24 dev-v0.1 | first label, κ | before the AI-prepared label review |",
         "| `rev_som.v4.jsonl` | rev_som | 24 dev-v0.1 | informational only | 4 claims decided / defined after the AI-prepared label review |",
         "| `rev_reviewer2.jsonl` | rev_reviewer2 (attested independent person) | 8 dev-v0.1 | second label, κ (historical) | evidence format fixed by the AI analyst; on AAPL-07, MSFT-06, MSFT-07 the reasons closely match the AI review's wording |",
         "| `rev_person2.dev-v0_2.jsonl` | rev_person2 (attested person) | 48 new | first label, κ | 6 evidence cells fixed by the AI analyst; labels match the Codex workbook on 47/48 and design intent on 46/48 (observed; researcher attests the labeller never saw Codex) |",
         "| `dev_blind_review_dev-v0.2_40_{filled,reviewed}.xlsx` (rev_person3) | — | 40 | **not usable** | content identical to the Codex workbook |",
         "| `dev_annotation_workbook_dev-v0.2_new48.xlsx` (ai_codex_dev48) | AI | 48 | **not usable** | AI-filled |",
         "| `design_intent_dev-v0.2.jsonl` | AI drafter | 48 | **not usable** | author expectation, not a label |",
         "| A2 / A3v2.1.1 R / RG predictions | system | 72 | **never** a label source | |", "",
         f"## Claims affected by prior AI review ({len(ai)}): adjudication required", "",
         "| Claim | Flag | Pre-review label (κ) | Post-review label | rev_reviewer2 | Record |", "|---|---|---|---|---|---|"]
    L += [f"| {r['claim_id']} | {', '.join(r['ai_exposure_flags'])} | {r['first_label_for_kappa']} | {r['post_review_label']} | "
          f"{r['second_label']} | {AI_AFFECTED[r['claim_id']]} |" for r in ai]
    L += ["", "These four are excluded from AGREED approval: an independent third person adjudicates them "
          "(`adjudication-packet` puts them in the packet with the **pre-review** v3 record, not v4). κ uses v3.", "",
          "## AI involvement by claim group", "",
          "- **48 new claims (dev-v0.2):**",
          "  - claim text and design intent were drafted by AI;",
          "  - an AI-filled workbook exists and is excluded;",
          "  - rev_person2's labels agree with that AI workbook on 47/48 claims. This is disclosed as a limitation of the "
          "first labels' independence; it rests on the researcher's attestation.",
          "- **24 dev-v0.1 claims:** first labels v1–v3 predate any AI review. v4 is not used for κ or approval.",
          "- **Tools and workbooks** were prepared by the AI analyst; none carries a label, a model output or a first-annotator answer "
          "(see the blind audits).", "",
          "## Per-claim record", "",
          "| Claim | Type | Version | Author | First (κ) | Second | Status | κ subset | Approval route | AI involvement |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['claim_id']} | {r['claim_type']} | {r['dataset_version']} | {r['claim_author']} | {r['first_labeller']}: "
          f"{r['first_label_for_kappa']} | {r['second_labeller'] or '—'}: {r['second_label'] or '—'} | {r['status']} | "
          f"{r['kappa_subset']} | {r['approval_route']} | {len(r['ai_involvement'])} |" for r in rows]
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 6 agreement

def _kappa_block(pairs: list[tuple[str, str]], n_boot: int = 2000) -> dict:
    if not pairs:
        return {"n": 0}
    lo, hi = bootstrap_agreement(pairs, cohen_kappa, n_boot=n_boot)
    return {"n": len(pairs), "raw_agreement": sum(a == b for a, b in pairs) / len(pairs), "cohen_kappa": cohen_kappa(pairs),
            "kappa_ci95_bootstrap": [lo, hi], "confusion": {f"{a}|{b}": n for (a, b), n in sorted(Counter(pairs).items())}}


def agreement(second: str | None, numeric: str | None = None, ann_dir: str = ANN_DIR, n_boot: int = 2000) -> dict:
    cs_all, first = claims(), first_labels()
    req = required_second()
    res = {"tool": TOOL_VERSION, "first_label_sources": {"dev-v0.1": _rel(PRE_REVIEW), "dev-v0.2-new": _rel(NEW_FIRST)},
           "excluded_from_all_kappa": {"rev_som.v4": "post AI review", **EXCLUDED_REVIEWERS,
                                       "design_intent": "AI author expectation", "A2/R/RG": "system outputs", "adjudications": "not an annotation"}}
    r2 = agr.load(OLD_SECOND)
    hp = [(first[c]["gold_label"], r2[c]["gold_label"]) for c in sorted(r2)]
    res["historical_dev_v0_1"] = {"pair": "rev_som v3 vs rev_reviewer2", "claims": sorted(r2), **_kappa_block(hp, n_boot),
                                  "caveat": "8 claims; reviewer2's reasons on AAPL-07, MSFT-06, MSFT-07 closely match the AI review's wording"}
    if second:
        s = load_second(second, first, ann_dir)
        sid = next(iter(s.values()))["reviewer_id"]
        shared = [c for c in req if c in s]
        pairs = [(first[c]["gold_label"], s[c]["gold_label"]) for c in shared]
        by_first, by_type = defaultdict(list), defaultdict(list)
        for c, p in zip(shared, pairs):
            by_first[first[c]["reviewer_id"]].append(p)
            by_type[cs_all[c].claim_category].append(p)
        res["primary_44"] = {
            "second_annotator": sid, "file": _rel(second), "sha256": _sha(second), "required": len(req), "covered": len(shared),
            "missing": sorted(set(req) - set(s)), "complete": len(shared) == len(req), "pooled": _kappa_block(pairs, n_boot),
            "by_first_labeller": {k: _kappa_block(v, n_boot) for k, v in sorted(by_first.items())},
            "by_claim_type": {k: _kappa_block(v, n_boot) for k, v in sorted(by_type.items())},
            "disagreements": [c for c, (a, b) in zip(shared, pairs) if a != b],
            "outside_required_ignored": sorted(set(s) - set(req)),
            "note": "Pooled κ mixes two first labellers (rev_person2 on 40, rev_som v3 on 4); the per-labeller rows are the "
                    "Cohen's κ proper. Report pooled and rev_person2 rows; the rev_som row has n=4 and no stable κ."}
    if numeric:
        nv = load_second(numeric, first, ann_dir)
        shared = [c for c in numerical_ids() if c in nv]
        pairs = [(first[c]["gold_label"], nv[c]["gold_label"]) for c in shared]
        res["numerical_verification"] = {"verifier": next(iter(nv.values()))["reviewer_id"], "file": _rel(numeric), "sha256": _sha(numeric),
                                         "covered": len(shared), "of": len(numerical_ids()), **_kappa_block(pairs, n_boot),
                                         "disagreements": [c for c, (a, b) in zip(shared, pairs) if a != b],
                                         "note": "Reported separately; never pooled with the primary 44."}
    return res


# ---------------------------------------------------------------- 7 adjudication packet

def adjudication_packet(second: str | None, numeric: str | None, out: str, ann_dir: str = ANN_DIR) -> list[str]:
    _no_overwrite(out)
    cs_all, first = claims(), first_labels()
    adj = load_adjudications(ADJ) if os.path.exists(ADJ) else {}
    r2 = agr.load(OLD_SECOND)
    pairs = {c: (first[c], r2[c]) for c in AI_AFFECTED}
    for path in (second, numeric):
        if path:
            for c, r in load_second(path, first, ann_dir).items():
                if c in first and r["gold_label"] != first[c]["gold_label"]:
                    pairs[c] = (first[c], r)
    todo = [c for c in sorted(pairs) if c not in adj and c != "DEV-AAPL-05"]
    if not todo:
        raise SystemExit("nothing to adjudicate")
    manifest = dwb.aw.load_manifest()
    wb = Workbook()
    ws = wb.active
    ws.title = "Adjudication"
    ws.append(da.HEAD)
    for cid in todo:
        c, x, y = cs_all[cid], *pairs[cid]
        fl = "\n".join(f"{f['form']} {f['accession_number']} filed {f['filed']}" for f in dwb.dev_eligible_filings(c, manifest))
        ws.append([cid, c.claim, c.reporting_period, c.as_of_date, fl,
                   x["reviewer_id"], x["gold_label"], x.get("review_notes"), f"{x.get('confidence')} / {x.get('uncertainty_type')}", da._evidence(x),
                   y["reviewer_id"], y["gold_label"], y.get("review_notes"), f"{y.get('confidence')} / {y.get('uncertainty_type')}", da._evidence(y),
                   None, None, None])
    _style_sheet(ws, [13, 45, 11, 11, 32, 12, 16, 50, 18, 60, 12, 16, 50, 18, 60, 16, 20, 50], input_from=16)
    _list_dv(ws, LABELS, f"Q2:Q{len(todo) + 1}")
    pv = wb.create_sheet("Provenance")
    pv.append(["Claim", "Why it is here"])
    for cid in todo:
        pv.append([cid, "first labeller's label history was affected by an outside review; Reviewer A shows the earlier "
                        "(pre-review) record" if cid in AI_AFFECTED else "independent labels disagree"])
    _style_sheet(pv, [14, 120])
    fs = wb.create_sheet("Filings")
    fs.append(["Accession", "Company", "Form", "Filed", "SEC link"])
    for f in manifest:
        if any(f["company"] == cs_all[i].company for i in todo):
            fs.append([f["accession_number"], f["company"], f["form"], f["filed"], dwb.aw.filing_url(f)])
            fs.cell(fs.max_row, 5).hyperlink = dwb.aw.filing_url(f)
    rd = wb.create_sheet("วิธีใช้", 0)
    for line in ["Adjudication ชุด dev-v0.2 (ไม่ใช่ Gold)",
                 "ผู้ตัดสินต้องเป็นคน ไม่ใช่ผู้ติด label คนใดในแถวนั้น ห้ามใช้ AI ห้ามเปิดผลของระบบ (A2/A3) workbook ตรวจหลักฐาน หรือรายงานที่ AI เตรียม",
                 "อ่าน claim และคำตอบของทั้งสองฝ่าย เปิด filing จากชีต Filings แล้วตัดสินตาม annotation_guidelines.md + dev_annotation_guidelines.md",
                 "กรอกช่องสีเหลือง: Adjudicator ID, Final label, เหตุผล (บังคับ) แล้วส่งคืน: scripts/dev_adjudication.py record <file>",
                 "claim ที่ระบุใน Provenance ว่าได้รับผลจาก AI review: แสดง label ก่อน AI review (rev_som v3) เท่านั้น"]:
        rd.append([line])
    rd.column_dimensions["A"].width = 140
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    wb.save(out)
    allowed = [t for cid in todo for r in pairs[cid] for t in (r.get("review_notes"), da._evidence(r))]
    audit = audit_workbook(out, todo, sheet="Adjudication", allowed=allowed)
    if not audit["blind"]:
        os.remove(out)
        raise SystemExit(f"packet audit failed; nothing kept: {audit['problems']}")
    return todo


# ---------------------------------------------------------------- 7-8 approval and validation

def _sources(second_paths, numeric_paths) -> dict[str, str]:
    return {p: _sha(p) for p in [PRE_REVIEW, OLD_SECOND, NEW_FIRST, *second_paths, *numeric_paths] + ([ADJ] if os.path.exists(ADJ) else [])}


def derive(second_paths=(), numeric_paths=(), adjudication_path: str = ADJ, ann_dir: str = ANN_DIR, ai_texts=None) -> tuple[dict, dict]:
    """Per claim: the approvable human label, or why there is none. Pure function of the human source files."""
    cs_all, first = claims(), first_labels()
    probs = []
    for p in (PRE_REVIEW, OLD_SECOND, NEW_FIRST):
        probs += check_source(p, ANN_DIR)
    seconds = defaultdict(list)
    for c, r in agr.load(OLD_SECOND).items():
        seconds[c].append(r)
    for p in [*second_paths, *numeric_paths]:
        try:
            for c, r in load_second(p, first, ann_dir, ai_texts).items():
                seconds[c].append(r)
        except SchemaError as e:
            probs.append(str(e))
    adj = load_adjudications(adjudication_path) if os.path.exists(adjudication_path) else {}
    for c, a in adj.items():
        if MODEL_ID.match(a.adjudicator_id) or a.adjudicator_id in EXCLUDED_REVIEWERS:
            probs.append(f"adjudication {c}: adjudicator {a.adjudicator_id!r} is not an accepted human id")
        if a.adjudicator_id in a.considered_reviewers or a.adjudicator_id == first.get(c, {}).get("reviewer_id"):
            probs.append(f"adjudication {c}: adjudicator {a.adjudicator_id} labelled this claim")
    if probs:
        raise SchemaError("approval refused:\n  " + "\n  ".join(probs))
    ok, missing = {}, {}
    for cid in cs_all:
        f = first[cid]
        if cid in adj:
            ok[cid] = {"final_label": adj[cid].final_label, "label_status": "ADJUDICATED", "adjudicator_id": adj[cid].adjudicator_id,
                       "label_sources": [{"reviewer_id": r, "role": "considered"} for r in adj[cid].considered_reviewers]}
            continue
        if cid in MUST_ADJUDICATE:
            missing[cid] = "ADJUDICATION_REQUIRED: " + MUST_ADJUDICATE[cid]
            continue
        sec = seconds.get(cid, [])
        if not sec:
            missing[cid] = "SINGLE: no independent second human label"
        elif any(s["gold_label"] != f["gold_label"] for s in sec):
            missing[cid] = "DISAGREED: " + ", ".join(f"{s['reviewer_id']} {s['gold_label']}" for s in sec) + f" vs {f['reviewer_id']} {f['gold_label']}"
        else:
            ok[cid] = {"final_label": f["gold_label"], "label_status": "AGREED", "adjudicator_id": None,
                       "label_sources": [{"reviewer_id": f["reviewer_id"], "role": "first", "label": f["gold_label"]}] +
                                        [{"reviewer_id": s["reviewer_id"], "role": s.get("annotation_kind") or "second", "label": s["gold_label"]} for s in sec]}
    return ok, missing


def approve(second_paths, numeric_paths, approved_by: str, out: str, allow_partial: bool = False,
            adjudication_path: str = ADJ, ann_dir: str = ANN_DIR) -> dict:
    if not approved_by or " " in approved_by or MODEL_ID.match(approved_by) or approved_by in EXCLUDED_REVIEWERS:
        raise SchemaError(f"--approved-by {approved_by!r}: a person's id is required (no model ids)")
    if os.path.basename(out).startswith("rev_") or not out.endswith(".approved.jsonl"):
        raise SchemaError("the approved file name must end with .approved.jsonl and must not start with rev_")
    man_path = out[:-len(".jsonl")] + ".manifest.json"
    _no_overwrite(out, man_path)
    ok, missing = derive(second_paths, numeric_paths, adjudication_path, ann_dir)
    if missing and not allow_partial:
        raise SchemaError(f"{len(missing)} claims cannot be approved yet:\n  " + "\n  ".join(f"{c}: {w}" for c, w in sorted(missing.items())))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ds_sha = _sha(DATASET)
    rows = [{"claim_id": c, **v, "approved_by": approved_by, "approved_at": now, "source": TOOL_VERSION,
             "dataset": _rel(DATASET), "dataset_sha256": ds_sha} for c, v in sorted(ok.items())]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    srcs = _sources(second_paths, numeric_paths)
    if adjudication_path != ADJ and os.path.exists(adjudication_path):
        srcs[adjudication_path] = _sha(adjudication_path)
    manifest = {"tool": TOOL_VERSION, "approved_by": approved_by, "approved_at": now, "approved_file": _rel(out), "approved_sha256": _sha(out),
                "dataset": _rel(DATASET), "dataset_sha256": ds_sha, "claims_approved": len(rows), "claims_total": len(claims()),
                "partial": bool(missing), "missing": missing, "label_status": dict(Counter(r["label_status"] for r in rows)),
                "sources": {_rel(p): h for p, h in srcs.items()}, "second_paths": [_rel(p) for p in second_paths],
                "numeric_paths": [_rel(p) for p in numeric_paths], "adjudication_path": _rel(adjudication_path)}
    with open(man_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    for p in (out, man_path):
        os.chmod(p, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    return manifest


def validate(path: str, ann_dir: str = ANN_DIR) -> list[str]:
    """Re-derive every approved row from the recorded human sources; any difference is a problem."""
    man_path = path[:-len(".jsonl")] + ".manifest.json"
    if not os.path.exists(man_path):
        return [f"{man_path} missing: the file was not produced by `approve`"]
    man = json.load(open(man_path, encoding="utf-8"))
    probs = []
    if _sha(path) != man["approved_sha256"]:
        probs.append("approved file changed after approval")
    for rel, h in man["sources"].items():
        p = os.path.join(RESEARCH_ROOT, rel)
        if not os.path.exists(p) or _sha(p) != h:
            probs.append(f"source {rel} missing or changed since approval")
    if _sha(DATASET) != man["dataset_sha256"]:
        probs.append("dataset changed since approval")
    if probs:
        return probs
    full = lambda rel: os.path.join(RESEARCH_ROOT, rel)  # noqa: E731
    try:
        ok, _ = derive([full(p) for p in man["second_paths"]], [full(p) for p in man["numeric_paths"]], full(man["adjudication_path"]), ann_dir)
    except SchemaError as e:
        return [str(e)]
    rows = [json.loads(x) for x in open(path, encoding="utf-8") if x.strip()]
    for r in rows:
        d = ok.get(r["claim_id"])
        if not d:
            probs.append(f"{r['claim_id']}: no human basis for an approved label")
        elif (d["final_label"], d["label_status"]) != (r["final_label"], r["label_status"]):
            probs.append(f"{r['claim_id']}: file says {r['final_label']}/{r['label_status']}, sources give {d['final_label']}/{d['label_status']}")
        if r.get("approved_by") != man["approved_by"]:
            probs.append(f"{r['claim_id']}: approved_by differs from the manifest")
    if len(rows) != man["claims_approved"]:
        probs.append("row count differs from the manifest")
    return probs


# ---------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("blind-package")
    b.add_argument("--out", default=os.path.join(WB_DIR, "dev-v0.2_second_annotation_44_blank.xlsx"))
    b.add_argument("--audit", default=os.path.join(OUT, "blind_package_audit.json"))
    a5 = sub.add_parser("aapl05-packet")
    a5.add_argument("--out", default=os.path.join(WB_DIR, "dev-v0.2_AAPL-05_adjudication_packet.xlsx"))
    a5.add_argument("--audit", default=os.path.join(OUT, "aapl05_packet_audit.json"))
    nc = sub.add_parser("numeric-checklist")
    nc.add_argument("--out", default=os.path.join(WB_DIR, "dev-v0.2_numerical_verification_20.xlsx"))
    ni = sub.add_parser("numeric-import")
    ni.add_argument("workbook")
    sub.add_parser("provenance")
    for name in ("agreement", "adjudication-packet", "approve"):
        p = sub.add_parser(name)
        p.add_argument("--second", nargs="*", default=[], help="independent second-annotation file(s) in datasets/annotations_dev/")
        p.add_argument("--numeric", nargs="*", default=[], help="numcheck_<id>.jsonl file(s)")
        if name == "adjudication-packet":
            p.add_argument("--out", required=True)
        if name == "approve":
            p.add_argument("--approved-by", required=True)
            p.add_argument("--out", default=lst.APPROVED)
            p.add_argument("--allow-partial", action="store_true")
            p.add_argument("--adjudications", default=ADJ, help="adjudication log (default: the dev-v0.2 log; a later label version may use its own copy)")
    v = sub.add_parser("validate")
    v.add_argument("approved")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "blind-package":
            r = blind_package(args.out, args.audit)
            print(f"wrote {_rel(args.out)}: {r['claims']} claims {r['by_type']}; blind {r['blind']}; audit {_rel(args.audit)}")
        elif args.cmd == "aapl05-packet":
            r = aapl05_packet(args.out, args.audit)
            print(f"wrote {_rel(args.out)}; blind {r['blind']}; audit {_rel(args.audit)}")
        elif args.cmd == "numeric-checklist":
            print(f"wrote {_rel(args.out)}: {len(numeric_checklist(args.out))} numerical claims")
        elif args.cmd == "numeric-import":
            print(f"wrote {numeric_import(args.workbook)}")
        elif args.cmd == "provenance":
            rows = provenance_rows()
            os.makedirs(OUT, exist_ok=True)
            with open(os.path.join(OUT, "annotation_provenance.jsonl"), "w", encoding="utf-8") as f:
                f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
            open(os.path.join(OUT, "annotation_provenance.md"), "w", encoding="utf-8").write(render_provenance(rows))
            print(f"wrote {_rel(OUT)}/annotation_provenance.{{jsonl,md}}: {len(rows)} claims, "
                  f"{sum(1 for r in rows if r['ai_exposure_flags'])} affected by prior AI review")
        elif args.cmd == "agreement":
            res = agreement(args.second[0] if args.second else None, args.numeric[0] if args.numeric else None)
            name = res.get("primary_44", {}).get("second_annotator", "historical_only")
            out = os.path.join(OUT, f"agreement_{name}.json")
            _no_overwrite(out)
            json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(json.dumps({k: v for k, v in res.items() if k not in ("excluded_from_all_kappa",)}, ensure_ascii=False, indent=1)[:3000])
        elif args.cmd == "adjudication-packet":
            print(f"wrote {args.out}: {adjudication_packet(args.second[0] if args.second else None, args.numeric[0] if args.numeric else None, args.out)}")
        elif args.cmd == "approve":
            m = approve(args.second, args.numeric, args.approved_by, args.out, args.allow_partial, adjudication_path=args.adjudications)
            print(f"wrote {m['approved_file']} ({m['claims_approved']}/{m['claims_total']}, {m['label_status']}); read-only; manifest beside it")
        else:
            probs = validate(args.approved)
            print("valid: every approved label traces to human sources" if not probs else "INVALID:\n  " + "\n  ".join(probs))
            if probs:
                sys.exit(1)
    except SchemaError as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
