# 06 ตรวจ Gold ซ้ำ: ข้อที่ A2 กับ A3 (ทุกเวอร์ชัน) ถูกฝั่งเดียว

> **POST-HOC EXPLORATORY / ไม่ blind** — ตรวจหลังประเมินผลแล้ว ผู้ตรวจคือ Claude (AI) คนเดียว และเห็นคำตอบของโมเดลก่อนตรวจ
> **ไม่แก้ Gold** (`Final_Gold_v3_approved.xlsx` sha `e47897c4…`) ไม่แก้ prediction หรือ `evaluation.json` (sha `e6422ff9…`) ไม่เรียก API
> ใช้เป็นข้อมูลประกอบบทข้อจำกัด (label ambiguity) และคำถามถึงอาจารย์เท่านั้น ไม่ใช่ผลยืนยัน

## ขอบเขต

ผู้วิจัยสงสัยว่า Gold ผิดในข้อที่ A3 ผิดหรือไม่ ถ้าตรวจเฉพาะข้อที่ A3 ผิดผลจะเอียงเข้าข้าง A3 จึงตรวจ**ทุกข้อที่ A2 กับ A3 รุ่นใดรุ่นหนึ่งถูกฝั่งเดียว** ทั้งสองทิศทาง ด้วยเกณฑ์เดียวกัน

- A3 ที่รวม: v1 (`claimverif-main-v1-20261110T104207Z`), A3v2.1.1 R, A3v2.1.1 RG, A3v2_2e (`a3v2.2-gold150-20261118T112814Z`)
- รวม 46 ข้อ (25 ข้อจาก A3v2_2e และอีก 21 ข้อจากรุ่นอื่น)
- อ่าน claim, เหตุผลและหลักฐานใน Gold ทุกข้อ ข้อที่หลักฐานใน Gold ไม่ได้คัดตรงตัว (PRIOR-CHECK) หรือเหตุผลน่าสงสัย เปิด 10-K/10-Q ใน cache ดู: NVDA-07, WMT-08, GOOGL-08, TSLA-15, KO-09

## ผล

| ผลตรวจ | จำนวน | ข้อ |
|---|---:|---|
| Gold ถูก มีหลักฐานรองรับ | 37 | เช่น NVDA-03 (75.2B > 40B), NVDA-06 และ KO-08 (10-K เขียนตรง), TSLA-15 (10-Q: "will necessitate additional funding beyond our operating cash flow"), KO-09 (10-Q ไม่ได้ระบุ refranchising เป็นปัจจัยของกำไร) |
| Gold แรงไป ควรเป็น INSUFFICIENT_EVIDENCE | 2 | NVDA-07, WMT-08 |
| กำกวมจริง ตอบได้ทั้งสองแบบ | 7 | GOOGL-08, AMZN-06, MSFT-14, WMT-07, AAPL-12, KO-14, WMT-09 |

**Gold แรงไป**
- **NVDA-07** (Gold CONTRADICTED): 10-K เขียนว่า margin ลด "as our business model transitioned … to Blackwell" และ "The gross margin decrease was also impacted by a $4.5 billion charge associated with H20" เอกสารไม่ได้หักล้างว่า H20 เป็นสาเหตุหลักโดยตรง จึงควรเป็น INSUFFICIENT ทั้งนี้คำตอบ SUPPORTED ของ A3 ผิดในทุกกรณี
- **WMT-08** (Gold CONTRADICTED): 10-K เขียนว่า "primarily driven by the Walmart U.S. segment, due to disciplined inventory management, as well as growth in higher margin businesses globally" mix เป็นปัจจัยรอง และ membership income ไม่ได้อยู่ใน gross profit จึงควรเป็น INSUFFICIENT คำตอบ SUPPORTED ของ A3 ก็ยังผิด

**กำกวม (อีกคำตอบที่มีเหตุผล)**

| ข้อ | Gold | อีกคำตอบ | เหตุผล |
|---|---|---|---|
| GOOGL-08 | S | I | 10-Q เขียนว่าโตจาก "interrelated factors" ไม่ได้บอกว่า paid clicks เป็นหลัก |
| AMZN-06 | I | C | 10-Q: "primarily due to increased unit sales and increased advertising sales" annotator 2/3 ตอบ C |
| MSFT-14 | I | S | ผลกระทบ 207M ≈ 0.57% ของกำไร ต่ำกว่าเกณฑ์ materiality ทั่วไป |
| WMT-07 | I | S | 10-Q: "primarily driven by store and club-fulfilled delivery" |
| AAPL-12 | I | S | gross margin เพิ่ม 46.2 → 46.9% แม้มี tariff costs ("resilient" ไม่มีเกณฑ์) |
| KO-14 | S | I | annotator ทั้ง 3 ตอบ I แต่ adjudication เปลี่ยนเป็น S |
| WMT-09 | I | S | membership income +67M ขณะที่ operating income +8M annotator 2/3 ตอบ S |

## ผลกระทบต่อคะแนน (จาก 150 ข้อ)

| Arm | Gold เดิม | แก้ NVDA-07 + WMT-08 | + ยอมรับทั้งสองคำตอบในข้อกำกวม (ขอบบน) |
|---|---:|---:|---:|
| A1 | 94 | 92 | 95 |
| **A2** | **103** | 101 | 104 |
| SR | 102 | 102 | 104 |
| A3 v1 | 96 | 96 | 100 |
| A3v2.1.1 R | 100 | 100 | 104 |
| A3v2.1.1 RG | 99 | 99 | 103 |
| **A3v2_2e** | **98** | 98 | 101 |

- คอลัมน์ขวาสุดเป็นขอบบนเพื่อดูความไว ไม่ใช่คะแนนจริง เพราะให้คะแนนทุก arm ทั้งสองคำตอบในข้อกำกวม
- **ไม่พบว่า Gold ผิดจนทำให้ A3 แพ้** ถ้าแก้ 2 ข้อที่แรงไป A2 ลดลง 2 แต่ A3 ทุกรุ่นคะแนนเท่าเดิม เพราะไม่มีรุ่นใดตอบ INSUFFICIENT ในสองข้อนี้
- ในขอบบน A3v2.1.1 R เสมอ A2 (104) ส่วน A3v2_2e ยังตามอยู่ 3 ข้อ ข้อสรุปหลักว่า "A3 ไม่ดีกว่า A2" จึงไม่เปลี่ยน
- จุดอ่อนจริงของ A3v2_2e ที่เห็นจากการตรวจ: ถอยไป INSUFFICIENT ทั้งที่เอกสารเขียนชัด (NVDA-03, NVDA-06, KO-08, AMZN-09)

## ถ้าจะทำต่อ (รอความเห็นอาจารย์)
- ทำ Gold v3.1 errata เป็นไฟล์ใหม่ ไม่แก้ไฟล์เดิม แล้วคำนวณใหม่เป็น sensitivity analysis โดยผลหลักยังใช้ Gold v3
- ให้ผู้วิจัยหรืออาจารย์ตรวจ 9 ข้อข้างบนแบบไม่ดูคำตอบของโมเดล แทนผลตรวจของ Claude
