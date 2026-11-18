# A3 Pre-flight Audit ก่อนประเมินบน Gold 150 (2026-11-18)

- **ขอบเขต:** ไม่เรียก API ที่เสียเงิน ไม่รัน Gold และไม่ commit
- **วิธีการ:** ทุกตัวเลขมาจาก run แบบ cache-only บน dev-v0.2 (`a3v2.2-dev-v0.2-20261118T052512Z`, 1,454 cache hits, live 0) กับ label v2 (`7dccc43a…`)
- **ข้อห้ามที่ปฏิบัติตาม:** ไม่ได้ใช้ Gold label เพื่อปรับกฎใด ๆ

## Phase 1: Baseline integrity

| ตรวจ | ผล |
|---|---|
| ทำไม A2/R/RG เปลี่ยนจาก 52/47/50 เป็น 53/48/51 | label เปลี่ยน**ข้อเดียว**: DEV-INTC-07 จาก INSUFFICIENT เป็น SUPPORTED (label v1 `0d288fe3…` → v2 `7dccc43a…` ตัดสินโดยผู้วิจัยหลัง AI audit ติดป้าย post hoc ไว้แล้ว) ทั้งสาม arm ตอบ SUPPORTED จึงได้ +1 เท่ากัน |
| prediction รายข้อ | A2 / R / RG ใน run ใหม่**เหมือนกับ run v2.1.1 เดิมทั้ง 72 ข้อ** (diff = ∅) |
| Dataset / config hash | dev `120d60d4…` ไม่เปลี่ยน; config hash ของ v2.0–v2.1.1 ไม่เปลี่ยน (มี test ยืนยัน) |
| Scoring | evaluation 1.0 → 1.1 เปลี่ยนแค่การ**รายงาน** guard (แยก RG−R กับ RG−A2) สูตร accuracy ไม่เปลี่ยน |
| Gold labels | `Final_Gold_v3_approved.xlsx` sha `e47897c4…` และ `gold_claims.jsonl` `1080323a…` ไม่เปลี่ยน; freeze verify ของ v1 ได้ `changed: [] removed: []` |
| Gold / claim ID ใน runtime | grep `a3v2/`, `engine/llm.py`, `engine/numeric.py`, `experiments/`, `graphs/` **ไม่พบ** ID ของ claim, path ของ label หรือไฟล์ annotation ในโค้ดที่รันจริง |

### การสัมผัส Gold 150 (contamination)

1. **A3 v2 รุ่นแรก:** ออกแบบจาก error analysis ของ A3 v1 บน Gold 150 (docstring ใน `a3v2/__init__.py`) คือ reviewer, guard และ periods
2. **ใน session นี้:** ดู accuracy รวมและแยกประเภทของ v1 บน Gold, นับจำนวน claim และบริษัทเพื่อวางแผน, ใช้ `--check-v1` ตรวจว่าตัวประเมินให้ผลตรงกับ v1 **ไม่ได้ดู label หรือ prediction รายข้อของ Gold และไม่มีกฎใดสร้างจาก Gold**
3. **กฎของ v2.2e ทุกข้อ** (G3b, Q1.1, G1, G4, D-sup, N1, N2, E1) ออกแบบบน dev-v0.2

→ **ผลบน Gold ต้องเรียกว่า "semi-held-out" ห้ามเรียก independent held-out**

## Phase 2: Root cause และ vote pattern (dev 72 ข้อ, label v2)

| ระบบ | ถูก | แก้ข้อที่ A2 ผิด | ทำข้อที่ A2 ถูกให้ผิด | INSUFF recall |
|---|---|---|---|---|
| A2 | 53 | — | — | 19/27 |
| RG v2.1.1 | 51 | 5 | 7 | 13/27 |
| v2.2 (ก+ง) | 63 | 12 | 2 | 22/27 |
| v2.2c (+ข) | 65 | 14 | 2 | 22/27 |
| **v2.2e (+E1)** | **64** | **14** | **3** | **24/27** |

### กลไกของ +12 จาก RG v2.1.1 → v2.2 (ยืนยันจาก reason code ใน trace)

| กลไก | ข้อ |
|---|---|
| G1 (คำประเมินไม่มีเกณฑ์) | CAT-01, CAT-03, PG-02 |
| G3b | CAT-07 |
| G4 | PG-08 |
| Q1.1 | MSFT-05 |
| D-sup | ADBE-03, CAT-02, INTC-02 |
| N1 | ADBE-10, INTC-12 |
| N2 | AMZN-07 |

- **v2.2e เพิ่มจาก E1:** AAPL-05 ✓, INTC-09 ✓ แต่ INTC-06 ✗ (คำตอบ CONTRADICTED ถูก แต่ไม่มีหลักฐานที่ผ่านการตรวจรองรับ)
- **v2.2c เพิ่มจาก contribution:** AAPL-04 ✓, PG-06 ✓

### Vote pattern ของ v2.2 (finding ที่ VALID หลัง Q1.1)

| Pattern | ทั้งคู่ถูก | A2 ผิด → A3 ถูก | A2 ถูก → A3 ผิด | ทั้งคู่ผิด |
|---|---|---|---|---|
| SUPPORT_ONLY | 21 | 6 | 0 | 2 |
| CONTRADICT_ONLY | 16 | 1 | **2** | 3 |
| CONFLICTING | 4 | 1 | 0 | 0 |
| NO_DECIDING | 10 | 4 | 0 | 2 |

- **ทั้ง 2 ข้อที่ A3 ทำพัง (AAPL-07, PG-05) เป็น CONTRADICT_ONLY:** reviewer ตัดสินว่าขัดแย้ง แต่จริง ๆ เป็น claim เชิงปฏิเสธ / เชิงสาเหตุที่หลักฐานไม่ได้ระบุ ต้องใช้ G5 / G2 ซึ่งต้องมีฟิลด์ใหม่ใน reviewer
- **CONFLICTING (AAPL-06):** ตอบถูก แต่ reviewer ติดป้าย R1 เป็น ENTAILS ทั้งที่เหตุผลบรรยายการขัดแย้ง

### ตอบถูกด้วยเหตุผลผิดหรือไม่

| ข้อ | ผล |
|---|---|
| AAPL-06 | ถูกด้วยเหตุผลถูก (R2/R3 CONTRADICTS: OCF ลด, NI เพิ่ม) แต่ข้อมูลมี relation error หนึ่งจุด |
| INTC-04 | ถูกด้วยเหตุผลถูก (รายได้รวมลดลง จึงไม่ใช่ "recovery") |
| INTC-02 / ADBE-03 / CAT-02 | ถูกเพราะ D-sup ตาม guideline (ไม่มีเกณฑ์) |
| **INTC-06 (v2.2 ไม่มี E1)** | **ถูกโดยไม่มีหลักฐานที่ผ่านการตรวจ** E1 จึงเปลี่ยนเป็น INSUFFICIENT |
| PG-12 | R เคยตอบถูกด้วยเหตุผลผิด (`< None`) ตอนนี้ไม่ผ่าน E1 ซึ่งถูกต้องแล้ว |

## Phase 3: สถาปัตยกรรมเทียบกับแนวทางของอาจารย์

| ขั้นของอาจารย์ | มีในระบบแล้ว | ไฟล์ / node | ช่องว่าง |
|---|---|---|---|
| **A3.0** Claim analysis / context | ✅ | `analyze_claim` (แยก assertion, ช่วงเวลา periods 1.1) + **decidability classifier** (LLM 1 call, เห็นแค่ข้อความ claim) | ยังไม่แยก claim หลายส่วนเป็น assertion ย่อยด้วย LLM |
| **A3.1** Structured counterevidence | ✅ | `generate_hypotheses` (≤ 3 challenge) → `counter_investigation` (retrieval + numeric check) | — |
| **A3.15** Evidence relevance / sufficiency | ✅ **มีแล้ว ไม่ต้องสร้าง agent ใหม่** | `evidence_review` (ตรวจ quote / บริษัท / วันตัด / ช่วงเวลา / ประเภทข้อความแบบ deterministic ก่อน แล้ว LLM reviewer) + guard (G3b, G1, G4, D-sup) + N1/N2 + **E1** | ไม่มีคลาส "qualifying" แยก (รวมอยู่ใน RELATED_NOT_DECIDING) และไม่มี G2/G5 |
| **A3.2** Reconciliation | ✅ | `reconcile_v2` (LLM) → `reconciliation_guard` (deterministic) | — |

**Design pattern:** Sequential + Review-and-Critique (reviewer แยก conversation, guard แบบ deterministic) **ยังไม่มี Bounded Loop**

**ข้อเสนอ Bounded Loop (1 retry เมื่อหลักฐานไม่พอ):**
- **ออกแบบ:** ถ้า E1 หรือ guard ได้ NO_DECIDING และ decidability = MEASURABLE ให้ retrieve รอบเดียวด้วย query จาก `required_evidence` → review ซ้ำ → guard ซ้ำ
  - **Budget:** +2 call ต่อ claim
  - **cap:** 8 call / 100k token
- **ไม่ใส่ใน candidate ที่จะรันบน Gold:**
  - ยังไม่มีหลักฐานบน dev (ต้องรันแบบเสียเงิน)
  - จะเปลี่ยน request ของ reviewer
  - ถ้าเพิ่มหลังเห็นผล Gold จะเป็นการไล่คะแนน
- **สถานะ:** future work แยก ต้องทดสอบบนชุดอื่น

## Phase 4: Prompt audit (prompt และ schema จริง)

| Agent | Prompt / version | Input | Output |
|---|---|---|---|
| A2 initial | `engine/prompts.py` SYSTEM + INITIAL_INSTRUCTION | claim + retrieved passages | label, numeric_assertions, citations |
| Decidability | `a3v2-decidability-prompt-0.1` | **claim text / บริษัท / งวดเท่านั้น** | predicate_type, evaluative_terms, criterion_source, scope, contribution, required_evidence |
| Contradiction investigator | CONTRADICTION_INSTRUCTION | conversation ของ A2 | ≤ 3 challenge + query + numeric_check |
| Evidence reviewer | `a3v2-review-prompts-0.3` (แยก conversation) | claim + assertions + evidence (deterministic checks แล้ว) | finding: relation / evidence_type / addresses / definition_mismatch / key_quote / justification |
| Reconciliation | RECONCILIATION_INSTRUCTION_V211 | challenges + counter-evidence + **ตาราง review พร้อม validation_status / period / statement_time** | label + citations + assessments |

- **Prompt 1–4 ของอาจารย์ไม่อยู่ใน repo จึงยังเทียบแบบคำต่อคำไม่ได้** ต้องให้ผู้วิจัยส่งมา
- **การแยก direct contradiction / qualifying / ไม่มีหลักฐานแย้ง:**
  - **direct:** CONTRADICTS (reviewer) / CHALLENGE_SUPPORTED (reconciliation)
  - **ไม่มี:** NO_RELEVANT_EVIDENCE / IRRELEVANT และ prompt บังคับว่า "Absence of evidence never supports a challenge"
  - **qualifying:** **ไม่มีคลาสแยก** อยู่ใน RELATED_NOT_DECIDING จึงเป็นช่องว่างที่แก้ได้เฉพาะใน version ถัดไป
- **Reconciliation ได้รับหลักฐานอะไร:** ได้ทั้ง counter-evidence ดิบและตารางที่ผ่าน validation แต่**คำตอบเด็ดขาดสุดท้ายต้องผ่าน guard + E1** ซึ่งรับเฉพาะ finding ที่ VALID (หรือกฎ numeric / deterministic ที่ผ่าน N1) เหตุผลที่ไม่มี citation จึงตัดสินไม่ได้
- **E1 ทำตามข้อกำหนดของอาจารย์โดยตรง:** ก่อนมี E1 พบคำตอบเด็ดขาดที่ไม่มีหลักฐานรองรับ 3 ข้อ

## Phase 5: Numerical และ causal audit

- **FCF (N2):** ตรวจ XBRL ของ AMZN-07 แล้ว
  - **H1 2026:** OCF 71,419M − capex 98,411M = **−26,992M**
  - **H1 2025:** OCF 49,530M − capex 57,202M = **−7,672M**
  - ทุกตัวเป็น 10-Q 0001018724-26-000026 หน่วย USD งวดตรง
  - **ข้อจำกัด:** tag `PaymentsToAcquireProductiveAssets` เป็นยอดรวม ส่วน FCF ของ Amazon หัก proceeds / incentives **ทิศทางในข้อนี้ไม่เปลี่ยน** (OCF +21.9B < capex +41.2B) แต่ขนาดจะต่างจากที่บริษัทรายงาน
- **N1:** ใช้ทั้งหมด 3 ครั้ง ไม่พบ PERIOD_MISMATCH ในข้ออื่นเลย แปลว่าข้อสรุปตัวเลขอื่นของ A2 ใช้งวดถูก
- **Synthetic tests (`tests/test_a3v2_2_prep.py`):**
  - multiple causes (50% ไม่นับว่าเป็นสาเหตุหลัก, ปัจจัยอื่นใหญ่กว่า → FALSE)
  - missing denominator → UNVERIFIED
  - incomplete disclosure → NOT_REPORTED
  - one-time gain (ระบบรายงานตามตัวเลข ไม่ซ่อน)
  - scope ผิด passage → UNVERIFIED
  - largest factor เสมอกัน → UNDECIDED
  - instant period, forward claim, ±10 วัน, งวดไม่ระบุ
  - FCF ขาดไตรมาส → UNVERIFIABLE
  - **พบ bug 1 จุดและแก้แล้ว:** ค่า prior = 0 ที่ filing พิมพ์เป็น "—" ทำให้ verify ไม่ผ่าน ผลบน dev ไม่เปลี่ยน
- **Bug ของ numeric parser (PG-12, `< None`):** แยกเป็น workstream ไม่ได้แก้ใน A2 และ E1 ทำให้ A3 ไม่ใช้ผลนั้นแล้ว

## Phase 6: Final candidate

| เกณฑ์ | v2.2 (ก+ง) | v2.2c (+ข) | **v2.2e (+E1)** |
|---|---|---|---|
| ความถูกต้องของกลไก | ดี แต่มีคำตอบเด็ดขาดที่ไม่มีหลักฐาน 3 ข้อ | เพิ่มขั้นดึงตัวเลขด้วย LLM แต่ตรวจซ้ำแบบ deterministic | **ทุกคำตอบเด็ดขาดมีหลักฐานที่ผ่านการตรวจ** |
| Regression บน dev | 2 | 2 | 3 |
| Evidence sufficiency | บางส่วน | บางส่วน | **ครบ** |
| ความเสี่ยง overfitting | D-sup เป็น post hoc | **สูงสุด:** แก้ 2 จุดหลังเห็นผล | E1 มาจากข้อกำหนดของอาจารย์ แต่ผล dev เห็นหลังใส่ |
| LLM call ต่อ claim (A3) | 5 | 5 (+1 ใน ~19% ของ claim) | 5 |
| ต้นทุนต่อ claim | ≈ $0.137 | +$0.026 ต่อ claim ที่เข้าข่าย | ≈ $0.137 |
| Latency ต่อ claim (median, v2.1.1 live) | ≈ 50 วิ + decidability | + extraction | ≈ 50 วิ + decidability |
| สอดคล้องกับ A3.15 | บางส่วน | บางส่วน | **ตรงที่สุด** |

**เลือก v2.2e เป็น final candidate**
- เหตุผลคือ**คุณภาพของหลักฐาน** ไม่ใช่ accuracy: ทุกคำตอบเด็ดขาดอ้างหลักฐานที่ผ่าน validation ได้ และตรงกับ A3.15 ของอาจารย์
- **ไม่เลือก v2.2c:** ต้องแก้กฎหลังเห็นผล และเพิ่ม LLM call แม้คะแนนบน dev จะสูงกว่า 1 ข้อ
- **ทั้ง v2.2 และ v2.2c ไม่รันบน Gold:** ลดปัญหาทดสอบหลายครั้งและป้องกันการเลือกผลภายหลัง

## Phase 7: Evaluation readiness

| รายการ | สถานะ |
|---|---|
| Code bundle (44 ไฟล์) | sha256 บันทึกใน `08_preregistration_gold150.md` ✅ **ต้อง commit ก่อนรัน** |
| Prompts | review 0.3, decidability 0.1, reconciliation V211 อยู่ใน config versions ✅ |
| Model | claude-sonnet-4-5-20250929, temperature 0 ✅ |
| Config / retrieval | `configs/a3v2_2_gold150.json` (top_k 6, chunk 1200/200, budget 6 call / 80k token) ✅ |
| Candidate | A3v2_2e (hash `5bf41b202ff248b0`) ✅ |
| Gate กัน Gold | ระบบปฏิเสธจนกว่าแผนจะ LOCKED และ hash ตรง ✅ |
| Prediction / evidence / token log | `predictions.jsonl` + trace รายข้อ (llm_calls พร้อม token / latency, rule_trace, decidability / numeric / coverage) ✅ |
| Cost ledger | ใหม่ `a3v2.2-gold150` cap $30 ⏳ (ต้องอนุมัติ) |
| Primary endpoint | paired accuracy difference เทียบ A2 + McNemar exact + bootstrap CI ✅ (`a3v2_gold_evaluate.py` ตรวจกับ v1 ได้ตรง) |
| Secondary / descriptive | macro-F1, INSUFF recall, correction / regression, latency, cost ✅ |
| Contamination statement | semi-held-out (ดู Phase 1) ✅ |
| Tests | 306 passed ✅ |

**ประมาณการต้นทุน:**
- ตัว plan ได้ typical $27 / upper bound $145 เพราะนับ request ของ R ซ้ำ
- **ค่าจริงประมาณ $21–22** = A2 150 × $0.020 + R 150 × $0.118 + decidability 150 × $0.008
- ขอ **cap $30**
