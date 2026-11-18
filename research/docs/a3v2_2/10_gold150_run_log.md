# Gold 150 run log: A3v2_2e

ไฟล์นี้บันทึกเหตุการณ์ตามลำดับเวลา (append-only) ไม่ใช่ส่วนหนึ่งของ preregistration ที่ล็อกไว้

## 2026-11-18: ก่อนรัน, ความต่างของผล dev 63/72 กับ 64/72
- **สาเหตุ:** ตัวเลขทั้งสองมาจากคนละ arm ไม่ได้มาจาก A3v2_2e ที่ให้ผลไม่คงที่
  - **63/72 = A3v2_2:** ยังไม่มี E1 รายงานใน `07_decidability_debug_run.md` addendum และ `offline_ablation/7dccc43a_r1.3`
  - **64/72 = A3v2_2e:** A3v2_2 + E1 (final candidate)
- **ยืนยันจาก run เดียวกัน** (`a3v2.2-dev-v0.2-20261118T052512Z`, label v2):

  | Arm | ถูก |
  |---|---|
  | A2 | 53 |
  | A3v2_2 | 63 |
  | A3v2_2e | 64 |
  | A3v2_2c | 65 |

- **E1 เปลี่ยนคำตอบ 3 ข้อ:**

  | Claim | ก่อน → หลัง | ผล |
  |---|---|---|
  | AAPL-05 | CONTR → INSUF | ถูก |
  | INTC-09 | CONTR → INSUF | ถูก |
  | INTC-06 | CONTR → INSUF | ผิด |

- **ไม่ได้แก้ final candidate**

## 2026-11-18 07:28 UTC: เริ่ม Gold run `a3v2.2-gold150-20261118T072827Z`
- **ก่อนเริ่ม ตรวจ hash ครบทุกตัว:** code bundle `c4d2112f…`, prereg `ffad4375…`, config `121c2ddf…`, evaluator `bb11cde0…`, Gold claims, reference, corpus และ hash ของทุก arm
- **Commit:** `0740c00`
- **Ledger:** `a3v2.2-gold150` cap $40
- **ผู้วิจัยอนุมัติด้วย phrase:** "I approve up to 1500 paid Claude API calls costing at most $40.00"

## 2026-11-18 10:16 UTC: เหตุขัดข้อง, worktree ถูกลบระหว่างรัน
- **worktree ที่รันอยู่** (`~/.local/share/kilo/worktree-pool/invesment-23ce5a1cc8f6/resolute-muskmelon`) ถูกลบทั้งโฟลเดอร์ รวมถึง `.git` ของ worktree
  - เกิดในวินาทีเดียวกับที่ Kilo restart (log ของ Kilo `2026-11-18T101617.log`: "parent process gone — shutting down server") และโฟลเดอร์อื่นใน worktree pool ก็ถูกแก้ในเวลาเดียวกัน
  - **ไม่ได้เกิดจากคำสั่งของผู้วิจัยหรือของ pipeline**
- **ตอนที่ถูกลบ:**
  - A1, A2, SR, R, RG เสร็จครบ 150/150
  - A3v2_2e เสร็จ 43/150
  - run หยุดด้วย `FileNotFoundError` เพราะเขียน trace ต่อไม่ได้
- **ข้อมูลที่หาย** (ยังไม่ได้ commit): predictions, traces, ledger `a3v2.2-gold150` และ response cache ของ Gold run
  - **เงินที่จ่ายไปแล้วประมาณ $22.5** ค่าสุดท้ายที่เห็นใน ledger คือ $21.97 ตอน 10:11 UTC ยอดจริงต้องยืนยันจาก Anthropic Console
- **ข้อมูลที่เหลือ:** `results/gold150/incident_20261118/`
  - `gold_run.log` มีคำตอบที่ทำนายของแต่ละ arm แต่ไม่มี trace
  - `llm_cache_after_deletion/` มี response 1 รายการที่เขียนหลังการลบ
- **ผลของ run นี้ยังไม่เคยถูกเทียบกับ label ของ Gold**
- **ไม่ได้รันซ้ำ** เพราะงบที่อนุมัติไว้ ($40) เหลือไม่พอ

## 2026-11-18: กู้คืน (ไม่เสียเงิน)
- สร้าง worktree ใหม่นอก Kilo pool ที่ `~/Desktop/Invesment-a3v2` จาก commit `0740c00`
- **เอกสาร SEC และ submissions ดาวน์โหลดใหม่จาก EDGAR**
  - hash ของไฟล์ดิบไม่ตรงกับ manifest เพราะ SEC แทรก `<script>` ป้องกัน bot แบบสุ่มไว้ท้ายไฟล์ทุกครั้งที่ดาวน์โหลด
  - ยืนยันว่าเนื้อหาเหมือนเดิมด้วยการ replay แบบ cache-only:
    - dev-v0.2: 288/288 pair ตรงกับ cache เดิม ได้ A2 53, R 48, RG 51, A3v2_2e 64 เท่าเดิม
    - Gold A1/A2: 300/300 pair ตรงกับ cache และ label ตรงกับ v1 ทุกข้อ (หลังดาวน์โหลดไฟล์ GOOGL ใหม่ เพราะสำเนาเก่าใน checkout หลักไม่ตรง)
- **ต่อไป:** ทุก run ต้องเขียนผลไว้นอก Kilo worktree pool และสำรอง ledger และ cache เป็นระยะ
