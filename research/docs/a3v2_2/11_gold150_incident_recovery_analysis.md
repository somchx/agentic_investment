# Gold 150 incident: recovery analysis

> **STATUS: INCOMPLETE / EXPLORATORY ห้ามใช้แทน Official Gold 150 Result**
>
> - เอกสารนี้**ไม่ได้เทียบคำตอบใน log กับ label ของ Gold** ตรวจเฉพาะความครบและความสอดคล้องภายในของ log
> - การเทียบกับ Gold ให้ทำหลังตัดสินเรื่อง official rerun แล้วเท่านั้น และถ้าทำต้องติดป้าย "post-incident exploratory"

- **วันที่:** 2026-11-18
- **Working directory:** `~/Desktop/Invesment-a3v2`
- **Branch:** `research/a3-v2-reviewer-guard`
- **Paid API calls ระหว่างการกู้คืน:** 0

## 1. ข้อมูลที่เหลือจาก run `a3v2.2-gold150-20261118T072827Z`

**ไฟล์ใน `results/gold150/incident_20261118/`**
- `gold_run.log`: progress log ของ runner มี 1 บรรทัดต่อคู่ (arm, claim) ในรูป `label (stop_reason)` และมี traceback ตอนจบ
- `llm_cache_after_deletion/`: response 1 รายการ (decidability ของ A3v2_2e ข้อ GOLD-AMZN-14) ที่เขียนหลังจากโฟลเดอร์ถูกลบ

**ความครบของ log** (ตรวจด้วย parser ที่อ่าน `^\s+ARM GOLD-XXX-NN: LABEL (STOP)$`)

| Arm | คำตอบใน log | claim ที่ขาด | ไม่ใช่ COMPLETED |
|---|---|---|---|
| A1_conventional_rag | 150 | 0 | 0 |
| A2_rag_numeric | 150 | 0 | 0 |
| SR_self_reflection | 150 | 0 | 1 NO_FINAL_VERDICT |
| A3v2_1_1_R | 150 | 0 | 2 NO_FINAL_VERDICT |
| A3v2_1_1_RG | 150 | 0 | 2 NO_FINAL_VERDICT |
| **A3v2_2e** | **43** (AAPL 15, MSFT 15, AMZN 13) | **107** | 1 NO_FINAL_VERDICT |

- ไม่มี claim ซ้ำ และไม่มี claim id ที่อยู่นอก `gold_claims.jsonl`
- ไม่มี ERROR
- **ตรวจกับ v1 (ไม่ได้ใช้ Gold label):** คำตอบของ A1 / A2 ใน log ตรงกับ predictions ของ v1 run ที่ freeze ไว้ 150/150 ทั้งสอง arm เพราะทั้งคู่มาจาก cache เดียวกัน
- **ความสอดคล้องภายใน 43 ข้อ** (ไม่ใช่ความถูกต้อง): A3v2_2e ตอบเหมือน RG 37 ข้อ และเหมือน A2 35 ข้อ

## 2. ความเป็นไปได้ในการกู้ trace หรือ cache

**กู้ไม่ได้**
- predictions.jsonl, traces, manifest, status และ SHA256SUMS ของ run
- ledger `a3v2.2-gold150`
- response cache ของ SR / R / A3v2_2e (ประมาณ 600 รายการ)

ทั้งหมดอยู่ใน worktree ที่ถูกลบ และไม่เคย commit หรือสำรองไว้ ค้นใน Trash, Spotlight, `/private/tmp` และ Time Machine แล้วไม่พบ (Time Machine mount ไม่ได้)

**ผลกระทบ:**
- log ไม่มีหลักฐาน, citation, token หรือ cost รายข้อ จึงคำนวณ evidence correctness, efficiency หรือตรวจรายข้อตาม prereg §4 ไม่ได้
- ยอดเงินที่จ่ายจริงต้องยืนยันจาก Anthropic Console ค่าสุดท้ายที่เห็นใน ledger คือ $21.97 ที่ 10:11 UTC ประมาณการรวมอยู่ที่ราว $22.5

## 3. ความต่างจาก preregistration ที่ LOCKED

| ข้อกำหนดใน prereg | สถานะ |
|---|---|
| §7 / AC7: run ครบ 150 ข้อทุก arm และ integrity ผ่าน | **ไม่ผ่าน**: A3v2_2e มี 43/150 และไม่มีไฟล์ run |
| §4 primary: A3v2_2e เทียบ A2 บน 150 ข้อ | **ทดสอบไม่ได้** |
| §4 secondary: A3v2_2e เทียบ SR / RG / V1 A3 | **ทดสอบไม่ได้** |
| §4 efficiency และ evidence correctness | **ทดสอบไม่ได้** (ไม่มี trace) |
| §7: ห้ามประเมินผลบางส่วนเมื่อ run หยุดกลางทาง | ยังปฏิบัติตาม: ไม่ได้ประเมิน |

**การใช้ log นี้:**
- ถ้าวิเคราะห์ log จะเป็น post-incident exploratory analysis ที่ไม่อยู่ในแผนเดิม
- **ความเสี่ยง:** ถ้าเห็นคะแนนเทียบ Gold ก่อนตัดสินใจรันใหม่ การตัดสินใจรันใหม่หรือไม่รันจะขึ้นกับผลที่เห็น ซึ่งทำให้ official rerun เสียความเป็น preregistered
- **แนะนำ:** ตัดสินใจเรื่อง official rerun ก่อน แล้วค่อยวิเคราะห์ log

## 4. Reproducibility หลังกู้คืน

**Hash** (เทียบกับ `results/gold150/prerun_manifest_a3v2.2.json`)

| รายการ | ผล |
|---|---|
| Code bundle `c4d2112f…` (`scripts/code_bundle_sha256.sh`) | PASS |
| Preregistration `ffad4375…` (STATUS: LOCKED) และ sha ที่อยู่ใน config | PASS |
| Experiment config `121c2ddf…` และ arm config hash ทั้ง 6 | PASS |
| Gold claims `1080323a…` / reference workbook `e47897c4…` | PASS |
| Evaluator `bb11cde0…` (`--check-v1` ได้ 0.6267 / 0.6867 / 0.64 ตรงกับ v1) | PASS |
| ไฟล์ `datasets/corpus_manifest.json` `75d87fb5…` | PASS |
| **Raw sha256 ของเอกสาร SEC เทียบกับ manifest** | **FAIL** สำหรับ 70/80 เอกสาร (ตรงกัน 10) |
| ความเหมือนของเนื้อหาเอกสาร SEC | PASS (ดูด้านล่าง) |
| LLM cache: 889 ไฟล์ parse ได้ และ `request_key` ตรงกับชื่อไฟล์ | PASS |

**เอกสาร SEC: แยก raw hash กับความเหมือนของเนื้อหา**
- **สาเหตุที่ raw hash ไม่ตรง:**
  - EDGAR แทรก `<script type="text/javascript" src="/…">` แบบสุ่มไว้ท้ายไฟล์ทุกครั้งที่ดาวน์โหลด ทดสอบโดยดาวน์โหลด `aapl-20260627.htm` สองครั้ง ได้ไฟล์ต่างกันเฉพาะบรรทัดนั้น
  - **ไม่ได้อ้างว่า raw hash ตรง**
- **เอกสารที่มีสำเนาเก่า 16 + 6 (GOOGL) ฉบับ:** เมื่อตัด script ออกแล้ว ไฟล์ดิบเหมือนกันทุก byte และข้อความหลัง `clean_filing_html` ก็เหมือนกัน
- **ตรวจผลลัพธ์ด้วยการ replay จาก cache** (request key รวมข้อความ passage ที่ส่งเข้า prompt ไว้ด้วย ถ้าเนื้อหาต่างจะ cache miss):
  - dev-v0.2 6 arm × 72 claims = 432/432 pair ตรงกับ cache
  - Gold A1 / A2 300/300 pair ตรงกับ cache และ label ตรงกับ v1 ทุกข้อ
- **พบความเสี่ยงใหม่:**
  - ไฟล์ `submissions_CIK*.json` (รายการ filing) **ไม่อยู่ใน corpus manifest**
  - สำเนา GOOGL เก่าใน checkout หลักทำให้ cache miss 6 ข้อ เมื่อดาวน์โหลดใหม่แล้วจึงตรง
  - ดังนั้นการเลือก filing ขึ้นกับไฟล์ submissions ที่ไม่ได้ pin ไว้ ต้องเก็บไว้คู่กับ run (ดูหัวข้อ 6)

## 5. Dev run artifacts ที่สร้างใหม่ (offline)

**วิธีสร้าง:** `scripts/restore_dev_runs.py` รันแต่ละ run ใหม่แบบ offline (cache เท่านั้น) ด้วย config และชุด claim เดิม ภายใต้ run id เดิม แต่ละโฟลเดอร์มี `RESTORED_FROM_CACHE.json` กำกับ ส่วน manifest และ status บอกสภาพของการสร้างใหม่ (offline, commit ปัจจุบัน) ไม่ได้แทนค่าของ run ต้นฉบับ

| Run | ผล | เทียบกับของเดิม |
|---|---|---|
| a3v2.1.1-…092214Z / 093519Z / 100923Z | complete 36 / 90 / 90, cache miss 0 | คำตอบตรงกับ `results/dev_v0_2/a3v2.1.1_claims.jsonl` 216/216 |
| a3v2.2-…052512Z (6 arm) | complete 432, miss 0 | A2 53, R 48, RG 51, A3v2_2 63, **A3v2_2e 64**, A3v2_2c 65 ตรงกับที่รายงานไว้ |
| a3v2.1-…085608Z | incomplete 28 (miss 8: R/RG ของ AMZN-07, ADBE-04, ADBE-08, PG-04) | run ต้นฉบับก็ incomplete (RG 8 ข้อ) แต่ต้นฉบับมี R 12 ข้อ ส่วนที่สร้างใหม่มี 8 ข้อ จึงเป็นไปได้ว่า 4 ข้อนั้นเป็น ERROR ที่ไม่ได้เข้า cache **ยืนยันไม่ได้** test ที่ใช้ run นี้อ่านเฉพาะ config hash ใน manifest |

**Tests:** 308/308 ผ่าน

## 6. สิ่งที่ต้องทำก่อน official rerun
1. ตัดสินใจเรื่องงบ:
   - **รันใหม่เต็มชุดตามแผน:** SR + R + A3v2_2e ประมาณ $23 (A1 / A2 ได้จาก cache)
   - **รันใหม่บางส่วน:** R + A3v2_2e ประมาณ $15.5 และใช้ SR จาก log ซึ่งต้องเขียน amendment เพราะไม่มี trace ของ SR
2. ถ้าแผนเปลี่ยน ต้องเขียน amendment ของ prereg เป็นไฟล์ใหม่ (`08` ห้ามแก้) และระบุว่ารอบนี้เป็นการรันซ้ำหลังเหตุขัดข้องทางเทคนิค โดยยังไม่เห็นผลเทียบ Gold
3. รันจากโฟลเดอร์นี้เท่านั้น (นอก Kilo pool) และระหว่างรันใช้ `scripts/backup_artifacts.sh` สำรอง run, cache, ledger และไฟล์ SEC เป็นระยะ
4. ก่อนรัน ให้เก็บ snapshot ของ `backend/app/data/cache` ทั้งหมด (submissions, companyfacts, เอกสาร) พร้อม sha256 เพื่อ pin ไฟล์ submissions ที่ไม่อยู่ใน manifest
5. ตรวจ hash ซ้ำตาม `prerun_manifest_a3v2.2.json` แล้วออก approval phrase ใหม่
