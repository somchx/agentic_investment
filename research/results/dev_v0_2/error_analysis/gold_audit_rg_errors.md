# ตรวจย้อน: 22 ข้อที่ A3 v2.1.1 (RG) ตอบไม่ตรงกับ approved label ของ dev-v0.2

- **ผู้ตรวจ:** AI analyst, 2026-11-18
- **สถานะ:** เป็นความเห็นที่สองเพื่อให้คนตรวจต่อ (human audit) **ไม่ได้แก้ label ใด ๆ**
- **วิธีตรวจ:** เปิดข้อความในรายงาน SEC ฉบับที่ cache ไว้ อ่าน trace ของระบบ และอ่านเหตุผลของผู้ติด label ทุกคน

## ผลรวม

| กลุ่ม | จำนวน | ข้อ |
|---|---|---|
| **ก. gold ถูกชัดเจน ระบบผิด** | 6 | ADBE-10, INTC-12, PG-06, PG-12, AMZN-07, AAPL-04 |
| **ข. gold ถูกตาม guideline** (คำประเมินไม่มีเกณฑ์ / สาเหตุ / scope / negative claim) **ระบบตัดสินเกินหลักฐาน** | 9 | CAT-01, CAT-02, CAT-03, CAT-07, PG-02, PG-05, PG-08, ADBE-03, INTC-09 |
| **ค. ตีความได้หลายทาง** (ผู้ติด label แยกกันเห็นต่าง หรือหลักฐานรองรับได้สองแบบ) | 6 | AAPL-05, AAPL-07, MSFT-05, MSFT-07, INTC-08, INTC-02 |
| **ง. gold น่าจะผิด** | 1 | INTC-07 |

## ก. gold ถูก ระบบผิด

| ข้อ | หลักฐานใน SEC | ทำไมระบบผิด |
|---|---|---|
| ADBE-10 | วันตัดหลักฐานคือ 2026-10-05 ตอนนั้นยังไม่มีผล Q4 FY2026 → INSUFFICIENT | **bug ของ numeric check ใน A2:** ใช้รายได้ Q3 ($6.76B) แทน Q4 แล้วตอบ CONTRADICTED จากนั้น A3 รักษาผลตัวเลขของ A2 ไว้ |
| INTC-12 | 10-Q Q3 2026: "CCPG revenue decreased $438 million" / "decreased 5%" → SUPPORTED | **bug ของ numeric check ใน A2:** เอารายได้รวมของ Intel (+21%) มาตรวจ claim ระดับ segment ได้ NUMERIC_FALSE ทั้งที่ reviewer ของ A3 เจอ ENTAILS ถูกต้อง 5 finding แต่ผลตัวเลขที่ผิดชนะ |
| PG-06 | 10-K FY2026: "120 basis points of decline from unfavorable product mix" เป็นปัจจัยลบที่ใหญ่ที่สุด (รองลงมาคือ 70, 60, 30 …) → SUPPORTED | ระบบระวังเกินไป ตอบ INSUFFICIENT |
| PG-12 | เงินปันผล 10,232 + ซื้อหุ้นคืนประมาณ 5,000 น้อยกว่า OCF 19,556 (ล้าน) → CONTRADICTED | R ตอบถูกด้วยเหตุผลที่ผิด (parser ได้ "< None") แล้ว RG บล็อก |
| AMZN-07 | FCF แบบ TTM จาก $18.2B → **−$7.6B** ขณะที่ operating income เพิ่ม → CONTRADICTED | R ตอบถูก แต่ RG บล็อก (CONTEXT_ONLY) |
| AAPL-04 | iPhone +9,670 จากที่รายได้รวมเพิ่ม 15,381 (63%) → SUPPORTED | ระบบระวังเกินไป ตอบ INSUFFICIENT |

## ข. gold ถูกตาม guideline
claim ทุกข้อในกลุ่มนี้ต้องใช้เกณฑ์ ("well", "exceptional", "solid", "well positioned"), ต้องมีข้อความระบุสาเหตุ หรือต้องมีหลักฐานเฉพาะขอบเขต แต่ระบบใช้ตัวเลขที่ "เกี่ยวข้อง" มาตัดสินแทน
- รายละเอียด 7 ข้อแรกอยู่ใน `a3v2.1.1_error_analysis.md`
- CAT-02, ADBE-03 และ INTC-09 เป็นรูปแบบเดียวกัน ข้อเหล่านี้ A2 ก็ตอบเด็ดขาดผิดเหมือนกัน (ยกเว้น INTC-09)

## ค. ตีความได้หลายทาง

| ข้อ | ประเด็น | ความเห็นของผู้ติด label |
|---|---|---|
| AAPL-05 | ผู้ติด label มองต่างกันว่า "mix of products and services" หมายถึง mix ภายในแต่ละกลุ่ม หรือ mix ระหว่าง Products กับ Services | INSUF / SUPPO แล้วตัดสินเป็น INSUF |
| AAPL-07 | เงินคืนภาษี tariff (ผลบวก) นับว่า "ได้รับผล" หรือไม่ | CONTR / INSUF แล้วตัดสินเป็น INSUF |
| MSFT-05 | margin เพิ่มขึ้นนับเป็นหลักฐานของ "improved operating efficiency" ได้หรือไม่ | SUPPO / INSUF แล้วตัดสินเป็น SUPPO |
| MSFT-07 | "fully offsetting" ไม่มีเกณฑ์ ขณะที่รายได้รวมโต 18% | SUPPO / INSUF แล้วตัดสินเป็น INSUF |
| INTC-08 | 10-Q บอกว่า ASP +54% เทียบกับ volume +10% แต่ "the majority of the increase in server ASPs resulted from a higher mix of premium products … pricing actions contributing to a lesser extent" ถ้า "higher server prices" หมายถึง ASP ก็ SUPPORTED ถ้าหมายถึงการขึ้นราคา ก็ CONTRADICTED หรือ INSUFFICIENT | SUPPO / INSUF แล้วตัดสินเป็น SUPPO (ระบบตอบ CONTR) |
| INTC-02 | ASP ของ client เพิ่ม "primarily resulting from pricing actions" ส่วน server มี pricing actions บางส่วน แต่คำว่า "pricing power across its product lines" เป็นคำประเมิน | INSUF / INSUF (ระบบตอบ SUPPO) |

## ง. gold น่าจะผิด: INTC-07

- **Claim:** "Foundry manufacturing supply constraints limited Intel's server revenue in the fourth quarter of 2025."
- **10-K FY2025 (0000050863-26-000011) ส่วน DCAI:**
  > "Our 2025 server revenue was limited in Q4 2025 by our available supply of products due to Intel Foundry wafer fabrication supply constraints, primarily with respect to our Intel 7 and Intel 3 process nodes, impacting our ability to fully meet demand."
- **ประโยคนี้ยืนยัน claim เกือบตรงตัว** ผู้ติด label ทั้งสองคนตอบ INSUFFICIENT
  - เหตุผลของ rev_somchai อ้างเฉพาะข้อความที่พูดถึง **client** volume
  - rev_person2 เขียนว่า "ไม่มีข้อความยืนยันผลต่อ Q4 2025"
  - ทั้งสองดูเหมือนไม่เห็นย่อหน้าของ DCAI
- **A2, R และ RG ตอบ SUPPORTED โดยอ้างประโยคนี้**

## ผลต่อคะแนน (A2 / R / RG ถูกกี่ข้อจาก 72)

| สถานการณ์ | A2 | R | RG |
|---|---|---|---|
| approved label ตามที่ freeze ไว้ | 52 | 47 | 50 |
| ถ้าแก้ INTC-07 เป็น SUPPORTED | 53 | 48 | 51 |
| (sensitivity) ถ้านับว่าถูกเมื่อตรงกับ label ของผู้ติด label คนใดคนหนึ่ง + แก้ INTC-07 | 57 | 51 | 55 |

**สรุป:** ความไม่แน่นอนของ label ไม่ได้เปลี่ยนลำดับ ทุกกรณียังเป็น A2 > RG > R และส่วนต่าง A2 − RG คงที่ที่ 2 ข้อ

## สิ่งที่ต้องให้คนทำ

1. **คนที่ไม่ใช่ผู้ติด label 2 คนเดิมตรวจ INTC-07** ถ้ายืนยันว่าผิด ให้ส่งตัดสินใหม่และออกไฟล์ approved เวอร์ชันใหม่ (เช่น `dev-v0.2_reference_labels.v2.approved.jsonl`) **ห้ามแก้ไฟล์เดิม**
2. **ทบทวนกลุ่ม ค ทั้ง 6 ข้อ:** ถ้าตัดสินใจให้คงไว้ ให้รายงาน sensitivity analysis ในเล่มแทนการเปลี่ยน label
3. **แยก workstream แก้ numeric check ของ A2:** การจับคู่งวด (ADBE-10) และขอบเขต segment กับรายได้รวม (INTC-12) เป็น bug จริงที่ทำให้ทั้ง A2 และ A3 ผิด
