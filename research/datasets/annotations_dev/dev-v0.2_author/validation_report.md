# รายงานการตรวจสอบ claims ใหม่ dev-v0.2 (48 ข้อ)

- วันที่: 2026-11-17
- **ผู้ร่าง:** AI (`ai_draft_claude-opus-5-5`)
- **สถานะ:** ร่าง ยังไม่ติด label และยังไม่ freeze
- **ไฟล์นี้สำหรับผู้เขียนและผู้วิจัยเท่านั้น** เพราะอ้างถึง pattern และ design intent

## 1. ผลการตรวจ

| การตรวจ | วิธี | ผล |
|---|---|---|
| Schema, รูปแบบ ID, ค่าในรายการ, author_id | `dev_claims_authoring.py validate` (บันทึกผลไว้ใน `validate_output.json`) | 48/48 valid, errors 0, warnings 0 |
| ไม่ใช่บริษัทของ Gold | validator บล็อก 10 บริษัทของ Gold | ADBE, INTC, PG, CAT ไม่มีใน Gold (AAPL, MSFT, AMZN, GOOGL, NVDA, META, TSLA, NFLX, WMT, KO) |
| ไม่ซ้ำหรือถอดความจาก Gold 150 | token Jaccard (บล็อกที่ ≥0.60, เตือนที่ ≥0.45) | สูงสุด **0.381** |
| ไม่ซ้ำกับ Dev เดิม 24 ข้อ | เหมือนกัน | สูงสุด **0.353** |
| ไม่ซ้ำกันเองใน 48 ข้อ | เหมือนกัน | สูงสุด **0.385** (PG-01 กับ PG-11) |
| Filing ยื่นก่อน evidence cutoff | `select_filings` ตัดทุก filing ที่ยื่นหลัง `as_of_date` และตรวจซ้ำหลังเลือก | filing ที่ยื่นหลัง cutoff = **0** ทุกข้อ |
| มี filing ของงวดที่ claim อ้างถึง ณ cutoff | จับคู่ `report_date` กับวันสิ้นงวด | มี 46/48 ข้อ ส่วน 2 ข้อที่ไม่มีคือ ADBE-10 และ INTC-10 ซึ่งเป็น PERIOD_NOT_COVERED ตามที่ออกแบบไว้ |
| ดาวน์โหลด filing ครบ | `dev_corpus.py --download` (SEC EDGAR ฟรี) | 19 เอกสาร ขาด 0 และมี XBRL companyfacts ครบ 4 บริษัท |
| Design intent ไม่หลุดไปถึงผู้ติด label | ค้นข้อความใน workbook ติด label และไฟล์ claims | ไม่พบ `design_intent`, `pattern_type`, ชื่อ pattern, "Trap:" หรือ "AI-drafted" ใน workbook ติด label ส่วนไฟล์ claims ไม่มีคีย์ intent หรือ pattern |
| Quota ตามแผน §2b | นับจากผล validate | ตรงทุกช่อง (ดูข้อ 2) |

## 2. Quota

| Category | เป้า | ได้ |
|---|---|---|
| ambiguous | 25 | 25 |
| interpretive | 15 | 15 |
| numerical | 8 | 8 |

| Pattern | เป้า | ได้ | สิ่งที่ทดสอบ |
|---|---|---|---|
| EVALUATIVE_NO_CRITERION | 12 | 12 | คำประเมินที่ไม่มีเกณฑ์ |
| EVALUATIVE_FACT_FALSE | 6 | 6 | คู่ของข้อบน: ส่วนข้อเท็จจริงผิด |
| CAUSE_NOT_STATED | 6 | 6 | ความสัมพันธ์เชิงสาเหตุที่ filing ไม่ได้ระบุ |
| CAUSE_STATED | 8 | 8 | คู่: สาเหตุที่ filing ระบุไว้ |
| ABSENCE_NOT_STATED | 4 | 4 | claim เชิงปฏิเสธที่ filing ไม่ได้ระบุ |
| ABSENCE_EFFECT_DISCLOSED | 2 | 2 | คู่: filing เปิดเผยว่ามีผลกระทบ |
| PERIOD_NOT_COVERED | 2 | 2 | งวดที่ยังไม่มี filing ณ cutoff |
| PERIOD_TRAP | 4 | 4 | ตัวเลขงวดสะสมเทียบกับรายไตรมาส หรือตัวเลขทั้งปีที่อยู่ใน 10-Q |
| COMPUTATION_OR_DEFINITION | 4 | 4 | การคำนวณ XBRL, organic เทียบกับ reported, การเปลี่ยนชื่อ segment |

**Design intent** (ความคาดหมายของผู้ร่าง ไม่ใช่ label):

| Intent | จำนวน |
|---|---|
| INSUFFICIENT_EVIDENCE | 24 |
| CONTRADICTED | 14 |
| SUPPORTED | 10 |

SUPPORTED มีน้อยกว่าประเภทอื่น ถ้าต้องการให้สมดุลขึ้น ให้เพิ่มในรอบถัดไป

## 3. ข้อที่พบและแก้ (แก้เฉพาะ claims ใหม่)

| ข้อ | ปัญหา | การแก้ |
|---|---|---|
| DEV-CAT-11 | ร่างแรกเขียนว่า "dealer inventories had no effect on 2025 sales volume" แต่เมื่ออ่านบริบทใน 10-K พบว่าประโยคที่ว่า volume "primarily driven by … dealer inventories" อยู่ในส่วน **EAME** ส่วนระดับบริษัทรวม 10-K อธิบายว่า volume มาจาก "sales of equipment to end users" claim เดิมจึงกำกวมเกินกว่าที่จะเป็นคู่ที่ตัดสินได้ | จำกัดขอบเขตเป็น "…sales in the EAME region" |
| DEV-INTC-09 | ตัวเลือกแรกคือ "Tariffs did not affect Intel's 2025 results" แต่ 10-K ระบุว่า tariff "have affected customer ordering patterns" จึงไม่ใช่ absence-not-stated | เปลี่ยนเป็นเรื่อง revenue จาก partnership กับ NVIDIA ซึ่ง filing ไม่ได้ระบุทั้งสองทาง |
| DEV-INTC-05 | ร่างแรกซ้อนกับ INTC-11 (ทั้งคู่เรื่อง net income 9 เดือน) | เปลี่ยน INTC-05 เป็นเรื่อง gross margin กับรายได้ (ข้อเท็จจริงผิด: รายได้เพิ่ม ไม่ได้ลด) |

ทั้งสามข้อแก้ก่อนสร้างไฟล์ ไม่มีข้อไหนที่ validator ปฏิเสธ

## 4. ข้อจำกัดที่ต้องรู้

- **ผู้ร่างเป็น AI ทั้ง 48 ข้อ**
  - บันทึกไว้ใน `author_id`, ใน `notes` ของไฟล์ claims ("drafted by ai_draft_claude-opus-5-5") และในชีตกติกาของ authoring workbook
  - ผู้ร่างอ่านเฉพาะ filing ที่ cache ไว้ของ 4 บริษัท ไม่ได้อ่านข้อความ Gold claims และไม่ได้ดูผลของ A1/A2/A3
  - ความคล้ายกับ Gold คำนวณโดย validator และรายงานไว้เป็นตัวเลขเท่านั้น
- **Design intent มาจากการอ่าน filing ของผู้ร่างเอง** จึงอาจผิดได้ ผู้ติด label ต้องตัดสินอิสระ
  - ข้อที่ผู้ร่างเห็นว่ากำกวมโดยตั้งใจ: INTC-03 (อาจเป็น SUPPORTED), INTC-08 (ASP สูงขึ้นเพราะ mix มากกว่าการขึ้นราคา), INTC-12 (การเปลี่ยนชื่อ segment), PG-07 (commodity ผูกอันดับหนึ่งกับ packaging)
- **วันสิ้นงวดของ PERIOD_NOT_COVERED เป็นค่าประมาณ** เพราะยังไม่มี filing: ADBE Q4 FY2026 ≈ 2026-11-27 และ INTC Q4 2026 ≈ 2026-12-26
  - ไม่มีผลต่อข้อสรุป เพราะทั้งสองงวดสิ้นสุดหลัง cutoff
- **CIK ของ ADBE, INTC และ CAT ไม่ได้อยู่ในรายชื่อของแอป**
  - เพิ่มไว้ฝั่ง research ที่ `engine/corpus.py` (`RESEARCH_CIKS`) โดยดึงจาก SEC `company_tickers.json` ไม่ได้พิมพ์เอง
  - ไม่ได้แตะโค้ดของแอป (`backend/`)
- **`corpus_manifest.json` อยู่ในชุดที่ freeze ไว้ จึงไม่ได้แก้**
  - filing ใหม่เขียนไว้ใน `datasets/corpus_manifest_dev-v0.2.json`
  - เครื่องมือของ dev (`dev_claims_authoring`, `dev_annotation_workbook`) อ่านทั้งสองไฟล์รวมกัน ส่วน gold workflow และ v1 ยังเห็นเหมือนเดิม
- **XBRL companyfacts ของ PG ใน cache ของแอปถูกรีเฟรช** เพื่อให้มีงวด FY2026 และ Q1 FY2027
  - ไฟล์นี้เป็น cache ที่ไม่ได้อยู่ใน git และไม่อยู่ในชุดที่ freeze

## 5. ความสมบูรณ์ของข้อมูลเดิม (ตรวจหลังทำเสร็จ)

| ไฟล์ | sha256 (12 ตัวแรก) | สถานะ |
|---|---|---|
| `gold_claims.jsonl` | `1080323acda6` | ไม่เปลี่ยน |
| `Final_Gold_v3_approved.xlsx` | `e47897c48245` | ไม่เปลี่ยน |
| `corpus_manifest.json` | `75d87fb53b8c` | ไม่เปลี่ยน |
| `development_cases.jsonl` (24 ข้อ) | `e5ef3168388e` | ไม่เปลี่ยน และ 24 บรรทัดแรกของ dev-v0.2 เหมือนกันทุกไบต์ |
| `rev_som.jsonl` | `dd3d78a6652c` | ไม่เปลี่ยน |
| `rev_som.v2.jsonl` | `f27950330829` | ไม่เปลี่ยน |
| `rev_som.v3.jsonl` | `00c644729ecd` | ไม่เปลี่ยน |
| `rev_som.v4.jsonl` | `d0c7ec1dc9b3` | ไม่เปลี่ยน |
| `rev_reviewer2.jsonl` | `ce27fd273831` | ไม่เปลี่ยน |

- **Freeze verify** (`claimverif-main-v1-20261110T104207Z`): changed [] และ removed []
- **Offline tests:** 198 passed (195 ข้อเดิม + 3 ข้อใหม่)
