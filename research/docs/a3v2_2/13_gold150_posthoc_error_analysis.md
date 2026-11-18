# Post-hoc Error Analysis: A3v2_2e บน Gold 150

> **สถานะ:** Post-hoc Exploratory Analysis — ไม่ใช่ส่วนหนึ่งของ preregistration (`08_preregistration_gold150.md`, LOCKED)
>
> - ผลหลักของการทดลองคือ `evaluation.json` ที่ freeze แล้ว เอกสารนี้**ไม่แก้และไม่แทนที่**ผลนั้น
> - ไม่มีการแก้ Gold label, evaluation, logic / prompt / guard / config ของ A3 และไม่มีการรัน experiment ใหม่
> - ไม่มีการเรียก Claude API หรือบริการที่เสียเงิน: ทุกตัวเลขคำนวณจาก predictions, traces และเอกสาร SEC ที่ cache ไว้ในเครื่อง
> - ไม่มีการทดสอบทางสถิติใหม่: ค่า p และ CI ที่อ้างทั้งหมดมาจาก `evaluation.json` ส่วนตัวเลขอื่นเป็นการนับเชิงพรรณนา
> - **สัญลักษณ์:** **[T]** = ยืนยันจาก trace / predictions โดยตรง, **[S]** = ยืนยันจากเอกสาร SEC ที่ cache ไว้, **[H]** = สมมติฐานที่ยังไม่ได้พิสูจน์
> - **ผู้วิเคราะห์:** AI (Claude) คนเดียว ยังไม่มีผู้ตรวจที่สองที่เป็นมนุษย์
>
> **การตรวจทานก่อน commit (2026-11-18, ปิดงาน IS)**
> - คำนวณซ้ำอย่างอิสระจาก `predictions.jsonl`, traces และ `engine.reference.load_reference()` แล้ว**ตรงทุกค่า**:
>   - correct ทั้ง 7 arm (ตรงกับ `evaluation.json`)
>   - รายชื่อ regression 15 ข้อและ correction 10 ข้อ
>   - accepted change precision 4/10
>   - ตารางกลไก (reviewer + guard 3/6, D-sup 0/3, E1 6/5, N1 1/1)
>   - ตารางแยกประเภทในหัวข้อ 9.1 และจำนวนครั้งที่ทำนาย INSUFFICIENT
>   - ทิศทาง regression ของ A3 v1 และ A3v2_2e (หัวข้อ 7.4)
>   - finding ที่ถูก downgrade 109/439 และเหตุผลแยกตามประเภท
>   - การเปลี่ยน label ของ D-sup (ช่วย 1 / ทำผิด 4 / เป็นกลาง 1) และ E1 (6 / 5)
> - ตัวเลข guard ในหัวข้อ 7.1 ตรงเมื่อนับ "ผลของ `decide()` ก่อน decidability gate" (เพิ่มหมายเหตุวิธีนับไว้ในหัวข้อนั้น)
> - **ไม่ได้ตรวจซ้ำ:** คำบรรยายรายข้อในหัวข้อ 4.2 / 5.2 และการ audit Gold กับเอกสาร SEC ในหัวข้อ 8
> - สิ่งที่แก้ในรอบตรวจทานนี้มีเฉพาะหมายเหตุ ผลหลัก ตัวเลข และข้อสรุปไม่เปลี่ยน

---

## 1. Executive Summary

**ผลหลัก (freeze แล้ว ไม่เปลี่ยน):** A3v2_2e ได้ 98/150 (65.3%) ต่ำกว่า A2 103/150 (68.7%) อยู่ −3.3 pp (McNemar exact p = 0.424, Holm p = 1.0, bootstrap 95% CI −10.0 ถึง +3.3 pp) และต่ำกว่า SR (P2) 102/150 อยู่ −2.7 pp (p = 0.585) ผลนี้เป็น **negative result** และรายงานตามนั้น

**ข้อค้นพบหลักจาก trace:**

1. **A3 เริ่มจากคำตอบของ A2 ทุกข้อ [T]:** label หลังขั้น numeric verification ของ A3v2_2e ตรงกับ prediction ของ A2 150/150 ข้อ ความต่างทั้ง 25 ข้อจึงเกิดจากส่วนที่ A3 เพิ่มเข้ามาเท่านั้น
2. **ความต่าง 25 ข้อแยกตามกลไกที่เปลี่ยน label [T]:**

   | กลไก | Correction | Regression | สุทธิ |
   |---|---:|---:|---:|
   | Reviewer เสนอ + Guard ACCEPT | 3 | 6 | **−3** |
   | Decidability gate (D-sup downgrade) | 0 | 3 | **−3** |
   | E1 evidence coverage gate | 6 | 5 | +1 |
   | N1 numeric validity check | 1 | 1 | 0 |
   | **รวม** | **10** | **15** | **−5** |

3. **ทิศทางของความผิดพลาดกลับด้านจาก A3 v1 [T]:**
   - A3 v1: regression 10/15 ข้อเป็นการเปลี่ยน INSUFFICIENT → คำตอบเด็ดขาด (over-interpretation)
   - A3v2_2e: regression 11/15 ข้อเป็นการเปลี่ยนคำตอบเด็ดขาด → INSUFFICIENT (over-abstention)
   - A3v2_2e ทำนาย INSUFFICIENT 52 ครั้ง (Gold มี 44) ถูกเพียง 26 ครั้ง (precision 50%)
4. **Guard แยกข้อเสนอดีกับข้อเสนอเสียไม่ออก [T]:**
   - จากข้อเสนอของ reviewer 33 ข้อ มี 10 ข้อที่จะแก้ A2 ผิด → ถูก และ 13 ข้อที่จะทำ A2 ถูก → ผิด
   - Guard รับข้อเสนอที่ดี 4/10 (40%) แต่รับข้อเสนอที่เสีย 7/13 (54%)
   - สาเหตุ: guard ตรวจ "รูปแบบ" ของหลักฐาน (quote, งวด, การอ้างอิง) แต่ตรวจ "ความหมาย" ไม่ได้ (scope, เหตุผลเชิงสาเหตุ, ศัพท์)
5. **ชั้นตรวจหลักฐานแบบ deterministic ตัดหลักฐานที่ถูกต้องทิ้ง [T][S]:**
   - finding ที่ reviewer ระบุว่าตัดสินได้ (ENTAILS / CONTRADICTS) ถูก downgrade 109/439 รายการ (25%)
   - 5 regression เกิดจากหลักฐานที่ถูกต้องถูกตัดเพราะ period resolver หรือ quote check ผิดพลาด แล้ว E1 จึงลดคำตอบเป็น INSUFFICIENT
   - ตัวอย่าง: AMZN-09 ข้อความ "in 2025, compared to the prior year" จาก 10-K ถูกตีว่าเป็นงวด 3 เดือน
6. **ประเภทที่แพ้มากที่สุดคือ interpretive [T]:** 25/50 เทียบ A2 30/50 (correction 3, regression 8) ขณะที่ SR ได้ 34/50
7. **Gold audit (25 ข้อ) [S]:**
   - Supported by Evidence 15, Defensible but Ambiguous 10, Potentially Incorrect 0, Unable to Verify 0
   - ข้อที่กำกวมกระจายเท่ากัน: อยู่ฝั่ง regression 5 ข้อ ฝั่ง correction 5 ข้อ จึง**ไม่พบหลักฐาน**ว่าความกำกวมของ Gold ทำให้ A3 เสียเปรียบอย่างเป็นระบบ

**คำตอบต่อคำถามวิจัย:** A3v2_2e ไม่ชนะ A2 และ P2 ด้วยเหตุผลสองชั้น
- ข้อเสนอของ reviewer ในข้อ interpretive มักผิดเชิงความหมาย และ guard ตรวจความหมายไม่ได้
- กลไกความระมัดระวังที่เพิ่มบน dev (decidability D-sup, E1, period / quote check) ทำงานโดยไม่สนว่าคำตอบเดิมถูกหรือผิด จึงลบคำตอบที่ถูกของ A2 ไปพอๆ กับที่ลบคำตอบที่ผิด

---

## 2. Experimental Context

| รายการ | ค่า |
|---|---|
| Run | `a3v2.2-gold150-20261118T112814Z` (complete 900/900, ERROR 0) |
| Evaluation | `results/gold150/a3v2.2-gold150-20261118T112814Z/evaluation.json` sha256 `e6422ff9f658c947…` (read-only) |
| Preregistration | `08_preregistration_gold150.md` STATUS: LOCKED, sha256 `ffad4375…` + amendment `12_…` |
| Gold | `datasets/gold_claims.jsonl` sha256 `1080323a…`; reference `Final_Gold_v3_approved.xlsx` sha256 `e47897c4…` |
| Evaluator | `scripts/a3v2_gold_evaluate.py` sha256 `bb11cde0…` |
| Model | `claude-sonnet-4-5-20250929`, temperature 0 |
| Label distribution (Gold) | SUPPORTED 68, CONTRADICTED 38, INSUFFICIENT 44 |

**ผลหลัก** (จาก `evaluation.json`):

| Approach | Correct | Accuracy | Macro-F1 | INSUFFICIENT recall |
|---|---:|---:|---:|---:|
| A1 | 94 | 62.7% | 0.605 | — |
| **A2** | **103** | **68.7%** | 0.657 | 21/44 (47.7%) |
| SR (P2) | 102 | 68.0% | 0.657 | 27/44 (61.4%) |
| R (v2.1.1) | 100 | 66.7% | 0.621 | — |
| RG (v2.1.1) | 99 | 66.0% | 0.622 | 19/44 |
| **A3v2_2e (P3)** | **98** | **65.3%** | 0.630 | 26/44 (59.1%) |
| A3 v1 | 96 | 64.0% | 0.590 | 12/44 |

**การทดสอบตาม prereg** (ไม่มีการทดสอบใหม่):
- A3v2_2e − A2 = −3.3 pp, McNemar exact p = 0.424, Holm 1.0, discordant 25
- A3v2_2e − SR = −2.7 pp, p = 0.585, Holm 1.0
- Acceptance: AC1–AC4 ไม่ผ่าน, AC5–AC6 ผ่าน

**ต้นทุน** (median ต่อ claim):

| Arm | LLM call | input token | ต้นทุน | API latency |
|---|---:|---:|---:|---:|
| A2 | 1 | 3.9k | $0.019 | 9.7 s |
| SR | 3 | 14.2k | $0.072 | 35.2 s |
| A3v2_2e | 5 | 29.0k | $0.141 | 59.8 s |

A3v2_2e ใช้ต้นทุนราว 7 เท่าของ A2 และ 2 เท่าของ SR โดยได้ความแม่นต่ำกว่าทั้งคู่

---

## 3. Methodology of Post-hoc Analysis

### 3.1 ตรวจความสมบูรณ์ของข้อมูล (Task 1)

| การตรวจ | ผล |
|---|---|
| Working directory / branch | `~/Desktop/Invesment-a3v2`, branch `research/a3-v2-reviewer-guard`, HEAD `41a4a39` (commit ผล freeze) |
| `SHA256SUMS` ของ run | ผ่าน 904/904 ไฟล์ |
| `status.json` | `complete`, 900/900, errors 0, cache miss 0, paid $23.24 (ledger cap $30) |
| Preregistration | sha256 ตรง `ffad4375…`, STATUS: LOCKED |
| Gold claims / reference workbook | sha256 ตรงกับ manifest และ `evaluation.json` |
| Evaluator / config | `bb11cde0…` / `121c2ddf…` ตรง |
| Code bundle | `scripts/code_bundle_sha256.sh` → `c4d2112f…` ตรงกับ prereg; ไฟล์โค้ด 47 ไฟล์ใน manifest ตรงทุกไฟล์ |
| `evaluation.json` | sha256 `e6422ff9f658c947…` ตรงกับ run log, permission read-only |
| Predictions | 6 arm × 150 ครบ, ไม่มีซ้ำ |
| Traces A2 / A3v2_2e | 150 + 150 ไฟล์ครบ, A3v2_2e มี `NO_FINAL_VERDICT` 3 ข้อ (AAPL-04, META-08, NFLX-08) ซึ่งไม่อยู่ใน 25 ข้อที่วิเคราะห์ |
| ตัวนับซ้ำ | คำนวณ correct / correction / regression / accepted change precision ใหม่จาก predictions + `engine.reference.load_reference` ได้ตรงกับ `evaluation.json` ทุกค่า |

**ข้อจำกัดที่พบ:**
- trace ของ A3 v1 อยู่คนละ run (`claimverif-main-v1-20261110T104207Z`) จึงเทียบ v1 ได้ที่ระดับ prediction เท่านั้น
- เอกสาร SEC ใน `backend/app/data/cache/` ถูกดาวน์โหลดใหม่หลังเหตุการณ์ 2026-11-18 จึงมี hash ดิบไม่ตรง manifest (SEC แทรก `<script>`) แต่ run log ยืนยันเนื้อหาด้วย cache-only replay แล้ว (`10_gold150_run_log.md`)

### 3.2 วิธีวิเคราะห์

1. **กำหนดกลุ่ม:** regression = A2 ถูก และ A3v2_2e ผิด; correction = A2 ผิด และ A3v2_2e ถูก (strict label match)
2. **ไล่ label chain ของ A3 ทีละขั้นจาก trace [T]:**
   `initial` → `numeric_verification` (= A2) → `reconciliation` (ข้อเสนอของ reviewer) → guard `decide()` → decidability gate → N1 / N2 numeric checks → E1 coverage → final
   - ลำดับนี้ยืนยันจาก `a3v2/graph.py:reconciliation_guard`
3. **ระบุจุดที่ label เปลี่ยน:** หาขั้นแรกที่ label เปลี่ยนไปเป็นคำตอบสุดท้ายที่ผิด (regression) หรือถูก (correction)
4. **ตรวจ findings ของ reviewer:** แยก `declared_relation` (ที่ reviewer ระบุ) ออกจาก `relation` / `validation_status` (หลังตรวจแบบ deterministic) เพื่อแยกความผิดของ reviewer ออกจากความผิดของชั้นตรวจหลักฐาน
5. **ตรวจหลักฐานกับเอกสาร SEC จริง [S]:** เทียบ quote และตัวเลขกับไฟล์ 10-K / 10-Q ที่ cache ไว้ ใช้ทั้งใน Task 2–4
6. **จัดสาเหตุ:** แยก Primary Cause กับ Contributing Factors โดยต้องมีหลักฐานจาก trace ทุกครั้ง

**ข้อจำกัดของวิธี:**
- การแยกตามกลไกเป็นการ**ระบุตำแหน่งที่ label เปลี่ยน** ไม่ใช่ counterfactual
- ไม่ได้อ้างว่าถ้าตัดกลไกใดออกแล้ว accuracy จะเป็นเท่าใด เพราะกลไกมีปฏิสัมพันธ์กัน และการเลือกตัดกลไกหลังเห็นผล Gold จะเป็นการ overfit แบบเดียวกับที่ทำให้ผล dev สูงเกินจริง (หัวข้อ 10)

### 3.3 นิยามที่ตรวจจากโค้ด

- **Accepted (decisive) change precision** (`a3v2_gold_evaluate.py:101-104`):

  ```
  changed = { i : pred_A3[i] != pred_A2[i]  and  pred_A3[i] ∈ {SUPPORTED, CONTRADICTED} }
  precision = Σ correct(i ∈ changed) / |changed|
  ```

  - คำนวณจาก **final prediction** ไม่ได้นับจาก outcome ACCEPT ของ guard
  - ไม่นับการเปลี่ยนไปเป็น INSUFFICIENT
  - บน Gold: |changed| = 10 ข้อ ถูก 4 → **40%**
  - ข้อที่ถูก: GOOGL-04, META-06, TSLA-04, WMT-13
  - ข้อที่ผิด: AMZN-08, NVDA-07, NVDA-09, META-12, NFLX-09, WMT-08
- **ห้ามสับสนกับ:**
  - correction rate 10/47 = 21.3% (ตัวหาร = ข้อที่ A2 ผิด)
  - regression rate 15/103 = 14.6% (ตัวหาร = ข้อที่ A2 ถูก)
  - guard accept precision (หัวข้อ 7) ซึ่งวัดที่ output ของ guard ก่อนผ่าน gate ถัดไป

---

## 4. Regression Analysis — 15 Cases (Task 2)

### 4.1 ตารางสรุป

ตัวย่อ: S = SUPPORTED, C = CONTRADICTED, I = INSUFFICIENT_EVIDENCE; Num = numerical, Int = interpretive, Amb = ambiguous

| # | Claim | ประเภท | Gold | A2 | A3 | ข้อเสนอ reviewer | ขั้นที่ทำให้ผิด | Primary cause |
|---|---|---|---|---|---|---|---|---|
| 1 | MSFT-12 | Amb | C | C | I | C (คงเดิม) | E1 coverage | Guard False Rejection (E1, หลักฐานต้องคำนวณหลายตัว) |
| 2 | AMZN-08 | Int | I | I | S | S | Reviewer + Guard ACCEPT | Evidence Scope Mismatch |
| 3 | AMZN-09 | Int | C | C | I | C (คงเดิม) | E1 coverage | Evidence Verification False Negative (period) |
| 4 | GOOGL-08 | Int | S | S | I | I | Reviewer + Guard ACCEPT | Ambiguous Predicate |
| 5 | GOOGL-13 | Amb | S | S | I | S (คงเดิม) | Decidability D-sup | Guard False Rejection (Decidability) |
| 6 | NVDA-03 | Num | S | S | I | S (คงเดิม) | N1 → ไม่มี basis | Evidence Verification False Negative (period) |
| 7 | NVDA-06 | Int | S | S | I | S (คงเดิม) | E1 coverage | Evidence Verification False Negative (period) |
| 8 | NVDA-07 | Int | C | C | S | S | Reviewer + Guard ACCEPT | Causal Overinterpretation |
| 9 | META-15 | Amb | S | S | I | S (คงเดิม) | Decidability D-sup | Guard False Rejection (Decidability) |
| 10 | NFLX-09 | Int | S | S | C | C | Reviewer + Guard ACCEPT | Unsupported Inference |
| 11 | WMT-08 | Int | C | C | S | S | Reviewer + Guard ACCEPT | Unsupported Inference |
| 12 | WMT-11 | Amb | C | C | I | I | Reviewer + Guard ACCEPT | Reviewer Under-labeling |
| 13 | WMT-15 | Amb | S | S | I | S (คงเดิม) | Decidability D-sup | Guard False Rejection (Decidability) |
| 14 | KO-08 | Int | C | C | I | C (คงเดิม) | E1 coverage | Evidence Verification False Negative (quote) |
| 15 | KO-13 | Amb | C | C | I | C (คงเดิม) | E1 coverage | Evidence Verification False Negative (intent rule) |

**ข้อสังเกตเชิงโครงสร้าง [T]:**
- **ใน 9/15 ข้อ reviewer ไม่ได้เสนอให้เปลี่ยนคำตอบเลย:** reviewer ยืนยันคำตอบของ A2 แต่คำตอบถูกเปลี่ยนโดย gate แบบ deterministic ภายหลัง (E1 5 ข้อ, D-sup 3 ข้อ, N1 1 ข้อ)
- **อีก 6 ข้อเกิดจาก reviewer เสนอผิดแล้ว guard รับ**

Path ของ trace: `results/runs/a3v2.2-gold150-20261118T112814Z/traces/A3v2_2e/<claim>.json` ใช้ stage `evidence_review`, `reconciliation` และ `reconciliation_guard`

### 4.2 รายข้อ

**1. GOLD-MSFT-12 (ambiguous):** "Microsoft's rising purchases of property and equipment in the quarter ended September 30, 2026 put no pressure on its free cash flow."
- **Gold C:** votes C / I / C
- **A2 = C:** อ้าง E3 "Cash used in investing increased $7.4 billion … primarily due to a $20.0 billion increase in additions to property and equipment" (10-Q 0001193125-26-436133)
- **A3 = I [T]:**
  - reviewer คง C และคำนวณใน reconciliation ว่า capex เพิ่ม $20.0B มากกว่า OCF ที่เพิ่ม $12.9B → FCF ลดลง
  - แต่ findings ทั้ง 4 รายการถูก declare เป็น `RELATED_NOT_DECIDING` เพราะหลักฐานแต่ละชิ้นตัดสินเองไม่ได้ ต้องนำสองตัวเลขมารวมกัน
  - N2 (FCF direction check) ได้ `NOT_APPLICABLE` แม้ claim พูดถึง free cash flow ตรงๆ
  - E1 จึงพบว่าไม่มี validated basis และลด C → I (`E1_NO_VALIDATED_BASIS`)
- **SEC [S]:**
  - OCF 58,000 เทียบ 45,057
  - Additions to P&E (39,367) เทียบ (19,394)
  - FCF = 18,633 เทียบ 25,663 → ลดลง สอดคล้องกับ Gold
- **Primary:** Guard False Rejection (E1)
- **Contributing:** Numerical Verification Failure (N2 ครอบคลุมรูป "no pressure on FCF" ไม่ได้), Reviewer under-labeling (finding ไม่รองรับหลักฐานที่ต้องคำนวณจากหลายแหล่ง)

**2. GOLD-AMZN-08 (interpretive):** "…technology and infrastructure expense … was primarily due to higher depreciation of servers and networking equipment."
- **Gold I:** votes S / S / I
- **A2 = I:** เหตุผลว่า filing ระบุ "infrastructure spending, including D&A" ไม่ได้เจาะจงค่าเสื่อม server
- **A3 = S [T]:**
  - reviewer ให้ R1 (E2) เป็น ENTAILS โดยใช้ข้อความ "primarily due to an increase in spending on infrastructure, including depreciation and amortization"
  - guard ACCEPT (`DECIDING_EVIDENCE_CITED`)
  - decidability ให้ `CAUSAL / PRIMARY_DRIVER / DECIDABLE` แต่ scope ว่าง จึงไม่มี scope gate ทำงาน
- **SEC [S]:** ข้อความยืนยันตามนั้น (10-Q 0001018724-26-000040) สาเหตุหลักคือ "spending on infrastructure" ซึ่ง**รวม** D&A ไม่ได้บอกว่า D&A ของ server / networking เป็นส่วนใหญ่
- **Primary:** Evidence Scope Mismatch (หลักฐานกว้างกว่า claim)
- **Contributing:** Unsupported Inference, Guard False Acceptance (guard ไม่ตรวจ scope), Gold ambiguity

**3. GOLD-AMZN-09 (interpretive):** "The increase in Amazon's International segment operating income in 2025 was driven primarily by lower fulfillment costs."
- **Gold C:** votes 3/3 C
- **A2 = C:** อ้างข้อความ verbatim จาก 10-K
- **A3 = I [T]:**
  - reviewer declare R1 (E2) เป็น **CONTRADICTS** ถูกต้อง
  - แต่ period check ให้ `PERIOD_MISMATCH` (`DURATION_DIFFERS:3M_vs_12M`) เพราะ resolver อ่าน marker "QUARTER" จากข้อความอื่นใน chunk เดียวกัน ("…recorded in Q3 2025…") ทั้งที่ quote ระบุ "in 2025, compared to the prior year" ในเอกสาร 10-K
  - E2 ถูกตัดออกจาก citation และ E1 ลด C → I
- **SEC [S]:** "The increase in International operating income in 2025 … is primarily due to increased unit sales and increased advertising sales, partially offset by increased fulfillment and shipping costs." (10-K 0001018724-26-000004)
- **Primary:** Evidence Verification False Negative (period resolver ใช้ marker ระดับ passage แทนระดับ quote)
- **Contributing:** Guard False Rejection (E1)

**4. GOLD-GOOGL-08 (interpretive):** "Growth in Google Search & other revenues in the quarter ended June 30, 2026 was primarily due to an increase in paid clicks."
- **Gold S:** votes S / C / I, Gold evidence เป็นแบบ PRIOR-CHECK (ไม่ verbatim)
- **A2 = S:** อ้าง paid clicks +13% เทียบ CPC +3%
- **A3 = I [T]:**
  - reconciliation ระบุว่า challenge H1 และ H2 ถูก **REFUTED** (ซึ่งสนับสนุน claim) แต่ยังเปลี่ยนเป็น I โดยให้เหตุผลว่า "primacy" ไม่ได้ระบุตรงๆ
  - findings ทั้ง 3 รายการเป็น `RELATED_NOT_DECIDING`
  - guard ACCEPT การเปลี่ยนเป็น I (`INITIAL_VERDICT_NOT_DECIDED_BY_VALID_EVIDENCE`)
- **SEC [S]:**
  - filing ระบุว่า "growth was driven by interrelated factors including increases in search queries…; growth in advertiser spending; and improvements … in ad formats and delivery"
  - paid clicks +13% / CPC +3% (10-Q 0001652044-26-000071)
- **Primary:** Ambiguous Predicate (การอ้างว่า "primarily due to" ต้องอนุมานจาก monetization metrics)
- **Contributing:** Reviewer inconsistency (H1 / H2 refuted แต่กลับเปลี่ยนคำตอบ), Guard False Acceptance (กฎ move-to-I ขึ้นกับ label ของ reviewer ทั้งหมด), Gold Label Disagreement (votes แตกทั้งสามทาง)

**5. GOLD-GOOGL-13 (ambiguous):** "Alphabet's net income … was boosted by gains on equity securities that do not reflect its operating performance."
- **Gold S:** votes S / I / S
- **A2 = S**
- **A3 = I [T]:**
  - reviewer คง S มี R1 (E5) **ENTAILS / VALID** ("OI&E … included net gains on equity securities of $99.0 billion")
  - decidability ให้ `EVALUATIVE / NEEDS_CRITERION` (terms: "boosted", "do not reflect its operating performance")
  - D-sup ลด S → I แม้มี finding ที่ตัดสินได้และ valid
- **SEC [S]:** Gain on equity securities 99,031 (Q2 2026), net income 112,193 เทียบ 28,196
- **Primary:** Guard False Rejection (Decidability D-sup)
- **Contributing:** Ambiguous Predicate (คำประเมินค่า)

**6. GOLD-NVDA-03 (numerical):** "NVIDIA's Data Center revenue for the quarter ended April 26, 2026 exceeded $40 billion."
- **Gold S:** votes 3/3
- **A2 = S (`NUMERIC_ALL_TRUE`) [T]:** แต่ numeric assertion ที่ A2 สกัดคือ **Revenue รวม** (81.6B) ไม่ใช่ Data Center
- **A3 = I [T]:**
  - N1 ตรวจพบ `SCOPE_MISMATCH` ของกฎ A2 ได้ถูกต้อง และถอน numeric basis
  - finding ที่ reviewer declare เป็น ENTAILS ทั้ง 4 รายการ (E5, E6 ตาราง "Data Center $ 75,246") ถูก downgrade เป็น `PERIOD_UNKNOWN` (`PASSAGE_STATES_SEVERAL_DURATIONS`)
  - จึงไม่มี basis เหลือ → I
- **SEC [S]:** ตาราง Data Center 75,246 (Q1 FY2027, 10-Q 0001045810-26-000052)
- **Primary:** Evidence Verification False Negative (period)
- **Contributing:** Numerical Verification Failure (การสกัด metric ของ A2 ผิดตั้งแต่ต้น ทำให้ A2 ถูกโดยบังเอิญ)
- **หมายเหตุ:** N1 ทำงานถูก ข้อเดียวกันนี้ใน TSLA-04 กลายเป็น correction (หัวข้อ 5)

**7. GOLD-NVDA-06 (interpretive):** "NVIDIA's Data Center revenue growth in fiscal 2026 was driven primarily by demand for its Blackwell platform."
- **Gold S:** votes 3/3
- **A2 = S:** อ้าง 10-K "Revenue from Data Center computing grew 59% driven by demand for our Blackwell computing platform"
- **A3 = I [T]:**
  - reviewer declare R1 (E3 = ข้อความเดียวกันใน 10-K) เป็น ENTAILS แต่ถูก downgrade เป็น `PERIOD_UNKNOWN` (`PASSAGE_STATES_SEVERAL_DURATIONS`)
  - E1 และ E2 (ข้อความแบบ 6 เดือน / 9 เดือนจาก 10-Q) ถูกตัดเป็น `PERIOD_MISMATCH` ซึ่ง**ถูกต้อง**
  - E1 coverage ลด S → I
- **SEC [S]:** ข้อความยืนยันใน 10-K 0001045810-26-000021 ส่วน Gold คำนวณว่า compute คิดเป็น 76.6% ของการเพิ่มของ Data Center
- **Primary:** Evidence Verification False Negative (period)
- **Contributing:** Guard False Rejection (E1)

**8. GOLD-NVDA-07 (interpretive):** "The decline in NVIDIA's gross margin in fiscal 2026 was caused mainly by charges related to H20 export restrictions."
- **Gold C:** votes C / C / I
- **A2 = C:** filing ระบุสองสาเหตุ (transition ไป Blackwell และ H20 charge)
- **A3 = S [T]:**
  - reconciliation อ้าง E6 "net effect on our gross margin was an unfavorable impact of 2.6%" แล้วสรุปว่า H20 คิดเป็น "≈67% ของการลด 3.9 pp"
  - guard ACCEPT โดย deciding finding คือ **R8 ซึ่งเป็น finding ของ assertion N1** ("gross margin ลดลง") **ไม่ใช่ A0** (คำกล่าวเชิงสาเหตุ)
  - เป็นข้อเดียวใน 12 ข้อที่ guard รับการเปลี่ยนเป็นคำตอบเด็ดขาด โดยไม่มี deciding finding ของ A0 เลย
- **SEC [S]** (10-K 0001045810-26-000021):
  - "Provisions … totaled $7.2 billion and $3.7 billion … including $4.5 billion associated with H20 … provision release of $1.5 billion and $689 million … net effect … unfavorable impact of 2.6% and 2.3% in fiscal years 2026 and 2025"
  - ผลกระทบสุทธิเพิ่มขึ้นจากปีก่อนเพียง 0.3 pp จาก gross margin ที่ลด 3.9 pp
  - reviewer ใช้ "ระดับ" (2.6 pp) แทน "การเปลี่ยนแปลง"
- **Primary:** Causal Overinterpretation
- **Contributing:** Numerical reasoning error (สับสนระดับกับการเปลี่ยนแปลง), Guard False Acceptance (ยอมรับ finding ระดับ sub-assertion), Gold ambiguity (หัวข้อ 8)

**9. GOLD-META-15 (ambiguous):** "Meta's revenue growth in 2025 was broad-based across geographic regions."
- **Gold S:** votes S / I / S
- **A2 = S**
- **A3 = I [T]:**
  - R1 และ R2 เป็น ENTAILS / VALID ("In 2025, revenue increased by 21% … 24% … 20% … 27%")
  - decidability ให้ `EVALUATIVE / NEEDS_CRITERION` ("broad-based")
  - D-sup ลด S → I
- **SEC [S]:** ข้อความตรง (10-K 0001628280-26-003942) ทุกภูมิภาคโต 20–27%
- **Primary:** Guard False Rejection (Decidability D-sup)
- **Contributing:** Ambiguous Predicate

**10. GOLD-NFLX-09 (interpretive):** "The increase in Netflix's marketing expenses in 2025 was driven mainly by higher advertising expenses."
- **Gold S:** votes 3/3
- **A2 = S**
- **A3 = C [T]:**
  - reviewer declare R1 (E5) เป็น CONTRADICTS โดยให้เหตุผลว่า "marketing" กับ "advertising" เป็นคนละหมวด
  - reviewer**ได้ retrieve E12** ("Advertising expenses were $2,001 million, $1,779 million") และคำนวณเองว่า +$222M แต่ให้เป็น `RELATED_NOT_DECIDING` โดยไม่เชื่อมกับ "$222 million increase in marketing expenses" ใน E5
  - guard ACCEPT (finding valid)
- **SEC [S]:** marketing expenses +$222M และ advertising expenses +$222M (2,001 − 1,779) ตรงกัน (10-K 0001065280-26-000034)
- **Primary:** Unsupported Inference (ตีความศัพท์ผิดแล้วสรุปเป็นการขัดแย้ง)
- **Contributing:** Reviewer synthesis failure (มีหลักฐานครบแต่ไม่เชื่อมกัน), Guard False Acceptance (guard ตรวจความหมายไม่ได้)
- **หมายเหตุ:** ไม่ใช่ retrieval failure เพราะหลักฐานถูก retrieve มาแล้ว

**11. GOLD-WMT-08 (interpretive):** "Walmart's gross profit rate improved in fiscal 2026 because of a more favorable business mix, including advertising and membership income."
- **Gold C:** votes I / S / C
- **A2 = C (`NUMERIC_PARTIALLY_UNVERIFIABLE`)**
- **A3 = S [T]:**
  - deciding findings R2 (A0, "growth in higher margin businesses globally") กับ R7 และ R8 (**N1**: gross profit rate +8 bps)
  - reviewer อ้าง E10 / E11 ("higher margin areas, such as digital advertising") แต่ไม่ได้จัดการกับ "membership income" ใน claim
- **SEC [S]** (10-K 0000104169-26-000055):
  - การเพิ่มของ gross profit rate "primarily driven by the Walmart U.S. segment, due to disciplined inventory management, as well as growth in higher margin businesses globally"
  - "Gross profit defined as net sales less cost of sales" และ Membership and other income เป็นบรรทัดแยก จึงไม่ได้อยู่ใน gross profit
- **Primary:** Unsupported Inference (ยืนยันทั้ง claim จากหลักฐานที่ครอบคลุมเพียงส่วนเดียว)
- **Contributing:** Evidence Scope Mismatch (membership income), Guard False Acceptance (นับ finding ของ N1 รวมเป็น deciding), Gold ambiguity

**12. GOLD-WMT-11 (ambiguous):** "Walmart's fiscal 2026 results show that tariffs did not pressure its profitability."
- **Gold C:** votes C / I / C
- **A2 = C:** อ้าง "We experienced the impacts noted above during fiscal 2026 as a result of incremental import tariffs."
- **A3 = I [T]:**
  - reviewer declare ข้อความเดียวกันนี้ (R2, E2) เป็น `RELATED_NOT_DECIDING` / VALID เพราะ "does not quantify"
  - ไม่มี deciding finding → guard ACCEPT การเปลี่ยนเป็น I
- **SEC [S]:** "…can impact, and have impacted, our business and profit margins…" และ "We experienced the impacts noted above during fiscal 2026…"
- **Primary:** Reviewer Under-labeling
- **Contributing:** Ambiguous Predicate ("pressure profitability"), Guard False Acceptance (การยอมให้เปลี่ยนเป็น I ใช้ label ของ reviewer เป็นเกณฑ์ทั้งหมด)

**13. GOLD-WMT-15 (ambiguous):** "Walmart's net income for fiscal 2026 was affected by fair value changes on equity investments that mask its operating performance."
- **Gold S:** votes S / I / S
- **A2 = S**
- **A3 = I [T]:**
  - R1, R2 และ R4 เป็น ENTAILS / VALID
  - decidability ให้ `EVALUATIVE` ("mask") → D-sup ลด S → I
- **SEC [S]:** "Other gains and losses … net gain of $2.1 billion … primarily driven by changes in the fair value of our equity and other investments"
- **Primary:** Guard False Rejection (Decidability D-sup)
- **Contributing:** Ambiguous Predicate, Gold ambiguity

**14. GOLD-KO-08 (interpretive):** "Foreign currency exchange rate fluctuations reduced Coca-Cola's net operating revenues in the quarter ended October 2, 2026."
- **Gold C:** votes 3/3
- **A2 = C:** อ้างข้อความเรื่อง **operating income** (+3%) ไม่ใช่ net operating revenues จึงถูกด้วยหลักฐานข้างเคียง
- **A3 = I [T]:**
  - reviewer declare R1 (E13 ตาราง "Foreign Currency Fluctuations … +1%") เป็น CONTRADICTS แต่ quote check ให้ `KEY_QUOTE_NOT_IN_EVIDENCE` เพราะ reviewer ต่อเซลล์ตารางด้วย "…"
  - E3 ถูกตัด (`PERIOD_MISMATCH`, ข้อความแบบ 3 เดือนและ 9 เดือนรวมกัน)
  - E1 ลด C → I
- **SEC [S]:** "Fluctuations in foreign currency exchange rates … favorably impacted our consolidated net operating revenues by 1%." (10-Q 0001628280-26-067844) ประโยคนี้**ไม่ถูก retrieve** โดยทั้ง A2 และ A3
- **Primary:** Evidence Verification False Negative (quote check กับข้อมูลตาราง)
- **Contributing:** Retrieval Failure (ไม่พบประโยคที่ตัดสินได้), Guard False Rejection (E1)

**15. GOLD-KO-13 (ambiguous):** "Coca-Cola's tax litigation with the IRS, as disclosed as of July 3, 2026, does not pose a material risk to its financial position."
- **Gold C:** votes 3/3
- **A2 = C**
- **A3 = I [T]:**
  - R1 (E1) เป็น CONTRADICTS, quote VERIFIED แต่ถูก downgrade ด้วย `NON_RESULT_EVIDENCE:FORWARD_LOOKING_OR_RISK`
  - R4 ได้ `KEY_QUOTE_NOT_IN_EVIDENCE`
  - E1 ลด C → I
- **SEC [S]:** "…would likely be subject to significant additional liabilities…, which could have a material adverse impact on the Company's financial position…" (10-Q 0001628280-26-050503)
- **Primary:** Evidence Verification False Negative (กฎ intent ตัดหลักฐานประเภท risk ทั้งที่ claim เป็น**คำกล่าวเรื่องความเสี่ยง**)
- **Contributing:** Guard False Rejection (E1), Ambiguous Predicate ("material risk")

---

## 5. Correction Analysis — 10 Cases (Task 3)

### 5.1 ตารางสรุป

| # | Claim | ประเภท | Gold | A2 | A3 | กลไกที่แก้ | A3 แก้ได้เพราะ | Evidence รองรับจริงหรือไม่ |
|---|---|---|---|---|---|---|---|---|
| 1 | AAPL-13 | Amb | I | S | I | E1 | Gate ระมัดระวังตรงกับข้อจำกัดของ claim | **บางส่วน:** reviewer ยังเชื่อว่าเป็น S |
| 2 | MSFT-14 | Amb | I | C | I | Guard REJECT + E1 | Guard กันข้อเสนอผิด (S) และ E1 ถอน C ที่ไม่มี basis | **บางส่วน:** I สอดคล้องกับ materiality ที่ไม่มีเกณฑ์ |
| 3 | AMZN-06 | Int | I | C | I | E1 | บังเอิญตรง Gold: reviewer ยังเชื่อว่าเป็น C | **ไม่:** ไม่มี finding ที่สนับสนุน I |
| 4 | AMZN-13 | Amb | I | C | I | E1 | บังเอิญตรง Gold: reviewer ยังเชื่อว่าเป็น C | **ไม่** |
| 5 | GOOGL-04 | Num | S | I | S | Reviewer + Guard ACCEPT | พบหลักฐานใหม่ (XBRL / งบดุล) | **บางส่วน:** finding ที่ผ่านการตรวจครอบคลุมเฉพาะยอด 30 ก.ย. 2026 |
| 6 | META-06 | Int | S | C | S | Reviewer + Guard ACCEPT | พบหลักฐานที่ระบุเฉพาะ Q3 และให้เหตุผลถูก | **ใช่** |
| 7 | META-11 | Amb | I | S | I | E1 (หลัง false period mismatch) | บังเอิญตรง Gold: กลไกผิด | **ไม่:** หลักฐานถูกตัดด้วย period check ที่ผิด |
| 8 | TSLA-04 | Num | S | C | S | N1 + finding ของ reviewer | ตรวจ scope ของตัวเลขเพิ่ม | **ใช่** |
| 9 | WMT-07 | Int | I | C | I | E1 (หลัง false period mismatch) | บังเอิญตรง Gold | **ไม่** |
| 10 | WMT-13 | Amb | C | I | C | Reviewer + Guard ACCEPT | ตรวจตัวเลขเพิ่ม (counter-numeric) | **ใช่** |

**สรุป [T]:**
- **แก้ได้จากหลักฐานจริงและเหตุผลถูก 3 ข้อ:** META-06, TSLA-04, WMT-13
- **แก้ได้แต่หลักฐานที่ผ่านการตรวจไม่ครบ 1 ข้อ:** GOOGL-04
- **แก้ได้จาก gate ความระมัดระวังที่บังเอิญตรงกับข้อจำกัดจริงของ claim 2 ข้อ:** AAPL-13, MSFT-14
- **ตรงกับ Gold โดยกลไกที่ไม่ได้ให้เหตุผลรองรับ 4 ข้อ:** AMZN-06, AMZN-13, META-11, WMT-07
- **6 ใน 10 correction มาจาก E1** ซึ่งลดคำตอบเป็น INSUFFICIENT โดยไม่ขึ้นกับว่า A2 ถูกหรือผิด ชุด regression มีอีก 5 ข้อที่ E1 ทำแบบเดียวกันกับคำตอบที่ถูกของ A2

### 5.2 รายข้อ

**1. GOLD-AAPL-13 (ambiguous):** "Apple's share repurchases in the first half of fiscal 2026 were funded from operating cash flow rather than new borrowing."
- **Gold I:** votes S / I / I
- **A2 = S:** OCF 82,627 > repurchases 36,989 และมีการชำระหนี้
- **A3 [T]:** reviewer คง S แต่ findings ทั้งหมดเป็น `RELATED_NOT_DECIDING` → E1 ลดเป็น I
- **SEC [S]:** ตัวเลขยืนยันใน 10-Q 0000320193-26-000013 แต่ไม่มีข้อความระบุว่าใช้เงินจากแหล่งใด (เงินสด fungible ตามเหตุผลของ Gold)
- **ข้อสรุป:** Prediction ถูก, evidence รองรับ I ในแง่ "ไม่มีข้อความระบุแหล่งเงิน" แต่ reviewer เองยังเชื่อว่าเป็น S

**2. GOLD-MSFT-14 (ambiguous):** "Microsoft's accounting for its investment in OpenAI had no material effect on its net income for the quarter ended September 30, 2026."
- **Gold I:** votes C / I / I
- **A2 = C:** อ้างกำไร $272M ใน other income
- **A3 [T]:**
  - reviewer เสนอ S (กระทบ 0.57% ของ net income)
  - guard REJECT (`CONTEXT_ONLY`) แล้ว E1 ถอน C ของ A2 เพราะไม่มี basis
- **SEC [S]:** "…increase in net income and diluted EPS of $207 million and $0.03" เทียบกับ net income 36,629 คิดเป็น 0.57%
- **ข้อสรุป:** Guard ป้องกันการเปลี่ยนที่ผิดไปเป็น S, คำตอบ I สอดคล้องกับหลักฐานเพราะไม่มีเกณฑ์ materiality ใน filing

**3. GOLD-AMZN-06 (interpretive):** "The improvement in Amazon's North America segment operating income in the quarter ended September 30, 2026 was driven mainly by advertising sales growth."
- **Gold I:** votes C / C / I
- **A3 [T]:** reviewer คง C และ challenge ทั้งสามได้ `NO_RELEVANT_EVIDENCE` แล้ว E1 ลด C → I
- **SEC [S]:** "…primarily due to increased unit sales and increased advertising sales…" (10-Q 0001018724-26-000040)
- **ข้อสรุป:** ตรงกับ Gold โดยไม่มีเหตุผลรองรับใน trace

**4. GOLD-AMZN-13 (ambiguous):** "Amazon's operating income in the quarter ended March 31, 2026 benefited from one-time items that overstate its underlying profitability."
- **Gold I:** votes C / I / I
- **A3 [T]:**
  - reviewer คง C โดยให้เหตุผลว่ากำไรจาก Anthropic อยู่ใน other income
  - finding ที่ declare เป็น ENTAILS 2 รายการได้ `KEY_QUOTE_NOT_IN_EVIDENCE` และไม่มี CONTRADICTS
  - E1 ลด C → I
- **SEC [S]:**
  - การปรับขึ้น $12.3B อยู่ใน "Other income (expense), net"
  - "Other operating expense (income), net … $447 million … primarily related to charges associated with damaged data centers…" (10-Q 0001018724-26-000014)
- **ข้อสรุป:** ตรงกับ Gold โดยบังเอิญ (ดูหัวข้อ 8 เรื่องความกำกวมของ Gold)

**5. GOLD-GOOGL-04 (numerical):** "Alphabet's long-term debt was higher as of September 30, 2026 than at December 31, 2025."
- **Gold S:** votes 3/3
- **A2 = I (`NUMERIC_PARTIALLY_UNVERIFIABLE`) [T]:** กฎตัวเลขของ A2 เทียบกับ 30 ก.ย. 2025 (yoy) ไม่ใช่ 31 ธ.ค. 2025 และ threshold ว่าง
- **A3 [T]:**
  - counter-retrieval พบ XBRL E7 (125,102) และ E13 (46,547 ณ 31 ธ.ค. 2025)
  - guard ACCEPT ด้วย R1 / R5 (ยอด ณ 30 ก.ย. 2026)
  - แต่ E13 ซึ่งเป็นยอดฐานเปรียบเทียบถูกตัดเป็น `PERIOD_MISMATCH`
- **SEC [S]:** งบดุล "Long-term debt 46,547 125,102" (10-Q 0001652044-26-000084)
- **ข้อสรุป:** พบหลักฐานใหม่จริงและ prediction ถูก แต่ chain ของหลักฐานที่ผ่านการตรวจไม่มียอดฐาน 31 ธ.ค. 2025

**6. GOLD-META-06 (interpretive):** "Meta's advertising revenue growth in the quarter ended September 30, 2026 was driven more by a higher average price per ad than by more ad impressions."
- **Gold S:** votes 3/3
- **A2 = C:** เหตุผลของ A2 ยอมรับว่า 14% > 10% แต่ยังตอบ C
- **A3 [T]:** R3 / R4 (E10, E18: "Ad impressions … increased 10% … average price per ad … increased 14%" เฉพาะ Q3) ได้ ENTAILS / VALID แล้ว guard ACCEPT
- **SEC [S]:** ข้อความตรงใน 10-Q 0001628280-26-066773
- **ข้อสรุป:** แก้ได้จากหลักฐานที่ระบุงวดชัดกว่า และ evidence รองรับจริง

**7. GOLD-META-11 (ambiguous):** "Meta's results … show that its AI investments are improving advertising performance."
- **Gold I:** votes 3/3
- **A3 [T]:**
  - reviewer คง S แต่ R1 (E1, ประโยคแบบ "three and nine months") ถูก downgrade เป็น `PERIOD_MISMATCH` (9M vs 3M)
  - ประโยคนี้ครอบคลุมงวด 3 เดือนด้วย จึงเป็น period check ที่ผิด
  - E1 ลด S → I
- **ข้อสรุป:** ตรงกับ Gold แต่กลไกผิด ข้อผิดพลาดชนิดเดียวกันทำให้เกิด regression ใน AMZN-09

**8. GOLD-TSLA-04 (numerical):** "Tesla's energy generation and storage revenue for fiscal year 2025 increased by more than 20%…"
- **Gold S:** votes 3/3
- **A2 = C (`NUMERIC_FALSE`) [T]:** สกัด metric เป็น **Revenue รวม** (−2.9%)
- **A3 [T]:** N1 พบ `SCOPE_MISMATCH` และถอนกฎของ A2 แล้วใช้ finding R1–R4 (E11 "+27%", E12 "12,771 vs 10,086") ที่ valid → S
- **SEC [S]:** "Energy generation and storage revenue increased $2.69 billion, or 27%…" (10-K 0001628280-26-003952)
- **ข้อสรุป:** แก้ได้จากการตรวจ scope ของตัวเลข และ evidence รองรับจริง

**9. GOLD-WMT-07 (interpretive):** "Walmart's eCommerce sales growth in the quarter ended July 31, 2026 was driven primarily by store-fulfilled pickup and delivery."
- **Gold I:** votes S / S / I
- **A3 [T]:** reviewer คง C แต่ E1 / E3 ถูกตัดเป็น `PERIOD_MISMATCH` (ประโยคแบบ "three and six months") แล้ว E1 ลดเป็น I
- **SEC [S]:**
  - 10-Q 0000104169-26-000154 ระบุ "primarily driven by store-fulfilled delivery" โดยไม่มีคำว่า pickup
  - 10-K ปีงบ 2026 ใช้ "store-fulfilled pickup and delivery"
- **ข้อสรุป:** ตรงกับ Gold โดยกลไกที่ไม่รองรับ

**10. GOLD-WMT-13 (ambiguous):** "Walmart's growing advertising business is the main reason its operating income grew faster than its sales in fiscal 2026."
- **Gold C:** votes 3/3
- **A2 = I:** เหตุผลของ A2 คำนวณผิด ("operating income did grow faster than sales")
- **A3 [T]:**
  - counter challenge H1 คำนวณ operating income +1.6% เทียบ net sales +4.7% → presupposition ของ claim เป็นเท็จ
  - guard ACCEPT (R3 ผ่าน quote check 1.1)
- **SEC [S]:** operating income 29,825 เทียบ 29,348, net sales 706,413 เทียบ 674,538
- **ข้อสรุป:** แก้ได้จากการตรวจตัวเลขเพิ่ม เป็นตัวอย่างที่ดีของคุณค่าของ counter-evidence

---

## 6. Root Cause Taxonomy

**นิยามสองหมวดที่เพิ่มจากรายการตั้งต้น** (เพราะหมวดเดิมแยกสาเหตุเหล่านี้ไม่ได้):
- **Evidence Verification False Negative:** check แบบ deterministic (period / quote / intent) ตัดหลักฐานที่ถูกต้องออก ใน taxonomy เดิมผลของมันจะไปปรากฏเป็น "Guard False Rejection" แต่ต้นเหตุอยู่ที่ชั้นตรวจหลักฐาน
- **Reviewer Under-labeling:** reviewer มีหลักฐานที่ตัดสินได้แต่ label เป็น `RELATED_NOT_DECIDING`

### 6.1 Primary cause ของ 15 regression [T]

| Primary cause | จำนวน | Claims |
|---|---:|---|
| Evidence Verification False Negative | 5 | AMZN-09 (period), NVDA-03 (period), NVDA-06 (period), KO-08 (quote), KO-13 (intent) |
| Guard False Rejection: Decidability D-sup | 3 | GOOGL-13, META-15, WMT-15 |
| Guard False Rejection: E1 (หลักฐานต้องคำนวณหลายตัว) | 1 | MSFT-12 |
| Unsupported Inference | 2 | NFLX-09, WMT-08 |
| Evidence Scope Mismatch | 1 | AMZN-08 |
| Causal Overinterpretation | 1 | NVDA-07 |
| Ambiguous Predicate | 1 | GOOGL-08 |
| Reviewer Under-labeling | 1 | WMT-11 |
| Retrieval Failure / Period Mismatch (จริง) / Gold Label Disagreement / Other | 0 | — |
| **รวม** | **15** | |

### 6.2 Contributing factors (หนึ่งข้อนับได้หลายปัจจัย) [T]

| Contributing factor | จำนวน | Claims |
|---|---:|---|
| Guard False Acceptance | 6 | AMZN-08, GOOGL-08, NVDA-07, NFLX-09, WMT-08, WMT-11 |
| Guard False Rejection (E1 ปิดท้าย) | 5 | AMZN-09, NVDA-03, NVDA-06, KO-08, KO-13 |
| Ambiguous Predicate | 5 | GOOGL-13, META-15, WMT-11, WMT-15, KO-13 |
| Gold ambiguity (Defensible but Ambiguous) | 5 | AMZN-08, GOOGL-08, NVDA-07, WMT-08, WMT-15 |
| Numerical Verification Failure | 3 | MSFT-12 (N2 ไม่ครอบคลุม), NVDA-03 (A2 สกัด metric ผิด), NVDA-07 (ระดับกับการเปลี่ยนแปลง) |
| Reviewer synthesis / under-labeling | 3 | MSFT-12, NFLX-09, GOOGL-08 |
| Evidence Scope Mismatch | 1 | WMT-08 |
| Unsupported Inference | 1 | AMZN-08 |
| Retrieval Failure | 1 | KO-08 |

### 6.3 ระดับ pipeline (ตำแหน่งที่ label เปลี่ยน)

| ชั้นที่เป็นต้นเหตุหลัก | Regression | Correction |
|---|---:|---:|
| Reviewer (เสนอผิด / label ไม่ครบ) | 6 | 3 (เสนอถูก) |
| Evidence verification (period / quote / intent) | 5 | 0 (ช่วยโดยบังเอิญใน META-11, WMT-07) |
| Decidability gate | 3 | 0 |
| N1 / numeric (สกัด metric ผิดตั้งแต่ A2) | 1 | 1 |
| Retrieval | 0 (contributing 1) | — |

**ข้อสรุป:** retrieval ไม่ใช่คอขวดหลัก ใน regression ส่วนใหญ่ หลักฐานที่ถูกต้อง**อยู่ใน trace แล้ว** แต่ถูกตีความผิด (reviewer) หรือถูกตัดทิ้ง (verification / gate)

---

## 7. Reviewer and Guard Failure Analysis (Task 5)

### 7.1 ตัวเลขจาก trace [T]

> **วิธีนับ:** ACCEPT / REJECT ในหัวข้อนี้คือผลของ `decide()` ของ guard **ก่อน** decidability gate
> - ใน trace ฟิลด์ `reconciliation_guard.outcome` ของ AAPL-12, KO-14 และ TSLA-14 เป็น `REJECT` (reason `DECIDABILITY:NO_CRITERION`) เพราะ decidability gate เขียนทับผลของ `decide()` (`a3v2/graph.py:156`)
> - `rule_trace` ของทั้งสามข้อบันทึกว่า `decide()` ให้ผล `ACCEPT: DECIDING_EVIDENCE_CITED`
> - ถ้านับจากฟิลด์ `outcome` ตรงๆ จะได้ ACCEPT 11 / REJECT 22 และรับข้อเสนอดี 3/10 กับข้อเสนอเสีย 6/13 ข้อสรุปว่า guard แยกข้อเสนอดีกับเสียไม่ออกยังเหมือนเดิม

| ตัวชี้วัด | ค่า |
|---|---:|
| Reviewer เสนอเปลี่ยนคำตอบ (reconciliation label ≠ A2) | **33** |
| Guard ACCEPT / REJECT | **14 / 19** |
| ACCEPT ที่แก้ A2 ผิด → ถูก (ที่ output ของ guard) | 4 (GOOGL-04, META-06, WMT-13, KO-14) |
| ACCEPT ที่ทำ A2 ถูก → ผิด (ที่ output ของ guard) | **7** (AAPL-12, AMZN-08, GOOGL-08, NVDA-07, NFLX-09, WMT-08, WMT-11) |
| ACCEPT ที่ผิดทั้งก่อนและหลัง | 3 (NVDA-09, META-12, TSLA-14) |
| REJECT ที่กันข้อเสนอผิดได้ถูกต้อง | 6 |
| **REJECT ข้อเสนอที่ควรรับ** (A2 ผิด, ข้อเสนอถูก) | **6** |
| REJECT ที่ผิดทั้งคู่ | 7 |

**ข้อเสนอ 6 ข้อที่ guard REJECT ทั้งที่ควรรับ:**

| Claim | เหตุผลที่ REJECT |
|---|---|
| NVDA-11 | `INVALID_DECIDING_EVIDENCE:PERIOD_UNKNOWN` |
| TSLA-15 | `CONTEXT_ONLY` |
| NFLX-13 | `CONTEXT_ONLY` |
| WMT-09 | `INITIAL_VERDICT_STILL_DECIDED` |
| KO-04 | `CONFLICTING_DECIDING_EVIDENCE` |
| KO-12 | `DECIDING_EVIDENCE_NOT_CITED` |

**gate หลัง guard เปลี่ยนผลของการ ACCEPT 3 ข้อ:**
- AAPL-12: D-sup ดึงกลับเป็น I ซึ่งถูก (กัน regression ได้ 1 ข้อ)
- KO-14: D-sup ดึง S ที่ถูกกลับเป็น I (ทำให้เสีย correction 1 ข้อ)
- TSLA-14: D-sup เปลี่ยน C → I ซึ่งยังผิดอยู่

**ผลสุดท้ายของเส้นทาง reviewer:** correction 3, regression 6

### 7.2 Guard แยกข้อเสนอดีกับข้อเสนอเสียไม่ออก [T]

- **ข้อเสนอดี** (A2 ผิด → ข้อเสนอถูก) มี 10 ข้อ guard รับ 4 = **40%**
- **ข้อเสนอเสีย** (A2 ถูก → ข้อเสนอผิด) มี 13 ข้อ guard รับ 7 = **54%**
- ถ้ารับข้อเสนอทั้งหมดโดยไม่มี guard จะได้ fix 10 / break 13 (สุทธิ −3) ส่วนเมื่อมี guard ได้ fix 4 / break 7 (สุทธิ −3) **guard ไม่ได้ปรับปรุงผลสุทธิของ reviewer**

**สาเหตุ [T]:**
- **การรับข้อเสนอเสีย:** ข้อเสนอเสีย 7 ข้อแบ่งเป็นสองแบบ
  - 5 ข้อเปลี่ยนเป็นคำตอบเด็ดขาด (AAPL-12, AMZN-08, NVDA-07, NFLX-09, WMT-08) และ**ทุกข้อ**มี deciding finding ที่ "valid" ครบทุก check ทั้ง quote, งวด และบริษัท ความผิดอยู่ที่**ความหมาย**: scope (AMZN-08), ศัพท์ (NFLX-09), ความครอบคลุมของ claim (WMT-08) และเหตุผลเชิงสาเหตุ (NVDA-07) ซึ่ง check แบบ deterministic มองไม่เห็น
  - อีก 2 ข้อเปลี่ยนเป็น I (GOOGL-08, WMT-11) ซึ่ง guard รับเพราะ reviewer ไม่ได้ label finding ใดว่าตัดสินได้
- **การปฏิเสธข้อเสนอดี:** ข้อเสนอดีถูกปฏิเสธด้วยกฎรูปแบบ (`CONTEXT_ONLY`, `PERIOD_UNKNOWN`, `NOT_CITED`) มากกว่าด้วยเหตุผลเชิงเนื้อหา
- **ช่องโหว่ระดับ assertion:** NVDA-07 แสดงว่า guard ยอมรับ deciding finding ของ sub-assertion (N1: "margin ลดลง") เป็นหลักฐานของ claim เชิงสาเหตุ (A0) ได้ เพราะ `decide()` ไม่ได้บังคับว่า finding ต้องอยู่บน A0

### 7.3 ความผิดพลาดเกิดที่ใดเป็นหลัก

- **Reviewer** (6 regression): ตีความเชิงความหมายผิดใน claim เชิงสาเหตุ / อธิบาย และ label หลักฐานไม่ครบ
- **Evidence verification** (5 regression): period resolver ใช้ marker ระดับ passage, quote check ไม่รองรับตาราง และกฎ intent ตัดหลักฐานประเภท risk
  - finding ที่ reviewer declare เป็น ENTAILS / CONTRADICTS ถูก downgrade 109/439 (25%) บน Gold ทั้งชุด
  - แยกเหตุผลได้: `KEY_QUOTE_NOT_IN_EVIDENCE` 85, `PERIOD_MISMATCH` 14, `PERIOD_UNKNOWN` 8, อื่นๆ 2
  - ไม่ได้ตรวจทุกรายการว่าเป็น false negative จึงไม่ใช่อัตรา error
- **Decidability** (3 regression): `EVALUATIVE / NEEDS_CRITERION` + D-sup ลด S → I แม้มี finding ที่ valid
- **Guard** เป็น**ตัวขยาย**ความผิดของ reviewer มากกว่าเป็นต้นเหตุ: รับ 7 ข้อเสนอเสีย และตัด 6 ข้อเสนอดี
- **Retrieval** ไม่ใช่สาเหตุหลักใน regression ใดเลย พบเป็นปัจจัยร่วมเพียง KO-08

### 7.4 Overinterpretation ของ A3 v1 ยังเกิดอยู่หรือไม่ [T]

| | A3 v1 | A3v2_2e |
|---|---:|---:|
| Regression ทั้งหมด | 15 | 15 |
| Regression แบบ I → คำตอบเด็ดขาด (over-interpretation) | **10** (I→S 7, I→C 3) | **1** (AMZN-08) |
| Regression แบบสลับ S ↔ C | 3 | 3 (NVDA-07, NFLX-09, WMT-08) |
| Regression แบบคำตอบเด็ดขาด → I (over-abstention) | 2 | **11** |
| จำนวนครั้งที่ทำนาย I | 21 | 52 |

**ข้อสรุป:**
- over-interpretation **ลดลงมาก** (10 → 1 ข้อแบบ I → decisive) แต่**ยังเหลือในรูปการสลับขั้วเชิงสาเหตุ**
- NVDA-07, NFLX-09 และ WMT-08 เป็น regression ของ v1 ด้วย หมายถึง claim กลุ่มเดียวกันยังหลอก reviewer ได้ทั้งสองรุ่น
- ความผิดพลาดหลักเปลี่ยนเป็น **over-abstention** ซึ่งเป็นผลข้างเคียงของกลไกที่เพิ่มมาเพื่อแก้ v1

---

## 8. Gold Label Audit Findings (Task 4)

> **หลักการ:** ไม่แก้ label หรือไฟล์ Gold และไม่ให้คะแนนใหม่ การ audit นี้ทำโดยผู้วิเคราะห์คนเดียว (AI) จึง**ไม่ใช่** adjudication อิสระโดยมนุษย์ ใช้เป็นข้อสังเกตประกอบเท่านั้น

### 8.1 ผลการจัดประเภท 25 ข้อ [S]

| หมวด | Regression (15) | Correction (10) | รวม |
|---|---|---|---:|
| Gold Supported by Evidence | MSFT-12, AMZN-09, GOOGL-13, NVDA-03, NVDA-06, META-15, NFLX-09, WMT-11, KO-08, KO-13 | GOOGL-04, META-06, META-11, TSLA-04, WMT-13 | **15** |
| Gold Defensible but Ambiguous | AMZN-08, GOOGL-08, NVDA-07, WMT-08, WMT-15 | AAPL-13, MSFT-14, AMZN-06, AMZN-13, WMT-07 | **10** |
| Gold Potentially Incorrect | — | — | **0** |
| Unable to Verify | — | — | **0** |

- ตัวเลขและ quote ที่ Gold อ้างใน 25 ข้อ **ตรงกับเอกสาร SEC ที่ cache ไว้ทุกรายการที่ตรวจ** รวมถึงข้อที่ Gold evidence เป็นแบบ "PRIOR-CHECK / not verbatim" (GOOGL-08, WMT-08, AMZN-06) ซึ่งตรวจพบข้อความจริงใน filing แล้ว
- **ความกำกวมกระจายเท่ากันสองฝั่ง** (5 regression / 5 correction) ผู้ลงคะแนนเห็นตรงกัน 3/3 ใน 6/15 regression และ 5/10 correction จึง**ไม่มีหลักฐาน**ว่า Gold ทำให้ A3 เสียเปรียบอย่างเป็นระบบ ข้อนี้ไม่เปลี่ยนผลหลัก

### 8.2 ข้อที่กำกวม และ label ทางเลือกที่ป้องกันได้ใกล้เคียงกัน (Audit Findings)

ข้อเหล่านี้**ไม่ได้**ถูกจัดเป็น "Potentially Incorrect" เพราะไม่มีหลักฐาน SEC ที่ขัดกับ Gold โดยตรง แต่ label ทางเลือกป้องกันได้ในระดับใกล้เคียงกัน

| Claim | Gold | ทางเลือก | หลักฐานและเหตุผล |
|---|---|---|---|
| GOOGL-08 | S | I | filing ระบุสาเหตุเป็น "interrelated factors including increases in search queries…; growth in advertiser spending; improvements … in ad formats" ไม่ได้บอกว่า paid clicks เป็นสาเหตุหลัก Gold อนุมานจาก clicks +13% เทียบ CPC +3% (rationale ของ Gold เองระบุว่า "เป็นการอนุมาน… ไม่ใช่ revenue attribution ตรง") votes S / C / I |
| NVDA-07 | C | I | filing ระบุสองสาเหตุโดยไม่จัดลำดับ ตัวเลขให้ผลต่างกันตามวิธีแยก (ดูด้านล่าง) votes C / C / I |
| WMT-08 | C | I | ส่วน "business mix / advertising" มีหลักฐานบางส่วน ("growth in higher margin businesses globally" และ "higher margin areas, such as digital advertising") แต่ "membership income" ไม่อยู่ใน gross profit (filing: "Gross profit defined as net sales less cost of sales") ส่วนที่เป็นเท็จทำให้เป็น C หรือ I ได้ทั้งคู่ votes I / S / C |
| AMZN-13 | I | C | filing แสดง one-time items ใน operating income เป็น**ค่าใช้จ่าย** ("charges associated with damaged data centers…") และกำไรพิเศษอยู่ใน other income ซึ่งอาจขัดกับ "benefited … overstate" ได้ votes C / I / I |
| MSFT-14 | I | S | ผลกระทบ $207M = 0.57% ของ net income 36,629 ถ้าใช้เกณฑ์ materiality ทั่วไปอาจถือว่า "no material effect" แต่ filing ไม่ได้ให้เกณฑ์ votes C / I / I |

**ตัวเลข NVDA-07 [S]** (10-K 0001045810-26-000021):
- gross margin 75.0% → 71.1% (−3.9 pp)
- H20 charge $4.5B / revenue $215.9B ≈ 2.1 pp ≈ 53% ของการลด ถ้าแยกแบบ gross charge
- net provision impact 2.6% เทียบ 2.3% → เพิ่มขึ้นเพียง 0.3 pp ≈ 8% ถ้าแยกแบบ net YoY
- **Gold C ป้องกันได้ด้วยวิธีแบบ net YoY และลำดับข้อความใน filing แต่ claim ไม่ได้ระบุวิธีแยก**

ข้อสังเกตเพิ่มเติม (ไม่กระทบผล): AMZN-08 และ WMT-07 มี votes S / S / I (เสียงข้างมากในการโหวตตอน annotate ต่างจาก label สุดท้าย) ทั้งสองข้อ Gold I ป้องกันได้ตามข้อความ SEC

- AMZN-08: "infrastructure, including D&A" ไม่เจาะจงอุปกรณ์
- WMT-07: 10-Q ระบุ "store-fulfilled delivery" ไม่มี pickup

**ข้อเสนอ:** ให้ผู้ annotate ที่เป็นมนุษย์อิสระ adjudicate 5 ข้อในตารางข้างบน รายงานแยกเป็น sensitivity analysis และ**ไม่นำไปแทนผลหลัก**

---

## 9. A2 vs SR vs A3v2_2e (Task 6)

### 9.1 แยกตามประเภท claim [T]

ค่า accuracy ตรงกับ `evaluation.json` → `by_category` ส่วน correction / regression นับเทียบ A2

| ประเภท (Gold S/C/I) | Arm | Accuracy | Correction | Regression | สุทธิ | INSUFFICIENT recall | ทำนาย I (ถูก) |
|---|---|---:|---:|---:|---:|---:|---:|
| **Numerical** (37/8/5) | A2 | 47/50 (94%) | — | — | — | 5/5 | 6 (5) |
| | SR | 47/50 (94%) | 0 | 0 | 0 | 5/5 | 7 (5) |
| | A3v2_2e | 48/50 (96%) | 2 | 1 | **+1** | 5/5 | 6 (5) |
| **Interpretive** (22/12/16) | A2 | 30/50 (60%) | — | — | — | 1/16 | 2 (1) |
| | SR | **34/50 (68%)** | 11 | 7 | +4 | **9/16** | 13 (9) |
| | A3v2_2e | 25/50 (50%) | 3 | 8 | **−5** | 2/16 | 8 (2) |
| **Ambiguous** (9/18/23) | A2 | 26/50 (52%) | — | — | — | 15/23 | 29 (15) |
| | SR | 21/50 (42%) | 6 | 11 | −5 | 13/23 | 29 (13) |
| | A3v2_2e | 25/50 (50%) | 5 | 6 | **−1** | **19/23** | 38 (19) |
| **รวม** | A2 | 103 (68.7%) | — | — | — | 21/44 | 37 (21) |
| | SR | 102 (68.0%) | 17 | 18 | −1 | 27/44 | 49 (27) |
| | A3v2_2e | 98 (65.3%) | 10 | 15 | −5 | 26/44 | 52 (26) |

### 9.2 การตีความ

- **Interpretive คือกลุ่มที่ทำให้ A3v2_2e แพ้ A2 มากที่สุด** (สุทธิ −5 จากทั้งหมด −5)
  - regression 8 ข้อ: AMZN-08, AMZN-09, GOOGL-08, NVDA-06, NVDA-07, NFLX-09, WMT-08, KO-08
  - ประกอบด้วย reviewer ตีความเชิงสาเหตุผิด 4 ข้อ (AMZN-08, NVDA-07, NFLX-09, WMT-08), evidence verification ตัดหลักฐานที่ถูกต้อง 3 ข้อ และ ambiguous predicate 1 ข้อ
- **A3 abstain ผิดกลุ่ม:**
  - ใน interpretive ซึ่ง Gold มี I 16 ข้อ A3 จับได้เพียง 2 (SR จับได้ 9)
  - ใน ambiguous A3 ทำนาย I 38 ครั้ง แม้ recall สูง (19/23) แต่ precision เพียง 50% (19/38)
  - กลไกความระมัดระวังของ A3 ตอบสนองต่อ "คำประเมินค่า" (decidability) และ "การไม่มี finding ที่ valid" (E1) ไม่ได้ตอบสนองต่อ "claim ที่ข้อมูลไม่พอจริง" ซึ่งพบมากใน interpretive
- **SR (P2) ชนะใน interpretive** เพราะการวิจารณ์ตัวเองทำให้ถอยไปเป็น I ได้ถูกจังหวะ (recall 9/16) แต่เสียใน ambiguous (−5) จึงเสมอกับ A2 โดยรวม
- **Numerical ไม่ใช่ปัญหา:** ทุก arm ทำได้ 94–96% และ A3 ดีกว่า A2 เล็กน้อย (+1) จาก N1 ที่ตรวจ scope ของ metric
- สรุป: ข้อได้เปรียบของ A3 อยู่ที่ตัวเลข ซึ่ง A2 แข็งแรงอยู่แล้ว ส่วนจุดอ่อนอยู่ที่การอธิบายเชิงสาเหตุ ซึ่งเป็นจุดที่งานวิจัยคาดหวังให้ A3 ช่วยมากที่สุด

---

## 10. Why Dev Gains Did Not Generalize to Gold

| | dev-v0.2 (72 ข้อ, label v2) | Gold 150 |
|---|---|---|
| A2 | 53 (73.6%) | 103 (68.7%) |
| A3v2_2e | 64 (88.9%) | 98 (65.3%) |
| ผลต่าง | **+11** (correction 14 / regression 3) | **−5** (correction 10 / regression 15) |
| สัดส่วน label I | 27/72 = **37.5%** | 44/150 = **29.3%** |
| สัดส่วน ambiguous | 30/72 = 41.7% | 50/150 = 33.3% |
| correction ที่เปลี่ยนเป็น I | 7/14 (C→I 4, S→I 3) | 6/10 |
| บริษัท | 3 บริษัทซ้ำกับ Gold | 7 บริษัทไม่เคยเห็นตอนออกแบบ |

**สิ่งที่ยืนยันได้ [T]:**
1. **กฎทุกข้อของ v2.2e ออกแบบบน dev-v0.2** และ D-sup ถูกเลือก**หลังเห็นผล replay บน dev** (prereg ข้อ 2)
2. **ครึ่งหนึ่งของผลบวกบน dev มาจากการถอยไปเป็น I:** dev มีสัดส่วน I สูงกว่า Gold (37.5% เทียบ 29.3%) กลไกที่ถอยไปเป็น I จึงได้คะแนนบน dev มากกว่า
3. **บน Gold กลไกเดียวกันทำงานโดยไม่สนว่า A2 ถูกหรือผิด:**
   - E1 เปลี่ยน label 11 ครั้ง ถูก 6 ผิด 5
   - D-sup เปลี่ยน label 6 ครั้ง ช่วย 1 (AAPL-12) ทำผิด 4 (GOOGL-13, META-15, WMT-15 และ KO-14 ที่เสีย correction) เป็นกลาง 1 (TSLA-14)
   - ผลบวกบน dev จึงเป็นผลของ **base rate ของ I ที่สูงบน dev** มากกว่าความสามารถในการแยกแยะ

**สมมติฐานที่ยังไม่ได้พิสูจน์ [H]:**
- **H1 (adaptive overfitting):** dev ถูกใช้ทั้ง debug, replay และเลือก rule หลายรอบ (v2.1 → v2.1.1 → v2.2 → E1) และ label dev มีการปรับเป็น v2 ระหว่างทาง ความได้เปรียบ +11 บน 72 ข้อจึงสะท้อนการปรับกับชุดนั้นด้วย ต้องทดสอบด้วย dev ชุดใหม่ที่ไม่ได้แตะ
- **H2 (รูปแบบเอกสาร):** period resolver และ quote check อาจเข้ากับรูปแบบ filing ของ AAPL / MSFT / AMZN บน dev ได้ดีกว่าของ NVDA / WMT / KO / META บน Gold
  - สอดคล้องกับที่ false negative ใน regression มาจาก NVDA, AMZN และ KO แต่ยังไม่ได้วัดอัตราแยกตามบริษัท
- **H3 (สัดส่วนประเภท claim):** dev มี interpretive 22/72 (31%) ใกล้ Gold (33%) แต่ ambiguous มากกว่า ส่วนที่ D-sup ช่วยบน dev อาจเป็น ambiguous ที่ label I ซึ่งบน Gold มีน้อยกว่า
- **H4 (ขนาดตัวอย่าง):** n = 72 ทำให้ผลต่าง +11 มีความไม่แน่นอนสูง ในเอกสาร dev ไม่มีการรายงาน CI ของผลต่างนี้

prereg ข้อ 6 กำหนดไว้ล่วงหน้าแล้วว่า "ไม่ผ่าน AC1: รายงานตามตรงว่า v2.2e ไม่ชนะ A2 บน Gold และผลบน dev สูงเกินจริงเพราะออกแบบบนชุดนั้น" การวิเคราะห์นี้สนับสนุนการตีความนั้นด้วยกลไกที่ตรวจพบใน trace

---

## 11. Implications for Agentic AI Design

1. **การยอมรับคำตอบต้องตรวจความหมาย ไม่ใช่แค่รูปแบบ**
   - Guard ที่ตรวจ quote, งวด และการอ้างอิงยอมรับข้อเสนอเสียได้มากกว่าข้อเสนอดี (54% เทียบ 40%)
   - ความผิดที่สำคัญคือ scope, ศัพท์ และเหตุผลเชิงสาเหตุ ซึ่งต้องใช้ verifier ระดับ assertion ที่ตรวจว่า "หลักฐานครอบคลุมทุกส่วนของ claim"
2. **Deciding evidence ต้องผูกกับ assertion หลัก:** finding ของ sub-assertion (เช่น "margin ลดลง") ต้องไม่นับเป็นหลักฐานของ claim เชิงสาเหตุ (NVDA-07)
3. **ชั้นตรวจหลักฐานแบบ deterministic มีต้นทุน false negative สูง**
   - period resolver ควรใช้ marker ระดับ quote ไม่ใช่ระดับ passage
   - quote check ต้องรองรับตาราง
   - กฎ intent ต้องรู้ว่าเมื่อใด claim เป็นเรื่องความเสี่ยงเอง
   - เมื่อชั้นนี้เป็น input ของ gate ที่ลด label (E1) false negative จะกลายเป็น regression ทันที
4. **Gate ความระมัดระวังที่ไม่ขึ้นกับความมั่นใจ = การเดาแบบมี base rate:** E1 และ D-sup ลดคำตอบเด็ดขาดโดยไม่สนว่าคำตอบเดิมถูกหรือผิด จะได้ผลบวกเฉพาะเมื่อ base rate ของ I สูง gate ที่ดีควรใช้กับ "ข้อที่ระบบไม่มั่นใจ" ไม่ใช่กับ "ข้อที่ระบบหา finding ที่ผ่านการตรวจไม่ได้"
5. **Reviewer ต้องรองรับหลักฐานที่ต้องคำนวณจากหลายแหล่ง:** MSFT-12, NFLX-09 และ GOOGL-04 ต้องใช้หลักฐานสองชิ้นขึ้นไปร่วมกัน แต่ schema ของ finding ผูกความตัดสินไว้กับหลักฐานทีละชิ้น
6. **คุณค่าที่เห็นจริงของ agentic approach:**
   - counter-numeric challenge (WMT-13)
   - การตรวจ scope ของ metric (TSLA-04)
   - counter-retrieval ที่พบข้อมูลใหม่ (GOOGL-04, META-06)
   - การกันข้อเสนอผิด (MSFT-14 และอีก 5 ข้อ)
   - ทั้งหมดนี้ทำงานได้ดีที่สุดกับ**ตัวเลข** และแย่ที่สุดกับ**การอธิบายเชิงสาเหตุ**
7. **ต้นทุน:** A3 ใช้ทรัพยากรราว 7 เท่าของ A2 และ 2 เท่าของ SR โดยไม่ได้ความแม่นเพิ่ม การออกแบบ agentic ควรเรียกขั้นตรวจเพิ่มแบบเลือกได้ (เช่นเฉพาะ claim ที่ A2 ไม่มั่นใจ) มากกว่ารันทุกข้อ

---

## 12. Threats to Validity

- **Internal**
  - การจัดสาเหตุทำโดยผู้วิเคราะห์คนเดียว (AI) จาก trace ยังไม่มีผู้ตรวจที่สองหรือ inter-rater agreement
  - การแบ่ง primary / contributing มีวิจารณญาณเข้ามาเกี่ยว
  - การแยกตามกลไกไม่ใช่ counterfactual
- **Gold**
  - Gold มาจาก `llm_annotated_ai_adjudicated_researcher_reviewed` และยังไม่มี IAA กับมนุษย์ (prereg ข้อ 2)
  - Gold audit ในเอกสารนี้ทำโดย AI จึงไม่ใช่ adjudication อิสระ
- **Construct**
  - strict label match ไม่ได้วัดคุณภาพของหลักฐาน: prediction ที่ถูกอาจมาจากเหตุผลผิด (4/10 correction) และ prediction ของ A2 ที่ถูกบางข้อก็มาจากหลักฐานข้างเคียง (KO-08, NVDA-03)
  - ผลนี้ไม่ได้ให้คะแนนใหม่ แต่ควรระบุว่า accuracy ไม่เท่ากับ evidence-grounded correctness
- **Statistical**
  - n = 150 มี power ตรวจผลต่างได้ราว 9 pp (prereg) ตัวเลขแยกตามประเภท (n = 50) และแยกตามกลไกเป็นการพรรณนาเท่านั้น
  - ไม่มีการทดสอบใหม่และไม่ควรอ่านเป็นหลักฐานเชิงอนุมาน
- **Gold exposure**
  - A3 v2 รุ่นแรกออกแบบจาก error analysis ของ v1 บน Gold 23 ข้อ (prereg ข้อ 2)
  - การวิเคราะห์นี้เป็นการแตะ Gold ครั้งที่สอง ผลจากเอกสารนี้**ห้ามใช้ปรับ A3 แล้วประเมินซ้ำบน Gold ชุดเดิม**
- **Corpus**
  - เอกสาร SEC ที่ใช้ตรวจเป็นชุดที่ดาวน์โหลดใหม่หลังเหตุการณ์ 2026-11-18
  - เนื้อหายืนยันด้วย cache replay แต่ hash ดิบไม่ตรง manifest (`10_gold150_run_log.md`)

---

## 13. Recommendations for Future Work

> **สถานะ (2026-11-18):** ผู้วิจัยยุติการพัฒนาและการทดลองเพิ่มเติมเพื่อปิดงาน IS ข้อเสนอในหัวข้อนี้ รวมถึง A4 (`results/dev_v0_2/a4_feasibility/`) และแผนใน `14_next_generation_research_plan.md` เป็น **future work เท่านั้น** และไม่ได้ดำเนินการ

ทุกข้อต้องทดสอบบน**ชุดข้อมูลใหม่ที่ไม่ได้แตะ** ไม่ใช่ Gold 150 ชุดนี้

1. **Assertion-level guard:** บังคับว่า deciding finding ต้องอยู่บน A0 และต้องครอบคลุมทุก component ของ claim (เช่น "advertising **and** membership income")
2. **Quote-level period resolution** และ quote check ที่รองรับตาราง พร้อมวัด false negative rate ของชั้นตรวจหลักฐานด้วยชุดที่มนุษย์ label
3. **ทบทวน E1 / D-sup ให้ขึ้นกับความไม่แน่นอน**
   - เช่น ลด label เฉพาะเมื่อ A2 กับ reviewer ไม่สอดคล้องกัน หรือเมื่อ predicate ไม่มีเกณฑ์**และ**ไม่มี finding ที่ valid
   - ไม่ใช่ลดทุกข้อที่เป็น EVALUATIVE
4. **Multi-evidence findings:** ให้ reviewer สร้าง finding ที่ตัดสินจากการคำนวณหลายตัวเลขได้ (FCF, สัดส่วนต่อการเปลี่ยนแปลง) โดยมี deterministic calculator ตรวจ
5. **ขยาย N2** ให้ครอบคลุม claim เรื่อง FCF แบบปฏิเสธ ("no pressure on FCF")
6. **Baseline คำถามแบบ fixed** เทียบกับคำถามที่ระบบสร้างเอง (prereg ข้อ 9) และ **selective invocation** (เรียก A3 เฉพาะข้อที่ A2 ไม่มั่นใจ)
7. **Human adjudication ของ 5 Gold items ในหัวข้อ 8.2** รายงานเป็น sensitivity analysis แยกจากผลหลัก
8. **Dev set ชุดใหม่ที่ไม่ได้แตะ** และกระจายบริษัทหรือรูปแบบเอกสารเหมือน Gold เพื่อตรวจ H1–H4 ในหัวข้อ 10

---

## 14. Conclusion

**ผลหลัก:**
- A3v2_2e ไม่ชนะ A2 (−3.3 pp, p = 0.424) และไม่ชนะ SR (P2) (−2.7 pp, p = 0.585) บน Gold 150
- ผลนี้ freeze แล้วและรายงานเป็น negative result

**การวิเคราะห์ trace ของ 25 ข้อที่ต่างจาก A2 แสดงว่า:**
- A3 เริ่มจากคำตอบของ A2 ทุกข้อ ความต่างทั้งหมดจึงมาจากชั้นที่เพิ่มเข้ามา
- ทั้ง reviewer และ guard ทำให้ผลสุทธิติดลบ (−3) เพราะ guard ตรวจความหมายไม่ได้
- gate ความระมัดระวังที่ออกแบบบน dev (D-sup −3, E1 +1) ลดคำตอบโดยไม่สนว่าถูกหรือผิด
- ชั้นตรวจหลักฐานแบบ deterministic ตัดหลักฐานที่ถูกต้องทิ้ง ซึ่งเป็นต้นเหตุหลักของ regression 5 ข้อ
- over-interpretation ของ v1 ลดลงจริง แต่ถูกแทนที่ด้วย over-abstention

**ความน่าเชื่อถือของ Gold:** Gold label ส่วนใหญ่ได้รับการรองรับจากหลักฐาน SEC ความกำกวมที่พบกระจายเท่ากันทั้งสองฝั่ง จึงไม่เปลี่ยนข้อสรุป

**คุณค่าของแนวทาง agentic:** การตรวจตัวเลขแบบท้าทาย การตรวจ scope ของ metric และการค้นหลักฐานเพิ่ม มีคุณค่าจริงในบางกรณี

**ข้อจำกัดของแนวทาง agentic:**
- การตัดสินเชิงความหมายใน claim เชิงสาเหตุ / อธิบาย
- การผูกหลักฐานกับ assertion
- ต้นทุน false negative ของ rule แบบ deterministic
- ต้นทุนที่สูงกว่า A2 ราว 7 เท่า

---

## ภาคผนวก: แหล่งข้อมูลที่ใช้

- **Predictions:** `results/runs/a3v2.2-gold150-20261118T112814Z/predictions.jsonl`
- **Traces:** `…/traces/A2_rag_numeric/*.json`, `…/traces/A3v2_2e/*.json`, `…/traces/SR_self_reflection/*.json`
- **A3 v1 predictions:** `results/runs/claimverif-main-v1-20261110T104207Z/predictions.jsonl`
- **Dev:** `results/runs/a3v2.2-dev-v0.2-20261118T052512Z/predictions.jsonl` + `datasets/annotations_dev/dev-v0.2_reference_labels.v2.approved.jsonl`
- **Gold labels:** `engine.reference.load_reference()` (workbook `Final_Gold_v3_approved.xlsx`)
- **เอกสาร SEC:** `backend/app/data/cache/doc_<accession>_*.htm` (ตรวจด้วยการค้นข้อความหลังแปลง HTML เป็นข้อความ)
- **นิยามจากโค้ด:** `scripts/a3v2_gold_evaluate.py` (accepted change precision), `a3v2/graph.py:reconciliation_guard` (ลำดับ gate), `a3v2/guard.py` (กฎ guard 0.3)
- **การคำนวณ:** อ่านอย่างเดียวด้วย Python จากไฟล์ข้างต้น ไม่มี LLM call และไม่เขียนไฟล์ใน `results/`
