# Decidability debug run บน dev-v0.2 (2026-11-18)

> **IN-SAMPLE DIAGNOSTIC:** ต้องยืนยันบนชุด held-out ห้ามนำผลนี้ไปอ้างเป็นผลยืนยัน

## การรัน (เสียเงิน ได้รับอนุมัติแล้ว)

- **การอนุมัติ:** ผู้วิจัยพิมพ์ "อนุมัติ" ในแชตหลังจากเห็นข้อเสนอ "debug run ≤ $1.50"
- **ขอบบนของแผน:** $1.01 สำหรับ 72 call
- **ผลจริง:**
  - live call 72 ครั้ง, retry 0, error 0, ทุกข้อได้ผลจาก tool
  - **จ่ายจริง $0.587**
  - ledger `a3v2-dev-v0.2` เหลือ $1.79 (cap $15 ไม่ได้เปลี่ยน)
- **Prompt:** `a3v2-decidability-prompt-0.1` (`a3v2/decidability.py`)
  - model เห็นแค่ข้อความ claim, บริษัท และงวด **ไม่เห็น filing, label, หมวดของ claim หรือผลของระบบ** มี test ยืนยันว่า `claim_category` และ `notes` ไม่ถูกส่งไป
- **Output:** `results/dev_v0_2/decidability/a3v2-decidability-prompt-0.1.jsonl`
- **ผลของ replay:** `results/dev_v0_2/offline_ablation/7dccc43a_r1.2/` (label v2)

## ผลการจำแนก

| predicate_type | จำนวน |
|---|---|
| MEASURABLE | 26 |
| CAUSAL | 22 |
| EVALUATIVE | 15 |
| NEGATIVE | 9 |

- **contribution:** PRIMARY_DRIVER 13, LARGEST_FACTOR 1
- **⚠️ สอดคล้องกับหมวดของ dataset แทบทั้งหมด:**
  - numerical → MEASURABLE 20/20
  - interpretive → CAUSAL 20/22
  - ambiguous → EVALUATIVE/NEGATIVE 24/30
  - claim 48 ข้อร่างโดย AI ตาม pattern ที่ระบุชัด จึงอาจจำแนกง่ายกว่า claim ที่คนเขียน **นี่เป็นเหตุผลหลักที่ต้องทดสอบบนชุด held-out ที่คนเขียน**

## กฎที่ใช้ (ระยะ 1: ไม่แก้ reviewer)

| กฎ | การทำงาน |
|---|---|
| G1 | ถ้า R จะเปลี่ยนคำตอบของ A2 เป็นคำตอบเด็ดขาด กับ claim แบบ EVALUATIVE ที่ไม่มีเกณฑ์ และ quote ที่ใช้ตัดสินไม่มีคำประเมินนั้น → คงคำตอบของ A2 |
| G4 | ถ้า claim จำกัด segment หรือ region แต่ quote ที่ใช้ตัดสินไม่มีชื่อนั้น → คงคำตอบของ A2 |
| D | คำตอบเด็ดขาดของ claim แบบ EVALUATIVE ที่ไม่มีเกณฑ์ → INSUFFICIENT (ทำงานกับคำตอบของ A2 ด้วย) |
| D-sup (post hoc) | เหมือน D แต่ลดเฉพาะ SUPPORTED เพื่อให้ตรงกับ guideline ที่บอกว่าถ้าส่วนข้อเท็จจริงถูกหักล้างให้ตอบ CONTRADICTED ใช้หลังจากเห็นว่า D ทำ ADBE-04 และ CAT-05 พัง |

## ผล (label v2, 72 ข้อ)

| Arm | ถูก | Acc | Δ A2 | McNemar p เทียบ A2 | INSUFF recall | ความแม่นตอนยอมรับให้เปลี่ยน |
|---|---|---|---|---|---|---|
| A2 | 53 | 73.6% | — | — | 19/27 | — |
| RG v2.1.1 | 51 | 70.8% | −2 | 0.77 | 13/27 | 4/11 |
| RG-0.3 + Q1.1 | 53 | 73.6% | 0 | — | 14/27 | 5/11 |
| + G1 | 56 | 77.8% | +3 | — | 17/27 | 5/8 |
| + G1 + G4 | 57 | 79.2% | +4 | 0.29 | 18/27 | 5/7 |
| + G1 + G4 + D | 59 | 81.9% | +6 | 0.18 | 22/27 | 5/7 |
| + G1 + G4 + D-sup (post hoc) | 60 | 83.3% | +7 | 0.065 | 21/27 | 5/7 |

- **เทียบ A2 ใน arm G1 + G4 + D-sup:** แก้ข้อที่ A2 ผิดได้ 9 ข้อ ทำข้อที่ A2 ถูกให้ผิด 2 ข้อ (AAPL-07, PG-05) ทั้งสองข้อต้องใช้ G5 / G2 ซึ่งอยู่ในระยะ 2
- **ยังผิด:**
  - AAPL-04, PG-06 → ต้องใช้ตัวคำนวณสัดส่วน
  - ADBE-10, INTC-12 → bug ของ numeric check ใน A2
  - AMZN-07 → ต้องคำนวณ FCF ครึ่งปี
  - PG-12 → bug ของ parser
  - AAPL-05, INTC-08, INTC-09, PG-05, AAPL-07 → ตีความได้หลายทาง หรือต้องใช้ G2/G5

## ข้อจำกัด

1. **In-sample:** กฎทุกข้อออกแบบหลังจากดู error ของชุดนี้ D-sup ยิ่งเป็น post hoc ชัดเจน
2. **ไม่มีผลต่างไหนมีนัยสำคัญที่ α 0.05 เมื่อเทียบ A2** (p ≥ 0.065)
3. **สอดคล้องกับหมวดของ dataset มากเกินไป:** ดูหัวข้อผลการจำแนก
4. **ยังไม่ได้ต่อเข้า pipeline:** G1 / G4 / D และ quote check 1.1 ตอนนี้อยู่ใน replay ต้องทำเป็น config v2.2 ใหม่ก่อนรันบน held-out
5. **ใช้ต้นทุนเพิ่มต่อ claim:** ประมาณ $0.008

## ข้อเสนอสำหรับ preregistration
- **Arm หลัก:** RG-0.3 + Q1.1 + G1 + G4 + D-sup
- **Arm รอง:** + D เต็ม และ G1 อย่างเดียว
- ลงทะเบียน**ก่อน**ติด label ของชุด held-out

## Addendum (2026-11-18): items ก and ง — A3-side numeric checks N1 / N2 (no LLM, $0)

- **N1** (`a3v2/numeric_checks.py`): A3 does not inherit A2's decisive numeric rule when
  - the claim's period ends after the evidence cutoff (FUTURE_PERIOD);
  - A2 computed a different period (PERIOD_MISMATCH);
  - the claim is segment- or region-scoped while A2's metrics are consolidated totals (SCOPE_MISMATCH).

  The label then comes from the reviewer's valid deciding findings when they all point one way; otherwise it is
  INSUFFICIENT.
- **N2:** free cash flow over the claim's exact window (operating cash flow minus capex; a filed fact, or the sum of
  filed quarters) is compared with the same window a year earlier. A refuted conjunct makes the claim CONTRADICTED.
- **Dev replay** (`offline_ablation/7dccc43a_r1.3`): 60 → **63/72** (87.5%).

  | Claim | Change | Rule |
  |---|---|---|
  | ADBE-10 | → INSUF | FUTURE_PERIOD |
  | INTC-12 | → SUPPO | SCOPE_MISMATCH |
  | AMZN-07 | → CONTR | H1 FCF −$27.0B vs −$7.7B |

  - All three are correct against gold, and no claim got worse.
  - Against A2: 12 claims fixed, 2 broken; McNemar p = 0.013 (in-sample).
- **Pipeline check:** `a3v2.2-dev-v0.2-20261118T050135Z` (cache-only, $0) reproduces the replay on 72/72 claims.
- **Limits:**
  - Designed on dev-v0.2 after seeing these three errors.
  - SCOPE_MISMATCH relies on the classifier's scope field.
  - N2 reads only the words right after "free cash flow".
