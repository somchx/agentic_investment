# 14. Next-Generation Research Plan: ReasonCheck Claim Verification

> **สถานะ: NOT PURSUED — FUTURE WORK ONLY (2026-11-18)**
> ผู้วิจัยยุติการพัฒนาและการทดลองเพิ่มเติมเพื่อปิดงาน IS แผนนี้ (SAV, dataset ชุดใหม่, Blind Test) **ไม่ได้ดำเนินการ** และเก็บไว้เป็นข้อเสนอสำหรับงานในอนาคตเท่านั้น งบในหัวข้อ 8 เป็นฉบับก่อนลดงบ (ฉบับประหยัด ≈ $45–60 อยู่ในบันทึกการสนทนา ไม่ได้แก้ในเอกสารนี้)
>
> **สถานะเดิม: PROPOSAL FOR REVIEW (ยังไม่ implement)**
> - วันที่: 2026-11-18, working directory `~/Desktop/Invesment-a3v2`, HEAD `4082206`
> - งานรอบนี้: อ่านโค้ด, predictions, traces, dev results และ frozen evaluation **แบบ offline เท่านั้น**
> - Paid API = 0, ไม่ได้รัน Gold ใหม่, ไม่ได้สร้าง dataset, ไม่ได้แก้ frozen code / Gold / prereg / evaluation / A4
> - ตัวเลขที่อ้างมีป้ายกำกับ: **[V]** ผมคำนวณซ้ำจาก trace/predictions ในรอบนี้, **[13]** มาจาก `13_gold150_posthoc_error_analysis.md` (post-hoc, ผู้วิเคราะห์ AI คนเดียว, ไฟล์ยังไม่ได้ commit), **[A4]** มาจาก `results/dev_v0_2/a4_feasibility/`, **[C]** อ่านจากโค้ด, **[H]** สมมติฐาน
> - Gold 150 ถูกเปิดดูรายข้อแล้ว จึงถือเป็น **exposed data**: ใช้ debug ได้ แต่ห้ามใช้เลือกโมเดลหรือรายงานเป็นผลยืนยัน

---

## 1. Root Causes ที่ยืนยันได้

### 1.0 ภาพรวม: ความผิดพลาดอยู่ที่ไหน
- **Retrieval ไม่ใช่คอขวดหลัก** [13]: ไม่มี regression ใดของ A3v2_2e ที่ต้นเหตุหลักเป็น retrieval (เป็นปัจจัยร่วม 1 ข้อ) และบน dev-v0.2 ข้อที่ 2e ยังผิด 8 ข้อไม่มีข้อใดเป็น retrieval failure (readiness audit)
- **A2 ผิด 47/150 ข้อ และ 38 ใน 47 เป็น claim ที่ A2 ตัดสินด้วย LLM ล้วน** (rule `NOT_APPLICABLE`) [V]
  - claim ที่ตรวจตัวเลขได้ครบ (`NUMERIC_ALL_TRUE`) ถูก 32/32
  - claim เชิงคุณภาพ (`NOT_APPLICABLE`) ถูกเพียง 48/86 = 56%
- **ความกำกวมของ label เป็นเพดานที่ใหญ่:** A2 ถูก 84/100 ในข้อที่ LLM annotator 3 ตัวเห็นตรงกัน แต่ถูกเพียง 19/50 (38%) ในข้อที่เห็นไม่ตรงกัน; **31 ใน 47 ข้อที่ A2 ผิดเป็นข้อที่ annotator เห็นไม่ตรงกัน** [V]
- **ความมั่นใจของ LLM ใช้แยกข้อผิดไม่ได้:** A2 ตอบ `high` 144/150 ข้อ (ถูก 100) [V]
- **Arm ต่างๆ ผิดคนละข้อ:** ถ้าเลือก arm ที่ถูกได้ทุกข้อ (oracle) จะได้ 131/150; ทุก arm ผิดพร้อมกันเพียง 19 ข้อ [V] → มีพื้นที่ให้ "เลือกเมื่อไหร่ควรเชื่อใคร" แต่ยังไม่มีสัญญาณที่ดีพอ

**Confusion ของ A2 บน Gold (gold → pred)** [V]

| | pred S | pred C | pred I |
|---|---:|---:|---:|
| gold S (68) | 56 | 7 | 5 |
| gold C (38) | 1 | 26 | **11** |
| gold I (44) | **12** | **11** | 21 |

ความผิดของ A2 มีสองทิศทางตรงข้ามกัน: **ตอบเด็ดขาดเกินหลักฐาน (I → S/C 23 ข้อ)** และ **พลาดข้อที่ถูกแย้ง (C → I 11 ข้อ)** กลไกที่แก้ทิศหนึ่งแบบไม่เลือกข้อจะทำอีกทิศแย่ลง ซึ่งตรงกับที่เกิดกับ A3 v1 (over-interpretation) และ A3v2_2e (over-abstention) [13]

### 1.1 Numeric Verification (Metric / Period / Scope / Unit / Formula)

| ปัญหา | หลักฐาน | ประเภท |
|---|---|---|
| **Metric ครอบคลุมแคบ:** คำนวณได้ 11 metric (Revenue, OI, NI, GP, OCF, CapEx, LTD, Cash, 3 margins) และ 2 measure (`level`, `yoy_growth`) | `engine/numeric.py:36-55` [C] | Verification |
| **ไม่มี segment / product / geography:** XBRL companyfacts ไม่มี dimension; ข้อมูล segment มีอยู่ใน inline XBRL ของไฟล์ 10-K/10-Q ที่ cache ไว้แล้ว (เช่น INTC 10-Q มี `StatementBusinessSegmentsAxis` 32 contexts) แต่ `clean_filing_html` ลบ `<ix:header>` ทิ้ง | `engine/corpus.py:122`, ไฟล์ cache [C][V] | Verification |
| **ไม่มีสูตรหลายตัวแปร:** ผลรวม (OCF เทียบ dividends + buybacks: PG-12), share-of-change ("primarily driven"), สัดส่วนข้ามงวด, qoq | readiness audit dev, [13] MSFT-12 | Verification |
| **Scope ถูกตัดสินโดย LLM ตอนสกัด assertion:** A2 ใช้ revenue รวมแทน segment (INTC-12 dev, TSLA-04 Gold) และสกัด metric ผิด (NVDA-03) | dev audit, [13] | Verification |
| `NUMERIC_FALSE` ถูกเพียง 10/14 ข้อ (false contradiction จาก scope/metric) | [V] | Verification |
| Unit check มีเฉพาะ ratio กับ USD; ไม่มีการตรวจ per-share, basis points, หรือ GAAP/non-GAAP | `numeric.py:73-74` [C] | Verification |

### 1.2 Evidence Verification (Period Resolver / Quote Check / Table / Coverage)

| ปัญหา | หลักฐาน | ประเภท |
|---|---|---|
| **ตารางถูกแบนเป็นข้อความบรรทัดเดียว:** `<tr>` กลายเป็นช่องว่าง หัวคอลัมน์ (งวด) แยกจากตัวเลข และ chunk 1,200 ตัวอักษรตัดกลางตาราง | `corpus.py:123-134`, `RetrievalConfig` [C] | Evidence representation |
| **Quote check ปัดตกหลักฐานจากตาราง:** finding ที่ reviewer ประกาศว่าตัดสินได้ถูก downgrade 109/439 (25%) โดย 85 รายการเป็น `KEY_QUOTE_NOT_IN_EVIDENCE` และ **80/85 เป็น quote ที่มีตัวเลข ≥ 3 ตัว** (ลักษณะแถวตาราง) | [V] | Verification (false negative) |
| **Period ของ passage มาจากระดับเอกสาร ไม่ใช่ระดับข้อความ:** งวดได้จาก `period_end` ของ filing + regex คำว่า quarter/three months ใน quote หรือ passage; ข้อความ "in 2025, compared to the prior year" ใน 10-K ถูกตีเป็น 3 เดือน (AMZN-09) | `a3v2/periods.py:385-429` [C], [13] | Verification (false negative) |
| แหล่งงวดของหลักฐาน passage บน Gold: quote marker 171, **passage marker 46**, filing default 10-K 26, filing report date 23 | [V] | — |
| **E1 coverage ใช้ผลของชั้นตรวจหลักฐานเป็น gate ลด label:** false negative ของชั้นนี้กลายเป็น regression ทันที (5 regression) | [13] | Decision policy |
| **Finding ผูกกับหลักฐานทีละชิ้น:** ความจริงที่ต้องคำนวณจากหลายชิ้น (MSFT-12, NFLX-09, GOOGL-04) ไม่มีที่ลง | [13] | Verification / schema |

### 1.3 Semantic Verification (Causal / Primary Driver / Materiality / Multiple Assertions)

| ปัญหา | หลักฐาน | ประเภท |
|---|---|---|
| **Claim เชิงสาเหตุคือจุดแพ้หลัก:** interpretive A2 30/50, A3v2_2e 25/50 (correction 3, regression 8), SR 34/50 | evaluation.json, [13] | Reasoning |
| **Primary driver ไม่มีเกณฑ์ร่วม:** ระบบใช้ > 50% (MSFT-04) ขณะที่ Gold บางข้อใช้วิธี net YoY (NVDA-07 ได้ 53% หรือ 8% แล้วแต่วิธี) | [13] §8.2 | Task definition + Reasoning |
| **Materiality / คำประเมิน ("strong", "resilient", "no material effect") ไม่มีเกณฑ์:** D-sup ลด S → I ใน 3 regression แม้มี finding ที่ valid | [13] | Task definition + Decision policy |
| **Multiple assertions:** claim "advertising **and** membership income" (WMT-08) ส่วนหนึ่งจริงอีกส่วนเท็จ; guard ไม่บังคับว่าหลักฐานครอบคลุมทุกส่วน และยอมให้ finding ของ sub-assertion ตัดสิน claim หลัก (NVDA-07) | [13] §7.2 | Verification |
| **Anchoring:** A3 เริ่มจากคำตอบ A2 ทุกข้อ (150/150) reviewer จึงทำงานแบบ "แก้คำตอบเดิม" ไม่ใช่ตัดสินอิสระ | [13] | Architecture |

### 1.4 Reviewer & Guard (False Acceptance / False Rejection / Over-abstention)

| ตัวชี้วัด (Gold) | ค่า |
|---|---|
| Reviewer เสนอเปลี่ยน 33 ข้อ: ข้อเสนอดี 10, ข้อเสนอเสีย 13 | [13] |
| Guard รับข้อเสนอดี 4/10 (40%) และรับข้อเสนอเสีย **7/13 (54%)** | [13] |
| ข้อเสนอเสียที่เป็นคำตอบเด็ดขาด 5 ข้อ **ผ่านทุก check รูปแบบ** (quote, งวด, บริษัท) ผิดที่ความหมาย | [13] |
| Over-abstention: A3v2_2e ทำนาย I 52 ครั้ง (Gold มี 44) precision 50%; regression 11/15 เป็น decisive → I | [13] |
| E1 เปลี่ยน label 11 ครั้ง (ถูก 6 ผิด 5); D-sup 6 ครั้ง (ช่วย 1 ทำผิด 4) | [13] |

**ข้อสรุป:** guard ตรวจ "รูปแบบ" ของหลักฐานได้ แต่ตรวจ "ความหมาย" ไม่ได้ ส่วน gate ความระมัดระวัง (E1, D-sup) ทำงานโดยไม่ขึ้นกับความไม่แน่นอน จึงได้ผลบวกเฉพาะเมื่อ base rate ของ I สูง (dev 37.5% เทียบ Gold 29.3%)

### 1.5 A4 Selective Verification: ข้อจำกัดและส่วนที่ยังไม่ถูกทดสอบ [A4]
- A4 บน dev: 63/72 (2e 64, A2 53), precision ของการเปลี่ยน 11/12 แต่ CI 65–99%
- **ไม่เคยถูกทดสอบ:** numeric lock (ไม่มีข้อไหนเข้าเงื่อนไข) และ evidence scope/coverage check (ไม่ได้บล็อกข้อไหน)
- **รับช่องโหว่เดียวกับ 2e:** A4 ใช้ finding และ validation ของ 2e จึงรับ false negative ของ quote/period check มาทั้งหมด
- **รูปแบบ PG-05 ผ่านทุก gate:** หลักฐานเชิงสาเหตุจริงแต่ตีความเกิน
- กฎของ A4 เลือกหลังเห็น dev trace และได้แรงบันดาลใจจากผล Gold → เป็น post-hoc proposal เท่านั้น

### 1.6 สรุปตามชั้นของระบบ

| ชั้น | Root cause หลัก | ความมั่นใจ |
|---|---|---|
| Retrieval | ไม่ใช่สาเหตุหลัก (ปัจจัยร่วม 1 ข้อ) | สูง (Gold [13] + dev audit) |
| Evidence representation | ตารางถูกแบน, period ระดับเอกสาร, inline XBRL ถูกทิ้ง | สูง (โค้ด + [V]) |
| Verification | metric/scope/formula แคบ; quote/period check มี false negative สูง | สูง |
| Reasoning | claim เชิงสาเหตุ / ประเมินค่า, anchoring กับคำตอบ A2 | สูง (Gold), ปานกลางในการแยกสาเหตุย่อย |
| Decision policy | gate ลด label ที่ไม่ขึ้นกับความไม่แน่นอน; ไม่มีสัญญาณความมั่นใจที่ใช้ได้ | สูง |
| Task definition / labels | เกณฑ์ "primarily", materiality, คำประเมินไม่ถูกนิยามร่วมกันระหว่าง annotator กับระบบ; 31/47 ข้อผิดของ A2 อยู่ในข้อที่ annotator เห็นไม่ตรงกัน | สูง |

---

## 2. เปรียบเทียบสถาปัตยกรรมใหม่ 3 แนวทาง

ทั้งสามแนวทางต่างจาก A3 ที่ขั้นพื้นฐาน: A3 = "ตอบก่อน แล้วหาข้อโต้แย้งและกรองด้วย guard"; แนวทางใหม่เปลี่ยน **หน่วยของการตรวจ**, **ผู้ตัดสิน** หรือ **นโยบายการตัดสินใจ**

### แนวทาง S: Structured Assertion Verification (SAV)
**แนวคิด:** แตก claim เป็นกราฟของ assertion ที่มีชนิดกำกับ ตรวจแต่ละ assertion ด้วย verifier เฉพาะชนิดบน evidence ที่มีโครงสร้าง แล้วรวมผลด้วยตรรกะที่เขียนไว้ชัด ไม่ใช่ให้ LLM ตัดสินรวมครั้งเดียว

**Data flow**
1. **Claim parser (LLM, 1 call):** claim → assertion graph
   - ชนิด: `MEASURABLE` (metric, scope, period, comparison), `CAUSAL_ATTRIBUTION` (effect, driver, strength: primary/contributing/any), `EVALUATIVE` (term → criterion id จาก registry หรือ `NO_CRITERION`), `NEGATION/ABSENCE`, `CONJUNCTION`
   - assertion หลัก (A0) แยกจาก premise (เช่น "revenue recovery" มี premise ว่ารายได้เพิ่ม)
2. **Structured evidence store (offline, deterministic):**
   - ตาราง → เซลล์ที่มี row header, column header, งวด, หน่วย, scale
   - inline XBRL ทั้ง consolidated และ dimensional (segment / product / geography)
   - ข้อความ → ประโยคพร้อม period ระดับประโยค (ปีหรือไตรมาสที่ประโยคระบุเอง ไม่ใช่ของเอกสาร)
3. **Verifier ตามชนิด:**
   - `MEASURABLE` → calculator แบบ deterministic (formula registry: level, yoy, qoq, sum, share-of-change, ratio) บน XBRL/เซลล์ตาราง
   - `CAUSAL_ATTRIBUTION` → หา attribution statement ของบริษัทเอง (MD&A bridge "primarily due to…", basis-point bridge) + คำนวณ share-of-change ตาม criterion ที่ registry กำหนด
   - `EVALUATIVE` → ใช้ criterion จาก registry ถ้ามี; ถ้า `NO_CRITERION` และไม่มีข้อความบริษัทยืนยันตรง → I
   - entailment ของข้อความ (LLM, ต่อ assertion) ใช้เฉพาะเมื่อไม่มีเส้นทาง deterministic และต้องอ้างประโยคที่ resolve งวดได้
4. **Aggregator (deterministic):** A0 ตัดสินจากผลของ assertion ลูกตามตรรกะ (AND สำหรับ conjunction, premise เท็จ → C, assertion จำเป็นตัดสินไม่ได้ → I) และบันทึก evidence ที่ตัดสินทุกชิ้น

| หัวข้อ | รายละเอียด |
|---|---|
| ปัญหาที่แก้ | 1.1 ทั้งหมด, 1.2 ทั้งหมด, 1.3 multiple assertions / primary driver / materiality, anchoring (ไม่เริ่มจากคำตอบ A2) |
| หลักฐานว่าปัญหามีจริง | 80/85 quote ที่ถูกปัดตกเป็นแถวตาราง [V]; inline XBRL segment มีแต่ถูกทิ้ง [V]; NOT_APPLICABLE 56% [V]; WMT-08 / NVDA-07 [13] |
| ตรวจ evidence | ระดับเซลล์ / ประโยค มีงวดและหน่วยของตัวเอง; ตัวเลขทุกตัวคำนวณซ้ำได้ |
| ตรวจ claim semantics | ผ่านชนิดของ assertion + criterion registry ที่เขียนไว้ก่อน |
| ลด false acceptance | ทุก assertion จำเป็นต้องมีหลักฐานของตัวเอง; sub-assertion ตัดสิน A0 ไม่ได้ |
| ลด false rejection | evidence ตารางไม่ถูกปัดตกเพราะรูปแบบ; I เกิดจาก "assertion จำเป็นไม่มีหลักฐาน" ไม่ใช่จาก gate ทั่วไป |
| ค่าใช้จ่าย (ประมาณ) | parser 1 call + entailment 0–3 calls ≈ **$0.04–0.08/claim** (A2 $0.02, 2e $0.14) |
| ความเสี่ยง overfit / leakage | criterion registry อาจถูกปรับให้ตรง label (ต้องล็อกก่อนสร้าง test และเปิดให้ annotator ใช้ร่วมกัน); parser อาจเรียนรูปแบบ claim ของ dev |
| Ablation | ถอด evidence store เชิงโครงสร้าง / dimensional XBRL / formula registry / aggregator / criterion registry ทีละตัว (หัวข้อ 7) |

### แนวทาง D: Two-sided Dossier + Independent Judge
**แนวคิด:** แทนที่การ "แก้คำตอบเดิม" ด้วยการสร้างหลักฐานสองฝั่งอย่างอิสระ แล้วให้ผู้ตัดสินที่ไม่เห็นคำตอบเดิมตัดสิน

**Data flow:** retrieval เดิม → **Pro builder** สร้าง dossier สนับสนุน และ **Con builder** สร้าง dossier คัดค้าน (แต่ละฝั่งต้องอ้าง evidence ที่ผ่านการตรวจ) → **Judge** (prompt ต่างกัน, ไม่เห็นคำตอบ A2 และไม่รู้ว่าแต่ละฝั่งมาจากไหน) ตัดสินตาม rubric ที่บังคับระบุเกณฑ์; ถ้าไม่มีฝั่งไหนผ่านเกณฑ์ → I

| หัวข้อ | รายละเอียด |
|---|---|
| ปัญหาที่แก้ | anchoring, reviewer ตีความฝั่งเดียว, false acceptance เชิงความหมาย |
| หลักฐาน | A3 เริ่มจาก A2 150/150 [13]; ข้อเสนอเสีย 5 ข้อผ่าน check รูปแบบทั้งหมด [13]; SR (คิดซ้ำแบบไม่ยึดคำตอบ) ชนะ interpretive 34/50 |
| ตรวจ evidence | ใช้ชั้นตรวจหลักฐานเดิมหรือของแนวทาง S |
| ตรวจ semantics | ผ่าน rubric ของ judge (ยังเป็น LLM) |
| ลด FA / FR | judge เห็นทั้งสองฝั่งพร้อมกัน; ตัดสินจากความแข็งของหลักฐานเปรียบเทียบ |
| ค่าใช้จ่าย | 3–4 calls ≈ **$0.10–0.16/claim** |
| ความเสี่ยง | judge ยังเป็น LLM ตัวเดียวกับ builder (Sonnet) จึงอาจมี bias ร่วม; prompt rubric ปรับตาม dev ได้ง่าย |
| Ablation | judge เห็น/ไม่เห็นคำตอบ A2; one-sided vs two-sided; rubric มี/ไม่มีเกณฑ์ |

### แนวทาง R: Calibrated Selective Routing
**แนวคิด:** ไม่เปลี่ยน verifier แต่เปลี่ยน **นโยบายการตัดสินใจ**: เรียกขั้นที่แพงเฉพาะข้อที่ไม่แน่นอน และรวมคำตอบหลาย arm ด้วยตัวรวมที่ calibrate แล้ว

**Data flow:** A2 + สัญญาณราคาถูก (ความเห็นตรงกันของการตอบซ้ำหลายครั้งที่ temperature > 0, ชนิด claim, rule ของ numeric, ผล SR) → **router** ตัดสินว่าเชื่อ A2 ได้หรือส่งต่อ → ข้อที่ส่งต่อใช้ SR/A3/S → **combiner** (logistic regression ขนาดเล็ก, เกณฑ์ตั้งบน dev, ตรวจบน validation)

| หัวข้อ | รายละเอียด |
|---|---|
| ปัญหาที่แก้ | decision policy, ต้นทุน, ความมั่นใจที่ใช้ไม่ได้ |
| หลักฐาน | oracle 131/150 [V]; confidence high 144/150 [V]; NUMERIC_ALL_TRUE 32/32 [V]; SR/A3 ผิดคนละข้อ |
| ตรวจ evidence / semantics | **ไม่ได้แก้** (ใช้ของ arm ที่มีอยู่) |
| ค่าใช้จ่าย | ขึ้นกับสัดส่วนที่ส่งต่อ ≈ **$0.04–0.10/claim** |
| ความเสี่ยง | combiner overfit กับ dev ขนาดเล็กได้ง่ายที่สุดในสามแนวทาง; เพดานคือ arm ที่มีอยู่ ซึ่งยังตรวจความหมายไม่ได้ |
| Ablation | router มี/ไม่มี; combiner vs majority vote; สัญญาณแต่ละตัว |

### ตารางเปรียบเทียบ

| เกณฑ์ | S: Structured Assertion | D: Dossier + Judge | R: Selective Routing |
|---|---|---|---|
| แก้ root cause ที่ยืนยันได้ | มากที่สุด (evidence, numeric, multi-assertion, anchoring) | anchoring, FA เชิงความหมาย | decision policy, ต้นทุน |
| Evidence-grounded correctness | สูง (ทุกการตัดสินย้อนไปที่เซลล์/ประโยค/การคำนวณ) | ปานกลาง | ไม่เปลี่ยน |
| ส่วนที่ตรวจได้แบบ deterministic | มาก | น้อย | ปานกลาง |
| ความเสี่ยง overfit | ปานกลาง (registry) | ปานกลาง (rubric) | สูง (combiner) |
| ค่าใช้จ่ายต่อ claim | $0.04–0.08 | $0.10–0.16 | $0.04–0.10 |
| งานวิศวกรรม | มาก (table parser, iXBRL, aggregator) | ปานกลาง | น้อย |
| งานที่ทำ offline ได้ก่อน | มาก (evidence store, calculator วัดได้โดยไม่เรียก API) | น้อย | ปานกลาง |

---

## 3. Architecture ที่แนะนำ

**แนะนำ S (Structured Assertion Verification) เป็นแกน + R แบบจำกัด (routing ด้วยกฎที่ล็อกไว้ ไม่ใช้ learned combiner ในรอบแรก)**

**เหตุผลเชิงวิศวกรรม**
1. Root cause ที่ยืนยันได้มากที่สุดอยู่ที่ **evidence representation และ verification** ซึ่งเป็นโค้ด deterministic ที่ทดสอบได้ด้วย unit test และวัดได้ offline โดยไม่เสียเงิน
2. ข้อมูลที่ต้องใช้ (ตาราง, inline XBRL segment) **มีอยู่ในเครื่องแล้ว** แต่ถูกทิ้งตอน clean HTML
3. การตัดสินที่ย้อนไปถึงเซลล์หรือการคำนวณได้ ทำให้วัด evidence-grounded correctness ได้จริง ไม่ใช่แค่ label match
4. ลด LLM call ต่อข้อเมื่อเทียบกับ A3 (ประหยัดกว่า 2e ราว 2 เท่า)

**เหตุผลเชิงงานวิจัย**
1. แยกคำถามวิจัยได้ชัด: ผลมาจาก "evidence ที่ดีขึ้น" หรือ "การแตก assertion" หรือ "นโยบายการตัดสินใจ" ด้วย ablation
2. ความผิดพลาดหลักของ A3 คือ guard ตรวจรูปแบบแต่ไม่ตรวจความหมาย SAV ย้ายการตรวจความหมายไปไว้ที่ **ชนิดของ assertion + เกณฑ์ที่เขียนไว้ก่อน** ซึ่งตรวจสอบได้มากกว่า prompt
3. D ยังพึ่ง LLM ตัวเดียวตัดสินความหมาย และ R มีเพดานเท่ากับ arm เดิม

**เงื่อนไขสำคัญ:** criterion registry (เช่น "primarily" = ส่วนเกิน 50% ของการเปลี่ยนแปลง หรือมีข้อความบริษัทยืนยัน; "material" = ตามที่บริษัทระบุ หรือ ≥ X% ของ metric ฐาน) **ต้องเขียนและล็อกก่อนสร้าง dataset ใหม่** และ annotator ใช้ฉบับเดียวกัน เพื่อให้ task definition ชัด ไม่ใช่ปรับ registry ให้ตรง label ทีหลัง

**ข้อควรระวัง:** แม้แก้ทุกอย่างแล้ว ข้อที่ annotator เห็นไม่ตรงกันอาจยังเป็นเพดาน การกำหนดเกณฑ์ร่วม (registry) คือทางเดียวที่ลดเพดานนี้ได้อย่างชอบธรรม

---

## 4. แผนพัฒนาเชิงเทคนิค

ทุก component เป็นโมดูลใหม่ (เช่น `research/sav/`) **ไม่แก้** `engine/` และ `a3v2/` ที่อยู่ใน code bundle `c4d2112f…`

| # | Component | งาน | ทดสอบอย่างไร | ต้องเรียก API |
|---|---|---|---|---|
| T1 | Table-aware document model | แปลง HTML เป็น block (ประโยค / ตาราง → เซลล์ที่มี row/col header, งวดจากหัวคอลัมน์, หน่วย, scale "in millions") | unit test บน filing ที่ cache; วัดสัดส่วนเซลล์ที่ resolve งวดได้ | ไม่ |
| T2 | Inline XBRL extractor | อ่าน `ix:nonFraction` + context (period, dimension) รวม segment / product / geography | เทียบ consolidated กับ companyfacts (ต้องตรง), สุ่มตรวจ segment กับตาราง | ไม่ |
| T3 | Statement-level period resolver | งวดของประโยคจากวันที่/ปี/คำว่า "fiscal 2025", "three months ended…" ในประโยคเอง ก่อน fallback ไปที่ระดับเอกสาร | ชุด evidence-period ที่มนุษย์ label (E-set, หัวข้อ 5) | ไม่ |
| T4 | Quote / cell verifier | ตรวจ quote กับประโยคหรือแถวตาราง (ตัวเลข + header) | E-set: false negative rate เทียบกับ check 1.1 เดิม | ไม่ |
| T5 | Formula registry + calculator | level, yoy, qoq, sum, difference, ratio, share-of-change, FCF (นิยามระบุชัด) บน XBRL/เซลล์ | unit test + ตัวอย่างจาก dev audit (PG-12, AMZN-07) | ไม่ |
| T6 | Assertion schema + parser | JSON schema ของ assertion graph; parser เป็น LLM 1 call | ความถูกต้องของการแตก assertion บน dev ที่มนุษย์ label (P-set) | **ใช่** (dev) |
| T7 | Criterion registry | ไฟล์เกณฑ์สำหรับ primarily / main driver / material / significant / strong ฯลฯ พร้อมเหตุผลและแหล่งอ้างอิง | ทบทวนโดยผู้วิจัย + annotator; **ล็อกก่อนสร้าง dataset** | ไม่ |
| T8 | Aggregator | ตรรกะรวม assertion → label + evidence trail | unit test ครบทุก combination | ไม่ |
| T9 | Router (กฎ) | ข้อที่ตรวจตัวเลขได้ครบ → ใช้ calculator; ข้อเชิงคุณภาพ → SAV เต็ม | วัดบน dev ใหม่ | ใช่ (dev) |

**ลำดับ:** T1–T5 และ T7–T8 ทำ offline ได้ทั้งหมดก่อน; T6/T9 ต้องใช้ API บน dev ใหม่เท่านั้น

**Baseline ที่ต้องเพิ่มเพื่อความเป็นธรรม:** **A2+E** = A2 ที่ใช้ evidence store ใหม่ (T1–T5) โดยไม่มี assertion graph เพื่อแยกว่าผลมาจาก evidence ที่ดีขึ้นหรือจากสถาปัตยกรรม

---

## 5. แผนสร้าง Dataset ใหม่อย่างมีคุณภาพ

**ห้ามเริ่มจนกว่าแผนนี้ได้รับอนุมัติ**

### 5.1 ชุดข้อมูล

| ชุด | ขนาด | ใช้ทำอะไร | บริษัท |
|---|---:|---|---|
| **Dev-v1** | 180 | พัฒนา, debug, ตั้งค่า | กลุ่ม D (8–10 บริษัท) |
| **Validation** | 150 | เลือกระหว่าง candidate ไม่เกิน 2 ตัว ครั้งเดียวต่อ candidate; ห้ามใช้ปรับกฎ | กลุ่ม V (5–6 บริษัท, ไม่ซ้ำ D) |
| **Blind Test** | **400** | ยืนยันผลครั้งเดียว | กลุ่ม T (10 บริษัท, ไม่ซ้ำ D/V และไม่ซ้ำ Gold 150 / dev-v0.2) |
| E-set | 300 คู่ (claim, evidence) | วัด false negative / false positive ของ period / quote / cell check | จาก Dev-v1 |
| P-set | 80 claims | วัดความถูกต้องของการแตก assertion | จาก Dev-v1 |

- **ขนาด Blind Test:** ถ้าสัดส่วนข้อที่สองระบบตอบต่างกันราว 20% (Gold: A2 vs 2e 25/150 = 17%) McNemar ที่ α = 0.05 สองทาง power 80% ต้องใช้ ≈ 370 ข้อเพื่อตรวจผลต่าง +6.5 pp และ ≈ 625 ข้อสำหรับ +5 pp; 400 ข้อจึงตรวจได้ที่ประมาณ +6–7 pp
- **ทางเลือกงบน้อย:** Test 300 (ตรวจได้ ≈ +7.5 pp) และ Dev 120 / Validation 100
- Gold 150 และ dev-v0.2 = **exposed development pool** (222 ข้อ) ใช้ debug ได้ แต่ห้ามใช้เลือกโมเดลหรือรายงานเป็นผลยืนยัน

### 5.2 การสร้าง claim
1. **กระจาย:** numerical / interpretive / evaluative-ambiguous อย่างละ 1/3; label เป้าหมาย S/C/I ใกล้ 45/30/25 (กำหนดก่อน ไม่ปรับตามผล)
2. **ที่มาของ claim:** ไม่ใช้ LLM ร่างจากรายชื่อ filing แบบเดิม (ข้อจำกัดเดิม: ไม่ได้อ่านรายงาน, ถ้อยคำคล้ายรายงาน) ใช้สองแหล่งผสม
   - ผู้วิจัยหรือผู้ช่วยเขียน claim แบบที่นักวิเคราะห์/สื่อเขียน (เช่น ประโยคจากข่าวหรือ earnings commentary ที่ paraphrase)
   - LLM สร้าง perturbation ที่ควบคุมได้ (เปลี่ยนตัวเลข, งวด, scope, ทิศทาง, driver) จากข้อความ filing แล้วให้มนุษย์คัด
3. **ห้าม:** ผู้เขียน claim ห้ามเห็น output ของระบบใดๆ; ห้ามใช้ Sonnet 4.5 (โมเดลที่ทดสอบ) ร่าง claim ชุด test
4. ทุก claim มี `as_of_date`, งวดที่อ้าง, บริษัท และ hash ของ filing ที่อนุญาต (corpus pin)

### 5.3 Annotation ที่ตรวจสอบได้
1. **Guideline v3 + criterion registry (T7)** ล็อกก่อนเริ่ม annotate
2. **Annotator 1 (มนุษย์)** ติด label ทุกข้อ พร้อม evidence locator (filing accession + ประโยค หรือเซลล์ตาราง) และ criterion ที่ใช้; evidence ต้องยื่นก่อนหรือใน `as_of_date`
3. **Annotator 2 (LLM ต่างตระกูลกับโมเดลที่ทดสอบ)** ติด label แยก
4. **Annotator 3 (มนุษย์คนที่สอง)** ติด label อิสระบนสุ่ม 25% ของทุกชุด เพื่อวัด human-human agreement
5. **Adjudication โดยมนุษย์** ทุกข้อที่ annotator ไม่ตรงกัน หรือ annotator 1 ระบุว่ากำกวม บันทึกเหตุผลและ label ทางเลือก
6. **Quality gates:** Krippendorff's α (human-human) ≥ 0.67 ทั้งชุด และ ≥ 0.60 ทุกหมวด; ถ้าไม่ถึง → แก้ guideline แล้วติดใหม่ (ก่อนเปิด test เท่านั้น)
7. ทุก label มีสถานะ `UNANIMOUS` / `ADJUDICATED` และเก็บ label ทางเลือก เพื่อรายงาน sensitivity
8. **Blind test sealing:** label ของ test เก็บโดยผู้วิจัย, commit เฉพาะ sha256 ของไฟล์ claims และ labels ก่อนเริ่มพัฒนา SAV บน Dev-v1; ระบบที่รันบน test เห็นเฉพาะ claims

**ภาระงานมนุษย์ (ประมาณ):** 730 claims × 6 นาที ≈ 73 ชม. + double annotation 25% ≈ 18 ชม. + adjudication ≈ 20 ชม. + E-set/P-set ≈ 15 ชม. → **≈ 125 ชม.** (ทางเลือกงบน้อย ≈ 85 ชม.)

---

## 6. Evaluation Protocol

### 6.1 Arms บน Blind Test
A2 (baseline หลัก), SR, A3v2_2e (อ้างอิง), **A2+E** (ablation evidence), **SAV** (candidate ที่ล็อกจาก validation)

### 6.2 Metrics

| Metric | นิยาม |
|---|---|
| Accuracy | strict label match |
| Macro-F1 | เฉลี่ย F1 ของ S/C/I |
| INSUFFICIENT precision / recall | precision = ทำนาย I ถูก / ทำนาย I ทั้งหมด; recall = ทำนาย I ถูก / gold I |
| Regression rate vs A2 | A2 ถูก แต่ arm ผิด / A2 ถูก |
| Correction rate vs A2 | A2 ผิด แต่ arm ถูก / A2 ผิด |
| Accepted change precision | ข้อที่ arm ≠ A2 และ arm ถูก / ข้อที่ arm ≠ A2 (นับทุกทิศ รวม → I) |
| **Evidence-Grounded Correctness (EGC)** | label ถูก **และ** evidence ที่ใช้ตัดสินอย่างน้อยหนึ่งชิ้นรองรับ label ตามการตรวจของมนุษย์ **และ** ไม่มี evidence ที่อ้างแล้วขัด label **และ** ตัวเลขที่คำนวณถูก; ประเมินโดยมนุษย์ที่ไม่รู้ว่าเป็น arm ไหน บนสุ่ม 150 ข้อของ test ต่อ arm หลัก (A2, SAV) |
| Cost per claim | list price จาก ledger (live) |
| Latency | median และ p90 ของ API latency ต่อ claim |

รายงานทุก metric แยก `UNANIMOUS` กับ `ADJUDICATED` และแยกหมวด claim (เชิงพรรณนา)

### 6.3 Primary Endpoint และเกณฑ์ตัดสิน (ล็อกใน prereg ก่อนเปิด test)
- **Primary endpoint:** ผลต่าง accuracy (SAV − A2) บน Blind Test 400 ข้อ, McNemar exact สองทาง α = 0.05
- **SAV ถือว่า "ดีกว่า A2" เมื่อผ่านทุกข้อ:**
  1. ผลต่าง accuracy > 0 และ p < 0.05
  2. regression rate vs A2 ≤ 7%
  3. EGC ของ SAV ≥ EGC ของ A2 − 3 pp (non-inferiority)
  4. INSUFFICIENT precision ≥ 60% (กัน over-abstention)
- **Secondary (Holm):** SAV vs SR, SAV vs A2+E, macro-F1 SAV vs A2
- ERROR policy, ห้ามทิ้ง claim, retry ไม่เกิน 2 รอบ ตามแบบ prereg 08

### 6.4 กติกาความสะอาดของข้อมูล
- Validation เปิดได้ไม่เกิน 2 ครั้ง (candidate ละครั้ง) ผลของ validation ใช้เลือก candidate เท่านั้น ห้ามใช้ปรับกฎแล้วรันซ้ำ
- Blind Test รันครั้งเดียวหลัง prereg LOCKED และ code bundle hash ล็อก
- ทุกการตัดสินใจหลังเห็นผลบันทึกใน run log แบบ append-only

---

## 7. Ablation Plan

**ทำบน Validation (เปิดครั้งเดียวพร้อม candidate หลัก) และรายงานเชิงพรรณนา ไม่ใช้เลือกกฎใหม่** ablation ส่วนใหญ่เป็น deterministic จึง replay จาก cache ของ SAV เต็มได้โดยไม่เรียก API เพิ่ม

| Ablation | ถอดอะไร | คำถามที่ตอบ | ต้องเรียก API เพิ่ม |
|---|---|---|---|
| SAV − T1/T4 | ใช้ข้อความแบนและ quote check เดิม | ตาราง/เซลล์ช่วยลด false rejection จริงไหม | ไม่ (replay) |
| SAV − T2 | ไม่ใช้ dimensional XBRL | segment facts ช่วยข้อที่เป็น segment/product ไหม | ไม่ |
| SAV − T3 | ใช้ period ระดับเอกสาร | period ระดับประโยคลด false mismatch ไหม | ไม่ |
| SAV − T5 | formula เหลือ level/yoy | สูตรหลายตัวแปรช่วยไหม | ไม่ |
| SAV − T8 | ให้ LLM ตัดสินรวมแทน aggregator | ตรรกะ assertion ดีกว่า LLM ตัดสินครั้งเดียวไหม | ใช่ (1 call/claim) |
| SAV − T7 | ไม่มี criterion registry (ให้ LLM ตีความเกณฑ์เอง) | การกำหนดเกณฑ์ร่วมคือแหล่งของผลไหม | ใช่ |
| A2+E vs A2 | evidence ใหม่บน A2 | แยกผลของ evidence ออกจากสถาปัตยกรรม | ใช่ (A2 ราคาถูก) |
| Router ปิด | ทุกข้อเข้า SAV เต็ม | routing ประหยัดโดยไม่เสียความแม่นไหม | ใช่ |

**Component-level metrics (offline):** false negative / false positive rate ของ period / quote / cell check บน E-set; ความถูกต้องของ assertion parser บน P-set; ความถูกต้องของ calculator บนชุดตัวเลขที่มนุษย์คำนวณ

---

## 8. Budget และ Decision Gates

ราคาอ้างอิง Sonnet 4.5 จากรอบ Gold: A2 ≈ $0.02/claim, SR ≈ $0.07, 2e ≈ $0.14; SAV ประมาณ $0.04–0.08 (ต้องยืนยันด้วย pilot)

| Phase | งาน | ประเภท | งบ API (ประมาณ) | งานมนุษย์ | Gate ก่อนไปต่อ | หยุดเมื่อ |
|---|---|---|---:|---|---|---|
| **P0** | Review แผนนี้ | — | $0 | ผู้วิจัย | อนุมัติแผน + งบรวม | — |
| **P1** | T1–T5, T7–T8 + unit tests; วัดบน exposed pool เชิงพรรณนา | Offline | $0 | ผู้วิจัยทบทวน registry | evidence check: FN บน E-set ลดลงอย่างน้อยครึ่งหนึ่งเทียบ check 1.1 และ FP ไม่เพิ่ม; consolidated iXBRL ตรง companyfacts ≥ 99% | ลด FN ไม่ได้ หรือ iXBRL ไม่น่าเชื่อถือ → หยุด S, พิจารณา D |
| **P2** | สร้าง Dev-v1, Validation, Test, E-set, P-set + annotation + sealing | Human + LLM annotator | $30–80 (LLM annotator ผ่าน API; $0 ถ้าใช้ UI) | ≈ 125 ชม. (หรือ 85) | α ≥ 0.67; distribution ตามแผน; hash ของ test commit แล้ว | α ไม่ถึงหลังแก้ guideline 1 รอบ → ทบทวน task definition ก่อนไปต่อ |
| **P3** | T6, T9 + พัฒนา SAV บน Dev-v1 (ใช้ cache, ≤ 4 รอบเต็ม) | Paid API | $40–70 | ผู้วิจัยตรวจ error | SAV ≥ A2 + 5 pp บน Dev-v1, regression ≤ 7%, INSUF precision ≥ 60% | ไม่ถึง A2 + 3 pp หลัง 4 รอบ → หยุด, รายงานเป็น negative |
| **P4** | Validation (≤ 2 candidates) + ablation | Paid API | $30–50 | — | candidate ≥ A2 + 3 pp และผ่าน regression / INSUF precision | ไม่ผ่าน → ไม่เปิด test, กลับ P3 ได้ครั้งเดียวด้วย Dev-v1 เท่านั้น |
| **P5** | Lock prereg + code bundle | Offline | $0 | ผู้วิจัยอนุมัติ | prereg LOCKED + hash | — |
| **P6** | Blind Test 400 ข้อ × 5 arms ครั้งเดียว + EGC | Paid API + Human | $110–150 (+ สำรอง 30%) | EGC ≈ 15 ชม. | — | — |

**รวม API ≈ $210–350** (สำรองรวม ≈ $400); ทางเลือกงบน้อย (Test 300, 4 arms ไม่รวม 2e) ≈ **$150–220**

**กติกาค่าใช้จ่าย:** ทุก phase ที่เสียเงินต้องขออนุมัติแยกด้วยประโยคที่ระบุจำนวน call และเพดาน; ใช้ ledger ใหม่ต่อ phase; รันนอก Kilo pool และ backup ทุก 2 นาทีตามขั้นตอนหลังเหตุขัดข้อง

---

## 9. Risks and Limitations

| ความเสี่ยง | ผลกระทบ | การลดความเสี่ยง |
|---|---|---|
| **เพดานจากความกำกวมของ label** (A2 ถูก 38% ในข้อที่ annotator เห็นไม่ตรงกัน) | แม้ระบบดีขึ้นก็อาจวัดไม่เห็น | criterion registry ร่วม, adjudication โดยมนุษย์, รายงานแยก UNANIMOUS |
| **Registry กลายเป็นการปรับเกณฑ์ให้ตรง label** | overfit แบบแฝง | ล็อก registry ก่อนสร้าง dataset, annotator ใช้ฉบับเดียวกัน, เปลี่ยนได้เฉพาะก่อนเปิด test และต้องบันทึก |
| **Adaptive overfitting บน Dev-v1** (เกิดแล้วกับ dev-v0.2: +11 บน dev, −5 บน Gold) | ผล dev สูงเกินจริง | จำกัดรอบ, validation แยกบริษัท, test แยกบริษัท |
| **Leakage จาก Gold 150 / dev-v0.2** | แนวคิดของ SAV มาจาก error analysis ของ Gold | ยอมรับว่า Gold เป็น exposed; ใช้บริษัทใหม่ทั้งหมดใน test |
| **ความผิดของ parser LLM ส่งต่อ** | แตก assertion ผิด → ตัดสินผิดทั้งข้อ | P-set วัดความถูกต้อง; fallback เป็น A2 เมื่อ parser ไม่มั่นใจ (กฎล็อกก่อน) |
| **iXBRL / ตารางของแต่ละบริษัทต่างกัน** | parser ใช้ได้กับบางบริษัท | ทดสอบหลายบริษัทใน P1; รายงาน coverage ต่อบริษัท |
| **โมเดล Sonnet 4.5 อาจถูกเลิกให้บริการระหว่างทาง** | เทียบกับผลเดิมไม่ได้ | ล็อก model id ใน prereg; ถ้าต้องเปลี่ยน รัน A2 ใหม่บน test ด้วยโมเดลเดียวกัน |
| **ภาระงานมนุษย์ ≈ 125 ชม.** | ไม่ทันกำหนด IS | ทางเลือกงบน้อย; เริ่ม P1 (offline) ระหว่างวางแผน annotation |
| **งบ API จำกัด** | หยุดกลางทาง | gate ทุก phase; ledger ต่อ phase; ทางเลือก $150–220 |
| **Same-family bias** | ผู้ร่าง/annotator/โมเดลเป็นตระกูลเดียวกัน | ห้ามใช้ Sonnet 4.5 ร่าง test; LLM annotator ต่างตระกูล |
| **EGC ต้องใช้มนุษย์** | ประเมินได้เฉพาะสุ่ม | สุ่ม 150 ข้อต่อ arm หลัก, blind ต่อ arm |
| **Power จำกัด** | ผลต่าง < 6 pp อาจไม่มีนัยสำคัญแม้มีจริง | รายงาน CI และ effect size; ระบุ MDE ไว้ใน prereg |

**ข้อจำกัดของเอกสารนี้**
- การจัด root cause อ้างอิง [13] ซึ่งทำโดยผู้วิเคราะห์ AI คนเดียว และยังไม่มีผู้ตรวจที่สอง
- ตัวเลข [V] เป็นการนับเชิงพรรณนาบน Gold ที่ exposed แล้ว ไม่ใช่การทดสอบใหม่
- ตัวเลข "80/85 quote เป็นแถวตาราง" ใช้เกณฑ์ตัวเลข ≥ 3 ตัวในข้อความ เป็น heuristic ไม่ใช่การตรวจทีละรายการ
- ค่าใช้จ่ายของ SAV เป็นการประมาณ ต้องยืนยันด้วย pilot ใน P3

---

## ภาคผนวก: สิ่งที่ตรวจในรอบนี้
- โค้ด: `engine/numeric.py`, `engine/corpus.py`, `a3v2/checks.py`, `a3v2/periods.py`, `a3v2/numeric_checks.py`, `a3v2/contribution.py`
- Run: `a3v2.2-gold150-20261118T112814Z` (predictions, traces A2 / A3v2_2e), `claimverif-main-v1-20261110T104207Z` (A3 v1 predictions), `a3v2.2-dev-v0.2-20261118T052512Z`
- Frozen evaluation: `results/gold150/a3v2.2-gold150-20261118T112814Z/evaluation.json` (อ่านอย่างเดียว)
- Reference: `engine.reference.load_reference()` (vote pattern ของ LLM annotator 3 ตัว)
- เอกสาร: `11`, `13`, `results/dev_v0_2/error_analysis/final_accuracy_readiness_audit.md`, `results/dev_v0_2/a4_feasibility/a4_feasibility.md`
- ไฟล์ cache: `backend/app/data/cache/doc_0000050863-26-000191_intc-20260926.htm` (ตรวจ inline XBRL dimension), `CIK0000050863.json` (companyfacts ไม่มี dimension)
