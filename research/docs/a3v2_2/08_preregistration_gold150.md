# Preregistration: A3 v2.2 บน Gold 150

STATUS: DRAFT

> **วิธีล็อก:** ผู้วิจัยยืนยันแล้วแก้บรรทัดบนเป็น `STATUS: LOCKED` พร้อมใส่ชื่อและวันที่ในหัวข้อ 10 จากนั้นนำ sha256 ของไฟล์นี้ไปใส่ใน `configs/a3v2_2_gold150.json` → `preregistration.sha256`
>
> **ผลของการล็อก:**
> - ระบบจะยอมรัน A3 v2 บน gold **เฉพาะเมื่อไฟล์นี้ LOCKED และ hash ตรง** (`a3v2/config.py`)
> - หลังล็อกแล้วแก้ไฟล์นี้ไม่ได้ ถ้าแก้ hash จะไม่ตรงและระบบจะไม่รัน ต้องทำเป็น amendment ไฟล์ใหม่พร้อมเหตุผล
>
> เอกสารนี้แทนที่ `04_preregistration.md` (ร่างสำหรับชุด heldout-v1) สำหรับการทดสอบบน Gold 150

## 1. คำถามวิจัยและสมมติฐาน
- **RQ1 (หลัก):** A3v2_2e ตรวจสอบ claim ทางการเงินได้แม่นกว่า A2 (RAG + ตรวจตัวเลขเชิงกำหนด) บนชุด Gold 150 หรือไม่
- **RQ2 (ตามแบบของอาจารย์, P1 / P2 / P3):** การค้นหลักฐานแย้งแบบมีโครงสร้าง (P3 = A3v2_2e) เพิ่มคุณค่าเหนือการให้ LLM วิจารณ์คำตอบตัวเองแบบทั่วไป (P2 = SR_self_reflection) หรือไม่ เมื่อใช้ LLM, เอกสาร และ retrieval ชุดเดียวกัน
- **สมมติฐาน (ของอาจารย์):** structured, assumption-driven counterevidence retrieval ทำให้การตรวจสอบ claim ทางการเงินน่าเชื่อถือขึ้นเมื่อเทียบกับ conventional RAG และ generic self-critique

## 2. ชุดทดสอบ
- **ชุดข้อมูล:** `datasets/gold_claims.jsonl` sha256 `1080323acda67ddb…`
  - 150 claim จาก 10 บริษัท
  - numerical 50, ambiguous 50, interpretive 50
- **Reference:** `datasets/workbooks/Final_Gold_v3_approved.xlsx` sha256 `e47897c48245f3e1…` ใช้ตัวโหลดเดียวกับ v1 (`engine.reference.load_reference`)
- **Scoring หลัก:** strict (label ตรงกันเท่านั้น)
  - variant adjudicated / lenient ของ v1 ใช้กับคำตอบของ v1 เท่านั้น จึงไม่ใช้กับการรันนี้
- **สถานะ "กึ่ง held-out" (ต้องเขียนในเล่ม):**
  - กฎของ v2.2e ทุกข้อ (G3b, Q1.1, G1, G4, D-sup, N1, N2, E1) ออกแบบบน dev-v0.2 ไม่ได้ออกแบบบน Gold
  - แต่ A3 v2 รุ่นแรกออกแบบจาก error analysis ของ A3 v1 บนชุด Gold 150 นี้
  - **D-sup ถูกเลือกหลังจากเห็นผล replay บน dev** (post hoc)
- **การสัมผัส Gold ก่อนหน้า (ต้องเปิดเผยในเล่ม):**
  - error analysis ของ v1 ดูคำตอบและ label ของ Gold **23 ข้อ** (`datasets/error_analysis/discordant_case_review__…csv`) ผลนี้ใช้ออกแบบ A3 v2.0
  - ผู้วิจัย adjudicate ข้อ INSUFFICIENT ของ v1 จำนวน **44 ข้อ** หลังเห็นคำตอบ v1 ผลนี้ใช้เฉพาะ variant adjudicated / lenient ไม่ได้แก้ label strict
  - **ไม่มีการแก้ label ของ Gold ในรอบ v2** ตรวจแล้ว: sha ของ `gold_claims.jsonl` และ workbook ตรงกับ freeze manifest ของ v1
  - dev-v0.2 มี AAPL / MSFT / AMZN เหมือน Gold แต่วันตัดหลักฐานต่างกัน ส่วนบริษัทอีก 7 แห่งของ Gold ไม่อยู่ใน dev
- **ที่มาของ label Gold:** `llm_annotated_ai_adjudicated_researcher_reviewed` (LLM ติด label, AI adjudicate, ผู้วิจัยตรวจ) ยังไม่ได้วัด inter-annotator agreement กับคนบน Gold
  - การ audit บน dev พบ label ผิด 1 ใน 72 ข้อ (INTC-07) จึงอาจมี label ผิดใน Gold ในสัดส่วนใกล้เคียงกัน ซึ่งกระทบทุก arm เท่ากัน
  - **ห้ามแก้ label Gold หลังเห็นผลรอบนี้**
- **runtime ไม่เห็น label:** pipeline ได้รับ `ClaimInput` ซึ่งมีเพียง id, บริษัท, ข้อความ, วันตัด, แหล่งที่อนุญาต และงวด `ClaimInput.from_record` จะ error ถ้ามี field ของ annotation หลุดมา ส่วน `claim_category` ใช้เฉพาะตอนเขียนผล ไม่ได้ส่งเข้า prompt

## 3. Arm (รันพร้อมกันครั้งเดียว ใช้ claim และ corpus เดียวกัน)

| Arm | config hash | บทบาท |
|---|---|---|
| A1_conventional_rag | `b978515979d7f241` | **P1** Standard RAG |
| A2_rag_numeric | `d5298a61c0ae91f8` | baseline หลัก (RAG + ตรวจตัวเลข) |
| SR_self_reflection | `166d47be253b74e9` | **P2** generic self-critique: A2 → วิจารณ์ตัวเอง ≤ 3 จุด → แก้คำตอบ **ไม่ retrieve ใหม่** |
| A3v2_1_1_R | `226a920c772a1af4` | A3 v2.1.1 แบบไม่มี guard (descriptive) |
| A3v2_1_1_RG | `84aba6df744a9382` | A3 v2.1.1 + guard 0.1 (replay ของ R, ไม่เสียเงินเพิ่ม) |
| **A3v2_2e** | `5bf41b202ff248b0` | **P3 / Final candidate (ตัวเดียว):** guard 0.3 (G3b) + quote check 1.1 + decidability prompt 0.1 + G1 + G4 + D-sup + numeric checks N1/N2 + E1 evidence coverage |
| V1: A3_contradiction_aware | จาก run ที่ freeze ไว้ `claimverif-main-v1-20261110T104207Z` | เปรียบเทียบรอง (ไม่รันใหม่) |

- **การควบคุมตัวแปร:** A1, A2, SR และ A3 ใช้ model, temperature, retrieval (top_k 6, chunk 1200/200), corpus, วันตัดหลักฐาน และ budget ต่อ claim เดียวกัน (fairness check ผ่าน) SR ใช้จำนวนรอบวิจารณ์ (3) เท่ากับจำนวน challenge ของ A3
- **Resource budget parity กับ resource consumption ไม่ใช่เรื่องเดียวกัน:**
  - **parity:** ทุก arm มีเพดานเท่ากัน คือ ≤ 6 LLM call, ≤ 80k input token และ ≤ 4 retrieval query ต่อ claim และใช้ output cap เดียวกัน
  - **consumption:** ใช้จริงไม่เท่ากัน ค่าวัดบน dev (median ต่อ claim):

    | Arm | LLM call | retrieval | input token | ต้นทุน |
    |---|---|---|---|---|
    | A1 / A2 | 1 | 1 | ≈ 3.8k | ≈ $0.020 |
    | SR | 3 | 1 | ยังไม่ได้วัด (วัดใน smoke test) | — |
    | A3v2_2e | 5 | 4 | ≈ 29k | ≈ $0.145 |

  - A3 ใช้ทรัพยากรประมาณ 7 เท่าของ A2 และมากกว่า SR (3 call) ต้องรายงานคู่กับความแม่นทุกครั้ง ห้ามอ้างว่า "ต้นทุนเท่ากัน"
- **Model:** `claude-sonnet-4-5-20250929`, temperature 0 (`backend/app/core/agent_config.py`)
- **Corpus:** `datasets/corpus_manifest.json` (61 เอกสาร ตรวจ sha ตรงครบ 61/61) แหล่ง SEC 10-K / 10-Q ตาม `allowed_sources` ของแต่ละ claim และไม่ใช้เอกสารที่ยื่นหลัง `as_of_date`
- **ไม่รันบน Gold:** A3v2_2 ที่ไม่มี E1 และ A3v2_2c (+contribution) ตาม pre-flight audit `09_preflight_audit.md` จึงมีระบบที่ทดสอบเพียงตัวเดียว

- **Config:** `configs/a3v2_2_gold150.json`
- **Model:** claude-sonnet-4-5-20250929, temperature 0
- **Budget ต่อ claim:** 6 call, 80,000 input token (ใช้ร่วมกันทุก arm)

## 4. Endpoint และสถิติ
- **Primary:** accuracy (strict) ของ A3v2_2e เทียบ A2_rag_numeric
  - McNemar exact แบบจับคู่, สองทาง
  - paired bootstrap 95% CI ของผลต่าง (10,000 resamples, seed 20261118)
- **Secondary (Holm ร่วมกับ primary):**
  - **A3v2_2e เทียบ SR_self_reflection** (P3 vs P2: การเทียบที่อาจารย์ระบุว่าสำคัญที่สุด)
  - A3v2_2e เทียบ A3v2_1_1_RG
  - A3v2_2e เทียบ V1: A3_contradiction_aware
- **การแก้ปัญหาทดสอบหลายครั้ง:** ใช้ Holm กับ 4 การเปรียบเทียบ (primary + 3 secondary, α = 0.05)
- **Descriptive (ไม่อยู่ใน Holm):** A2 เทียบ A1 และ SR เทียบ A1 (P2 vs P1)
- **Descriptive (ไม่ทดสอบ):**
  - macro-F1
  - recall ของ INSUFFICIENT
  - ผลแยกตามประเภท claim
  - correction / regression เทียบ A2 (Wilson CI)
  - ความแม่นตอนยอมรับให้เปลี่ยนเป็นคำตอบเด็ดขาด
  - จำนวนครั้งที่ G1 / G4 / D-sup / G3b / Q1.1 / N1 / N2 / E1 ทำงาน และผลเทียบ gold
  - **ประสิทธิภาพต่อ arm** (median และรวม): input / output token, จำนวน LLM call (live / cache), จำนวน retrieval call, LLM latency, ต้นทุน
    - **latency ที่ใช้เทียบคือ `api_latency_ms`** = latency ของ API ตอนที่ได้คำตอบนั้นมาครั้งแรก (cache บันทึกไว้) เพราะ A1 / A2 ดึงจาก cache ของ v1 และ call แรกของ SR / A3 ก็ใช้ร่วมกัน ถ้าใช้เวลาของรอบนี้ arm ที่ได้จาก cache จะดูเร็วเกินจริง
    - RG เป็น replay ของ R จึงใช้ call ชุดเดียวกับ R ไม่ได้เรียก API เพิ่ม
  - evidence correctness แบบ deterministic: สัดส่วน citation ที่ผ่านการตรวจ quote / งวด / บริษัท / วันตัด
  - การกระจายของ predicate_type
  - ต้นทุนต่อ claim
- **เครื่องมือประเมิน:** `scripts/a3v2_gold_evaluate.py`
  - ตรวจกับ run v1 ที่ freeze ไว้แล้ว ได้ A1 62.67%, A2 68.67%, A3 64.00% ตรงกับผล v1

## 5. Acceptance criteria (ผ่านทุกข้อจึงจะสรุปว่า v2.2e "ดีกว่า หรือไม่ด้อยกว่า A2")

| # | เกณฑ์ |
|---|---|
| AC1 | accuracy ของ A3v2_2e ≥ A2 (point estimate) **และ** ขอบล่างของ 95% CI ของ (A3v2_2e − A2) > −8 pp |
| AC2 | accuracy ของ A3v2_2e > A3v2_1_1_RG |
| AC3 | ความแม่นตอนยอมรับให้เปลี่ยนเป็นคำตอบเด็ดขาด (เทียบ A2) ≥ 70% |
| AC4 | regression rate เทียบ A2 ≤ 7% |
| AC5 | recall ของ INSUFFICIENT ≥ recall ของ A2 − 5 pp |
| AC6 | numerical ถูก ≥ A3v2_1_1_RG − 1 ข้อ |
| AC7 | ไม่มี prediction ที่เป็น ERROR, ครบ 150 ข้อ, ต้นทุนอยู่ในงบที่อนุมัติ |

**จะอ้างว่า "A3 v2.2e ดีกว่า A2 อย่างมีนัยสำคัญ" ได้ก็ต่อเมื่อ primary test มี p_holm < 0.05 และผลต่าง > 0**
- **Power:** ที่ n = 150 ตรวจผลต่างได้ราว 9 pp (ถ้าข้อที่ตอบต่างกันมีประมาณ 15%) ผลต่างที่เล็กกว่านี้อาจ "ไม่มีนัยสำคัญ" แม้จะมีอยู่จริง

## 6. การตีความ (กำหนดล่วงหน้า)
- **AC ผ่านครบ และ primary มีนัยสำคัญ:** "v2.2e ดีกว่า A2 บน Gold 150"
- **AC ผ่านครบ แต่ไม่มีนัยสำคัญ:** "v2.2e ไม่ด้อยกว่า A2 และลดการเปลี่ยนคำตอบที่ผิดลง แต่ยังไม่พบความต่างที่มีนัยสำคัญ"
- **ไม่ผ่าน AC1:** รายงานตามตรงว่า v2.2e ไม่ชนะ A2 บน Gold และผลบน dev สูงเกินจริงเพราะออกแบบบนชุดนั้น
- **การรายงาน:** ผล dev-v0.2 (ทั้ง debug และ replay) อยู่ในบท development เท่านั้น ห้ามรวมกับผล Gold

## 7. ห้ามทำหลังเห็นผล
- ห้ามแก้กฎ, prompt หรือ config แล้วรันซ้ำบน Gold 150
- ห้ามตัด claim ออก
- ห้ามเปลี่ยน primary endpoint หรือ scoring
- ห้ามเลือก arm อื่นมาเป็น "ระบบหลัก" แทน A3v2_2e
- **ถ้ารันล้มกลางทาง:** ใช้ `--resume` หรือ `--retry-errors` ได้เฉพาะความล้มเหลวทางเทคนิค (เช่น 529 / network) และต้องบันทึกไว้
- **ERROR / timeout / retry (กำหนดล่วงหน้า):**
  - แต่ละ call retry อัตโนมัติไม่เกิน 5 ครั้ง (backoff) ทุก attempt ถูกจองเงินใน ledger และ attempt ที่ล้มยังนับเป็นเงินที่ใช้ไป
  - ถ้ายังมี prediction เป็น ERROR ให้ `--resume <run> --retry-errors` ได้ **ไม่เกิน 2 รอบ** โดย retry ทุกข้อที่ ERROR ใน arm นั้น เลือกเฉพาะบางข้อไม่ได้
  - ERROR ที่เหลือหลัง 2 รอบ **นับเป็นตอบผิด** (`a3v2_gold_evaluate.py --errors-as-wrong`) และแสดงรายชื่อใน `errors_scored_wrong` **ไม่ตัด claim ออก**
  - NO_FINAL_VERDICT (fallback ที่ยังมีคำตอบ) ให้คะแนนตามคำตอบนั้น เหมือน v1
  - ถ้า run หยุดเพราะถึงเพดานเงิน (BudgetExceeded) ห้ามประเมินผลบางส่วน ต้องขออนุมัติงบเพิ่มแล้ว resume ให้ครบ 150 ข้อก่อน

## 8. ขั้นตอนการรันและงบ
**ราคาที่ใช้คำนวณ:** `claude-sonnet-4-5-20250929` input $3 / 1M token, output $15 / 1M token (`Pricing` เวอร์ชัน `anthropic-2025-09:sonnet-4.5`)

**ต้นทุนที่คาดแยกตาม arm** (คิดจากค่าที่วัดได้บน dev-v0.2 ต่อ claim × 150 สำหรับ A2 ต้นทุนต่อ claim บน Gold v1 คือ $0.0195 ใกล้เคียงกับ dev ที่ $0.0198)

| Arm | ที่มา | ปกติ | สูง (p90) | worst ที่เคยเห็น |
|---|---|---|---|---|
| A1, A2 | **cache ของ v1:** probe แบบ offline ได้ครบ 150/150 ทั้งสอง arm และคำตอบตรงกับ v1 150/150 | $0 | $0 | $0 |
| SR | 2 call ใหม่ (call แรกใช้ร่วมกับ A2) | ≈ $7 | ≈ $10 | ≈ $14 |
| R | 3 call ใหม่ (+$0.118/claim) | ≈ $17.7 | ≈ $20.0 | ≈ $21.9 |
| RG | replay ของ R | $0 | $0 | $0 |
| A3v2_2e | ใช้ call ของ R ร่วมกัน + decidability 1 call | ≈ $1.2 | ≈ $1.3 | ≈ $1.4 |
| **รวม** | | **≈ $26** | **≈ $31** | **≈ $37** |

- ตัวเลขของ SR **ยังไม่เคยวัดจริง** (smoke test จะวัดให้)
- **ขอบบนตามสูตรของ `plan_run` ($187)** ไม่ได้หัก cache ของ A1 และ call ที่ A3v2_2e ใช้ร่วมกับ R จึงไม่ใช้เป็นตัวประมาณการ **วงเงินจริงถูกจำกัดโดย ledger cap $40**
- **BudgetGuard:** จองเงินแบบ worst-case **ก่อน**ทุก call (input คิดที่ chars/2 และ output คิดเต็ม cap) จึงหยุดก่อนเกินวงเงินจริง และอาจหยุดก่อนถึง $40 เล็กน้อย

**Stage 1: Smoke test** (ขออนุมัติแยก, ledger `a3v2.2-smoke` cap **$1.00**)
- **Config:** `configs/a3v2_2_smoke.json` ใช้ arm config hash ชุดเดียวกับ Gold ทุก arm
- **Claim:** 3 ข้อใหม่ที่ไม่มี label ใน `datasets/smoke_cases_a3v2.2.jsonl` (CAT / INTC / PG ไม่ใช่บริษัทใน Gold) claim ของ dev อยู่ใน cache ทั้งหมด จึงใช้ทดสอบการเรียก API จริงไม่ได้
- **ประมาณการ:** ≈ $0.60
- **ขั้นตอน:**
  1. รัน live ด้วย `--max-cost 0.25` เพื่อดูว่าระบบหยุดก่อนเกินเพดาน
  2. `--resume` ให้ครบ
- **สิ่งที่ตรวจ:**
  - ทุก call ได้ structured output (tool_use)
  - citation เปิดดูได้ คือมี accession และ quote ที่พบในเอกสารจริง
  - ledger settle ตรงกับ token ใน trace
  - ไม่มี request_key ที่ถูกจ่ายซ้ำโดยไม่มีเหตุผล (attempt ที่ล้มต้องมีเหตุผลกำกับ)
  - resume ไม่จ่ายซ้ำ
  - วัดต้นทุนจริงของ SR
- **ไม่นำผล smoke test ไปให้คะแนนหรือปรับระบบ** ถ้าพบ bug ต้องแก้แล้ว**ทำ amendment** ไม่แก้ไฟล์นี้

**Stage 2: Gold run** (cap $40)
1. ล็อกไฟล์นี้ (หัวข้อด้านบน) แล้วใส่ sha ลงใน config
2. รัน `run_experiment.py configs/a3v2_2_gold150.json --plan --split gold --allow-gold --ledger a3v2.2-gold150 --ledger-cap 40 --max-cost 40`
3. **เปิด ledger ใหม่** `a3v2.2-gold150` ตั้ง cap **$40** (ledger เดิมเหลือ $1.42 และไม่เพิ่ม cap $15)
4. ผู้วิจัยพิมพ์ approval phrase ตามที่ plan บอก แล้วรันแบบ live
5. รัน `scripts/a3v2_gold_evaluate.py --run <run id>` ครั้งเดียว แล้ว freeze run และบันทึก CHANGELOG

**Stage 3: Contingency**
- **ไม่มีงบสำรองอัตโนมัติ**
- ถ้า run หยุดเพราะถึง $40 หรือ ERROR ค้าง ให้รายงานยอดใน ledger และจำนวนข้อที่เหลือ แล้วขออนุมัติใหม่ (คาดว่าไม่เกิน $10) ก่อน `--resume`
- ห้ามแก้ config ระหว่างนั้น (resume จะไม่ยอมรันถ้า config เปลี่ยน)

## 9. ข้อจำกัดที่ทราบก่อนรัน (เทียบกับ Prompt 1–4 ของอาจารย์)
- **ไม่มีคลาส "Qualifying evidence" แยก:** รวมอยู่ใน RELATED_NOT_DECIDING
- **Investigator ไม่ได้อิสระเต็มที่:** ขั้นสร้างคำถามท้าทายรันใน conversation เดียวกับ A2 (reviewer ส่วน verifier แยก conversation แล้ว) และไม่มีขั้น "ระบุสมมติฐาน" แยกออกมา
- **ไม่มี baseline แบบคำถาม fixed:** อาจารย์เสนอให้เทียบคำถาม fixed กับคำถามที่ระบบสร้างเอง ยังไม่ได้ทำ (future work)
- **ไม่มีกฎเรื่อง one-time gain / G2 / G5:** สำหรับ claim เชิงสาเหตุและเชิงปฏิเสธ
- **ไม่มีการวัด evidence correctness โดยคน บน Gold:** ใช้การตรวจแบบ deterministic แทน

## 10. ล็อกโดย
- **ผู้วิจัย:** __________ (rev_som)
- **วันที่:** __________
- **Code bundle sha256 ตอนร่าง:** `c4d2112f803def614e1e6300d6e857739240dcaff3a22f3299500628f4fa4662`
  - คำนวณซ้ำได้ด้วย `sh scripts/code_bundle_sha256.sh`
  - ครอบคลุม 51 ไฟล์:
    - `a3v2/`, `engine/`, `experiments/`, `graphs/`
    - `scripts/a3v2_gold_evaluate.py`, `scripts/run_experiment.py`
    - backend core ที่ถูก import ตอนโหลด: `agent_config`, `evidence_ledger`, `sec_client`, `xbrl_extract`, `models` และ API client `investigation_engine` / `investigation_tools`
  - prompt ทั้งหมดอยู่ในโค้ดเหล่านี้ hash จึงครอบคลุม prompt ด้วย
  - ก่อนรัน Gold ต้องคำนวณใหม่แล้วได้ค่าเดิม และ commit ที่ใช้รันต้องมีไฟล์เหล่านี้ครบ
  - runner จะบันทึก code hash ของตอนรันลงใน manifest ของ run เองด้วย
