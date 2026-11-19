# POST-HOC EXPLORATORY — ทุกไฟล์ในโฟลเดอร์นี้

ผลการวิเคราะห์เพิ่มเติมเชิงพรรณนาหลังประเมินผล Gold 150 ตาม preregistration แล้ว (2026-11-19) **ไม่ใช่ผลยืนยัน (confirmatory)** และไม่แทนที่ `results/gold150/a3v2.2-gold150-20261118T112814Z/evaluation.json`
ไฟล์บางรายการ (`proxy_rows_*.json`, `run_*.json`, `predictions_*.jsonl`) ไม่มีป้ายในตัวไฟล์เพราะเป็นผลดิบที่บันทึก hash ไว้แล้ว ป้ายนี้ครอบคลุมไฟล์เหล่านั้น

รายงาน: `docs/is_report/03_posthoc_descriptive_analysis.md`

| โฟลเดอร์ | เนื้อหา | สคริปต์ |
|---|---|---|
| `citation_evidence/` | Task 1 citation validity / unsupported rate, Task 3A proxy ของหลักฐาน | `scripts/posthoc_citation_evidence.py` |
| `rule_baseline/` | Task 2 rule-based (RB-1.0) และ majority-class baseline | `scripts/posthoc_rule_baseline.py` |
| `human_review/` | Task 3B workbook ผู้ตรวจแบบ blind + manifest การสุ่ม | `scripts/posthoc_review_workbook.py` |

## ลำดับการล็อกกฎของ rule baseline
- `rule_baseline/LOCK.json` เขียนเมื่อ 2026-11-19T02:45:31.434Z (mtime) ก่อน `predictions_gold.jsonl` (02:45:31.856Z) และ `run_gold.json`
- ค่า `locked_at` / `ran_at` ในไฟล์บันทึกถึงระดับวินาทีจึงเท่ากัน ลำดับยืนยันจาก mtime และจากสคริปต์ที่ปฏิเสธการรัน Gold ถ้าไม่มี LOCK, hash ไม่ตรง หรือมีผล Gold อยู่แล้ว
- sha256 ของสคริปต์ตอนรัน (`run_gold.json`) ตรงกับใน LOCK (`13ed066b…`)

## Human review
- `human_review/evidence_review_blind.xlsx` คือไฟล์ตามที่สร้าง (judgment ว่าง) ไม่มีชื่อ arm และเฉลย
- ไฟล์ที่กรอกครบแล้ว: `datasets/workbooks/evidence_review_blind.xlsx` (ผู้วิจัยตรวจเอง, researcher self-reported)
- **ไฟล์ mapping (`mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx`) ไม่ได้ commit และห้ามส่งพร้อมไฟล์ผู้ตรวจ** สร้างซ้ำได้จาก seed 20261119 ด้วย `posthoc_review_workbook.py build`; sha256 อยู่ใน `sample_manifest.json`
- ผล EGC: `human_review/egc_result.json` — **POST-HOC EXPLORATORY / HUMAN-ASSESSED (researcher self-reported)** ตัวหารเฉพาะแถวที่ประเมินได้; 25 แถว UNABLE_TO_ASSESS (คำตอบ INSUFFICIENT ที่ไม่มี citation) รายงานแยก
