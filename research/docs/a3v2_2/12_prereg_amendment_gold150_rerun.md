# Amendment 1 ของ preregistration `08_preregistration_gold150.md`: รัน Gold 150 ใหม่หลังเหตุขัดข้อง

STATUS: APPROVED

> - เอกสารนี้ไม่ได้แก้ `08` (LOCKED, sha256 `ffad4375…`)
> - ทุกข้อของ `08` ยังใช้ตามเดิม ยกเว้นข้อที่ระบุไว้ด้านล่าง

## เหตุผล
- run `a3v2.2-gold150-20261118T072827Z` ไม่ครบ เพราะ worktree ถูกลบระหว่างรัน ซึ่งเป็นเหตุขัดข้องทางเทคนิคที่ไม่เกี่ยวกับระบบ (`10_gold150_run_log.md`, `11_gold150_incident_recovery_analysis.md`)
- **ไม่เคยเทียบคำตอบของ run นั้นกับ label ของ Gold** ก่อนเขียน amendment นี้
- run นั้นจึงเป็น INCOMPLETE และ run ใหม่ตาม amendment นี้คือ official result เพียงรอบเดียว

## สิ่งที่ไม่เปลี่ยน
- final candidate A3v2_2e, arm ทั้ง 6 และ arm config hash
- code bundle `c4d2112f…`, evaluator `bb11cde0…`, gold claims / reference
- endpoint, Holm, AC1–AC7 และกติกาเรื่อง ERROR / NO_FINAL_VERDICT

## สิ่งที่เปลี่ยน
1. **Ledger:** ใช้ ledger ใหม่ `a3v2.2-gold150-rerun` เพราะ ledger `a3v2.2-gold150` สูญหาย
   - **เพดานเงินของรอบนี้:** $30
   - เงินประมาณ $22.5 ที่ใช้ไปกับ run ที่ไม่ครบ บันทึกไว้ใน `10` ยอดจริงดูจาก Anthropic Console
2. **Corpus:** ก่อนรันต้องผ่าน `scripts/corpus_pin.py verify` (`datasets/corpus_pin_a3v2.2.json`: เอกสาร 80, submissions 14, company facts 14)
   - เอกสาร SEC เทียบกันด้วย content sha256 (ตัด script ที่ EDGAR แทรกออก) แทน raw sha256
   - Gold run อ่านเอกสาร 61 ฉบับชุดเดียวกับ `corpus_manifest.json`
3. **การจัดเก็บ:**
   - รันจาก `~/Desktop/Invesment-a3v2` (นอก Kilo pool)
   - ระหว่างรันใช้ `scripts/backup_artifacts.sh` สำรองไป `~/ReasonCheck-backups` ทุก 5 นาที
4. **ถ้าเลือกรันบางส่วน (ทางเลือก B):**
   - ใช้ผลของ SR จาก incident log ซึ่งไม่มี trace
   - **ข้อจำกัดที่ตามมา:** P3 vs P2 ยังทดสอบด้วย McNemar ได้ แต่รายงาน efficiency และ evidence correctness ของ SR ไม่ได้
   - **ต้องเปิดเผยในเล่ม**

## ลงนาม
- **ผู้วิจัย:** rev_som (พิมพ์ในแชตว่า "อนุมัติ amendment ทางเลือก A")
- **วันที่:** 2026-11-18
- **ทางเลือกที่อนุมัติ:** **A (รันเต็มชุดทุก arm)**
- **Approval phrase:** "I approve up to 1500 paid Claude API calls costing at most $30.00"
