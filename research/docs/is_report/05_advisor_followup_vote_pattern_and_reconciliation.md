# 05 ตอบคำถามอาจารย์: Vote pattern และ Input ของ Reconciliation Agent

> **POST-HOC EXPLORATORY** — วิเคราะห์หลังประเมินผล Gold 150 ตาม preregistration แล้ว ไม่ใช่ผลยืนยัน ไม่แก้ label, prediction หรือ `evaluation.json` ไม่เรียก API
> สคริปต์ `scripts/posthoc_vote_pattern.py` → `results/posthoc_20261119/vote_pattern/vote_pattern_summary.json` (มี sha256 ของ input และสคริปต์)

คำถามจากอาจารย์ (2026-11-16):
1. "each claim has vote pattern, can we analyze anything in association with this column?"
2. "How did you set LLM for reconciliation. What are input data for this agent?"

---

## ส่วนที่ 1 Vote pattern

**Vote pattern คืออะไร:** label เริ่มต้นจาก LLM 3 ตัว (Claude Opus 5.5 | Gemini 4 Argon | GPT-6.0 Astra) ก่อน AI-assisted adjudication และก่อนผู้วิจัยทบทวน จึง**ไม่ใช่ gold label** ใช้เป็นตัวแทน "ความยาก/ความกำกวม" ของ claim

### 1.1 การกระจาย

| กลุ่ม | จำนวน | numerical | interpretive | ambiguous |
|---|---:|---:|---:|---:|
| เห็นตรงกัน 3/3 (unanimous) | 100 | 46 | 28 | 26 |
| เสียงข้างมาก 2-1 | 46 | 4 | 18 | 24 |
| แตก 3 ทาง | 4 | 0 | 4 | 0 |

- ข้อ numerical เกือบทั้งหมด (46/50) เป็น unanimous แต่ข้อ ambiguous ราวครึ่งหนึ่ง (24/50) มีเสียงแตก
- ใน 46 ข้อที่เป็น 2-1 มี gold ตรงกับเสียงข้างมาก 33 ข้อ และ adjudication กลับเป็นเสียงข้างน้อย 13 ข้อ
- นับรวมข้อ unanimous ด้วย มี 18 ข้อที่ gold ไม่ตรงกับเสียงข้างมากของ annotator

### 1.2 ความแม่นยำแยกตามกลุ่ม

| Arm | Unanimous (100) | 2-1 (46) | 3 ทาง (4) | รวมข้อที่ไม่ unanimous (50) | gold ≠ เสียงข้างมาก (18) |
|---|---:|---:|---:|---:|---:|
| A1 RAG | 78 | 14 | 2 | 16 (32%) | 2 |
| **A2 RAG + XBRL** | **84** | 17 | 2 | 19 (38%) | 2 |
| SR self-reflection | 79 | **22** | 1 | **23 (46%)** | **8** |
| A3v2.1.1 R | 83 | 17 | 0 | 17 (34%) | 4 |
| A3v2.1.1 RG | **86** | 13 | 0 | 13 (26%) | 2 |
| **A3v2_2e** | **83** | 15 | 0 | 15 (30%) | 3 |

ข้อสังเกต:
- **ทุก arm ทำได้ดีในข้อ unanimous (78–86%) และตกลงมาก (26–46%) ในข้อที่ annotator เห็นไม่ตรงกัน** ความยากของ claim (วัดจาก vote) จึงอธิบายความผิดพลาดได้มากกว่าความต่างระหว่าง approach
- ในข้อ unanimous A3v2_2e (83) กับ A2 (84) แทบเท่ากัน ส่วน A3v2.1.1 RG ได้ 86 ซึ่งสูงกว่า A2
- ในข้อที่ gold ไม่ตรงกับเสียงข้างมาก ทุก arm ได้ต่ำมาก (2–8/18) เพราะ model มักตอบแบบเดียวกับเสียงข้างมาก SR ได้สูงสุด (8/18)
- **คำตอบผิดส่วนใหญ่ในข้อ 2-1 ตรงกับ label ของ annotator อย่างน้อย 1 ตัว** (A2 23/29, A3v2_2e 25/31) หมายความว่าคำตอบเหล่านี้เป็นการอ่านที่มีคนอื่นอ่านแบบเดียวกัน ไม่ใช่ผิดแบบไร้เหตุผล ส่วนในข้อ unanimous สัดส่วนนี้ต่ำ (A2 4/16, A3v2_2e 4/17)

### 1.3 A2 เทียบ A3v2_2e แบบจับคู่ (ข้อที่ถูกฝั่งเดียว)

| กลุ่ม | n | A2 ถูก A3 ผิด | A3 ถูก A2 ผิด | สุทธิ | McNemar p (exploratory) |
|---|---:|---:|---:|---:|---:|
| Unanimous | 100 | 6 | 5 | A2 +1 | 1.0 |
| ไม่ unanimous | 50 | 9 | 5 | A2 +4 | 0.424 |
| **รวม 150** | 150 | 15 | 10 | A2 +5 (103 เทียบ 98) | — |

- **A2 ชนะ A3v2_2e สุทธิ 5 ข้อ ในจำนวนนี้ 4 ข้อมาจากข้อที่ annotator เห็นไม่ตรงกัน** ในข้อที่ชัดเจน (unanimous) ทั้งสองแทบเท่ากัน
- รูปแบบใน 14 ข้อที่ไม่ unanimous และถูกฝั่งเดียว:
  - **A3 ผิด 9 ข้อ:** 6 ข้อเป็นกรณีที่ A3 ถอยไปตอบ INSUFFICIENT_EVIDENCE ทั้งที่ gold ตัดสินได้ ได้แก่ GOOGL-08, GOOGL-13, META-15, MSFT-12, WMT-11, WMT-15 อีก 3 ข้อ A3 ตอบ SUPPORTED เกินหลักฐาน ได้แก่ AMZN-08 (gold เป็น INSUFFICIENT), NVDA-07 และ WMT-08 (gold เป็น CONTRADICTED) ส่วน WMT-08 เป็นข้อที่ annotator แตก 3 ทาง
  - **A3 ถูก 5 ข้อ:** ทั้ง 5 ข้อเป็นกรณีที่ A3 ถอยไป INSUFFICIENT ถูกต้องในขณะที่ A2 ตัดสินเกินหลักฐาน ได้แก่ AAPL-13, AMZN-06, AMZN-13, MSFT-14, WMT-07
  - กลไกถอยไป INSUFFICIENT ของ A3v2_2e (decidability gate, D-sup, guard) จึงแก้ปัญหา v1 ที่เปลี่ยนเป็น SUPPORTED/CONTRADICTED เกินหลักฐานได้บางส่วน แต่ทำงาน**เกินขนาด**ในข้อกำกวม ได้ 5 เสีย 6 ซึ่งตรงกับ over-abstention ที่ doc 13 พบ และยังมีข้อที่เปลี่ยนเป็น SUPPORTED เกินหลักฐานเหลืออยู่ 3 ข้อ

### 1.4 สรุปสำหรับอาจารย์
1. Vote pattern เป็นตัวแบ่งความยากที่ชัดที่สุด: unanimous ได้ราว 80–86% ส่วนข้อที่ไม่ unanimous ได้ราว 26–46% ในทุก arm
2. ความต่าง A2 กับ A3 แทบทั้งหมดอยู่ในข้อที่ไม่ unanimous ซึ่งเป็นข้อที่ LLM 3 ตัวก็ตอบไม่ตรงกันเอง การตัดสินว่า A3 แพ้จริงในข้อเหล่านี้จึงขึ้นกับ adjudication ของ gold มาก
3. ข้อเสนอสำหรับงานต่อ (ยังไม่ได้ทำ):
   - รายงานผลแยกเป็น "unanimous subset" ควบคู่กับผลรวม
   - ใช้ความไม่ตรงกันของ annotator เป็นสัญญาณให้ router (แนวทาง R ใน doc 14) ส่งข้อกำกวมไปให้ A3 ทำงานลึกกว่า หรือให้ตอบพร้อมระบุว่ากำกวม
   - ทั้งหมดนี้เป็นสมมติฐานที่ต้องทดสอบบนชุดข้อมูลใหม่ ห้ามปรับบน Gold 150

**ข้อจำกัด:**
- n ของกลุ่มย่อยเล็ก (โดยเฉพาะกลุ่ม 3 ทางมี 4 ข้อ) ค่า p ใช้เพื่อพรรณนาเท่านั้น
- vote มาจาก LLM ไม่ใช่มนุษย์
- annotator ตัวหนึ่ง (Claude Opus 5.5) เป็นตระกูลเดียวกับโมเดลที่ใช้ใน arm (Claude Sonnet 4.5)

---

## ส่วนที่ 2 Reconciliation Agent ของ A3v2_2e ตั้งค่าอย่างไร และรับ input อะไร

### 2.1 การตั้งค่า (จาก `manifest.json` ของ run Gold)
- **โมเดล:** `claude-sonnet-4-5-20250929` ใช้ตัวเดียวกันทุก arm และทุก node
- **temperature 0**, max output 1,500 tokens
- บังคับตอบผ่าน tool `submit_reconciliation` (structured output)
- **RAG:** BM25, chunk 1,200 ตัวอักษร, overlap 200, top-k 6 และเพิ่ม top-k 3 ต่อคำค้นโต้แย้ง
- **โต้แย้ง:** สูงสุด 3 ข้อ และค้นหลักฐานเพิ่มได้ไม่เกิน 4 ครั้งต่อ claim
- **งบต่อ claim:** LLM ไม่เกิน 6 call และ input ไม่เกิน 80k tokens

### 2.2 ลำดับ node ใน LangGraph (`a3v2/graph.py:240-262`)
```
retrieve_evidence → initial_verdict → numeric_verification (A2 จบตรงนี้)
→ analyze_claim → generate_hypotheses → counter_investigation
→ evidence_review → reconcile_v2 → apply_guards → reconciliation_guard → finalize
```

### 2.3 Input ของ `reconcile_v2` (`a3v2/graph.py:106-127`)

Reconciliation **ต่อจากบทสนทนาเดิม** (`experiments/pipeline.py:104` `ClaimRun.ask`) จึงเห็นทุกอย่างที่ A2 เห็น แล้วได้ packet ใหม่เพิ่มดังนี้

| Input | มาจาก node | เนื้อหา |
|---|---|---|
| ประวัติบทสนทนา | retrieve_evidence, initial_verdict | claim, passage SEC 6 ชิ้นแรก, คำตอบเริ่มต้นพร้อม citation |
| `initial_verdict` | numeric_verification | label ของ A2 (หลังตรวจตัวเลข XBRL) และ claim_type |
| `assertions` | analyze_claim | claim ถูกแตกเป็นข้อความย่อยที่ตรวจได้ (ข้อความ, ชนิด, งวดเวลา) |
| `hypotheses` | generate_hypotheses | ข้อโต้แย้งไม่เกิน 3 ข้อ แต่ละข้อมีคำค้นภาษาอังกฤษและ numeric check ได้ 1 รายการ |
| `counter_evidence` | counter_investigation | passage SEC ใหม่ที่ค้นได้ด้วย BM25 จากคำค้นโต้แย้ง |
| `counter_numeric` | counter_investigation | ตัวเลขที่คำนวณแบบ deterministic จาก XBRL ตาม numeric check |
| `evidence_review` | evidence_review | ตารางผลตรวจหลักฐานรายชิ้นจาก **LLM ตัวที่สองที่แยกบทสนทนา** (`a3v2/reviewer.py:52` `ask_isolated`) และไม่เห็นคำตอบเดิม: relation (ENTAILS / CONTRADICTS / RELATED_NOT_DECIDING / IRRELEVANT), ผลตรวจ quote, บริษัท, ความเข้ากันของงวดเวลา (period_compatibility), statement_time (ข้อเท็จจริงในอดีตหรือการคาดการณ์), definition mismatch |

### 2.4 คำสั่งที่ให้ (`engine/prompts.py:118`, `a3v2/prompts.py:78-92`)
1. ตัดสินข้อโต้แย้งทีละข้อเป็น CHALLENGE_SUPPORTED (ต้องอ้าง quote ตรงตัว), CHALLENGE_REFUTED หรือ NO_RELEVANT_EVIDENCE โดย**การไม่พบหลักฐานไม่นับเป็นการสนับสนุนข้อโต้แย้ง**
2. ให้ label สุดท้ายพร้อมหลักฐาน และอธิบายว่าเปลี่ยนจากเดิมหรือไม่ เพราะอะไร
3. **เปลี่ยนคำตอบได้เฉพาะเมื่อหลักฐานที่ reviewer ให้ ENTAILS** (เปลี่ยนเป็น SUPPORTED) **หรือ CONTRADICTS** (เปลี่ยนเป็น CONTRADICTED) ส่วนการถอยไป INSUFFICIENT ทำได้เมื่อไม่มีหลักฐานที่ยังยืนยันคำตอบเดิม
4. ใช้ได้เฉพาะหลักฐานที่งวดเวลาตรง (EXACT_MATCH หรือ COMPATIBLE_AFTER_VERIFIED_DERIVATION)
5. การคาดการณ์ ("expect", "will") ไม่ใช้ยืนยันหรือหักล้างผลที่รายงานไปแล้ว

### 2.5 หลัง reconcile (ไม่ใช้ LLM)
- `apply_guards` และ `reconciliation_guard` ตรวจแบบ deterministic ว่าการเปลี่ยนคำตอบมีหลักฐานที่ผ่านการตรวจรองรับหรือไม่ ถ้าไม่ผ่าน**คืนคำตอบและ citation ของ A2**
- decidability gate และ E1 coverage: คำตอบ SUPPORTED/CONTRADICTED ต้องมี finding ที่ผ่านการตรวจ, กฎตัวเลขของ A2 ที่ใช้ได้ หรือ deterministic check ของ A3

### 2.6 เทียบกับไอเดียของอาจารย์ (16 พ.ย.)

| ไอเดียอาจารย์ | ใน A3v2_2e |
|---|---|
| เริ่มจากผล A2 | มีแล้ว: `initial_verdict` คือคำตอบของ A2 |
| A3.0 วิเคราะห์ผล A2 / ปรับ context | มีบางส่วน: `analyze_claim` แตก assertion และกำหนดงวดเวลา |
| A3.1 หาหลักฐานโต้แย้ง | มีแล้ว: `generate_hypotheses` และ `counter_investigation` |
| A3.15 ตรวจว่าหลักฐานเกี่ยวกับคำถามไหม | มีแล้ว: `evidence_review` (LLM แยกบทสนทนา) และ deterministic checks |
| วนจนกว่า A3.15 จะพอใจ | **ยังไม่มี** graph เป็นเส้นตรง ถ้าไม่ผ่านจะคืนคำตอบ A2 แทนการค้นใหม่ |
| A3.2 reconcile | มีแล้ว: `reconcile_v2` และ guard |
| Routing ข้อง่ายไปโมเดลถูก | **ยังไม่มี** มีแค่แผนใน doc 14 (แนวทาง R) |
