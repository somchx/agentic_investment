# โครงร่างรายงาน IS ฉบับสมบูรณ์: ReasonCheck

**หัวข้อ:** Evaluating Contradiction-Aware Agentic AI for Evidence-Grounded Financial Claim Verification

**สถานะ:** โครงร่างสำหรับเขียนเล่ม (2026-11-18) ใช้เฉพาะผลที่ freeze แล้ว ไม่มีการทดลองหรือเรียก API เพิ่ม

**แหล่งตัวเลข:** ทุกตัวเลขในบทที่ 4–5 มาจาก `results/is_report/tables/` (สร้างด้วย `scripts/is_report_assets.py` จาก `evaluation.json` ที่ freeze แล้ว) หรืออ้างไฟล์ต้นทางไว้ในวงเล็บ

---

## บทที่ 1 บทนำ

### 1.1 ความเป็นมาและความสำคัญของปัญหา
- ข้อความเกี่ยวกับผลประกอบการ (financial claims) ในข่าว บทวิเคราะห์ และสื่อสังคม มีทั้งตัวเลขและการตีความเชิงสาเหตุ ผู้ลงทุนต้องตรวจกับรายงาน SEC (10-K / 10-Q) ซึ่งยาวและมีตาราง
- LLM ตอบได้คล่องแต่เสี่ยงต่อการตอบเกินหลักฐาน (hallucination / over-claiming) และการอ้างหลักฐานผิดงวด
- แนวคิด agentic / contradiction-aware: ให้ระบบตั้งข้อโต้แย้งต่อคำตอบตนเองแล้วค้นหลักฐานแย้ง เป็นสมมติฐานที่นิยมแต่ยังขาดการประเมินแบบควบคุมในโดเมนการเงิน
- ต่อยอดจากแอป ReasonCheck (ก.ย.–ต.ค. 2026) ไปสู่ระบบวิจัยที่ทำซ้ำได้

### 1.2 คำถามวิจัย
- **RQ หลัก:** การให้ AI ค้นหาหลักฐานที่ขัดแย้ง (contradiction-aware investigation) ช่วยเพิ่มความแม่นยำในการตรวจสอบ financial claims เมื่อเทียบกับ RAG และ RAG + การตรวจตัวเลขแบบ deterministic หรือไม่
- **RQ ย่อย**
  1. การตรวจตัวเลขแบบ deterministic (A2) เพิ่มความแม่นยำจาก RAG (A1) หรือไม่
  2. ผลของ A3 มาจาก "การหักล้าง" หรือจาก "การคิดซ้ำ" (เทียบกับ SR self-reflection ที่ใช้ LLM call ใกล้เคียงกัน)
  3. A3 แลกต้นทุนและเวลาเท่าใด

### 1.3 วัตถุประสงค์
1. พัฒนา pipeline ที่ทำซ้ำได้ ตรวจย้อนหลังได้ (trace ทุก node, cache, manifest, checksum)
2. สร้างชุดทดสอบ 150 claims พร้อมเฉลยที่มีที่มาตรวจสอบได้
3. เปรียบเทียบ A1, A2, A3 (v1 และ v2.2) และ SR อย่างเป็นธรรมภายใต้ preregistration
4. วิเคราะห์ความผิดพลาดเพื่ออธิบายว่าเหตุใดผลจึงเป็นเช่นนั้น

### 1.4 ขอบเขต
- 10 บริษัทใน Gold (AAPL, MSFT, AMZN, GOOGL, NVDA, META, TSLA, NFLX, WMT, KO), 50 numerical / 50 interpretive / 50 ambiguous
- หลักฐานจาก SEC EDGAR (10-K, 10-Q, XBRL company facts) ที่ยื่นก่อน `as_of_date` เท่านั้น
- โมเดลเดียว: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`), temperature 0
- label 3 ค่า: SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE

### 1.5 ประโยชน์ที่คาดว่าจะได้รับ
- หลักฐานเชิงประจักษ์ (รวมผลลบ) ว่าเมื่อใดการเพิ่มขั้น agentic ไม่คุ้ม
- กรอบการประเมินที่ทำซ้ำได้: preregistration, ledger ค่าใช้จ่าย, freeze + checksum

### 1.6 นิยามศัพท์
claim, evidence-grounded, contradiction-aware, guard, decidability, D-sup, E1 coverage, correction / regression vs A2, accepted change precision, preregistration

---

## บทที่ 2 ทฤษฎีและงานวิจัยที่เกี่ยวข้อง
> ต้องเติมแหล่งอ้างอิงจริงในเล่ม (ยังไม่ได้ค้นในรอบนี้)

2.1 Fact verification และ claim verification (เช่น ชุดข้อมูลแบบ FEVER, งานด้าน scientific / financial claim verification)

2.2 Retrieval-Augmented Generation (BM25, dense, hybrid) และข้อจำกัดเรื่อง grounding

2.3 การตรวจตัวเลขทางการเงินและ XBRL (us-gaap concepts, inline XBRL)

2.4 Agentic LLM, self-reflection / self-critique และ debate / adversarial verification

2.5 การประเมินแบบ paired: McNemar exact test, bootstrap CI, Holm correction

2.6 Preregistration และ adaptive overfitting ในการพัฒนาระบบ ML

---

## บทที่ 3 วิธีดำเนินการวิจัย

### 3.1 สถาปัตยกรรมระบบ
- LangGraph pipeline ที่ทุก arm ใช้ขั้นแรกร่วมกัน (retrieval BM25, chunk 1,200 / overlap 200, top-k 6, 10-K ล่าสุด 1 + 10-Q ล่าสุด 2)
- **A1** Conventional RAG: LLM ตัดสินครั้งเดียว
- **A2** RAG + numeric verification: LLM สกัด assertion ตัวเลข → คำนวณจาก XBRL แบบ deterministic
- **SR** self-reflection: คิดซ้ำ 3 call โดยไม่ค้นหลักฐานใหม่ (control)
- **A3 v1** contradiction-aware: hypotheses → counter-retrieval → reconcile → guards
- **A3 v2.1.1 R / RG** และ **A3v2_2e** (final candidate): reviewer + guard 0.3 + quote check 1.1 + decidability (D-sup) + N1/N2 numeric checks + E1 evidence coverage
- ภาพ: graph ของ LangGraph (มีในรายงานความคืบหน้า)

### 3.2 ชุดข้อมูลและเฉลย
- Gold 150: claim ร่างโดย Claude Opus 5.5 จากรายชื่อ filing, 3 LLM annotator (Claude Opus 5.5, Gemini 4 Argon, GPT-6.0 Astra), AI-assisted adjudication, ผู้วิจัยทบทวน → Final Gold v3 (sha256 `e47897c4…`)
- ความเห็นตรงกัน: Fleiss' κ = Krippendorff's α = 0.634 (numerical 0.862, interpretive 0.436, ambiguous 0.377)
- label: SUPPORTED 68 / CONTRADICTED 38 / INSUFFICIENT 44
- dev-v0.2: 72 claims (7 บริษัท, 3 บริษัทซ้ำกับ Gold) label โดยผู้วิจัย + numeric verification (v2 `7dccc43a`) ใช้พัฒนา A3 v2.x

### 3.3 การออกแบบการทดลองและความเป็นธรรม
- claims, คลังเอกสาร, วันตัด, โมเดล, ค่าค้นหาเดียวกันทุก arm; fairness check ใน config
- กันข้อมูลอนาคต (กรองตามวันตัด), กันเฉลยรั่ว (canary test), ห้ามรัน gold โดยไม่เปิด `allow_gold`
- ทุก request ผ่าน cache ที่ key ด้วย hash; การเรียกจริงต้องมีประโยคอนุมัติ + ledger เพดานเงิน

### 3.4 Preregistration (v2.2)
- `08_preregistration_gold150.md` LOCKED (sha256 `ffad4375…`) ก่อนรัน: primary = A3v2_2e vs A2 (McNemar exact), secondary 3 คู่ (Holm), AC1–AC7, กติกา ERROR / NO_FINAL_VERDICT
- Amendment 1 (`12_…`): รันใหม่ทั้งชุดหลังเหตุขัดข้องทางเทคนิค (worktree ถูกลบระหว่างรัน, ไม่เคยเทียบผลรอบนั้นกับเฉลย)

### 3.5 Metrics และสถิติ
accuracy, macro-F1, INSUFFICIENT recall, accuracy แยกหมวด, correction / regression vs A2, accepted decisive change precision, tokens, LLM calls, API latency, cost (list price); McNemar exact, paired bootstrap 10,000 รอบ (seed 20261118), Holm

### 3.6 การควบคุมความน่าเชื่อถือ
freeze + SHA256SUMS ของทุก run, code bundle hash (`c4d2112f…`), corpus pin ด้วย content hash, run log แบบ append-only, backup ระหว่างรัน

---

## บทที่ 4 ผลการวิจัย

### 4.1 ผลรอบ v1 (A1 / A2 / A3 v1)
- A1 → A2: +6.0 pp, 95% CI [+2.0, +10.7], McNemar p = 0.012 (มีนัยสำคัญ)
- A2 → A3 v1: −4.7 pp, CI [−10.7, +1.3], p = 0.21 (ไม่มีนัยสำคัญ), ต้นทุน 4.2 เท่า
- sensitivity ต่อเกณฑ์ให้คะแนน 3 แบบ: ข้อสรุปเชิงสถิติไม่เปลี่ยน

### 4.2 ผลหลักรอบ v2.2 ตาม preregistration
- **ตาราง 4.1** ผลหลัก 7 arm (`T4_1_main_results.csv`) + **ภาพ 4.1** (`F4_1_accuracy_ci`)
  - A2 103/150 (68.7%) สูงสุด, SR 102 (68.0%), A3v2_2e 98 (65.3%)
- **ตาราง 4.2** การทดสอบแบบจับคู่ + **ภาพ 4.2** (`F4_2_paired_differences`)
  - primary: A3v2_2e − A2 = −3.3 pp, CI [−10.0, +3.3], p = 0.424, Holm 1.0
  - ทุกคู่ secondary Holm = 1.0
- **ตาราง 4.3** acceptance: AC1–AC4 ไม่ผ่าน, AC5–AC7 ผ่าน
- **ข้อสรุป:** ไม่ปฏิเสธสมมติฐานว่าง; A3v2_2e ไม่ดีกว่า A2

### 4.3 ผลแยกตามประเภท claim
- **ภาพ 4.3** (`F4_3_accuracy_by_category`): numerical ทุก arm 94–96%; interpretive A2 60% / SR 68% / A3v2_2e 50%; ambiguous 52% / 42% / 50%
- รายงานเชิงพรรณนา (n = 50 ต่อหมวด ไม่ทดสอบ)

### 4.4 การแก้ถูกและทำพังเทียบ A2
- **ตาราง 4.4** + **ภาพ 4.4** (`F4_4_correction_regression`): A3v2_2e แก้ถูก 10/47, ทำพัง 15/103, accepted change precision 4/10
- SR แก้ถูกมากที่สุด (17) แต่ทำพัง 18

### 4.5 ประสิทธิภาพและต้นทุน
- **ตาราง 4.5** + **ภาพ 4.5** (`F4_5_cost_vs_accuracy`): median ต่อ claim A2 $0.019 / 9.7 วินาที, SR $0.072 / 35 วินาที, A3v2_2e $0.141 / 60 วินาที (≈ 7 เท่าของ A2)
- ค่าใช้จ่ายจริงของ run ทางการ $23.24 (+ รอบที่ขัดข้อง ≈ $22.5, รอบ v1 $12.25)

### 4.6 Confusion matrix (ตาราง 4.6)
- A2 ผิดสองทิศ: ตอบเด็ดขาดเกินหลักฐาน (gold I → S/C 23 ข้อ) และพลาดข้อที่ถูกแย้ง (gold C → I 11 ข้อ)

---

## บทที่ 5 อภิปรายผล สรุป และข้อเสนอแนะ

### 5.1 สรุปผล
- การตรวจตัวเลขแบบ deterministic คือส่วนที่เพิ่มความแม่นยำได้จริงและถูก
- การค้นหาหลักฐานแย้งแบบ agentic (ทั้ง v1 และ v2.2) ไม่เพิ่มความแม่นยำเหนือ A2 และแพงกว่ามาก

### 5.2 อภิปราย: ทำไม A3 ไม่ชนะ (จาก `13_gold150_posthoc_error_analysis.md`, exploratory)
- **ตาราง 5.1 + ภาพ 5.2** (`F5_2_change_mechanism`): reviewer + guard 3 / 6, D-sup 0 / 3, E1 6 / 5, N1 1 / 1
- guard ตรวจรูปแบบหลักฐาน (quote, งวด) แต่ไม่ตรวจความหมาย: รับข้อเสนอเสีย 7/13 รับข้อเสนอดี 4/10
- ชั้นตรวจหลักฐานตัดหลักฐานที่ถูกต้อง (finding ถูก downgrade 109/439 ส่วนใหญ่เป็นข้อความจากตาราง) แล้ว E1 ลดคำตอบเป็น INSUFFICIENT
- ความผิดพลาดเปลี่ยนจาก over-interpretation (v1: I → decisive 10/15) เป็น over-abstention (v2.2: decisive → I 11/15)
- claim เชิงสาเหตุ / ตีความเป็นจุดอ่อนหลัก ขณะที่ SR ทำได้ดีกว่าในหมวดนี้
- retrieval ไม่ใช่สาเหตุหลักของ regression

### 5.3 อภิปราย: ผลบน dev ไม่ generalize
- **ตาราง 5.2 + ภาพ 5.1** (`F5_1_dev_vs_gold`): dev +11 (64 vs 53) → Gold −5 (98 vs 103)
- dev ถูกใช้พัฒนาหลายรอบ (adaptive overfitting), สัดส่วน INSUFFICIENT บน dev สูงกว่า (37.5% vs 29.3%)
- นี่คือเหตุผลที่ preregistration และชุดทดสอบที่ไม่แตะจำเป็น

### 5.4 ข้อจำกัดของงานวิจัย
ดู `02_limitations_and_committee_questions.md` หัวข้อ A

### 5.5 ข้อเสนอแนะสำหรับงานในอนาคต (ไม่ได้ดำเนินการ)
- ตัวแทนหลักฐานแบบมีโครงสร้าง (ตารางระดับเซลล์, inline XBRL ที่มี segment, period ระดับประโยค)
- ตรวจระดับ assertion และเกณฑ์ที่นิยามร่วมกับ annotator ("primarily", materiality)
- selective verification เช่น A4 (exploratory บน dev: 63/72, precision ของการเปลี่ยน 11/12 แต่ยังไม่ทดสอบบนข้อมูลใหม่)
- dataset ใหม่ที่มนุษย์ annotate และ blind test แยกบริษัท (`14_next_generation_research_plan.md`)

### 5.6 บทสรุป
ผลลบที่ได้ตาม preregistration: ในงานนี้ ความแม่นยำมาจากการคำนวณที่ตรวจสอบได้มากกว่าการให้ LLM คิดหรือโต้แย้งเพิ่ม

---

## ภาคผนวก (เสนอ)
- ก. Preregistration 08 + Amendment 12
- ข. Run log 10 และรายงานเหตุขัดข้อง 11
- ค. Post-hoc error analysis 13 (ระบุว่า exploratory)
- ง. ตารางรายข้อ 25 ข้อที่ A3v2_2e ต่างจาก A2
- จ. รายการ hash / checksum และวิธีตรวจซ้ำ
- ฉ. A4 offline feasibility (exploratory)
