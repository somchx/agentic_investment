# Literature Review

**Trustworthy Agentic AI for Continuous and Personalized Investment Decision Support**

*เอกสารทบทวนวรรณกรรม — จัดทำเพื่อประกอบ [PROPOSAL.md](PROPOSAL.md) และผลการทดลองใน [README.md](README.md)*

---

## บทนำ

งานวิจัยเรื่อง Agentic AI สำหรับการเงินและการลงทุนเติบโตอย่างรวดเร็วในช่วงปี 2024–2026 โดยเฉพาะหลังจากที่โมเดลภาษาขนาดใหญ่ (LLM) เริ่มถูกผนวกเข้ากับกลไก tool-calling และ retrieval-augmented generation (RAG) อย่างแพร่หลาย งานสำรวจล่าสุดอย่าง *Large Language Model Agents in Finance: A Survey* (EMNLP Findings 2025) และ *Agentic Trading: When LLM Agents Meet Financial Markets* (arXiv:2605.19337, 2026 — evidence map ครอบคลุม 77 การศึกษาที่ผ่านการคัดกรองถึงเดือนมีนาคม 2026) ต่างชี้ตรงกันว่าสาขานี้กำลังเปลี่ยนผ่านจาก "LLM ตอบคำถามการเงินแบบ single-shot" ไปสู่ "Agent ที่เลือกใช้เครื่องมือหลายชนิดเพื่อค้นคว้าและให้เหตุผลแบบหลายขั้นตอน" อย่างไรก็ตาม เมื่อพิจารณาวรรณกรรมสายนี้อย่างละเอียด จะพบว่ายังมีช่องว่างเชิงระบบ (systemic gaps) อยู่หลายจุดที่ยังไม่ถูกปิดพร้อมกันในงานชิ้นเดียว ซึ่งเป็นที่มาของ Contribution ทั้ง 3 ข้อของโปรเจกต์นี้

เอกสารนี้ทบทวนวรรณกรรมใน 6 สาย ที่เกี่ยวข้องโดยตรงกับปัญหาที่โปรเจกต์นี้แก้ไข ได้แก่ (1) Agentic LLM ในบริบทการเงิน (2) การยึดโยงหลักฐานและอาการหลอน (grounding & hallucination) ในการให้เหตุผลทางการเงิน (3) อคติจากข้อมูลอนาคต (look-ahead bias) และการดึงข้อมูลแบบ point-in-time (4) การจัดการหลักฐานที่ขัดแย้งกันใน RAG หลายแหล่ง (5) ความน่าเชื่อถือและความคงเส้นคงวาของ Agent (reliability & consistency) และ (6) การติดตามเหตุผลการลงทุนอย่างต่อเนื่อง (continuous investment thesis tracking) ซึ่งเป็นแนวคิดที่ใกล้เคียงกับหัวใจของโปรเจกต์นี้ที่สุด

---

## 1. Agentic LLM ในบริบทการเงิน (Agentic LLMs in Finance)

งานสำรวจ *Agentic Large Language Models, a survey* (arXiv:2503.23037, 2025) นิยาม "Agentic LLM" ว่าเป็นระบบที่ไม่เพียงตอบคำถาม แต่ตัดสินใจเลือก action/tool เอง สังเกตสิ่งแวดล้อม และวนซ้ำกระบวนการให้เหตุผลจนกว่าจะบรรลุเป้าหมาย — สอดคล้องกับกรอบคิดพื้นฐานของ ReAct (Yao et al., 2023, ICLR) ที่เสนอการสลับกันระหว่าง "Thought → Action → Observation" เป็นครั้งแรก และยังคงเป็นสถาปัตยกรรมพื้นฐานที่งาน Agentic ส่วนใหญ่ในปี 2025–2026 ต่อยอดมา รวมถึง `agent.py` ของโปรเจกต์นี้เองที่ implement การวนซ้ำ tool-call ↔ reasoning ในรูปแบบเดียวกัน

ในบริบทการเงินโดยเฉพาะ *Finance Agent Benchmark: Benchmarking LLMs on Real-world Financial Research Tasks* (arXiv:2508.00828, 2025) และ FinToolBench (Lu et al., 2026) ประเมินความสามารถของ Agent ในการเลือกใช้เครื่องมือทางการเงินจริง (เช่น Google Search, SEC EDGAR) ในงานวิจัยเชิงลึก ผลการศึกษาชี้ว่าความสามารถในการ "เลือก tool ให้ถูกกับสถานการณ์" ยังเป็นจุดอ่อนของ LLM Agent ทั่วไป โดยเฉพาะเมื่อสถานการณ์ต้องการหลักฐานจากหลายแหล่งพร้อมกัน — ตรงนี้เองที่งาน `run_full_experiment.py` ของโปรเจกต์นี้แสดงให้เห็นเป็นรูปธรรม: Agent ที่มี `get_secondary_evidence` และ `get_filing_context` เลือกเรียกใช้เครื่องมือทั้งสองเองเมื่อพบเคส Broken (เช่น GOOGL debt +315.8%) โดยไม่มีใครสั่ง

**ช่องว่าง:** งานสำรวจส่วนใหญ่วัดผลที่ "ความแม่นยำของคำตอบสุดท้าย" (task success rate) เป็นหลัก แต่ยังไม่ค่อยมีงานที่แยกวัดว่า Agent เพิ่ม *คุณภาพของกระบวนการ* (evidence-grounded explanation, escalation ที่เหมาะสม) เหนือกว่า baseline ที่ deterministic อยู่แล้วหรือไม่ — ซึ่งตรงกับสิ่งที่ `run_full_experiment.py` พบจริง: Rule-based กับ Agent ได้ Accuracy เท่ากัน (100%/39) เพราะทั้งคู่พึ่ง tool คำนวณตัวเลขเดียวกัน ความแตกต่างที่แท้จริงอยู่ที่ *investigation depth* ไม่ใช่ accuracy — เป็นมุมมองที่ยังไม่ค่อยถูกแยกวัดชัดเจนในวรรณกรรมส่วนใหญ่

---

## 2. การยึดโยงหลักฐานและอาการหลอนในเหตุผลทางการเงิน (Grounding & Financial Hallucination)

การหลอน (hallucination) ของ LLM ในบริบทการเงินมีความเสี่ยงสูงกว่าโดเมนทั่วไป เนื่องจากต้องการความแม่นยำระดับตัวเลข (precision), ความถูกต้องตามช่วงเวลา (point-in-time accuracy), การระบุตัวตนบริษัทที่ถูกต้อง (entity resolution) และความเป็นปัจจุบันของข้อมูล (recency) ตามที่สรุปไว้ใน *Why LLMs Hallucinate in Finance (and How Grounding Fixes It)* งานวิจัยที่ตรงประเด็นที่สุดคือ **FinGround: Detecting and Grounding Financial Hallucinations via Atomic Claim Verification** (arXiv:2604.23588, 2026) ซึ่งเสนอให้ตรวจสอบ "atomic claim" แต่ละข้ออ้างอิงกับหลักฐานต้นทาง — แนวคิดเดียวกับที่ `earnings_release.py` และ `filing_context.py` ของโปรเจกต์นี้ทำจริง คือแทนที่จะเชื่อคำอธิบายของ LLM เฉยๆ ระบบบังคับให้ทุกข้อสรุปผูกกับ Fact object ที่อ้างอิง accession number, filed date และข้อความที่ยกมาโดยตรง (quoted_text) จากตัวเอกสารจริง

งานอื่นในสายนี้ เช่น *FinCoT: Grounding Chain-of-Thought in Expert Financial Reasoning* (arXiv:2506.16123, 2025) และ *FinChain: A Symbolic Benchmark for Verifiable Chain-of-Thought Financial Reasoning* (arXiv:2506.02515, 2025) มุ่งเน้นการตรวจสอบ **ขั้นตอนการคำนวณ** (เช่น สูตรการหา margin, growth) ให้ verifiable แต่ไม่ได้ขยายไปถึงการตรวจสอบว่า *ตัวเลขตั้งต้น* ที่ใช้คำนวณนั้นถูกต้องหรือไม่ในตัวมันเอง

**ช่องว่าง:** วรรณกรรมสาย grounding ส่วนใหญ่ตรวจสอบว่า "คำอธิบายของ LLM สอดคล้องกับหลักฐานที่ retrieve มาหรือไม่" แต่ไม่ได้ตั้งคำถามย้อนกลับไปอีกชั้นว่า **หลักฐานตั้งต้นเองน่าเชื่อถือแค่ไหน** — โปรเจกต์นี้ปิดช่องว่างนี้ด้วยการสร้าง verification pipeline 3 ชั้น (XBRL → 8-K earnings release → primary 10-Q/10-K text) ที่ตรวจสอบ **ความถูกต้องของตัวเลขต้นทาง** ก่อนที่ Agent จะนำไปให้เหตุผลต่อ ผลลัพธ์จริงคือพบบั๊กในกระบวนการ extraction เอง 6 ครั้ง (unit mismatch ของ NFLX/TSLA, XBRL tag ผิด scope ของ ORCL, การรวมสอง accounting concept ผิดของ MSFT ฯลฯ) ซึ่งเป็นหลักฐานเชิงประจักษ์ว่าการ "เชื่อหลักฐานที่ retrieve มา" อย่างไม่มีวิจารณญาณเป็นความเสี่ยงจริง ไม่ใช่แค่สมมติฐานเชิงทฤษฎี

---

## 3. อคติจากข้อมูลอนาคตและการดึงข้อมูลแบบ Point-in-Time

หัวข้อนี้เป็นสายวรรณกรรมที่พัฒนาเร็วที่สุดสายหนึ่งในปี 2026 เนื่องจากงานวิจัยเริ่มตระหนักว่าการ backtest LLM กับข้อมูลย้อนหลังมีความเสี่ยงจาก "หน่วยความจำที่คาดเดาได้" (predictable memory) ของโมเดล — กล่าวคือ LLM ที่ถูกฝึกในปี 2024 "รู้อยู่แล้ว" ว่าหุ้นในปี 2018–2020 เคลื่อนไหวไปทางไหน ทำให้การประเมินความสามารถ "พยากรณ์" ที่แท้จริงคลาดเคลื่อน ประเด็นนี้ถูกวัดเชิงปริมาณอย่างเป็นระบบครั้งแรกใน *AI's Predictable Memory in Financial Analysis* (ScienceDirect, 2025) ซึ่งเสนอวิธีวัดขนาดของ look-ahead bias ในงานประยุกต์ทางการเงิน

งานล่าสุดที่ตรงประเด็นที่สุดคือ **Look-Ahead-Bench: a Standardized Benchmark of Look-ahead Bias in Point-in-Time LLMs for Finance** (arXiv:2601.13770, 2026) ซึ่งพบว่า LLM ทั่วไปมี look-ahead bias อย่างมีนัยสำคัญเมื่อเทียบกับโมเดลที่ถูกออกแบบให้เป็น Point-in-Time (PiT) โดยเฉพาะ และ **Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias in Financial Backtesting with Large Language Models** (arXiv:2605.24564, 2026) ที่เสนอ FinCAD — เทคนิค inference-time decoding ที่กด "ความจำ" ของ LLM เกี่ยวกับผลลัพธ์ในอดีตโดยไม่ต้อง retrain โมเดล ส่วน *Scaling Point-in-Time Language Models* (arXiv:2607.11889, 2026) แสดงว่าโมเดลที่ฝึกบน corpus ที่ตัดข้อมูลตามเวลาอย่างเคร่งครัดให้ผลพยากรณ์ที่แข็งแรงกว่าและมีนัยสำคัญเชิงเศรษฐกิจมากกว่าโมเดลทั่วไปอย่างชัดเจน

**ช่องว่าง:** งานวิจัยสายนี้เกือบทั้งหมดแก้ปัญหาที่ **ระดับโมเดล** — คือปรับ decoding, ปรับ training corpus หรือสร้างโมเดลใหม่ที่ "ไม่รู้อนาคต" ตั้งแต่ต้น ซึ่งต้องการทรัพยากรการฝึกโมเดลจำนวนมาก โปรเจกต์นี้เลือกแนวทางที่ตรงข้ามและเข้าถึงได้ง่ายกว่ามาก คือแก้ปัญหาที่ **ระดับ pipeline การดึงข้อมูล** — `facts_as_of()` ใน `xbrl_extract.py` กรองข้อมูลตาม `filed date` อย่างง่ายๆ ก่อนส่งให้ Agent เห็น โดยไม่ต้องแตะโมเดลเลย วิธีนี้ตรวจสอบได้ตรงไปตรงมา (สามารถพิสูจน์ได้ว่า ณ วันที่จำลอง Agent ไม่มีทางเห็น fact ที่ filed หลังจากนั้น) และไม่ต้องพึ่งงบประมาณสำหรับ fine-tune หรือ pretrain โมเดลใหม่ — เหมาะกับขอบเขตงาน Independent Study ที่ไม่ได้ตั้งเป้าฝึก Foundation Model

---

## 4. การจัดการหลักฐานที่ขัดแย้งกันใน RAG หลายแหล่ง (Conflicting Evidence in Multi-Source RAG)

งานสำรวจ *Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG* (arXiv:2501.09136, 2025) ชี้ว่า RAG แบบดั้งเดิม (single-shot retrieval) มีข้อจำกัดพื้นฐานคือไม่สามารถตัดสินใจ "ไปค้นเพิ่ม" ได้เมื่อหลักฐานที่ได้มาดูไม่น่าเชื่อถือหรือขัดแย้งกัน — ตรงกับสิ่งที่โปรเจกต์นี้พิสูจน์ได้เชิงประจักษ์ใน `run_full_experiment.py`: Baseline 2 (single-shot RAG) พลาดการ escalate เคส Broken จริง 3 จาก 5 เคส (recall 40%) ทั้งที่มีข้อมูลตัวเลขที่ถูกต้องอยู่แล้ว เพราะไม่มีกลไกไปตรวจสอบเพิ่มเมื่อค่าที่ได้อยู่ใกล้เส้นแบ่งสถานะ

งานที่ตรงประเด็นเรื่อง "หลักฐานขัดแย้งกัน" โดยตรงคือ **Retrieval-Augmented Generation with Conflicting Evidence** (arXiv:2504.13079, 2025) ซึ่งชี้ว่าโมเดลส่วนใหญ่เมื่อเจอเอกสารที่ให้ข้อมูลขัดกันมักจะ "เลือกคำตอบแบบสุ่ม" หรือผสมข้อมูลอย่างไม่มีหลักการ แทนที่จะประเมินความน่าเชื่อถือของแต่ละแหล่ง และ **Astute RAG: Overcoming Imperfect Retrieval Augmentation and Knowledge Conflicts for Large Language Models** (arXiv:2410.07176, 2024) เสนอกรอบคิดให้โมเดลรวมความรู้ในตัว (parametric knowledge) เข้ากับหลักฐานที่ retrieve มาอย่างมีชั้นเชิง เมื่อพบว่าแหล่งข้อมูลขัดแย้งกัน ส่วน **DRAGged into Conflicts: Detecting and Addressing Conflicting Sources in Search-Augmented LLMs** (arXiv:2506.08500, 2025) เสนอกลไกตรวจจับความขัดแย้งระหว่างแหล่งอย่างเป็นระบบก่อนสังเคราะห์คำตอบ

**ช่องว่าง:** งานวิจัยสายนี้เกือบทั้งหมดทดสอบกับ "ความขัดแย้งเชิงเนื้อหา" ในเอกสารทั่วไป (เช่น Wikipedia, ข่าว) แต่ยังไม่มีงานที่ทดสอบกับ **ความขัดแย้งเชิงตัวเลขในเอกสารการเงินที่มีโครงสร้าง (structured filings)** โดยตรง ซึ่งมีความซับซ้อนเฉพาะทาง เช่น การแยก "การ restate ตัวเลขจริง" (MSFT's ASC 606 restatement: $20,453M → $21,928M) ออกจาก "การรวมสอง accounting concept ที่ต่างกันโดยไม่ได้ตั้งใจ" (MSFT's `LongTermDebtNoncurrent` vs `LongTermDebt`) — ทั้งสองกรณีนี้ ถ้าดูแค่ตัวเลขจะดู "ขัดแย้งกัน" เหมือนกัน แต่ต้องการวิธีจัดการที่ต่างกันโดยสิ้นเชิง (กรณีแรกควรเชื่อค่าล่าสุด กรณีหลังไม่ควรถูกมองว่าเป็นความขัดแย้งเลยด้วยซ้ำ) โปรเจกต์นี้แก้ปัญหานี้ด้วยกฎ same-accession-number collision ใน `xbrl_extract.py` ซึ่งเป็น heuristic เฉพาะโดเมนที่ไม่ปรากฏในวรรณกรรม RAG ทั่วไป

---

## 5. ความน่าเชื่อถือและความคงเส้นคงวาของ LLM Agent (Reliability & Consistency)

นี่คือสายวรรณกรรมที่เพิ่งเกิดขึ้นชัดเจนในปี 2026 และเป็นสายที่ผลการทดลอง Consistency Experiment ของโปรเจกต์นี้ (63 runs, 9 บริษัท × 7 รอบ) เชื่อมโยงได้ตรงที่สุด งานที่ตรงประเด็นที่สุดสองชิ้นคือ **How Consistent Are LLM Agents? Measuring Behavioral Reproducibility in Multi-Step Tool-Calling Pipelines** (arXiv:2605.28840, 2026) และ **When Agents Disagree With Themselves: Measuring Behavioral Consistency in LLM-Based Agents** (arXiv:2602.11619, 2026) ซึ่งพบว่าเมื่อรัน ReAct-style agent ซ้ำ 3,000 ครั้งบน benchmark HotpotQA ด้วย input เดียวกัน Agent ให้ **ลำดับ action ที่ต่างกัน 2.0–4.2 แบบ จากทุก 10 รอบ** โดยเฉลี่ย และเคสที่ agent ให้ action sequence เหมือนกันทุกรอบกลับมี accuracy เพียง 25–60% เท่านั้น (ต่างจากเคสที่ inconsistent อยู่ 32–55 percentage points) — สะท้อนว่า "ความเสถียรของกระบวนการ" กับ "ความถูกต้องของคำตอบ" เป็นคนละมิติกัน ซึ่งตรงกับสิ่งที่โปรเจกต์นี้พบ: **Status เสถียร 100%, Human-review verdict เสถียร 97.9%, แต่ tool-selection process เสถียรแค่ 71.4%** — ยืนยันแพทเทิร์นเดียวกันในบริบทการเงินโดยเฉพาะ

งานสำรวจ *Evaluation and Benchmarking of LLM Agents: A Survey* (arXiv:2507.21504, 2025) ระบุตรงๆ ว่า "variance ข้ามการรันซ้ำแทบไม่เคยถูกรายงาน" ในงานประเมิน Agent ส่วนใหญ่ ทั้งที่ในบริบทที่มีเดิมพันสูง (การเงิน สุขภาพ กฎหมาย) การวัด self-consistency ได้กลายเป็น "สิ่งจำเป็นพื้นฐาน" ไม่ใช่ทางเลือกเสริมอีกต่อไป

ในสายที่เกี่ยวข้อง **Know Your Limits: A Survey of Abstention in Large Language Models** (2025) และ **Cost-Sensitive Conformal Prediction and Human-in-the-Loop Abstention for Imbalanced High-Stakes Decision Support** (arXiv:2607.27143, 2026) ทบทวนกลไก "การงดตอบ" (abstention) ในบริบทที่มีเดิมพันสูง โดยชี้ว่าการปฏิเสธตอบหรือส่งต่อให้มนุษย์ตรวจสอบเมื่อความไม่แน่นอนสูง ช่วยลดความเสียหายได้แม้จะแลกมาด้วย coverage ที่ลดลง — ตรงกับกลไก Adaptive Human-in-the-Loop ของโปรเจกต์นี้ ที่ Agent ตัดสินใจ escalate ให้มนุษย์ตรวจสอบเฉพาะเมื่อพบ evidence ขัดแย้งหรือสถานะรุนแรง (Broken/Not-enough-data) แทนที่จะ escalate ทุกเคสหรือไม่ escalate เลย

**ช่องว่าง:** งานวิจัยสาย consistency ส่วนใหญ่ทดสอบกับ benchmark ทั่วไป (HotpotQA, coding tasks) ที่มีคำตอบถูกผิดชัดเจนแบบ binary ไม่มีงานที่วัด consistency ของ Agent ในบริบทที่ **คำตอบสุดท้ายต้องแม่นยำ (deterministic) แต่กระบวนการให้เหตุผลเป็นการตัดสินใจเชิงคุณภาพ (qualitative judgment)** พร้อมกัน อย่างในกรณี "ควร escalate ให้มนุษย์ตรวจสอบหรือไม่" — โปรเจกต์นี้เป็นกรณีศึกษาที่แยกวัดทั้งสามชั้น (status, human-review verdict, tool-selection path) พร้อมกันในโดเมนการเงินจริง ซึ่งยังไม่พบในวรรณกรรมที่สืบค้นได้

---

## 6. การติดตามเหตุผลการลงทุนอย่างต่อเนื่อง (Continuous Investment Thesis Tracking)

นี่คืองานวิจัยที่ใกล้เคียงกับแก่นของโปรเจกต์นี้ที่สุด **High-Stakes Personalization: Rethinking LLM Customization for Individual Investor Decision-Making** (arXiv:2604.04300, 2026) เสนอแนวคิด **"living thesis"** — โครงสร้างเหตุผลการลงทุนรายหุ้นที่บันทึกไม่ใช่แค่ "ถืออะไร" แต่ "ทำไมถึงถือ" ประกอบด้วย conviction statement, validation trigger, break condition, macro dependency และ catalyst ที่จะมาถึง โดยแต่ละ thesis จะถูกประเมินใหม่ทุกวันผ่านการเรียก LLM ครั้งหนึ่งที่คืนค่าสถานะแบบมีโครงสร้าง: **CONFIRMED (+1), UNCHANGED (0), WEAKENED (-1), BROKEN (-2)** — ระบบต้นแบบชื่อ InvestMate ผสานการจัดการ living thesis, การให้คะแนนความเชื่อมั่นรายวัน, การดึง behavioral memory และการตรวจจับ drift เข้าด้วยกัน

แนวคิดนี้ใกล้เคียงกับสถานะ Supported/Weakened/Broken/Not-enough-data ของโปรเจกต์นี้อย่างเห็นได้ชัด อย่างไรก็ตาม เมื่อตรวจสอบเนื้อหาของงานนี้โดยละเอียด (WebFetch ตัว abstract และเนื้อหาโดยตรง) พบว่า **เป็นเอกสารระดับ position/vision paper ความยาว 4 หน้าสำหรับ workshop** ที่ระบุ "ความท้าทายเชิงแนวคิด" (behavioral memory complexity, thesis consistency under drift, style-signal tension, alignment without ground truth) เป็นหลัก **โดยไม่มี**:

- การตรวจสอบหลักฐานข้ามหลายแหล่งอิสระ (multi-source verification)
- กลไก point-in-time / การป้องกัน look-ahead bias ที่ implement จริง
- Agent ที่ investigate สาเหตุความผิดปกติด้วยการอ่านเอกสารต้นทาง (primary document)
- การวัด run-to-run consistency เชิงประจักษ์
- กรอบตรวจจับ data artifact เช่น restatement หรือ XBRL tagging error

กล่าวคือ งานชิ้นนี้ตั้งคำถามและเสนอ "รูปร่าง" ของปัญหาไว้อย่างสวยงาม แต่ยังไม่มีการ implement หรือ evaluate เชิงประจักษ์ในมิติที่โปรเจกต์นี้ทำจริงทั้งหมด — ไม่ว่าจะเป็น pipeline การตรวจสอบ 3 ชั้น (XBRL → 8-K → primary text, 352 entries, 89% confirmed), การทดลองเปรียบเทียบ 4 วิธี 45 เคสกับ reference set อิสระ, หรือการวัด consistency เชิงปริมาณ 63 การรัน

**ช่องว่าง:** โปรเจกต์นี้อาจเป็นหนึ่งในงานแรกๆ ที่ **implement แนวคิด "living thesis / continuous investment reason revalidation" ให้เป็นระบบที่รันได้จริง พร้อม evidence pipeline ที่ตรวจสอบได้ และผลการทดลองเชิงประจักษ์** แทนที่จะหยุดอยู่ที่ระดับการเสนอแนวคิด — นี่คือช่องว่างที่ชัดเจนที่สุดที่โปรเจกต์นี้ปิด และเป็นเหตุผลสนับสนุนที่หนักแน่นที่สุดสำหรับ Research Question ปัจจุบันของงาน

---

## 7. การให้ Decision Support ที่สอดคล้องกับบริบทของผู้ลงทุนแต่ละคน (Personalized & Context-Aware Decision Support)

งานวิจัยที่ตรงประเด็นที่สุดในสายนี้ปรากฏขึ้นล่าสุดคือ **Evaluating Investment Logic in Large Language Models: A Real-World Benchmark Towards Personalized Financial Agents** หรือที่รู้จักในชื่อ **InvestLogicBench** (Jiang, Zou, Lin, Yu, Huang, Jia, & Dai, arXiv:2608.06108, 2026) ซึ่งสร้าง benchmark จากการตัดสินใจจริงกว่า 201,247 รายการของนักลงทุนจริง 151 คน โดยตั้งข้อสังเกตเชิงระเบียบวิธีที่สำคัญมากว่า **หลักฐานตลาดชุดเดียวกันสามารถนำไปสู่การตัดสินใจที่ถูกต้องได้หลายแบบ** ขึ้นอยู่กับเป้าหมาย ระยะเวลาการลงทุน พอร์ตที่ถืออยู่ และขอบเขตความเสี่ยงของนักลงทุนแต่ละคน งานนี้จึงออกแบบ annotation schema เป็นห่วงโซ่ **Profile → Event → Reasoning → Decision → Outcome** แทนที่จะประเมินแค่ "หลักฐาน → คำตอบที่ถูกต้องหนึ่งเดียว" แบบ benchmark การเงินทั่วไป และชี้ว่า LLM ปัจจุบันยังปฏิบัติต่อนักลงทุนทุกคนเหมือนกันเมื่อเจอเหตุการณ์เดียวกัน ทั้งที่ในทางปฏิบัติไม่ควรเป็นเช่นนั้น

สอดคล้องกับที่กล่าวถึงในหัวข้อ 6 **High-Stakes Personalization: Rethinking LLM Customization for Individual Investor Decision-Making** (arXiv:2604.04300, 2026) ก็เน้นย้ำประเด็นเดียวกันจากอีกมุม คือระบบต้องรักษาสมดุลระหว่าง personal investment philosophy ของผู้ใช้กับ objective evidence ที่อาจขัดกับความเชื่อเดิม — ซึ่งเป็นหลักการที่บังคับให้การ personalize ต้องเกิดขึ้น **หลัง** จากหลักฐานถูกตรวจสอบอย่างเป็นกลางแล้วเท่านั้น ไม่ใช่บิดหลักฐานให้เข้ากับสิ่งที่ผู้ใช้อยากได้ยิน ส่วน **LLM-based Personalized Portfolio Recommender: Integrating Large Language Models and Reinforcement Learning for Intelligent Investment Strategy Optimization** (arXiv:2512.12922, 2025/2026) แสดงให้เห็นว่าการออกแบบคำแนะนำให้สัมพันธ์กับ individual risk preference และสภาวะตลาดโดยตรง เป็นแนวทางที่ถูกยอมรับในวรรณกรรมสายนี้อยู่แล้ว ไม่ใช่แนวคิดที่ถูกสร้างขึ้นใหม่เฉพาะกิจ

**ช่องว่าง:** แม้ InvestLogicBench จะเป็นงานที่ตรงประเด็นที่สุดและยืนยันว่าโจทย์ "หุ้นเดียวกันไม่ควรได้คำแนะนำเดียวกันสำหรับทุกคน" เป็นปัญหาวิจัยจริง แต่ตัวงานเองยังเป็น **benchmark สำหรับประเมิน** LLM ที่มีอยู่ ไม่ใช่ระบบที่เสนอสถาปัตยกรรมแก้ปัญหา และไม่ได้ผูกกับกลไก point-in-time evidence หรือ multi-source verification ที่โปรเจกต์นี้มีอยู่แล้วในชั้น Objective Evidence — ส่วน High-Stakes Personalization ก็ยังคงเป็น position paper ที่ไม่มี implementation (ดูหัวข้อ 6) โปรเจกต์นี้ปิดช่องว่างนี้ด้วยการ **แยกสถาปัตยกรรมเป็น 2 ชั้นอย่างชัดเจน**: Objective Evidence Layer (ไม่ personalize, สถานะ Supported/Weakened/Broken เหมือนกันสำหรับทุกคน) และ Investor Context Layer (แปลสถานะเดียวกันเป็น priority tier ที่ต่างกันตาม risk tolerance, investment horizon, position size และ objective ของผู้ใช้แต่ละคน) พร้อมมี Evidence Integrity Safeguard Experiment ตรวจสอบเชิงประจักษ์ว่าการ personalize ในชั้นที่สองไม่เคยรั่วไปบิดข้อเท็จจริงในชั้นแรก — เป็นการตอบโจทย์ที่ InvestLogicBench ตั้งคำถามไว้ (same evidence, different valid decisions ตาม profile) ด้วยสถาปัตยกรรมที่ตรวจสอบความซื่อสัตย์ของหลักฐานได้โดยตรง ซึ่งยังไม่ปรากฏในงานทั้งสามชิ้นนี้

---

## 8. บริบทเสริม: Data Quality ในเอกสารการเงินแบบมีโครงสร้าง (XBRL)

แม้จะไม่ใช่สายวรรณกรรม Agentic AI โดยตรง แต่ประเด็นคุณภาพข้อมูลใน XBRL มีความสำคัญมากต่อ Contribution 2 ของโปรเจกต์นี้ การวิเคราะห์ของ XBRL US Data Quality Committee (อ้างอิงใน "XBRL 2025: Driving Transparency, Accuracy, and Compliance in Financial Reporting") จากการตรวจสอบ filing กว่า 2,000 ฉบับ พบว่า **invalid axis-member combination คือประเภทข้อผิดพลาดที่พบบ่อยที่สุด (34% ของข้อผิดพลาดทั้งหมด)** ตามด้วย negative-value error (12%) — ยืนยันว่าปัญหาคุณภาพข้อมูลใน XBRL เป็นปรากฏการณ์ที่มีอยู่จริงและมีขนาดใหญ่ ไม่ใช่กรณีพิเศษ งานวิจัย *Financial misstatement detection: a realistic evaluation* (arXiv:2305.17457, 2023) และ **FinVerBench: Benchmark Validity and Calibration in Large Language Model Financial Statement Verification** (arXiv:2605.29586, 2026) ตอกย้ำว่าการตรวจสอบความถูกต้องของงบการเงินยังเป็นปัญหาเปิดที่โมเดลปัจจุบันยังทำได้ไม่สมบูรณ์

โปรเจกต์นี้พบตัวอย่างที่เป็นรูปธรรมของปัญหานี้เองระหว่างการพัฒนา: Oracle's FY2020 10-K tag ตัวเลขรายได้รายปี ($39.4B) ด้วยวันที่ start/end ที่มีความยาว 91 วัน (ผ่าน filter single-quarter ของระบบ) ซึ่งเป็นความไม่สอดคล้องภายในของการ tag เอง ไม่ใช่บั๊กของโค้ดที่ extract ข้อมูล — ตัวอย่างเชิงประจักษ์นี้เพิ่มน้ำหนักให้ข้อค้นพบของ XBRL US DQC ในบริบทของงานวิจัยนี้โดยตรง

---

## ตารางสรุป: ช่องว่างในวรรณกรรม → วิธีที่โปรเจกต์นี้ปิดช่องว่าง

| # | ช่องว่างในวรรณกรรม | งานอ้างอิงหลัก | สิ่งที่โปรเจกต์นี้ทำจริง |
|---|---|---|---|
| 1 | Agentic RAG ยังไม่แยกวัด "คุณภาพกระบวนการ" ออกจาก "ความแม่นยำคำตอบ" | Agentic RAG survey (2501.09136); Finance Agent Benchmark (2508.00828) | `run_full_experiment.py`: Rule-based/Agent เท่ากันที่ Accuracy 100% แต่ต่างกันที่ investigation depth (`get_filing_context`) |
| 2 | Grounding ตรวจแค่ "คำอธิบายตรงกับหลักฐานที่ retrieve มาไหม" ไม่ตรวจ "หลักฐานตั้งต้นถูกไหม" | FinGround (2604.23588); FinCoT (2506.16123) | Verification pipeline 3 ชั้น (XBRL→8-K→primary text), พบบั๊ก extraction จริง 6 ครั้ง |
| 3 | Look-ahead bias แก้ที่ระดับโมเดล (decoding/training) ซึ่งต้องการทรัพยากรมาก | Look-Ahead-Bench (2601.13770); FinCAD (2605.24564) | แก้ที่ระดับ pipeline ด้วย `facts_as_of()` filter ตาม filed date — ตรวจสอบได้ตรง ไม่ต้อง retrain |
| 4 | RAG จัดการ conflicting evidence แบบทั่วไป ไม่ได้ทดสอบกับตัวเลขการเงินที่มีโครงสร้าง | RAG with Conflicting Evidence (2504.13079); Astute RAG (2410.07176) | แยก "restatement จริง" ออกจาก "คนละ accounting concept" ด้วย same-accession-number heuristic เฉพาะโดเมน |
| 5 | Consistency ของ Agent วัดแค่ benchmark ทั่วไป ไม่มีบริบทที่ต้องแม่นยำ+ตัดสินใจเชิงคุณภาพพร้อมกัน | How Consistent Are LLM Agents? (2605.28840); Agents Disagree With Themselves (2602.11619) | วัด 3 ชั้นพร้อมกันในโดเมนการเงินจริง: Status 100%, Review 97.9%, Tool-path 71.4% (63 runs จริง) |
| 6 | "Living thesis" ถูกเสนอเป็นแนวคิดเท่านั้น ไม่มี implementation/evaluation | High-Stakes Personalization (2604.04300) — position paper 4 หน้า | Implement เต็มระบบ + ทดลองเชิงประจักษ์ (352-case verification, 45-case baseline experiment, 63-run consistency test) |
| 7 | หลักฐานเดียวกันควรนำไปสู่การตัดสินใจต่างกันตาม investor profile แต่มีแค่ benchmark ประเมินปัญหานี้ ยังไม่มีสถาปัตยกรรมที่แก้ + ป้องกันการบิดข้อเท็จจริง | InvestLogicBench (2608.06108); High-Stakes Personalization (2604.04300) | แยก Objective Evidence Layer / Investor Context Layer อย่างเคร่งครัด + Evidence Integrity Safeguard Experiment ตรวจสอบว่า personalization ไม่บิด evidence status |

---

## References

1. Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., & Cao, Y. (2023). *ReAct: Synergizing Reasoning and Acting in Language Models*. ICLR 2023.
2. *Agentic Large Language Models, a survey*. arXiv:2503.23037 (2025).
3. *Large Language Model Agents in Finance: A Survey*. EMNLP Findings 2025. aclanthology.org/2025.findings-emnlp.972
4. *Agentic Trading: When LLM Agents Meet Financial Markets*. arXiv:2605.19337 (2026).
5. *Finance Agent Benchmark: Benchmarking LLMs on Real-world Financial Research Tasks*. arXiv:2508.00828 (2025).
6. Lu et al. *FinToolBench* (2026).
7. *FinGround: Detecting and Grounding Financial Hallucinations via Atomic Claim Verification*. arXiv:2604.23588 (2026).
8. *FinCoT: Grounding Chain-of-Thought in Expert Financial Reasoning*. arXiv:2506.16123 (2025).
9. *FinEval-KR: A Financial Domain Evaluation Framework for Large Language Models' Knowledge and Reasoning*. arXiv:2506.21591 (2025).
10. *FinChain: A Symbolic Benchmark for Verifiable Chain-of-Thought Financial Reasoning*. arXiv:2506.02515 (2025).
11. *Summoning the Oracle to Slay It: Mitigating Look-Ahead Bias in Financial Backtesting with Large Language Models*. arXiv:2605.24564 (2026).
12. *Look-Ahead-Bench: a Standardized Benchmark of Look-ahead Bias in Point-in-Time LLMs for Finance*. arXiv:2601.13770 (2026).
13. *Scaling Point-in-Time Language Models*. arXiv:2607.11889 (2026).
14. *AI's Predictable Memory in Financial Analysis*. ScienceDirect (2025), S0165176525004392.
15. *Retrieval-Augmented Generation with Conflicting Evidence*. arXiv:2504.13079 (2025).
16. *Astute RAG: Overcoming Imperfect Retrieval Augmentation and Knowledge Conflicts for Large Language Models*. arXiv:2410.07176 (2024).
17. *Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG*. arXiv:2501.09136 (2025).
18. *DRAGged into Conflicts: Detecting and Addressing Conflicting Sources in Search-Augmented LLMs*. arXiv:2506.08500 (2025).
19. *How Consistent Are LLM Agents? Measuring Behavioral Reproducibility in Multi-Step Tool-Calling Pipelines*. arXiv:2605.28840 (2026).
20. *When Agents Disagree With Themselves: Measuring Behavioral Consistency in LLM-Based Agents*. arXiv:2602.11619 (2026).
21. *Evaluation and Benchmarking of LLM Agents: A Survey*. arXiv:2507.21504 (2025).
22. *Know Your Limits: A Survey of Abstention in Large Language Models* (2025).
23. *Cost-Sensitive Conformal Prediction and Human-in-the-Loop Abstention for Imbalanced High-Stakes Decision Support: A Multi-Domain Benchmark*. arXiv:2607.27143 (2026).
24. *High-Stakes Personalization: Rethinking LLM Customization for Individual Investor Decision-Making*. arXiv:2604.04300 (2026).
25. Jiang, Y., Zou, J., Lin, Z., Yu, X., Huang, Q., Jia, S., & Dai, S. (2026). *Evaluating Investment Logic in Large Language Models: A Real-World Benchmark Towards Personalized Financial Agents* (InvestLogicBench). arXiv:2608.06108.
26. *LLM-based Personalized Portfolio Recommender: Integrating Large Language Models and Reinforcement Learning for Intelligent Investment Strategy Optimization*. arXiv:2512.12922 (2025/2026).
27. *A Survey of Large Language Models for Financial Applications: Progress, Prospects and Challenges*. arXiv:2406.11903 (2024).
28. *Financial misstatement detection: a realistic evaluation*. arXiv:2305.17457 (2023).
29. *FinVerBench: Benchmark Validity and Calibration in Large Language Model Financial Statement Verification*. arXiv:2605.29586 (2026).
30. XBRL US Data Quality Committee analysis, cited in "XBRL 2025: Driving Transparency, Accuracy, and Compliance in Financial Reporting," ez-XBRL.com.

---

## หมายเหตุเชิงระเบียบวิธี

เอกสารนี้จัดทำโดยสืบค้นผ่าน web search (สิงหาคม 2026) โดยยึดหลักไม่ปั้นแต่งชื่อผู้แต่งหรือรายละเอียดที่ไม่สามารถยืนยันได้จากผลการสืบค้นจริง — บทความที่ไม่มีชื่อผู้แต่งปรากฏในผลการสืบค้นจะอ้างอิงด้วยชื่อบทความและ arXiv ID แทนการเดาชื่อผู้แต่ง เพื่อให้ผู้อ่านตรวจสอบย้อนกลับไปยังต้นฉบับได้โดยตรงผ่าน arXiv ID ที่ระบุไว้ทุกรายการ กรณีบทความ *High-Stakes Personalization* (arXiv:2604.04300) ได้ทำการ fetch เนื้อหาโดยตรง (ไม่ใช่แค่ผลสรุปจาก search) เพื่อยืนยันว่าเป็น position paper ที่ไม่มี implementation จริง ก่อนนำมาใช้เป็นหลักฐานสนับสนุนช่องว่างข้อ 6
