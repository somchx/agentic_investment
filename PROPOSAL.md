# Agentic AI for Evidence-Grounded Revalidation of Investment Assumptions

**ชื่อหัวข้อเดิม (วิสัยทัศน์ระยะยาวของโปรเจกต์):**
Trustworthy Agentic AI for Continuous and Personalized Investment Decision Support

**ชื่อภาษาไทย:**
AI ที่ช่วยตรวจว่า "เหตุผลแต่ละข้อที่เราใช้ลงทุน ยังเป็นจริงอยู่ไหม" โดยอ้างอิงข้อมูลจริงที่มีอยู่ ณ เวลานั้น

> **หมายเหตุเรื่อง Scope:** เอกสารนี้อธิบายทั้งวิสัยทัศน์ระยะยาวของระบบ (สิ่งที่อยากให้เป็นในที่สุด) และ **Scope จริงที่จะลงมือทำก่อนสำหรับ Independent Study** ซึ่งแคบกว่ามากและตรวจสอบได้ด้วยตัวเลขล้วน ๆ ดูรายละเอียดที่ [ส่วนที่ 3.1 Phased Scope](#31-phased-scope-สิ่งที่ทำจริงก่อน)

---

## บทคัดย่อ (Abstract)

งานวิจัยนี้นำเสนอระบบ Agentic AI ที่ไม่ได้ทำหน้าที่ "แนะนำว่าควรซื้อหุ้นอะไร" แต่ทำหน้าที่ **จดจำเหตุผลที่นักลงทุนใช้ตัดสินใจลงทุนในหุ้นแต่ละตัว แล้วติดตามอย่างต่อเนื่องว่าเหตุผลเหล่านั้นยังคงเป็นจริงอยู่หรือไม่** เมื่อมีข้อมูลใหม่เข้ามา (งบการเงิน, Earnings Call, ข่าว, ราคาตลาด) ระบบจะให้ Agent สืบค้นหลักฐานทั้งฝั่งสนับสนุนและฝั่งขัดแย้งอย่างจงใจ (forced dual-sided evidence retrieval) ตรวจสอบความขัดแย้งระหว่างแหล่งข้อมูล ประเมินผลกระทบต่อเหตุผลการลงทุนแต่ละข้อแบบมีหลักฐานอ้างอิง (evidence-grounded) และปรับคำแนะนำให้สอดคล้องกับ Portfolio และข้อจำกัดความเสี่ยงของผู้ลงทุนแต่ละคน ระบบจะงดฟันธง (abstain) เมื่อหลักฐานไม่เพียงพอ และเรียก Human-in-the-loop เมื่อกรณีมีความซับซ้อนหรือความเสี่ยงสูง งานวิจัยนี้มุ่งวัด **คุณภาพและความน่าเชื่อถือของกระบวนการตัดสินใจ (decision process quality)** มากกว่าความสามารถในการทำกำไร โดยเปรียบเทียบกับ LLM ธรรมดา, RAG, และ Agentic RAG ทั่วไป

เพื่อให้พิสูจน์แนวคิดได้จริงภายในเวลาของ Independent Study **ระยะแรกของงานจะจำกัดเฉพาะเหตุผลการลงทุนที่ตรวจสอบได้ด้วยตัวเลขจากงบการเงินโดยตรง** (เช่น Revenue Growth, Operating Margin, Debt Ratio) ซึ่งทำให้ Ground Truth ชัดเจนไม่ต้องพึ่ง Human Labeling จำนวนมาก ส่วนเหตุผลเชิงคุณภาพ (Demand, Management Confidence) และแหล่งข้อมูลที่ตีความยาก (News, Earnings Call Transcript) จะถูกเลื่อนไปเป็น Phase 2

### Research Question

> Agentic AI ที่สามารถติดตามและตรวจสอบเหตุผลในการลงทุนจากหลักฐานแบบ Point-in-Time และนำผลที่ได้มาวิเคราะห์ร่วมกับบริบทเฉพาะของนักลงทุนแต่ละคน สามารถให้ Decision Support ที่มีหลักฐานรองรับ สอดคล้องกับความเสี่ยงและพอร์ตของผู้ใช้ และรู้ว่าเมื่อใดควรสืบค้นเพิ่มเติมหรือส่งต่อให้มนุษย์ได้หรือไม่?

คำถามนี้แยกได้เป็น 2 ส่วนที่ต้องพิสูจน์แยกกัน (ดู [Contribution 1–2](#3-research-contribution-หลัก) สำหรับส่วนแรก และ [Contribution 4](#contribution-4--personalized-decision-support-layer) สำหรับส่วนหลัง): (ก) การประเมิน "สถานะเหตุผล" จากหลักฐานเชิงวัตถุ (objective, ไม่ personalize) และ (ข) การแปลสถานะนั้นเป็น "ผลกระทบต่อผู้ลงทุนคนนี้" โดยเฉพาะ (subjective ต่อ profile แต่ไม่บิดข้อเท็จจริง)

---

## 1. ที่มาและปัญหา (Motivation)

นักลงทุนที่ถือหุ้นหลายตัวต้องเผชิญข้อมูลใหม่จำนวนมากทุกวัน (ข่าว, งบการเงิน, คำแถลงผู้บริหาร, ราคาตลาด) และต้องตอบคำถามเหล่านี้ด้วยตัวเองตลอดเวลา:

- ข่าวไหนเกี่ยวข้องกับหุ้นที่ตนถืออยู่?
- ข่าวนั้นกระทบ "เหตุผล" ที่เคยใช้ตัดสินใจซื้อหุ้นข้อไหน?
- เป็นเรื่องสำคัญจริง หรือแค่ Noise?
- แหล่งข้อมูลต่าง ๆ พูดตรงกันหรือขัดแย้งกัน?
- ตนเองกำลัง Bias เข้าข้างหุ้นที่ชอบอยู่หรือไม่?

เครื่องมือ AI ทางการเงินที่มีอยู่ในปัจจุบันส่วนใหญ่วิเคราะห์แบบ "ครั้งเดียวจบ" (one-shot analysis) ให้คำตอบที่ฟังดูมั่นใจแต่ขาดการอ้างอิงหลักฐานที่ตรวจสอบได้ และไม่ได้ปรับให้เหมาะกับบริบทเฉพาะของผู้ลงทุนแต่ละคน งานวิจัยนี้จึงเสนอระบบที่เปลี่ยนมุมมองจาก **"AI ทำนายหุ้น"** ไปเป็น **"AI ที่ติดตามและทบทวนเหตุผลการลงทุนอย่างมีหลักฐานและต่อเนื่องตามเวลา"**

**มุมมองเชิงทฤษฎีที่งานนี้ยืมมาจากแนวคิด Model Drift**: ในบริบทของ Machine Learning, Model Drift คือปรากฏการณ์ที่โมเดลซึ่งฝึกจากข้อมูลอดีตเริ่มทำงานผิดพลาดเมื่อโลกจริงเปลี่ยนไปจากช่วงที่ใช้ฝึก (data distribution เปลี่ยน) จึงต้องมี Model Monitoring คอยตรวจจับ ไม่ใช่ฝึกครั้งเดียวแล้วใช้ตลอดไป งานวิจัยนี้นำ insight เดียวกันมาใช้กับ **ความเชื่อของนักลงทุน** แทนที่จะเป็นโมเดล ML: เหตุผลที่นักลงทุนใช้ตัดสินใจซื้อหุ้น ณ วันหนึ่ง (เช่น "Operating margin จะสูงกว่า 20%") ไม่ได้ "drift" ไปเอง แต่ **โลก (ปัจจัยพื้นฐานของบริษัท) ต่างหากที่ drift ไปจากตอนตั้งเหตุผลนั้น** — และเช่นเดียวกับที่ ML System ที่ดีต้องมี Monitoring คอยจับสัญญาณว่าโมเดลเริ่มเพี้ยนจากโลกจริง นักลงทุนก็ต้องมีกลไกที่คอยเทียบ "เหตุผลตอนซื้อ" กับ "หลักฐานล่าสุด" อย่างต่อเนื่อง แทนที่จะเชื่อเหตุผลเดิมไปเรื่อย ๆ โดยไม่ตรวจสอบซ้ำ — นี่คือหัวใจของ Contribution 1 (Continuous Revalidation) ที่อธิบายด้วยกรอบคิดเดียวกับที่ใช้อธิบายความเสื่อมของโมเดล ML ใน Production

---

## 2. ช่องว่างงานวิจัย (Research Gap)

| Gap ที่พบในงานปัจจุบัน | แนวทางแก้ไขของโปรเจกต์นี้ |
|---|---|
| AI วิเคราะห์หุ้นแบบครั้งเดียว (one-shot) | ติดตามเหตุผลเดิมต่อเนื่องตามเวลา (Continuous Revalidation) |
| AI สรุปผลลัพธ์โดยไม่มีหลักฐานรองรับเพียงพอ | ทุกข้อสรุปต้องผูกกับ Evidence ที่ตรวจสอบย้อนกลับได้ |
| ข้อมูลจากหลายแหล่งขัดแย้งกันแต่ไม่ถูกจัดการอย่างเป็นระบบ | มีกลไก Evidence Conflict Resolution |
| AI มักค้นหาแต่ข้อมูลที่สนับสนุนสมมติฐานเดิม (confirmation bias) | บังคับให้ค้นหาทั้ง Supporting และ Contradicting Evidence |
| เหตุผลของ AI เปลี่ยนแปลงไปโดยไม่มีการบันทึกที่มา | มี Reasoning Version / Decision Ledger |
| AI เผลอใช้ข้อมูลอนาคตเวลาทำ Backtest (lookahead bias) | ใช้ Point-in-Time Retrieval อย่างเคร่งครัด |
| AI ฟันธงคำตอบทั้งที่ข้อมูลไม่เพียงพอ | มีกลไก Insufficient Evidence / Abstention |
| หุ้นตัวเดียวกันถูกวิเคราะห์เหมือนกันสำหรับทุกคน | วิเคราะห์ร่วมกับ Investor Profile และ Portfolio ของแต่ละคน |
| AI รู้ข้อจำกัดของผู้ใช้แต่ยังแนะนำสิ่งที่ขัดกับข้อจำกัดนั้น | มี Constraint Checker ก่อนเสนอ Action ใด ๆ |
| เหตุการณ์หนึ่งอาจกระทบหลายทอดแต่ไม่ถูกสืบสาวอย่างเป็นระบบ | มี Event → Business Impact → Financial Metric → Investment Reason Reasoning |
| ไม่มีกลไกบอกว่าเมื่อไรควรให้มนุษย์เข้ามาตรวจสอบ | Adaptive Human-in-the-Loop |
| งานวิจัยเดิมส่วนใหญ่วัดผลที่ "กำไร" | งานนี้วัด "คุณภาพของกระบวนการตัดสินใจ" |

---

## 3. Research Contribution หลัก

เพื่อควบคุมขอบเขตงานวิจัยไม่ให้กว้างเกินไป โปรเจกต์นี้กำหนด Contribution ที่ **implement และวัดผลจริงภายใน IS นี้ไว้ 3 ข้อ คือ Contribution 1, 2 และ 4** ส่วน Contribution 3 เป็นวิสัยทัศน์ระยะยาวที่เกินขอบเขต (ดูเหตุผลใน [Contribution 3](#contribution-3--full-personalized--constraint-aware-decision-support-วิสัยทัศน์ระยะยาว)) กลไกอื่นนอกจากนี้ (Time-aware retrieval, Abstention, Human review, Reasoning versioning, Evidence citation) ถูกจัดเป็น **กลไกสนับสนุนความน่าเชื่อถือของระบบ (trust-enabling mechanisms)** ไม่ใช่ Contribution แยกต่างหาก

### Contribution 1 — Continuous Investment Reason Revalidation
ติดตามว่าเหตุผลแต่ละข้อในการตัดสินใจลงทุน (เช่น Revenue Growth, Margin, Debt, Demand) มีสถานะเปลี่ยนแปลงอย่างไรตามเวลา (Supported / Weakened / Broken / Uncertain) แทนที่จะวิเคราะห์ใหม่ทุกครั้งแบบไม่มีความต่อเนื่อง

### Contribution 2 — Evidence Conflict-Aware Reasoning
เมื่อหลักฐานจากหลายแหล่งขัดแย้งกัน Agent ต้องรู้จักตรวจสอบเพิ่มเติม ประเมินความน่าเชื่อถือของแต่ละแหล่ง และไม่เฉลี่ยข้อมูลเพื่อสรุปแบบกลาง ๆ ในวิสัยทัศน์ระยะยาว ความขัดแย้งนี้ครอบคลุมถึงกรณีเชิงคุณภาพ (เช่น Management Guidance บอกว่า Demand ยังดี แต่ข่าวบอกว่าลูกค้ารายใหญ่ลด Order) แต่ **ใน Phase 1 จะจำกัดเฉพาะความขัดแย้งเชิงตัวเลขที่ตรวจสอบได้ชัดเจน** เช่น ตัวเลขที่บริษัทประกาศเบื้องต้นใน Earnings Release กับตัวเลขที่ถูก Restate ใน 10-Q ฉบับทางการภายหลัง หรือ Analyst Estimate กับ Actual — ยังอยู่ในโดเมนตัวเลขล้วน ๆ แต่มีของจริงให้ Agent ต้อง "ตัดสินใจว่าจะเชื่อแหล่งไหน" ไม่ใช่แค่คำนวณอย่างเดียว

### Contribution 3 — Full Personalized & Constraint-Aware Decision Support (วิสัยทัศน์ระยะยาว)
ผลกระทบของเหตุการณ์เดียวกันอาจมีนัยยะไม่เหมือนกันสำหรับนักลงทุนแต่ละคน เนื่องจากสัดส่วนใน Portfolio เป้าหมายการลงทุน และข้อจำกัดความเสี่ยงต่างกัน ระบบเวอร์ชันเต็มต้องมี Portfolio Database จริง, Constraint Checker ที่ตรวจสอบ Compliance เชิงกฎ, และ Macro Data ประกอบ — **นี่คือวิสัยทัศน์ระยะยาวที่เกินขอบเขต IS นี้** ยังคงเป็น Phase 3 ของ [3.1 Phased Scope](#31-phased-scope-สิ่งที่ทำจริงก่อน) และเป็น Future Work (ดู [12. งานในอนาคต](#12-งานในอนาคต))

### Contribution 4 — Personalized Decision Support Layer (เวอร์ชันย่อที่ Implement จริงใน IS นี้)
เพื่อตอบ Research Question ในส่วนที่สอง โดยไม่ขยาย scope ไปเต็มรูปแบบของ Contribution 3 งานนี้ implement **เวอร์ชันย่อที่พิสูจน์แนวคิดได้จริง**: แยกระบบเป็น 2 ชั้นอย่างเคร่งครัด

- **ชั้นที่ 1 — Objective Evidence Layer** (ของเดิม ไม่เปลี่ยน): สถานะเหตุผล Supported / Weakened / Broken / Not enough data ที่คำนวณจากหลักฐานล้วน ๆ **ห้าม personalize** — ข้อเท็จจริงต้องเหมือนกันสำหรับทุกคน
- **ชั้นที่ 2 — Investor Context Layer** (ใหม่): รับผลจากชั้นที่ 1 มาประกอบกับ Investor Profile (`risk_tolerance`, `investment_horizon`, `position_size_pct`, `objective`) แล้วตัดสิน **priority tier** (Monitor / Watch / Review Soon / Review Now) พร้อมคำอธิบายว่าทำไมเรื่องนี้ถึงสำคัญ/ไม่สำคัญกับผู้ใช้คนนี้

ตัวอย่างที่ระบบต้องแสดงให้เห็นได้จริง: เหตุผล "Debt growth" ของบริษัทเดียวกัน Broken เหมือนกันสำหรับทุกคน (ชั้น 1 ไม่เปลี่ยน) แต่ Investor A (position 3%, horizon 10 ปี, risk สูง) ได้ tier "Monitor" ในขณะที่ Investor B (position 25%, horizon 1 ปี, risk ต่ำ) ได้ tier "Review Now" จากหลักฐานชุดเดียวกัน

**Decision logic เป็นแบบ Hybrid:** LLM เป็นคนตัดสิน priority tier โดยรับทั้ง evidence status (คงที่ ห้ามเปลี่ยน) และ investor profile เป็น input — ข้อดีคือยืดหยุ่นกว่า rule matrix ล้วน ๆ (จับ interaction ระหว่างปัจจัยได้ดีกว่า) แต่ข้อเสี่ยงคือ LLM อาจ "เผลอ" ไปปรับสถานะ evidence เองแทนที่จะปรับแค่ tier ดังนั้นงานนี้ต้องมี **Evidence Integrity Safeguard Experiment** กำกับไว้เสมอ: ป้อน evidence status เดียวกันให้ LLM ภายใต้ investor profile ที่ต่างกันหลายแบบ แล้ววัดว่า status ที่ LLM สะท้อนกลับมาคงที่ 100% หรือไม่ (ถ้าไม่คงที่ = personalization รั่วเข้าไปบิดข้อเท็จจริง ซึ่งเป็นความล้มเหลวที่ต้อง flag ทันที) และเทียบกับ rule-based tier เป็น reference baseline เพื่อดูว่า LLM ตัดสิน tier ได้สมเหตุสมผลกว่าหรือไม่ในเคสที่ต่างกัน

**ผลการทดลองจริง (implement และวัดผลแล้ว — ดูรายละเอียดใน README.md หัวข้อ "Personalization layer"):** รันจริง 68 calls งบ **$0.341** (ต่ำกว่า cap $1 ที่ตั้งไว้) บน 17 เคส (15 เคสที่ status ไม่ใช่ Supported + 2 เคส Supported เป็น control) × 4 investor profile สังเคราะห์

- **Evidence integrity: 68/68 ผ่าน (100%)** — LLM ไม่เคยเปลี่ยน evidence status เองแม้แต่ครั้งเดียว พิสูจน์ว่าสถาปัตยกรรม 2 ชั้นทำงานตามที่ออกแบบจริง ไม่ใช่แค่ทฤษฎี
- **15/17 เคสได้ priority tier ต่างกันตาม profile** ส่วน 2 เคสที่ไม่ต่างคือ 2 เคส Supported control พอดี (ได้ "Monitor" ทุก profile ตามที่ rule-based กำหนดไว้) — reproduce ตัวอย่าง Investor A vs B ที่ยกไว้ตอนออกแบบได้ครบทุกเคสที่มี evidence ไม่ Supported
- **Agreement กับ rule-based baseline แค่ 41.2%** แต่มีทิศทางชัดเจน ไม่ใช่ noise: **LLM ให้ tier สูงกว่าหรือเท่ากับ rule เสมอ ไม่เคยต่ำกว่า** — โดยเฉพาะ profile position เล็ก/risk สูง ที่ rule ยอมให้ position size หักล้าง severity ได้เต็มที่กลับไปเป็น Monitor แต่ LLM มักตั้ง floor ไว้ที่ Watch เสมอเมื่อ evidence เป็น Broken/Weakened — สะท้อนปรัชญาการตัดสินใจที่ต่างกันระหว่าง rule matrix (severity กับ position หักล้างกันได้เต็มที่) กับ LLM (severity เป็นฐานที่ profile ปรับได้บางส่วนแต่ล้างไม่หมด) เป็นประเด็นที่ควรพูดถึงใน Discussion ไม่ใช่ตัดสินว่าอันไหน "ถูกกว่า"

**Pipeline wiring (เพิ่มหลัง design review):** เดิม Contribution 1/2 (evidence status จาก Agent) กับ Contribution 4 (personalization) เป็นคนละสคริปต์ที่ต้องรันแยกแล้ว copy ผลมาต่อกันเอง (`run_full_experiment.py` แล้วเอา status ไปป้อน `run_personalization_experiment.py`) ตอนนี้มีฟังก์ชัน `investigate_and_personalize(ticker, profile)` (`personalization.py`) ต่อท่อ `agent.run_with_llm()` → `rule_based_tier()`/`llm_tier()` ให้อัตโนมัติในเรียกเดียว — ทดสอบจริงกับ GOOGL + investor profile จริง ได้ status/rule_tier/llm_tier/integrity_ok ครบในผลลัพธ์เดียว ยืนยันว่า Contribution 1/2 กับ 4 เป็น pipeline เดียวกันจริง ไม่ใช่แค่ 2 experiment ที่บังเอิญใช้ข้อมูลร่วมกันได้

ข้อมูลเต็มอยู่ที่ `data/personalization_experiment_results.json`

Scope ที่ตัดออกจาก Contribution 4 (ยกให้ Contribution 3 / Future Work): ไม่มี Portfolio Database ที่ผูกกับมูลค่า/สัดส่วนตลาดจริง (มีแค่ลิสต์ ticker ที่ถือ), ไม่มี Constraint Checker เชิงกฎที่ตรวจ Compliance, ไม่มี Macro Data

**อัปเดต (เพิ่มหลังจากนี้):** สองข้อที่เคยขึ้นว่า "ยังทำไม่ได้" ใน Manual ของเว็บ (กำหนดเหตุผลเอง, มุมมองพอร์ตรวม) **ทำจริงแล้วทั้งคู่** และยังฟรี 100% (ไม่มี LLM):
- **กำหนดเหตุผลเอง** — แก้ปัญหาความเสี่ยงเดิม (พิมพ์ metric ผิดชื่อ tag) ด้วยการให้เลือกจาก dropdown ที่ดึงจาก tag จริงที่บริษัทนั้นเคยรายงานเท่านั้น (`xbrl_extract.list_available_tags`) ไม่ใช่พิมพ์เอง — พิมพ์ผิดไม่ได้เพราะเลือกจากของจริง เชื่อมเข้ากับ `check_reason_status`/`calculate_metric` ผ่าน `get_reason_def()` ที่เช็คทั้ง built-in และ DB
- **มุมมองพอร์ตรวม** — เพิ่ม `holdings` table + หน้า "My Portfolio" ใช้ logic เดิมจาก `get_company_report` วนดูทุกบริษัทที่ถือ รวมสถานะ + ให้คลิกดูรายละเอียดแต่ละบริษัทได้

ทดสอบจริงทั้งคู่ฟรี (SEC data ล้วน ไม่มี LLM) ผ่าน UI จริงทุก flow (ดูรายละเอียดใน README.md)

---

## 3.1 Phased Scope (สิ่งที่ทำจริงก่อน)

เพื่อไม่ให้ต้องสร้างทั้งระบบตามวิสัยทัศน์ตั้งแต่วันแรก งานจะแบ่งเป็น 3 เฟส แต่ละเฟสต้อง "วิ่งจบ end-to-end" ก่อนขยาย:

### Phase 1 — Numeric-Only Thin Vertical Slice (เป้าหมายหลักของ Independent Study)
- **ขอบเขตเหตุผล:** เฉพาะเหตุผลที่ตรวจสอบได้ตรงจากตัวเลขในงบการเงิน เช่น
  - "Revenue growth ต้องมากกว่า 10%"
  - "Operating margin ต้องไม่ต่ำกว่า 20%"
  - "Debt ต้องไม่เพิ่มเกิน 15%"
- **ขอบเขตข้อมูล:** SEC 10-Q / 10-K (ผ่าน SEC XBRL / Financial Statement API แบบ structured data ไม่ parse PDF เอง), Earnings Release จาก Investor Relations, ราคาหุ้นย้อนหลัง (ใช้ประกอบถ้าจำเป็น) — **ยังไม่เอา News API และ Earnings Call Transcript เข้ามาเป็น Core** เพราะเพิ่มต้นทุนและความซับซ้อนโดยไม่จำเป็นต่อการพิสูจน์แนวคิดหลัก
- **ขอบเขตบริษัท/เวลา:** เริ่มจาก 1 บริษัท × 1 เหตุผล × 4–8 ไตรมาส ให้ Flow วิ่งจบก่อน แล้วขยายเป็น 1 บริษัท × 3 เหตุผล → 5 บริษัท → 10–15 บริษัท ตามลำดับ (**ไม่เขียนระบบครอบคลุม 15 บริษัทตั้งแต่วันแรก**)
- **Ground Truth:** ได้ตรงจากงบการเงินจริง (เช่น Revenue โต 6% → เหตุผล "> 10%" ไม่เป็นจริง) ไม่ต้องอาศัยผู้เชี่ยวชาญตีความข่าว
- **Agent Orchestration:** ไม่สร้าง Agent runtime / planner framework / tool router / memory engine เอง — ใช้ framework สำเร็จรูป (เช่น LangGraph หรือเทียบเท่า) ทำ orchestration สิ่งที่สร้างเองและเป็น Contribution จริงคือ **domain logic การตรวจสอบเหตุผล**:
  ```
  Investment Reason
        ↓
  หา Evidence ที่เกี่ยวข้อง
        ↓
  ตรวจตัวเลข / Claim
        ↓
  หา Evidence สนับสนุนและขัดแย้ง (เทียบตัวเลขเบื้องต้น vs Restated / Estimate vs Actual)
        ↓
  เปรียบเทียบกับเงื่อนไขเดิม
        ↓
  Supported / Weakened / Broken / Not enough data
  ```
- **Point-in-Time โดยไม่ต้องพึ่ง API:** เก็บเอกสารเป็น Dataset ของเราเองพร้อม `published_at` แล้วบังคับกฎว่า ณ วันที่จำลอง Agent เห็นได้เฉพาะเอกสารที่ `published_at` ≤ วันที่จำลอง เท่านั้น
  ```
  Document { published_at: 2024-04-25 }
  จำลองวันที่ 2024-06-01 → ใช้เอกสารนี้ได้
  จำลองวันที่ 2024-03-01 → ห้ามใช้
  ```

### Phase 2 — Qualitative Reasons
เพิ่มเหตุผลเชิงข้อความ (เช่น "Demand ยังแข็งแรง", "Management ยังมั่นใจในธุรกิจ") และแหล่งข้อมูล News API / Earnings Call Transcript เข้ามา ซึ่งต้องมี Human Label หรือเกณฑ์การตัดสินที่ชัดเจนกว่า Phase 1

### Phase 3 — Personalization & Portfolio-Level Reasoning
แยกเป็น 2 ระดับ:

- **Phase 3-light (อยู่ใน scope ของ IS นี้ = Contribution 4):** เพิ่ม Investor Profile แบบ structured (synthetic, ไม่ผูกกับข้อมูลตลาดจริง) และ Investor Context Layer ที่ตัดสิน priority tier แบบ Hybrid (rule baseline + LLM) บนเคสที่มี evidence status อยู่แล้วจาก Phase 1 — ไม่มี Portfolio Database จริง ไม่มี Constraint Checker เชิงกฎ ไม่มี Causal Multi-hop เต็มรูปแบบ
- **Phase 3-full (Future Work, นอก scope ของ IS นี้ = Contribution 3):** Portfolio Database ที่ผูกกับข้อมูลตลาดจริง, Constraint Checker ที่ตรวจ Compliance เชิงกฎ, Macro Data, และ Causal Multi-hop Impact เต็มรูปแบบ

---

## 4. แนวคิดการทำงานของระบบ (System Reasoning Flow)

ระบบไม่ได้ทำงานแบบ `Prompt → LLM → Answer` แต่ทำงานแบบวนซ้ำของการให้เหตุผลและเลือกใช้เครื่องมือ:

```
ข้อมูลใหม่เข้ามา
      ↓
เกี่ยวข้องกับเหตุผลข้อไหนของหุ้นที่ผู้ใช้ถืออยู่?
      ↓
ข้อมูลแต่ละแหล่งพูดตรงกันหรือไม่?
      ↓
ถ้าขัดแย้งกัน แหล่งไหนน่าเชื่อถือกว่า และต้องหาข้อมูลเพิ่มหรือไม่?
      ↓
เหตุการณ์นี้กระทบ Business / Financial Metric อย่างไร (Event → Business → Financial → Investment Reason)?
      ↓
เหตุผลเดิมยังเป็นจริงอยู่หรือไม่? (Supported / Weakened / Broken / Uncertain)
      ↓
กระทบต่อ Portfolio ของผู้ใช้มากน้อยเพียงใด?
      ↓
ขัดกับข้อจำกัดความเสี่ยงของผู้ใช้หรือไม่ (Constraint Checker)?
      ↓
ข้อมูลเพียงพอที่จะสรุปหรือไม่ (ถ้าไม่พอ → Abstain / ขอ Human Review)
```

### ตัวอย่าง Reasoning แบบ Multi-hop Causal Impact (ระดับที่ควบคุมได้)

ขอบเขตของ Causal Impact ถูกจำกัดไว้เพียง 3 ขั้น เพื่อไม่ให้ Reasoning Chain ยาวเกินจัดการ:

```
Event  →  Company / Business Impact  →  Financial Metric  →  Investment Reason
```

ตัวอย่าง: "โรงงานหยุดผลิต" → "Production Capacity ลดลง" → "Revenue / Margin มีความเสี่ยง" → กระทบเหตุผล "Revenue Growth > 10%"

---

## 5. เครื่องมือ (Tools) ที่ Agent เลือกใช้ตามสถานการณ์

Agent ต้องให้เหตุผลก่อนว่าควรใช้เครื่องมือใดในการตอบคำถามหรือหาหลักฐานเพิ่มเติม ตารางนี้ระบุด้วยว่าเครื่องมือใดเป็น Core ของ Phase 1 และเครื่องมือใดถูกเลื่อนไปยังเฟสถัดไป:

| เครื่องมือ | หน้าที่ | เฟส |
|---|---|---|
| SEC XBRL / Financial Statement API | ดึงตัวเลขงบการเงินแบบ structured (Revenue, Margin, Debt) | Phase 1 (Core) |
| SEC / Company Filing (10-K, 10-Q) | ข้อมูลทางการ ใช้เป็นแหล่งอ้างอิงหลักและตรวจ Restated figures | Phase 1 (Core) |
| Earnings Release (Investor Relations) | ตัวเลขที่บริษัทประกาศเบื้องต้น ใช้เทียบกับตัวเลขทางการภายหลัง | Phase 1 (Core) |
| Calculator / Python | คำนวณ Growth Rate, Margin, Financial Ratios | Phase 1 (Core) — แยกเป็น tool `calculate_metric` ที่ Agent เรียกเองได้แล้ว (`tools.py`), ใช้ logic เดียวกับ `check_reason_status` ผ่าน helper กลาง ไม่มีความเสี่ยงคำนวณไม่ตรงกัน |
| Market Data | ราคาหุ้น, Volume — ใช้ประกอบถ้าจำเป็น | Phase 1 (Optional) |
| Earnings Call Transcript | สิ่งที่ผู้บริหารพูดและ Guidance | Phase 2 |
| News Search | เหตุการณ์ใหม่ที่อาจกระทบธุรกิจ | Phase 2 — **implement แล้วนอกแผนเดิม** (`tools.WEB_SEARCH_TOOL`, ใช้ web search ของ Anthropic เอง) ตาม request ให้ทำ full production vision แต่ **มีข้อจำกัดสำคัญที่ต้องระบุไว้ชัดเจน**: ผลค้นหาเป็นข้อมูล ณ ปัจจุบัน ไม่ใช่ point-in-time เหมือนข้อมูลจาก SEC ดังนั้น**ห้ามใช้ตัดสินสถานะเหตุผล** (Supported/Weakened/Broken) เด็ดขาด เพราะจะทำลาย point-in-time guarantee ที่เป็นหัวใจของ Contribution 1 — จำกัดให้ใช้ได้แค่เสริมคำอธิบาย (rationale) เท่านั้น และ log ทุกครั้งที่ใช้เพื่อตรวจสอบย้อนหลังได้ |
| Macro Data | ดอกเบี้ย, เงินเฟ้อ, ตัวแปรเศรษฐกิจมหภาค | Phase 3 |
| Portfolio Database | สัดส่วนการถือครองของผู้ใช้แต่ละคน | Phase 3-light — **มี Database จริงแล้ว บน PostgreSQL** (`backend/`, FastAPI + SQLAlchemy + Alembic migrations, แทนที่ SQLite เดิม เพราะข้อมูลของระบบนี้มีความสัมพันธ์กันชัดเจน — user → screening rule → position → reason snapshot → evaluation — ซึ่งเหมาะกับ Relational DB มากกว่า Document/Vector DB) เก็บ Investor Profile, ประวัติการรัน (`investigation_runs`), และ **`purchases` table จริงพร้อม qty/cost basis/วันที่ซื้อ** — ผู้ใช้ register/login (JWT), ตั้งเงื่อนไขคัดกรอง (`reasons`, ผูกกับ `user_id`), ระบบ**คัดกรอง** (ไม่ใช่ "แนะนำ") หุ้นที่ตรงเงื่อนไขข้าม 15 บริษัทแบบ mechanical (`/api/screen`, logic เดียวกับ `check_reason_status` ทุกประการ ไม่มี LLM), บันทึกการซื้อพร้อม **frozen snapshot ของเหตุผล ณ วันที่ซื้อ** (`reason_snapshot_json`, JSONB) แล้วเทียบกับสถานะปัจจุบันทุกครั้งที่เปิดหน้า Portfolio เพื่อตอบคำถามหลักของงานวิจัยนี้ตรงๆ: "เหตุผลตอนซื้อยังเป็นจริงอยู่ไหม" — ยังไม่ผูกกับมูลค่าตลาด ณ ปัจจุบันแบบ real-time (ราคาซื้อเป็นตัวเลขที่ผู้ใช้กรอกเอง ไม่ใช่ live quote) |
| Rule Engine | ตรวจสอบข้อจำกัดความเสี่ยงของผู้ลงทุน (Constraint Checker) | Phase 3 — ยังไม่ทำ |

---

## 6. กลไกสนับสนุนความน่าเชื่อถือของระบบ (Trust-Enabling Mechanisms)

กลไกเหล่านี้ไม่ใช่ Contribution หลัก แต่จำเป็นต่อความน่าเชื่อถือของ Contribution ทั้ง 3 ข้อ — และร่วมกันตอบโจทย์มิติคุณภาพ (Quality Dimension) ที่งานนี้เลือกให้ความสำคัญที่สุดตามลักษณะงาน คือ **Correctness และ Groundedness** ไม่ใช่ Diversity/Creativity/Fluency ที่เหมาะกับงาน Generative เชิงสร้างสรรค์มากกว่า (การเลือก Quality Dimension ตาม Use Case เป็นหลักการที่ตั้งใจ ไม่ใช่มองข้าม):

- **Sampling Strategy: Temperature = 0 ทุก LLM call** — งานทุกจุดที่ระบบเรียก LLM (ตัดสิน status, ตอบคำถามอิสระ, จัดลำดับความสำคัญ) เป็นงาน fact-grounded classification/extraction ไม่ใช่ Creative Generation หลักการ Deterministic vs. Stochastic Generation ระบุชัดว่างานที่ต้องการความแน่นอน (Structured Information, ข้อมูลข้อเท็จจริง) ควรลด Randomness ระบบนี้ตั้ง `temperature=0` เป็นค่า default ที่ทุก call site (`llm_client.call_claude`, ทั้ง 2 จุดใน `agent.py`) แทนค่า default เดิมของ API เอง (1.0) ซึ่งไม่เคยถูกตั้งค่าไว้มาก่อน — ผลข้างเคียงที่บันทึกไว้ตรงๆ: การทดลองเดิมทั้งหมด (baseline comparison, consistency experiment) รันด้วย temperature=1.0 ผลก่อน/หลังการเปลี่ยนนี้จึงเทียบกันตรงๆ ไม่ได้ ต้องระบุ temperature ที่ใช้กำกับไว้เสมอเมื่อรายงานผล
- **Grounding ผ่าน Tool-Calling ไม่ใช่ RAG (การตัดสินใจด้านสถาปัตยกรรมที่ตั้งใจ)** — Hallucination คือปัญหาที่ LLM สร้างข้อความดูน่าเชื่อถือแต่ไม่มีหลักฐานรองรับจริง วิธีมาตรฐานที่ใช้แก้ปัญหานี้คือ **Grounding** (ให้ AI อ้างอิงข้อมูลที่เชื่อถือได้แทนการตอบจากความจำ) ซึ่ง **RAG (Retrieval-Augmented Generation)** เป็นเทคนิค Grounding ที่นิยมใช้ที่สุดสำหรับเอกสารข้อความอิสระ (unstructured text) — ผ่านขั้นตอน Chunking → Embedding → Vector Database → Similarity Search งานวิจัยนี้ **พิจารณา RAG แล้วตัดสินใจไม่ใช้** เพราะข้อมูลหลักที่ระบบต้องอ้างอิง (ตัวเลขงบการเงินจาก XBRL) เป็น **structured data ที่มี schema ชัดเจนอยู่แล้ว** (tag name, period, value, filed date) การค้นหาจึงทำได้ด้วย exact-match query ต่อ API ของ SEC โดยตรง (`sec_client.py` + `xbrl_extract.py`) แม่นยำกว่าและไม่มีความเสี่ยงจาก Semantic Similarity ที่คลาดเคลื่อน (เช่น คะแนน Cosine Similarity สูงไม่ได้แปลว่าข้อมูลถูกต้องหรือเป็นฉบับล่าสุด) — นี่คือ **Grounding แบบ Tool-Calling**: Agent เรียกเครื่องมือ (`check_reason_status`, `calculate_metric`) ที่คืนค่าจาก API ตรงๆ แทนการค้นจาก Vector Database ส่วนจุดเดียวในระบบที่ต้องอ่าน**เอกสารข้อความอิสระ** จริง (MD&A narrative ใน 10-Q/10-K, `filing_context.py`) ปัจจุบันใช้ regex/keyword matching อย่างง่าย ซึ่งเป็นจุดที่ RAG แบบเต็มรูปแบบ (chunking + embedding + vector search ผ่าน pgvector ที่เตรียมโครงสร้างรองรับไว้แล้วใน PostgreSQL) จะเป็นการต่อยอดที่เหมาะสมในอนาคต (ดู [12. งานในอนาคต](#12-งานในอนาคต))
- **Point-in-Time Retrieval** — ป้องกัน Agent ใช้ข้อมูลอนาคตขณะทำ Backtest (lookahead bias) กลไกนี้ป้องกัน Failure Mode ที่รู้จักกันดีในระบบ AI Assistant ทั่วไปคือ **Outdated Data** (AI ดึงข้อมูลเก่ามาตอบราวกับเป็นปัจจุบัน เช่น ใช้ระเบียบปีก่อนตอบคำถามปีนี้) — ระบบนี้ป้องกันปัญหาเดียวกันในระดับสถาปัตยกรรม ไม่ใช่แค่ความหวังว่า Agent จะเลือกข้อมูลถูก: ทุก `Fact` มี `filed` date กำกับ และ `facts_as_of()` กรองเฉพาะข้อมูลที่ `filed <= as_of_date` เท่านั้น
- **Insufficient Evidence / Abstention** — ระบบต้องกล้าตอบว่า "ข้อมูลยังไม่พอสรุป" แทนการฟันธง
- **Reasoning Version / Decision Ledger** — บันทึกการเปลี่ยนแปลงของแต่ละเหตุผลตามเวลา พร้อมที่มาของการเปลี่ยนแปลง
- **Evidence Citation** — ทุกข้อสรุปต้องอ้างอิงแหล่งข้อมูลที่ตรวจสอบย้อนกลับได้
- **Adaptive Human-in-the-Loop** — ระบบประเมินความซับซ้อน/ความเสี่ยงของกรณี แล้วตัดสินใจว่าควรเรียกมนุษย์เข้ามาทบทวนหรือไม่
- **Investigation State + Deterministic Evidence Assessor** (เพิ่มหลัง design review) — เดิม state ของ Agent มีแค่ประวัติสนทนาดิบ (`messages`) และการตัดสินว่า "หลักฐานพอหรือยัง" ฝากไว้กับ LLM ทั้งหมด ไม่มีจุดตรวจซ้ำเป็นโค้ด ตอนนี้เพิ่ม `InvestigationState` (`investigation_state.py`) เก็บ tool call ทุกครั้งแยกจาก conversation history และ `assess_sufficiency()` เป็น checkpoint แบบ deterministic ที่รันก่อนยอมรับ `finalize_report` ทุกครั้ง — ถ้า reason ที่มีสถานะไม่แน่นอน (Weakened/Broken/Not enough data) ไม่เคยถูกเรียก `get_secondary_evidence`, หรือมี conflicting evidence แต่ไม่เคยเรียก `get_filing_context` จะ**reject แล้วบังคับให้ Agent ไปตรวจเพิ่มจริง** ไม่ใช่แค่เตือนใน prompt เฉยๆ (มี cap กันวนซ้ำไม่รู้จบ) — นี่คือสิ่งที่ทำให้ "Evidence Assessor" เป็น component แยกจาก LLM Decision จริงตามที่ออกแบบไว้ ไม่ใช่แค่ concept
- **Confidence Field** — `finalize_report` เดิมไม่มีทางบอกว่า "เจอสถานะนี้แต่ไม่ชัวร์เต็มร้อย" แยกจากตัว status เอง เพิ่ม field `confidence: high|medium|low` แล้ว (required ในทุกคำตอบ) เป็นคนละมิติกับ `human_review_recommended` โดยตั้งใจ (confidence ต่ำแต่ Supported ไม่จำเป็นต้อง escalate, confidence สูงแต่ Broken ก็ยัง escalate ได้เพราะความรุนแรง) — ทดสอบจริงกับ MSFT ได้ `confidence: high` ทุก reason ($0.023)
- **Human Escalation เมื่อ Loop หมดรอบ** — เดิมถ้า Agent วน 10 รอบแล้วยังไม่เรียก `finalize_report` ระบบจะ `raise RuntimeError` (crash) ตอนนี้เปลี่ยนเป็น return ผลลัพธ์ปกติที่มี `escalated: True` พร้อม `escalation_reason` บอกว่าตรวจ reason ไหนไปแล้วก่อนจะหมดรอบ — ทดสอบฟรีด้วย mock ให้ agent ไม่เรียก finalize_report เลย ยืนยันว่าไม่ crash และ escalate ถูกต้องจริง
- **False Rejection ใน Evidence Assessor** — `assess_sufficiency` ที่ reject คำตอบของ Agent มีความเสี่ยงแบบเดียวกับระบบตรวจสอบ Output เข้มเกินไปทั่วไป คือ **False Rejection** (ปฏิเสธคำตอบที่จริง ๆ ถูกต้องแล้ว เพราะ evidence ที่มีเพียงพออยู่แล้วแต่ไม่ตรงรูปแบบที่ assessor คาดหวังเป๊ะ) ไม่ใช่แค่ False Acceptance (ปล่อยคำตอบที่ยังมี gap ผ่านไป) ที่มักถูกพูดถึงมากกว่า ระบบนี้จำกัดความเสี่ยงนี้ด้วย `MAX_REJECTIONS = 2` — reject ได้ไม่เกิน 2 ครั้งต่อ 1 finalize_report แล้วยอมรับคำตอบพร้อม flag `assessor_gaps` แทนที่จะปฏิเสธไม่มีที่สิ้นสุด
- **Ground Truth ที่ผ่านการตรวจสอบซ้ำ** — หลักการที่ว่า "Ground Truth เองก็ต้องถูก validate ไม่ใช่เชื่อว่าถูกอัตโนมัติ" สะท้อนอยู่ใน `data/gold_set.json` ของงานนี้อยู่แล้วตั้งแต่ก่อนเขียนส่วนนี้: เอกสารตั้งชื่อไฟล์ตรงๆ ว่าเป็น **cross-checked reference set ไม่ใช่ ground truth** (ตัวเลขมาจาก 2 แหล่งอิสระของบริษัทเดียวกัน คือ XBRL 10-Q กับ earnings release 8-K แต่ไม่ใช่คนละแหล่งที่ verify โดยอิสระจริง) และ `data/primary_source_verification_set.json` เพิ่มแหล่งที่ 3 (ตัวเนื้อหา 10-Q/10-K จริง) เพื่อลดความเสี่ยงที่ reference set เองจะผิด

---

## 7. ตัวอย่างหน้าตาผลลัพธ์ (Illustrative Prototype Output)

```
Microsoft — My reasons for investing

1. Azure growth > X%                         🟢 Supported
2. Operating margin remains strong           🟡 Weakened
3. AI investment generates revenue growth    🟡 Uncertain
4. Debt remains manageable                   🟢 Supported

What's changed since last review?
⚠ Operating margin assumption: Supported → Weakened

Why?
• New quarterly filing
• Higher infrastructure cost
• Management commentary

Conflicting evidence detected:
Management expects margin recovery, but current cost trend remains elevated.

AI conclusion: Not enough evidence to mark this assumption as Broken.
Human review: Recommended
```

---

## 8. ขอบเขตข้อมูลสำหรับงานวิจัย (Scope for Independent Study)

เพื่อให้เหมาะสมกับระดับ Independent Study (ไม่ใช่การ Train Foundation Model ใหม่) กำหนดขอบเขตข้อมูลสูงสุด (เป้าหมายท้ายทาง หลังขยายครบทุกเฟสของ Phase 1) ดังนี้:

- บริษัท: 10–15 บริษัท
- ช่วงเวลา: ประมาณ 6–8 ไตรมาส
- เหตุผลการลงทุน: 3–5 เหตุผลเชิงตัวเลขต่อบริษัท

รวมประมาณ 15 บริษัท × 8 ไตรมาส × 4 เหตุผล ≈ **480 การประเมินเหตุผล (reason-evaluation instances)** ซึ่งเพียงพอสำหรับการทำ Experiment เชิงเปรียบเทียบ

แต่ **จะไม่เริ่มจากขนาดนี้** — ขยายตามลำดับที่ระบุใน [3.1 Phased Scope](#31-phased-scope-สิ่งที่ทำจริงก่อน): 1 บริษัท × 1 เหตุผล → 1 บริษัท × 3 เหตุผล → 5 บริษัท → 10–15 บริษัท เพื่อให้ทุกขั้นตรวจสอบ Flow ได้จริงก่อนขยายขนาด

---

## 9. การออกแบบการทดลอง (Experiment Design)

### Baselines สำหรับเปรียบเทียบ

1. LLM ธรรมดา (Zero-shot prompting)
2. RAG (Retrieval-Augmented Generation แบบพื้นฐาน)
3. Agentic RAG (Multi-step retrieval แต่ไม่มีกลไก Conflict-aware / Reasoning ledger)
4. ระบบที่นำเสนอ (Trustworthy Agentic AI)

Baseline ทั้ง 4 นี้ต้อง **fix ให้นิ่งตั้งแต่ตอนเริ่ม Phase 1** (ตั้งค่าบน scope เหตุผลเชิงตัวเลข) เพื่อไม่ให้ต้องปรับ Baseline ซ้ำทุกครั้งที่ขยาย Scope ในเฟสถัดไป

### มิติการประเมิน (Evaluation Dimensions)

- ความถูกต้องของสถานะเหตุผลที่ประเมิน (Reason status accuracy)
- ความสามารถในการค้นหาหลักฐานที่ถูกต้องและครบถ้วน
- ความสามารถในการจัดการข้อมูลที่ขัดแย้งกัน
- อัตราการ "พูดโดยไม่มีหลักฐานรองรับ" (Unsupported claims / hallucination rate)
- การใช้ข้อมูลอนาคตโดยไม่ตั้งใจ (Lookahead bias rate)
- ความสามารถในการงดฟันธงเมื่อข้อมูลไม่เพียงพอ (Appropriate abstention rate)
- ความสอดคล้องกับข้อจำกัดความเสี่ยงของผู้ใช้ (Constraint compliance)
- ความสม่ำเสมอของเหตุผลระหว่างรอบการประเมิน (Reasoning consistency / no arbitrary flip-flopping)
- ความแม่นยำในการเรียก Human Review ในจังหวะที่เหมาะสม (Human-in-the-loop trigger precision)

### มิติการประเมินเพิ่มเติมสำหรับ Contribution 4 (Personalized Decision Support Layer)

- **Evidence integrity (ต้อง 100%):** evidence status ที่ Investor Context Layer เห็นและอ้างอิง ต้องตรงกับ status จาก Objective Evidence Layer เป๊ะ ไม่ว่า investor profile จะเป็นแบบไหน — ถ้าไม่ตรง = ความล้มเหลวร้ายแรง (personalization บิดข้อเท็จจริง)
- **Priority divergence:** สัดส่วนของเคสที่ evidence เดียวกันได้ priority tier ต่างกันเมื่อ investor profile ต่างกัน (คาดหวังว่าควร "ต่างกันเมื่อควรต่าง" ไม่ใช่ต่างกันทุกเคสหรือเหมือนกันทุกเคส)
- **Agreement กับ rule-based baseline:** LLM-derived tier ตรงกับ rule matrix กี่ % และในเคสที่ไม่ตรง เหตุผลที่ LLM ให้สมเหตุสมผลหรือไม่ (ตรวจโดยมนุษย์)

**หมายเหตุสำคัญ:** งานวิจัยนี้ **ไม่ได้มุ่งพิสูจน์ว่าระบบทำกำไรได้สูงกว่า** แต่มุ่งพิสูจน์ว่าระบบช่วยให้กระบวนการติดตามและตัดสินใจลงทุน **มีหลักฐานรองรับ น่าเชื่อถือ และสอดคล้องกับบริบทของผู้ลงทุนมากกว่า** ซึ่งเป็นมุมมองเชิง Information Systems ที่ชัดเจนกว่าการแข่งขันด้านผลตอบแทน

---

## 10. คุณค่าทางธุรกิจ (Business Value)

นักลงทุนที่ถือหุ้น 15 ตัว อาจเผชิญข่าวใหม่วันละ 100 เรื่อง ระบบนี้เปลี่ยนปัญหาจาก "ข้อมูลท่วมท้น" ให้เหลือเพียงสิ่งที่มีนัยสำคัญจริง เช่น:

> "วันนี้มีข้อมูลใหม่ 42 รายการ แต่มีเพียง 3 รายการที่อาจเปลี่ยนเหตุผลในการลงทุนของคุณ"

นี่คือคุณค่าหลักของระบบ — ลดภาระการติดตามข้อมูล และเพิ่มความมั่นใจว่าไม่มีสัญญาณสำคัญที่ถูกมองข้าม

---

## 11. ข้อจำกัดของงานวิจัย (Limitations)

- ขอบเขต Causal Impact จำกัดที่ 3 ขั้น (Event → Business → Financial → Investment Reason) ไม่สืบสาวผลกระทบระดับมหภาคหลายทอด (เช่น ภูมิรัฐศาสตร์ → Commodity → Inflation → Interest Rate)
- ขนาดข้อมูลจำกัดที่ 10–15 บริษัท เหมาะกับการพิสูจน์แนวคิด (proof of concept) ไม่ใช่ระบบ Production ขนาดใหญ่
- ระบบไม่ได้ Train Foundation Model ใหม่ แต่ใช้ LLM ที่มีอยู่ร่วมกับ Agentic Orchestration และ Tool Use

## 12. งานในอนาคต (Future Work)

- ขยายขอบเขต Causal Impact ให้ครอบคลุมปัจจัยมหภาคหลายทอด
- ขยายจำนวนบริษัทและช่วงเวลาเพื่อทดสอบความสามารถในการ Generalize
- เพิ่มการเรียนรู้จากพฤติกรรมการตัดสินใจของผู้ใช้จริงเพื่อปรับ Personalization ให้แม่นยำขึ้น
- เพิ่ม RAG เต็มรูปแบบ (Chunking + Embedding + pgvector) สำหรับการค้นหา MD&A narrative ใน `filing_context.py` แทน regex/keyword matching ปัจจุบัน (ดูเหตุผลของการไม่ใช้ RAG ในส่วนอื่นของระบบใน [6. กลไกสนับสนุนความน่าเชื่อถือของระบบ](#6-กลไกสนับสนุนความน่าเชื่อถือของระบบ-trust-enabling-mechanisms))
- ทำ RBAC (Role-Based Access Control) ให้มี role ผู้ตรวจสอบ (Human Reviewer) แยกจาก Investor จริง พร้อมหน้าจอ queue สำหรับเคสที่ถูก escalate — ปัจจุบันมีแค่ field `human_review_recommended`/`escalated` แต่ไม่มี workflow ให้มนุษย์จริงเข้ามาตรวจ
- วัดผล **Escalation Accuracy** อย่างเป็นทางการ — ปัจจุบันมี field `human_review_recommended`/`escalated` และวัด "ความเสถียร" ของค่านี้ข้าม run ไปแล้ว (run-to-run consistency experiment, 97.9%) แต่ไม่เคยวัดว่า Agent escalate เคส "ถูกที่ควร escalate จริง" มากน้อยแค่ไหนเทียบกับที่ผู้เชี่ยวชาญ/มนุษย์จะตัดสินใจ escalate (Precision/Recall ของการ escalate ไม่ใช่แค่ความเสถียร) — ต่อยอดจาก stratified review packet ที่มีอยู่แล้ว (`build_review_sample.py`) ได้โดยตรง
- เพิ่ม **Moving Window / Trend Signal** หลายไตรมาสต่อเนื่อง — ปัจจุบัน `reason_engine.py` เทียบแค่ 2 จุดข้อมูล (ไตรมาสล่าสุด vs ไตรมาสเดียวกันของปีก่อน) ไม่เคยดูทิศทางของหลายไตรมาสติดต่อกัน แนวคิด Moving Window ของ Time-series Forecasting (`[x_{t-3}, x_{t-2}, x_{t-1}] → x_t` แล้วเลื่อน Window ไปเรื่อย ๆ ซึ่งเป็นรากเดียวกับที่ ARIMA ใช้ แม้จะไม่ใช่ Generative AI) สามารถนำมาเสริม Continuous Monitoring ได้โดยตรง — เช่น สร้างสัญญาณเสี่ยงเพิ่มเติมแบบ deterministic ล้วน (ไม่ใช้ LLM) ว่า "metric นี้แย่ลงต่อเนื่องกัน N ไตรมาสติด" ซึ่งเป็นสัญญาณที่การเทียบแค่ 2 จุดแบบปัจจุบันมองไม่เห็น
- เพิ่ม Model Monitoring ให้ครบทุกมิติ (Latency, Cost, Hallucination Rate, Safety ของ Investigation Agent) ไม่ใช่แค่ Distribution/Drift ของสถานะเหตุผลที่ Continuous Monitoring ปัจจุบันตรวจอยู่

---

## 13. การประเมินความเสี่ยง (Risk Assessment)

ตามหลัก Consequence of Error ความเสี่ยงของระบบ AI ไม่ได้วัดจากอัตราความผิดพลาดเพียงอย่างเดียว แต่ต้องพิจารณาร่วมกับความรุนแรงของผลกระทบเมื่อผิดพลาด (**Probability of Error × Severity of Impact**) ตารางนี้วิเคราะห์จุดเสี่ยงหลักของระบบตามกรอบคิดดังกล่าว:

| จุดเสี่ยง | Probability of Error | Severity of Impact | มาตรการที่มีอยู่ |
|---|---|---|---|
| Rule Engine ตัดสิน status ผิด (Supported/Weakened/Broken) | ต่ำ — เป็น deterministic code ไม่ใช่ LLM, ทดสอบกับ gold set 352 เคสแล้ว | สูง — ผู้ใช้อาจเข้าใจผิดว่าเหตุผลยังเป็นจริงทั้งที่ไม่ใช่ | Sensitivity analysis ยืนยัน boundary ไม่ไวต่อค่า buffer ที่เลือก (มีเพียง 7-9% ของเคสที่เปลี่ยนแม้ปรับ buffer ±25 จุด), Restatement tolerance กันตัวเลข noise |
| Investigation Agent (LLM) ตอบผิดจากข้อมูลที่มี (Hallucination) | ปานกลาง — LLM ยังมีโอกาสตีความผิด แม้ grounding ด้วยข้อมูลจริง | ปานกลาง — เป็น rationale ประกอบ ไม่ใช่ตัวตัดสิน status เอง (status มาจาก Rule Engine เท่านั้น) | Evidence Assessor เป็น Program Gate (ไม่ใช่ AI ตรวจ AI), บังคับ `finalize_report` แบบ structured, log ทุก tool call |
| `web_search` ถูกใช้ตัดสิน status แทนที่จะใช้ประกอบ rationale | ต่ำ — ถูกห้ามชัดเจนใน system prompt และ tool ไม่ได้ผูกกับ classification logic | สูงมาก — จะทำลาย point-in-time guarantee ทั้งระบบ (lookahead bias) | แยก tool ออกจาก TOOL_SPECS ที่ใช้ตัดสิน, เขียนข้อจำกัดไว้ทั้งใน system prompt และ docstring ของโค้ด |
| Continuous Monitoring แจ้งเตือนผิด (false alarm) หรือไม่แจ้งเตือนเมื่อควร (missed detection) | ต่ำ — ใช้ deterministic check เดียวกับ Rule Engine | ต่ำ — เป็นแค่ signal ให้ผู้ใช้ไปดูเอง ไม่มี action อัตโนมัติต่อจากนั้น | ไม่เรียก LLM อัตโนมัติเด็ดขาด, ผู้ใช้ตัดสินใจเองว่าจะเปิด Investigation Agent (paid) ต่อหรือไม่ |
| ข้อมูลจาก SEC เอง (Custom Reason ผูก tag ผิดความหมาย) | ปานกลาง — ผู้ใช้เลือก metric เองจากรายการ tag จริง แต่ยังตีความความหมาย tag ผิดได้ | ปานกลาง — กระทบเฉพาะเหตุผลที่ user นั้นสร้างเอง ไม่กระทบ built-in reasons | บังคับเลือกจาก `list_available_tags()` เท่านั้น ห้าม free text, preview ผลการคำนวณจริงก่อนบันทึก |
| Error Propagation ในบทสนทนาหลายรอบของ Agent Chat | ต่ำ-ปานกลาง — เกิดเมื่อรอบแรกมี assumption หรือ tool result คลาดเคลื่อน แล้ว `history` ของรอบถัดไปอ้างอิงต่อ (คล้าย Autoregressive Generation ที่ Token ผิดตัวแรกกลายเป็น Context ผิดของตัวถัดไป) | ปานกลาง — จำกัดอยู่แค่บทสนทนานั้น ไม่กระทบ status ที่มาจาก Rule Engine ซึ่งคำนวณแยกอิสระเสมอ | ปุ่ม "New chat" ล้าง `history` ทิ้งทั้งหมดให้ user ตัดวงจรได้เอง, ทุกคำตอบยังต้องอ้างอิง tool result จริงเสมอ (ไม่ใช่เดาจาก history อย่างเดียว) |

**ข้อสรุปจาก Risk Matrix**: จุดที่มี Severity สูงที่สุด (web_search ปนเข้าไปในการตัดสิน status) มี Probability ต่ำเพราะถูกกันไว้ตั้งแต่ระดับสถาปัตยกรรม ไม่ใช่แค่ความหวังว่า LLM จะทำตามคำสั่ง — สอดคล้องกับหลักที่ว่าความเสี่ยงที่ Severity สูงต้องมีมาตรการควบคุมที่เข้มงวดแม้ Probability จะต่ำก็ตาม

---

## 14. Self-Check ตามหลักการออกแบบระบบ Generative AI (Course Checklist Compliance)

ตอบคำถาม 10 ข้อที่ควรทบทวนก่อนสร้างระบบ Generative AI (ตามแนวทางที่สอนในวิชา) โดยตรง เพื่อยืนยันว่าระบบนี้ผ่านการคิดตามกรอบดังกล่าวจริง ไม่ใช่แค่ใช้ AI สร้าง Output ได้:

| # | คำถาม | คำตอบของโปรเจกต์นี้ |
|---|---|---|
| 1 | กำลังแก้ปัญหาอะไร และ Business Process เป็นอย่างไร? | นักลงทุนถือหุ้นหลายตัว ต้องติดตามว่าเหตุผลที่เคยใช้ตัดสินใจซื้อยังเป็นจริงหรือไม่ เมื่อมีข้อมูลใหม่เข้ามาต่อเนื่อง (ดู [1. ที่มาและปัญหา](#1-ที่มาและปัญหา-motivation)) |
| 2 | Stakeholder คือใคร? | Investor (ผู้ใช้หลัก), Human Reviewer (เมื่อระบบ escalate เคสที่ไม่แน่ใจ — ปัจจุบันยังไม่มี role/UI แยก ดู [12. งานในอนาคต](#12-งานในอนาคต)) |
| 3 | มี Data อะไร มาจากไหน และ Input/Output คืออะไร? | SEC EDGAR XBRL Company Facts API + 10-Q/10-K/8-K filings (structured + narrative text), Input = ticker/reason/คำถามผู้ใช้, Output = status พร้อมหลักฐานอ้างอิงกลับไปยัง filing ต้นฉบับ |
| 4 | จำเป็นต้องใช้ AI หรือใช้โปรแกรมธรรมดาก็พอ? | **ตอบแยกตามงาน ไม่ใช่ตอบรวม**: การคำนวณและตัดสิน status (Rule Engine, Screener, Continuous Monitoring) เป็นงานคำนวณแน่นอน ใช้ deterministic Python ล้วน ไม่มี LLM เลย — ใช้ LLM เฉพาะงานที่ต้องอ่าน-ตีความ-อธิบายเป็นภาษาธรรมชาติ (Investigation Agent อธิบายเหตุผลเบื้องหลัง Broken status, ตอบคำถามอิสระ) ตรงตามหลักที่ว่าไม่ควรใช้ Generative AI ในทุกขั้นตอนของระบบ |
| 5 | ควรใช้ Model อะไร และทำไมจึงเลือก? | Claude Sonnet 4.5 ผ่าน Anthropic Messages API โดยตรง (ไม่ผ่าน SDK เพราะเจอ bug ใน environment) เลือกเพราะรองรับ tool-use/function-calling ที่จำเป็นสำหรับ Agent เรียก Rule Engine/Calculator เอง และรองรับ structured output (forced tool call) ที่ทำให้ผลลัพธ์ parse ได้แน่นอน |
| 6 | Resource, Hardware, Latency และ Cost เพียงพอหรือไม่? | ระบบรันบน CPU ปกติ (ไม่ต้อง GPU เพราะไม่ได้ train/infer โมเดลเอง) ต้นทุนต่อการเรียก Investigation Agent วัดจริงแล้ว (README.md, run_full_experiment.py) อยู่ในหลัก cent ต่อครั้ง, cost tracking ($3/$15 ต่อ 1M token) ฝังอยู่ในทุก LLM call |
| 7 | ประเมินและ Verify Output ด้วยอะไร? | Gold set 352 เคส (cross-checked จาก 2 แหล่งอิสระ), primary-source verification set (10-Q/10-K text จริง), baseline comparison 4 วิธี × 45 เคส, sensitivity analysis, human review packet — วัดหลายมิติตาม Rubric-style criteria (ความถูกต้องของ status, ความสอดคล้องของ rationale กับหลักฐาน, ความเสถียรข้าม run) ไม่ใช่แค่ accuracy ตัวเดียว |
| 8 | มี Risk และผลกระทบเมื่อผิดพลาดอย่างไร? | ดู [13. การประเมินความเสี่ยง](#13-การประเมินความเสี่ยง-risk-assessment) — วิเคราะห์แยกทั้ง Probability of Error และ Severity of Impact ต่อจุดเสี่ยงแต่ละจุด |
| 9 | Human ต้องตรวจ อนุมัติ หรือ Override ตรงไหน? | `human_review_recommended` ต่อเหตุผล + `escalated` ต่อทั้ง run เมื่อ Agent หาข้อสรุปไม่ได้ในจำนวนรอบที่กำหนด — ระบบวางตัวเป็น **Decision Support เท่านั้น** ไม่เคยตัดสินใจซื้อ/ขายแทนผู้ใช้ (เทียบกับตัวอย่าง Medical AI ที่ highlight จุดผิดปกติให้แพทย์ตรวจ ไม่ใช่วินิจฉัยแทน) |
| 10 | เมื่อเข้าสู่ Production จะ Monitor และจัดการ Error อย่างไร? | Continuous Monitoring (background job รายชั่วโมง, ฟรี ไม่เรียก LLM) ตรวจจับการเปลี่ยนสถานะของทุกเหตุผลที่ user ถืออยู่ แล้วสร้าง Notification — เป็น autonomy tier กลางตามที่ควรออกแบบ (อัตโนมัติเฉพาะงานความเสี่ยงต่ำ/deterministic, งานที่มีต้นทุนสูงหรือความเสี่ยงสูงกว่า เช่น Investigation Agent ยังต้องให้ user เป็นคนกดเริ่มเองเสมอ) |

**ข้อสังเกตสำคัญจาก Self-Check**: ข้อ 2 และข้อ 9 (Human Reviewer role, monitoring metrics ที่ครบทุกมิติ) ยังเป็นช่องว่างที่ตอบได้ไม่เต็มร้อย — บันทึกไว้ตรงๆ ใน [12. งานในอนาคต](#12-งานในอนาคต) แทนที่จะอ้างว่าทำครบแล้ว
