# A3 v2.2: schema และ design specification (ร่าง 2026-11-18)

- **ที่มา:** การตัดสินใจของผู้วิจัยวันที่ 18 พ.ย. 2026 ให้ใช้ Approach A (Decidability-first) + G3 + G6 เป็นตัวหลัก และใช้ Approach C เป็น baseline
- **ขอบเขตของเอกสารนี้:** offline เท่านั้น ไม่มี prompt ใหม่ ไม่มีการเรียก LLM ไม่แก้ v2.0 / v2.1 / v2.1.1
- **ตรวจแล้ว:** config hash เดิมไม่เปลี่ยน (`A3v2_1_1_R b2736e77`, `A3v2_1_1_RG b1ec2fe9`) และมี test ยืนยัน

## 1. ส่วนที่ implement แล้ว (offline)

| ส่วน | ไฟล์ | สถานะ |
|---|---|---|
| Guard 0.2 (กฎ G3, G6) | `a3v2/guard.py`, `a3v2/__init__.py` (`GUARD_VERSION_V02`) | ✅ เปิดใช้ด้วย `guard.version: "0.2"` ถ้าไม่ระบุจะได้ 0.1 เหมือนเดิม |
| สวิตช์เวอร์ชัน guard ใน config | `a3v2/config.py` | ✅ ใช้ได้แค่ "0.1" หรือ "0.2"; arm แบบ replay ต่าง guard version จาก arm ต้นทางได้ |
| ส่ง version เข้า graph | `a3v2/graph.py` | ✅ |
| Decidability schema + gate (G1/G2/G4/G5) | `a3v2/decidability.py` | ✅ เป็น schema และฟังก์ชันล้วน **ยังไม่ต่อเข้า graph** เพราะต้องมีขั้น LLM ที่เสียเงินก่อน |
| Offline replay | `scripts/a3v2_guard_replay.py` | ✅ ตรวจได้ว่า guard 0.1 replay ตรงกับที่บันทึกไว้ 72/72 |
| Metrics report 1.1 | `scripts/a3v2_dev_evaluate.py` | ✅ แยก `rg_minus_r` กับ `rg_minus_a2`, เพิ่ม `accepted_change_precision`, `net_helpful` เปลี่ยนชื่อเป็น `_legacy`, output dir มี `_r1.1` ต่อท้าย (ไม่ทับผลเดิม) |
| Tests | `tests/test_a3v2_2_prep.py` (7 test) | ✅ ทั้งชุดผ่าน 289 ข้อ |

**แก้ bug ของเครื่องมือด้วย:** `required_second()` ใน `dev_v0_2_human_workflow.py` เดิมคำนวณจากสถานะ label ปัจจุบัน หลังมีการตัดสินแล้วจึงหดจาก 44 เหลือ 32 ตอนนี้กำหนดเป็นชุดคงที่ คือ ambiguous/interpretive ที่ไม่มี rev_reviewer2 การแก้นี้ไม่กระทบไฟล์ approved, `validate` หรือ κ ที่บันทึกไว้แล้ว

## 2. Guard 0.2

### G3: finding ที่ใช้ตัดสินต้อง self-contained

- **กฎ:** หลักฐานทุกตัวที่ `justification` อ้างถึง (รูป `E<n>`) ต้องอยู่ใน `evidence_ids` ของ finding นั้นเอง ถ้าไม่ใช่ finding นั้นใช้ตัดสินไม่ได้
- **ถ้าไม่เหลือ finding ที่ตัดสินได้เลย:** REJECT ด้วย `INVALID_DECIDING_EVIDENCE:UNCITED_REFERENCE`
- **บันทึกใน `rule_trace`:** `G3 not self-contained: R1 names E10`

### G6: ตรวจ conflict สองทาง

`CONFLICTING_DECIDING_EVIDENCE` เดิมตรวจเฉพาะการเปลี่ยนเป็น SUPPORTED (ถ้ามี CONTRADICTS ที่ VALID) ตอนนี้ตรวจการเปลี่ยนเป็น CONTRADICTED ด้วย (ถ้ามี ENTAILS ที่ VALID)

### สิ่งที่ไม่เปลี่ยน
การตรวจ citation, A2 numeric preservation, การเปลี่ยนเป็น INSUFFICIENT และ reason code อื่นทั้งหมด

## 3. Decidability schema (Approach A)

หนึ่ง record ต่อหนึ่ง assertion ฟิลด์ที่ขาดหรือค่าผิดจะกลายเป็น `UNKNOWN` และบันทึกเหตุไว้ใน `issues`

| ฟิลด์ | ค่า | ความหมาย |
|---|---|---|
| `predicate_type` | MEASURABLE / EVALUATIVE / CAUSAL / NEGATIVE / UNKNOWN | ชนิดของสิ่งที่ claim ยืนยัน |
| `criterion_source` | CLAIM_STATES / FILING_STATES / NONE / UNKNOWN | เกณฑ์ของคำประเมินมาจากไหน |
| `required_evidence[]` | `{kind, scope{entity, segment, region, metric}}` | หลักฐานแบบไหนที่ตัดสินได้ |
| `required_evidence.kind` | NUMERIC_FACT / CRITERION_DEFINITION / EXPLICIT_CAUSAL_STATEMENT / EXPLICIT_ABSENCE_STATEMENT / SCOPE_MATCHED_FACT | |
| `status` (คำนวณเอง ไม่ได้ถาม LLM) | DECIDABLE / NEEDS_CRITERION / UNKNOWN | |

### Gate

ใช้เฉพาะเมื่อมีการเปลี่ยนเป็น SUPPORTED หรือ CONTRADICTED

| กฎ | เงื่อนไขที่บล็อก | reason |
|---|---|---|
| G1 | EVALUATIVE และ `criterion_source = NONE` | `NO_CRITERION` |
| G2 | CAUSAL แต่ไม่มี finding ที่ตัดสินได้ซึ่งมี `support_mode = EXPLICIT` | `CAUSE_NOT_EXPLICIT` |
| G5 | NEGATIVE, จะเปลี่ยนเป็น CONTRADICTED แต่ไม่มี finding ที่ `polarity_match = true` | `POLARITY_MISMATCH` |
| G4 | มี scope (segment / region / metric) แต่ไม่มี key quote ไหนครอบคลุม | `SCOPE_NOT_COVERED` |

- **ถ้าเป็น `UNKNOWN`:** ไม่บล็อก (fail-open) และให้ guard ทำงานแบบ 0.2 พร้อมนับจำนวน UNKNOWN ในรายงาน
  - **เหตุผล:** ถ้าตัวจำแนกล้ม ระบบจะไม่กลายเป็น A2 แบบเงียบ ๆ
  - **ข้อเสีย:** เคสที่เป็น UNKNOWN ไม่ได้รับการป้องกัน
- **G4** ตรวจด้วยการจับคู่ข้อความแบบตรงตัว (ไม่สนตัวพิมพ์และช่องว่าง) **ยังไม่มีพจนานุกรมคำพ้อง** เช่น "China" กับ "Greater China" จึงอาจบล็อกเกิน ต้องทดสอบบนชุด held-out

### ต้องเพิ่มก่อนรันแบบเสียเงิน (ยังไม่ได้ทำ)

1. **Prompt ของขั้น decidability:** เรียก LLM 1 ครั้งต่อ claim, ผลลัพธ์ส่งเข้า guard เท่านั้น **ไม่ส่งเข้า reviewer prompt**
   - ทำให้ R ใช้ cache เดิมได้ ต้นทุนจึงเพิ่มแค่การเรียกนี้
   - ablation ก็แยกผลได้สะอาด
2. **ฟิลด์ `support_mode` และ `polarity_match` ใน reviewer:** ต้องแก้ reviewer prompt และรัน R ใหม่ทั้งหมด จึงแยกเป็น **ระยะ 2** ระหว่างที่ยังไม่มี finding ใดมีฟิลด์นี้:
   - G2 จะบล็อกทุก claim เชิงสาเหตุ
   - G5 จะบล็อกทุก negative claim ที่จะเปลี่ยนเป็น CONTRADICTED
   - ระยะ 1 จึงควรเปิดแค่ G1 + G4 + G3 + G6 (ดูแผน ablation)
3. **สวิตช์ใน config:** `decidability.name` (ตอนนี้เป็น `not_assessed`) เพิ่มค่าใหม่ เช่น `llm_v0.1` และต้องได้ config hash ใหม่

## 4. การตรวจว่าหลักฐานครอบคลุม predicate และ scope

| มิติ | วิธีตรวจ | ใช้ข้อมูลจาก |
|---|---|---|
| Predicate | เทียบ `required_evidence.kind` กับ `evidence_type` / `support_mode` ของ finding ที่ตัดสินได้ | decidability + reviewer |
| Scope | ข้อความ scope ต้องอยู่ใน key quote (G4) | decidability + key quote (กฎล้วน) |
| Polarity | `polarity_match` (G5) | reviewer ระยะ 2 |
| Self-containment | G3 | justification + evidence_ids (กฎล้วน) |
| งวดเวลา / ข้อความคาดการณ์ | periods 1.1 (มีอยู่แล้ว) | กฎล้วน |

## 5. Workstream แยก: bug ของ numeric parser (PG-12)

- **อาการ [ข้อเท็จจริง]:** claim "dividends and share repurchases together exceeded its operating cash flow" ถูกแปลงเป็น assertion `OperatingCashFlow level < None` (threshold = null)
  - **ฝั่ง A2:** ได้ `UNVERIFIABLE` → INSUFFICIENT ซึ่งปลอดภัย
  - **ฝั่ง reviewer ของ R:** ได้ข้อความ "level < None" ไปด้วย แล้วตัดสิน CONTRADICTED ด้วยเหตุผล "positive, not less than None" คือถูกโดยบังเอิญ
- **สาเหตุ [ข้อเท็จจริง]:** schema ของ `numeric_assertions` (`engine/numeric.py`) เทียบได้แค่ metric เดียวกับ threshold แบบค่าคงที่ จึงแสดงผลรวมของหลาย metric เทียบกับ metric อื่นไม่ได้
- **ข้อเสนอ:**
  1. ไม่ส่ง assertion ที่ threshold เป็น null และ comparison เป็น `<`/`>` ต่อให้ reviewer หรือติดป้าย `MALFORMED`
  2. ระยะยาว: เพิ่ม composite metric
- **ข้อจำกัดสำคัญ:** `engine/numeric.py` เป็นส่วนของ A2 และ v1 ถ้าแก้จะกระทบ hash ของ A2 / v1 ที่ freeze ไว้ **ต้องทำเป็นเวอร์ชันใหม่แยกและขออนุมัติก่อน** ห้ามรวมกับงาน v2.2
