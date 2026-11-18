# สรุปการขยาย Development Dataset: dev-v0.1 (24 ข้อ) → dev-v0.2 (72 ข้อ)

- วันที่: 2026-11-17
- **สถานะ:** claims ใหม่เป็นร่างของ AI ทั้งหมด ยังไม่มี label ยังไม่ freeze และยังไม่ commit

## 1. บริษัทและงวด

| บริษัท | อุตสาหกรรม | ปีบัญชี | Cutoff A (งวดปี) | Cutoff B (งวดไตรมาส) |
|---|---|---|---|---|
| Adobe (ADBE) | Software | สิ้นสุดปลาย พ.ย. | 2026-01-31: 10-K FY2025 (ยื่น 2026-01-15) | 2026-10-05: 10-Q Q3 FY2026 (ยื่น 2026-09-22) |
| Intel (INTC) | Semiconductor | สิ้นสุดปลาย ธ.ค. | 2026-02-15: 10-K FY2025 (ยื่น 2026-01-23) | 2026-11-15: 10-Q Q3 2026 (ยื่น 2026-10-30) |
| Procter & Gamble (PG) | Consumer staples | สิ้นสุด 30 มิ.ย. | 2026-08-20: 10-K FY2026 (ยื่น 2026-08-04) | 2026-11-05: 10-Q Q1 FY2027 (ยื่น 2026-10-22) |
| Caterpillar (CAT) | Industrial | ปีปฏิทิน | 2026-03-01: 10-K FY2025 (ยื่น 2026-02-13) | 2026-11-15: 10-Q Q3 2026 (ยื่น 2026-11-04) |

- **เหตุผลที่เลือกงวดเหล่านี้**
  - เป็น filing ล่าสุดที่ยื่นแล้วของแต่ละบริษัท ณ วันนี้
  - cutoff ตั้งไว้หลังวันยื่นราว 2 สัปดาห์
- **บริษัทเหล่านี้ไม่ซ้ำกับชุดอื่น**
  - ไม่ใช่บริษัทของ Gold
  - ไม่ใช่ 3 บริษัทของ Dev เดิม
- **Holdout:** เมื่อวางแผน holdout ต้องไม่ใช้ 4 บริษัทนี้ในงวดเดียวกัน
- **รูปแบบที่ได้จากปีบัญชีที่ต่างกัน:** ปีบัญชีของ ADBE และ PG ไม่ตรงกับปีปฏิทิน จึงใช้สร้าง claim แบบ period trap และ period-not-covered ได้ตามธรรมชาติ

## 2. Claims ใหม่ (12 ข้อต่อบริษัท)

| | ambiguous | interpretive | numerical | รวม |
|---|---|---|---|---|
| ADBE | 5 | 4 | 3 | 12 |
| INTC | 7 | 4 | 1 | 12 |
| PG | 6 | 3 | 3 | 12 |
| CAT | 7 | 4 | 1 | 12 |
| **รวม** | **25** | **15** | **8** | **48** |

**ประเด็นที่ทดสอบ** (ตามที่ขอ):

| ประเด็น | Claims | ตัวอย่าง |
|---|---|---|
| หลักฐานไม่เพียงพอ / คำประเมินที่ไม่มีเกณฑ์ | 12 ข้อ | "Intel's 2025 results show that its turnaround is on track." |
| ความสัมพันธ์เชิงสาเหตุ | 6 ข้อที่ filing ไม่ได้ระบุ และ 8 ข้อที่ระบุ | ADBE-06: ซื้อหุ้นคืนน้อยลงเพราะ Semrush (ไม่ได้ระบุ) เทียบกับ CAT-08: tariff ทำให้ manufacturing costs สูงขึ้น (ระบุ) |
| Claim เชิงปฏิเสธ | 4 ข้อที่ไม่ได้ระบุ และ 2 ข้อที่เปิดเผยผลกระทบ | PG-09: "Tariffs had no effect on P&G's gross margin in fiscal 2026." |
| การเปลี่ยนนิยามหรือ segment | 2 ข้อ | INTC-12: CCG เปลี่ยนชื่อเป็น CCPG; PG-11: organic เทียบกับ reported net sales |
| การคำนวณ XBRL | 2 ข้อ | ADBE-12: FCF = OCF − capex; PG-12: dividends + buybacks เทียบกับ OCF |
| Reporting period mismatch | 4 ข้อ period trap และ 2 ข้อ period-not-covered | CAT-12: +21% เป็นตัวเลข 9 เดือน ส่วนไตรมาสคือ +17% |

- **มีทั้งข้อที่น่าจะพิสูจน์ได้และข้อที่หลักฐานอาจไม่พอ**
  - ผู้ร่างคาดว่า (design intent): INSUFFICIENT_EVIDENCE 24, CONTRADICTED 14, SUPPORTED 10
  - ค่าเหล่านี้ **ไม่ใช่ label** และเก็บแยกไฟล์
- **รายการเต็ม:** ดู `claims_list_with_intent.md` (สำหรับผู้เขียนเท่านั้น)

## 3. ไฟล์

**ส่งให้ผู้ติด label ได้:**

| ไฟล์ | เนื้อหา |
|---|---|
| `datasets/workbooks/dev_annotation_workbook_dev-v0.2_new48.xlsx` | Workbook ว่างสำหรับติด label 48 ข้อ (มีชีต Filings พร้อมลิงก์ SEC; ไม่มี intent หรือ pattern) |
| `datasets/development_cases_dev-v0.2.jsonl` | ไฟล์ claims 72 ข้อ (24 ข้อเดิม ไบต์ตรงกัน + 48 ข้อใหม่) |

**สำหรับผู้เขียนและผู้วิจัยเท่านั้น** (`datasets/annotations_dev/dev-v0.2_author/` และ `design_intent_dev-v0.2.jsonl`):

| ไฟล์ | เนื้อหา |
|---|---|
| `dev_claims_authoring_dev-v0.2_ai_draft.xlsx` | Claims Authoring Workbook 48 ข้อ (มี pattern, intent และ author notes พร้อมตัวเลขอ้างอิง) |
| `dev-v0.2_sec_filing_references.xlsx` | SEC Filing References: filing ของงวดแต่ละ claim, ชุดที่ระบบดึง ณ cutoff, ลิงก์, sha256 และที่มาของ CIK |
| `validation_report.md` และ `validate_output.json` | Validation Report |
| `expansion_summary.md` | ไฟล์นี้ |
| `claims_list_with_intent.md` | รายการ 48 ข้อพร้อม intent |
| `../design_intent_dev-v0.2.jsonl` | Design intent แยกไฟล์ (สร้างโดย `build`) |

**ไฟล์อื่น:**

| ไฟล์ | เนื้อหา |
|---|---|
| `datasets/corpus_manifest_dev-v0.2.json` | Manifest ของ filing ใหม่ 19 เอกสาร แยกจาก manifest ที่ freeze ไว้ |

## 4. โค้ดที่เปลี่ยน (ยังไม่ commit)

- **`engine/corpus.py`**
  - เพิ่ม `RESEARCH_CIKS` สำหรับ ADBE, INTC และ CAT
  - `build_corpus` ส่ง CIK ให้ `get_submissions` แทน ticker
  - ผลกับบริษัทเดิมเหมือนเดิม
- **`scripts/dev_corpus.py`** (ใหม่)
  - ดาวน์โหลด filing สำหรับ authoring workbook และเขียน manifest แยกตามเวอร์ชัน
  - `load_manifest()` รวม manifest ที่ freeze ไว้กับ manifest ของ dev
- **`scripts/dev_claims_authoring.py`**
  - ใช้ manifest รวม
  - `notes` ของ claim บันทึกผู้ร่าง
- **`scripts/dev_annotation_workbook.py`**
  - ใช้ manifest รวม
  - เพิ่มตัวเลือก `--claims` ให้ export และ import กับไฟล์ dev-v0.2 ได้
- **`tests/test_dev_adjudication_authoring.py`:** เพิ่ม test 3 ข้อ

## 5. ขั้นต่อไป (ต้องให้คนทำ)

1. **ผู้วิจัยอ่านทบทวน 48 ข้อ** ใน authoring workbook แล้วตัด แก้ หรือแทนข้อที่ไม่ต้องการ
   - ถ้าแก้ ให้รัน `validate` และ `build --version dev-v0.3` (เวอร์ชันใหม่ ไม่ทับของเดิม)
2. **ติด label** ด้วย `dev_annotation_workbook_dev-v0.2_new48.xlsx`
   - ผู้ติด label ไม่ควรเห็นโฟลเดอร์ `dev-v0.2_author/` และไฟล์ `design_intent_*`
   - ข้อ ambiguous และ interpretive (40 ข้อ) ควรมีผู้ติด label 2 คนแบบ blind
   - Import ด้วย:

     ```
     dev_annotation_workbook.py import <filled>.xlsx --claims datasets/development_cases_dev-v0.2.jsonl --version dev-v0.2
     ```
3. **วัด κ ก่อน adjudication** แล้วตัดสินข้อที่ไม่ตรงกันด้วย `dev_adjudication.py`
4. **Freeze dev-v0.2** หลังได้ label ครบแล้วเท่านั้น
