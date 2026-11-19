# การวิเคราะห์เพิ่มเติมเชิงพรรณนา (POST-HOC EXPLORATORY)

> **STATUS: POST-HOC EXPLORATORY — ไม่ใช่ผลยืนยันตาม preregistration**
> - ทำหลังประเมินผลตาม preregistration แล้ว (2026-11-19) ไม่ได้อยู่ในแผนที่ล็อกไว้
> - ไม่เรียก API ที่เสียเงิน, ไม่แก้ Gold label / predictions / evaluation / code bundle A3 (`c4d2112f…`), `evaluation.json` ยังเป็น `e6422ff9…`
> - Gold 150 ถูกเปิดดูรายข้อแล้ว (exposed) ผลในเอกสารนี้จึงใช้อธิบายประกอบบทที่ 4–5 เท่านั้น ห้ามอ้างเป็นผลยืนยัน
> - ใช้ประกอบ: ตารางในบทที่ 4 (หัวข้อใหม่ "การวิเคราะห์เพิ่มเติมเชิงพรรณนา") และการอภิปรายในบทที่ 5

---

## 1. Citation Validity และ Unsupported Conclusions (Task 1)

### 1.1 สิ่งที่ตัวชี้วัดวัดจริง
- `unsupported_conclusion` ถูกบันทึกตอนรันใน `experiments/pipeline.py:318` (`build_prediction`):
  **คำตอบเป็น SUPPORTED หรือ CONTRADICTED แต่ไม่มี citation ที่รองรับคำตอบนั้นผ่านการตรวจเลย**
- การตรวจ citation (`ClaimRun.validate`, `pipeline.py:145-174`) ไม่ใช้ LLM และตรวจเฉพาะ**รูปแบบ**:
  1. evidence id ถูกออกในการรันนั้นจริง
  2. บริษัทตรงกับ claim
  3. ยื่นก่อนหรือใน `as_of_date`
  4. quote ของ passage อยู่ในข้อความ passage ตรงตัว (ยาวอย่างน้อย 12 ตัวอักษร)
- `engine/metrics.py:unsupported_rate` = จำนวน unsupported / จำนวนคำตอบเด็ดขาด
- **ไม่ได้ตรวจว่าหลักฐานมีความหมายรองรับคำตอบจริง** (semantic support) ซึ่งเป็นเรื่องของหัวข้อ 3

### 1.2 ผล (Gold 150, n = 150 ต่อ arm)

| Arm | คำตอบเด็ดขาด | Unsupported (rate) | Unsupported ที่ผิดเฉลย | Citation ทั้งหมด | Citation ไม่ผ่าน (claims) | เหตุผลที่ไม่ผ่าน |
|---|---:|---:|---:|---:|---:|---|
| A1 RAG | 103 | 5 (4.9%) | 2 | 190 | 16 (14) | QUOTE_NOT_IN_PASSAGE 14, MALFORMED_ITEM 2 |
| A2 RAG + numeric | 113 | 3 (2.7%) | 1 | 236 | 16 (14) | QUOTE_NOT_IN_PASSAGE 14, MALFORMED_ITEM 2 |
| SR self-reflection | 101 | 1 (1.0%) | 0 | 241 | 18 (11) | QUOTE_NOT_IN_PASSAGE 17, UNKNOWN_EVIDENCE_ID 1 |
| A3 v2.1.1 R | 128 | 1 (0.8%) | 0 | 350 | 22 (19) | QUOTE_NOT_IN_PASSAGE 22 |
| A3 v2.1.1 RG | 116 | 3 (2.6%) | 1 | 280 | 6 (5)* | QUOTE_NOT_IN_PASSAGE 6 |
| A3v2_2e | 98 | 1 (1.0%) | 1 | 280 | 7 (6)* | QUOTE_NOT_IN_PASSAGE 7 |
| A3 v1 | 129 | 2 (1.6%) | 0 | 351 | 31 (26) | QUOTE_NOT_IN_PASSAGE 28, MALFORMED_ITEM 2, UNKNOWN_EVIDENCE_ID 1 |

\* RG และ A3v2_2e ตัด citation ที่ guard ไม่รับออก **ก่อน** การตรวจนี้ (`a3v2/graph.py`, `excluded_citations` รวม 49 รายการต่อ arm) จำนวน citation ที่ไม่ผ่านของสอง arm นี้จึงเทียบกับ arm อื่นตรงๆ ไม่ได้

### 1.3 การตีความ
- ทุก arm มี unsupported conclusion ต่ำ (≤ 5%) **ความผิดของระบบส่วนใหญ่จึงไม่ใช่การตอบโดยไม่อ้างหลักฐาน** แต่เป็นการอ้างหลักฐานที่มีอยู่จริงแล้วตีความผิด หรือไม่กล้าตอบ (สอดคล้องกับเอกสาร 13)
- A3 ทุกรุ่นและ SR มีอัตราต่ำกว่า A1/A2 เล็กน้อย แต่จำนวนเหตุการณ์น้อยมาก (1–5 ข้อ) ไม่ควรสรุปว่าต่างกัน
- **การทำซ้ำ:** สคริปต์เรียก `unsupported_rate` เดิมโดยไม่แก้ และนับซ้ำเองได้ตรงกัน (มี assert ในสคริปต์)

---

## 2. Rule-Based และ Majority-Class Baseline (Task 2)

### 2.1 วิธี
- **Rule set RB-1.0** (`scripts/posthoc_rule_baseline.py`) ไม่เรียก LLM: regex แปลง claim เป็น assertion ตัวเลขได้สูงสุด 1 ข้อ แล้วตรวจด้วย numeric engine เดิม (`engine/numeric.py:verify_assertion`) บน XBRL ที่ยื่นภายใน `as_of_date`
- กฎ R1–R5 (รายละเอียดในหัวสคริปต์):
  - **R1** metric ต้องเป็นระดับบริษัท (ตามหลัง possessive ของบริษัท หรือคำว่า total / consolidated) ส่วน segment / product ไม่ทำ
  - **R2** แยก yoy growth, level threshold และทิศทางขึ้น/ลง
  - **R3** งวดจากวันที่ใน claim → FY label → ไตรมาสล่าสุด ณ วันตัด; ข้อความแบบ YTD / ครึ่งปี / ผลรวม ไม่ทำ
  - **R4** free cash flow = OCF − CapEx (เฉพาะเทียบกับเกณฑ์)
  - **R5** ไม่มี assertion → INSUFFICIENT; ตัวเลขเท็จ → CONTRADICTED; ตัวเลขจริงและไม่มีคำเชิงสาเหตุ/ประเมิน → SUPPORTED; อื่นๆ → INSUFFICIENT
- **Majority-class:** ตอบ SUPPORTED ทุกข้อ
- **Input:** ข้อความ claim, บริษัท, reporting_period, as_of_date เท่านั้น คำสั่ง `run` ไม่อ่านเฉลย

### 2.2 กระบวนการล็อกกฎ
1. พัฒนาและ debug บน **dev-v0.2 เท่านั้น** (ได้ 42/72) แก้กฎ 1 ครั้งบน dev: เพิ่มคำบอกวัตถุประสงค์ ("used to", "to fund") เข้ารายการคำเชิงคุณภาพ หลังพบ DEV-AMZN-05
2. ล็อก: `results/posthoc_20261119/rule_baseline/LOCK.json` (rule version RB-1.0, script sha256 `13ed066b…`, 2026-11-19T02:45:31Z)
3. รัน Gold ครั้งเดียว: สคริปต์ปฏิเสธการรันถ้า hash ไม่ตรง LOCK หรือมีผล Gold อยู่แล้ว
4. ไม่ได้ปรับกฎหลังเห็นผล Gold
- **ข้อจำกัดของการล็อก:** ผู้เขียนกฎเคยเห็นข้อความ claim บางข้อของ Gold มาก่อนในโครงการ (Gold เป็น exposed set)

### 2.3 ผลบน Gold 150

| Arm | ถูก | Accuracy | Macro-F1 | ตัวเลข | ตีความ | กำกวม | ตอบเด็ดขาด (ถูก) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Majority (SUPPORTED ทุกข้อ) | 68 | 45.3% | 0.208 | 37/50 | 22/50 | 9/50 | 150 (68) |
| **RB-1.0 rule-based** | **77** | **51.3%** | **0.463** | 37/50 | 17/50 | 23/50 | **33 (33)** |
| A1 RAG (อ้างอิง, frozen) | 94 | 62.7% | 0.605 | 38/50 | 31/50 | 25/50 | 103 (73) |
| A2 RAG + numeric (อ้างอิง, frozen) | 103 | 68.7% | 0.657 | 47/50 | 30/50 | 26/50 | 113 (82) |

**Confusion matrix ของ RB-1.0 (เฉลย → คำตอบ):** S→S 27, S→I 41, C→C 6, C→I 32, I→I 44 (ไม่มีการตอบผิดขั้ว)

**กฎที่ทำงาน:** ไม่มี assertion 111 ข้อ, ตัวเลขจริง 27, ตัวเลขเท็จ 6, ตรวจไม่ได้ 6

**เทียบ A2 (เชิงพรรณนา):** A2 ถูก RB ผิด 51 ข้อ, RB ถูก A2 ผิด 25 ข้อ (McNemar exact p = 0.004; ไม่อยู่ใน Holm family ของ prereg)

### 2.4 การตีความ
- **กฎล้วนแม่นมากเมื่อกล้าตอบ (33/33) แต่ตอบได้เพียง 22% ของ claim** ที่เหลือเป็น INSUFFICIENT
- ใน 33 ข้อที่ RB ตอบเด็ดขาด A2 ก็ถูก 31 ข้อ: ส่วนที่ตรวจด้วยกฎได้ A2 ทำได้ดีอยู่แล้ว
- ส่วนที่ LLM ช่วยจริงคือ claim ที่กฎแปลงไม่ได้ (segment, เหตุผล, คำประเมิน) ซึ่งเป็นส่วนใหญ่ของชุดข้อมูล
- หมวดตัวเลข RB ได้ 37/50 ต่ำกว่า A2 (47/50) เพราะ claim ตัวเลขหลายข้ออยู่ระดับ segment หรือใช้ถ้อยคำที่ regex ไม่ครอบคลุม
- RB ได้ INSUFFICIENT recall 44/44 เพราะตอบ INSUFFICIENT ถึง 117 ข้อ (ไม่ใช่ความสามารถในการแยกแยะ)

---

## 3. Evidence-Grounded Correctness

### 3.1 ส่วน A: Automated Proxy Metrics (คำตอบเด็ดขาดเท่านั้น)

ทุก proxy เป็น**เงื่อนไขจำเป็นแต่ไม่เพียงพอ**ของหลักฐานที่ถูกต้อง ผ่านทุกข้อก็ยังไม่ได้แปลว่าหลักฐานรองรับความหมายของคำตอบ

| Proxy | นิยาม |
|---|---|
| valid backing | มี citation ที่ผ่านการตรวจรูปแบบรองรับคำตอบ (= ไม่ใช่ unsupported) |
| temporal ok | ทุก citation ยื่นก่อนหรือใน as_of_date |
| in run corpus | ทุก accession อยู่ในคลังเอกสารของ run และเป็นของบริษัทเดียวกับ claim |
| span in source | quote ของ passage พบในเอกสาร SEC ฉบับเต็ม (tolerant quote check 1.1) |
| same filing as reference | อ้าง filing เดียวกับที่เฉลยใช้อย่างน้อย 1 ฉบับ |
| reference number overlap | มีตัวเลขในหลักฐานของเฉลยปรากฏใน quote ที่อ้าง |

**ผลบนคำตอบเด็ดขาดที่ถูกเฉลย (k / n)**

| Arm | คำตอบเด็ดขาดที่ถูก | valid backing | temporal ok | in corpus | span in source | same filing | number overlap |
|---|---:|---:|---:|---:|---:|---:|---:|
| A1 | 73 | 70/73 | 71/71 | 71/71 | 70/71 | 69/73 | 56/73 (77%) |
| A2 | 82 | 80/82 | 81/81 | 81/81 | 73/74 | 79/82 | 59/82 (72%) |
| SR | 75 | 74/75 | 75/75 | 75/75 | 70/70 | 74/75 | 58/75 (77%) |
| A3 v2.1.1 R | 86 | 85/86 | 86/86 | 86/86 | 78/79 | 86/86 | 73/86 (85%) |
| A3 v2.1.1 RG | 80 | 78/80 | 79/79 | 79/79 | 70/70 | 79/80 | 68/80 (85%) |
| A3v2_2e | 72 | 72/72 | 72/72 | 72/72 | 63/63 | 72/72 | 64/72 (89%) |
| A3 v1 | 84 | 82/84 | 83/83 | 83/83 | 77/78 | 83/84 | 70/84 (83%) |

(ตัวหารต่างกันเพราะบางคำตอบไม่มี citation ประเภทที่ proxy นั้นตรวจได้; ผลบนคำตอบเด็ดขาดทั้งหมดอยู่ใน `citation_evidence.json`)

**การตีความ**
- temporal ok, in corpus และ span in source ใกล้ 100% ทุก arm: ระบบไม่ได้อ้างเอกสารอนาคต ไม่ได้อ้างนอกคลัง และ quote ส่วนใหญ่มีอยู่จริงในเอกสาร
- **same filing as reference ใกล้เพดาน (≥ 95%) ทุก arm จึงแยกคุณภาพหลักฐานไม่ได้** เพราะแต่ละ claim มีเอกสารที่ใช้ได้เพียง 3 ฉบับ การอ้าง filing เดียวกับเฉลย**ไม่ได้แปลว่าหลักฐานถูก**
- number overlap ของ A3 สูงกว่า A1/A2 (85–89% เทียบ 72–77%) สอดคล้องกับที่ A3 ค้นหลักฐานเพิ่ม แต่เป็นตัวชี้วัดแบบหยาบ และ**ไม่ได้ทำให้ accuracy ดีขึ้น**
- proxy เหล่านี้ไม่ตอบคำถามว่า "หลักฐานรองรับความหมายของคำตอบหรือไม่" ซึ่งต้องใช้ส่วน B

### 3.2 ส่วน B: Human Blind Review Workbook (รอผู้ตรวจ)

| รายการ | รายละเอียด |
|---|---|
| ไฟล์ผู้ตรวจ | `results/posthoc_20261119/human_review/evidence_review_blind.xlsx` (sheet "คู่มือผู้ตรวจ" + "review") |
| ไฟล์ mapping (แยก ห้ามเปิดก่อนตรวจเสร็จ) | `mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx` (review_id → claim, arm, เฉลย, ถูก/ผิด) **ไม่ได้ commit และห้ามส่งพร้อมไฟล์ผู้ตรวจ** เก็บในเครื่องและ backup แยก สร้างซ้ำได้จาก seed; sha256 อยู่ใน `sample_manifest.json` |
| การสุ่ม | stratified random, seed 20261119: ตัวเลข 16, ตีความ 17, กำกวม 17 claims จาก claim id ที่เรียงแล้วของแต่ละหมวด ไม่อ่านเฉลยตอนสุ่ม |
| จำนวนแถว | 50 claims × 2 arm (A2, A3v2_2e) = 100 แถว เรียงแบบสุ่มด้วย seed เดียวกัน |
| สิ่งที่ผู้ตรวจเห็น | claim, บริษัท, as_of_date, คำตอบระบบ, เหตุผลของระบบ, citation (form, accession, วันยื่น, งวด, quote), ลิงก์ที่อ้าง, ลิงก์เอกสาร 10-K/10-Q ที่ระบบใช้ได้ |
| สิ่งที่ซ่อน | ชื่อ arm และเฉลย (ตรวจแล้วไม่มีข้อความรั่วในไฟล์ผู้ตรวจ) |
| ช่องกรอก (สีเหลือง) | judgment (dropdown: SUPPORTED_BY_EVIDENCE / PARTIALLY_SUPPORTED / NOT_SUPPORTED / UNABLE_TO_ASSESS), reviewer_reason, reviewer_citation |
| ภาระงาน | ราว 2–3 นาทีต่อแถว (≈ 3–5 ชั่วโมง) |
| สถานะ | **ยังไม่มีการตรวจ** ไม่มี judgment ใดถูกกรอกแทนผู้ตรวจ; `score` ปฏิเสธการคำนวณจนกว่าจะกรอกครบ |
| Manifest | `sample_manifest.json` (seed, claim ที่สุ่ม, ลำดับแถว, sha256 ของ input/output) |

**การคำนวณหลังตรวจเสร็จ** (`posthoc_review_workbook.py score`), แยกตาม arm:
- ตัดแถว UNABLE_TO_ASSESS ออกจากตัวหาร และรายงานจำนวนแยกต่างหาก
- **EGC strict** = คำตอบถูกเฉลย **และ** SUPPORTED_BY_EVIDENCE / แถวที่ตรวจได้
- **EGC lenient** = คำตอบถูกเฉลย **และ** (SUPPORTED หรือ PARTIALLY) / แถวที่ตรวจได้
- **ข้อจำกัด:** 25 แถวไม่มี citation (ส่วนใหญ่เป็นคำตอบ INSUFFICIENT) ผู้ตรวจต้องตัดสินจากเหตุผลและเอกสารที่ระบบใช้ได้; ผู้ตรวจคนเดียว (ไม่มี inter-rater agreement); 50 claims ให้ CI กว้าง

---

## 4. ข้อจำกัดรวม
1. ทุกผลเป็น post-hoc บน Gold ที่ exposed แล้ว ใช้อธิบาย ไม่ใช่ยืนยัน
2. Citation validity ตรวจรูปแบบ ไม่ตรวจความหมาย; RG / A3v2_2e ตัด citation บางส่วนก่อนตรวจ
3. Rule baseline ครอบคลุมเฉพาะ claim ตัวเลขระดับบริษัทที่ถ้อยคำตรงกับ template; ผู้เขียนกฎเคยเห็น claim บางข้อของ Gold
4. Proxy ของหลักฐานเป็นเงื่อนไขจำเป็นแต่ไม่เพียงพอ; same filing ใกล้เพดานจนไม่มีความหมาย
5. EGC จากคนยังไม่มีผล จนกว่าผู้ตรวจจะกรอก workbook

## 5. ประโยคที่ใช้ในเล่มได้ (ร่าง)
- "การวิเคราะห์เพิ่มเติมเชิงพรรณนาหลังประเมินผล (post-hoc) พบว่าทุกระบบมีอัตราการตอบเด็ดขาดโดยไม่มีการอ้างอิงที่ผ่านการตรวจต่ำ (1.0–4.9%) ความผิดพลาดส่วนใหญ่จึงมาจากการตีความหลักฐาน ไม่ใช่การขาดหลักฐาน"
- "baseline แบบกฎล้วน (ไม่ใช้ LLM) ได้ accuracy 51.3% โดยถูกทุกข้อที่ตอบเด็ดขาด (33/33) แต่ตอบเด็ดขาดได้เพียง 22% ของ claim แสดงว่าการคำนวณแบบ deterministic แม่นยำแต่ครอบคลุมน้อย และ LLM มีบทบาทหลักใน claim ที่เป็นการตีความหรือระดับ segment"

## 6. การทำซ้ำ

```
research/.venv/bin/python research/scripts/posthoc_citation_evidence.py
research/.venv/bin/python research/scripts/posthoc_rule_baseline.py score --split gold      # predictions ล็อกแล้ว ห้าม run gold ซ้ำ
research/.venv/bin/python research/scripts/posthoc_review_workbook.py score                # หลังผู้ตรวจกรอกครบ
```

| ไฟล์ | sha256 (16 ตัวแรก) |
|---|---|
| `scripts/posthoc_citation_evidence.py` | `1fc76c68ed94534c` |
| `scripts/posthoc_rule_baseline.py` (= LOCK) | `13ed066b1ccbf1c1` |
| `scripts/posthoc_review_workbook.py` | `3425dea543629c6d` |
| `citation_evidence/citation_evidence.json` | `d654b8b07579811c` |
| `rule_baseline/predictions_gold.jsonl` | `cd9d40dada4acfcc` |
| `rule_baseline/score_gold.json` | `5a65d5a4975fdaed` |
| `human_review/evidence_review_blind.xlsx` (ตามที่สร้าง ก่อนกรอก) | `5637d333c424a425` |
| `human_review/mapping_DO_NOT_OPEN_BEFORE_REVIEW.xlsx` | `06ce018f98c1f311` |

Input hash ของแต่ละสคริปต์บันทึกไว้ใน `citation_evidence.json`, `rule_baseline/run_gold.json` และ `human_review/sample_manifest.json`
