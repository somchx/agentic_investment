# Paired Evidence-Grounded Correctness: A2 เทียบ A3v2_2e (POST-HOC EXPLORATORY)

> **STATUS: POST-HOC EXPLORATORY**
> - ทำหลังประเมินผลตาม preregistration และหลังเปิดดู Gold รายข้อแล้ว ไม่ใช่ผลยืนยัน ไม่แทนผลหลักใน `evaluation.json` (`e6422ff9…`)
> - ใช้ judgment 100 แถวเดิมทั้งหมด ไม่ตัดสินใหม่ ไม่แก้เฉลย predictions หรือ evaluation ค่าใช้จ่าย $0
> - การทดสอบทางสถิติในเอกสารนี้เป็น exploratory เท่านั้น ไม่อยู่ใน Holm family ของ preregistration
> - สคริปต์: `scripts/posthoc_paired_egc.py` ผลสรุป: `results/posthoc_20261119/paired_egc/paired_egc_summary.json` (ระดับ claim ไม่มี review_id จึงไม่เปิดเผย mapping)

---

## 1. Research Question
แม้ A3v2_2e จะมี accuracy ต่ำกว่า A2 บน Gold 150 (98 เทียบ 103) **A3v2_2e มี evidence-grounded correctness หรือคุณภาพหลักฐานดีกว่า A2 หรือไม่** บน 50 claims ที่สุ่มมาตรวจหลักฐาน

## 2. Data Provenance และข้อจำกัดของ judgment

**ที่มาของ judgment: ผู้วิจัย (rev_som) ตรวจเองทั้ง 100 แถว** แบบไม่เห็นชื่อระบบและเฉลย (ผู้วิจัยยืนยัน 2026-11-19; ตรงกับ commit `5b52eb6`) ป้าย: **POST-HOC EXPLORATORY / HUMAN-ASSESSED (researcher self-reported)**

**ข้อจำกัดของ judgment**
- ผู้ประเมินคนเดียว ไม่มี inter-rater agreement และไม่มี adjudication
- ผู้ตรวจคือผู้วิจัยเอง ซึ่งเคยทบทวนและอนุมัติเฉลย Gold ทั้ง 150 ข้อ จึงไม่ใช่ independent review
- ไม่เห็นชื่อระบบและเฉลยในไฟล์ (ตรวจแล้วไม่มีข้อมูลรั่ว)

**การตรวจ input (ผ่านทุกข้อ)**
- hash ของ workbook ที่กรอกแล้วตรงกับ `egc_result.json`; hash ของ mapping ตรงกับ `sample_manifest.json`
- 50 claims ตรงกับรายการสุ่ม ทุก claim มีแถวของ A2 และ A3v2_2e ครบ (100 แถว)
- คำตอบใน mapping ตรงกับ frozen predictions และเฉลยตรงกับ Gold reference ทุกแถว
- จำนวน judgment แต่ละประเภทตรงกับผลเดิม และ EGC ที่คำนวณใหม่ตรงกับ `egc_result.json` (assert ในสคริปต์)
- ตัวอย่าง: ตัวเลข 16, ตีความ 17, กำกวม 17 claims

## 3. Definitions and Denominators

| คำ | นิยาม |
|---|---|
| **EGC Strict (success)** | คำตอบของระบบตรงเฉลย **และ** judgment = SUPPORTED_BY_EVIDENCE |
| EGC Lenient (success) | คำตอบตรงเฉลย **และ** judgment = SUPPORTED หรือ PARTIALLY_SUPPORTED |
| Verified EGC failure | แถวที่ประเมินได้ (ไม่ใช่ UNABLE) แต่ไม่เป็น success |
| UNABLE_TO_ASSESS | ผู้ประเมินตัดสินไม่ได้ **ไม่นับเป็นผิดโดยอัตโนมัติ** |
| EGC rate (assessable) | success / (success + verified failure) |
| Observed success / 50 | success / 50 claims = **coverage-adjusted descriptive yield ไม่ใช่ EGC accuracy ของทั้งชุด** |
| Bounds | ต่ำสุด: UNABLE ทั้งหมดเป็น failure = success / 50; สูงสุด: UNABLE ทั้งหมดเป็น success = (success + UNABLE) / 50 |

**EGC เป็นตัวชี้วัดร่วมของ "คำตอบถูก" กับ "หลักฐานรองรับ" ไม่ใช่การวัดคุณภาพหลักฐานอย่างเดียว** คำตอบผิดเฉลยจะเป็น failure เสมอ แม้หลักฐานที่อ้างจะดี (หัวข้อ 7 แยกวัดคุณภาพหลักฐานโดยไม่สนความถูกของคำตอบ)

## 4. EGC Results บน 50 Claims

| | A2 strict | A3v2_2e strict | A2 lenient | A3v2_2e lenient |
|---|---:|---:|---:|---:|
| Verified success | 22 | 23 | 24 | 26 |
| Verified failure | 15 | 15 | 13 | 12 |
| UNABLE_TO_ASSESS | 13 | 12 | 13 | 12 |
| รวม | 50 | 50 | 50 | 50 |
| **EGC rate (assessable)** | **22/37 = 59.5%** | **23/38 = 60.5%** | 24/37 = 64.9% | 26/38 = 68.4% |
| Observed success / 50 (descriptive yield) | 44.0% | 46.0% | 48.0% | 52.0% |
| Bounds (UNABLE ทั้งหมดผิด – ถูก) | 44.0–70.0% | 46.0–70.0% | 48.0–74.0% | 52.0–76.0% |

ช่วง bounds ของสองระบบซ้อนทับกันเกือบทั้งหมด ผลต่างของ point estimate (1 ข้อใน strict, 2 ข้อใน lenient) เล็กกว่าความไม่แน่นอนจาก UNABLE มาก

## 5. Evidence Support Rate Among Correct Predictions

นับเฉพาะคำตอบที่ตรงเฉลย แล้วดูว่าหลักฐานรองรับเพียงใด

| | A2 | A3v2_2e |
|---|---:|---:|
| คำตอบถูก (จาก 50) | 32 | 34 |
| — SUPPORTED / PARTIAL / NOT / UNABLE | 22 / 2 / 0 / 8 | 23 / 3 / 0 / 8 |
| ประเมินได้ | 24 | 26 |
| **Strict support rate** | **22/24 = 91.7%** | **23/26 = 88.5%** |
| Lenient support rate | 24/24 = 100% | 26/26 = 100% |
| ถูกแต่หลักฐานไม่ครบ (PARTIAL + NOT) | 2 | 3 |

**แยกตามชนิดคำตอบ**

| | A2 decisive | A3v2_2e decisive | A2 INSUFFICIENT | A3v2_2e INSUFFICIENT |
|---|---:|---:|---:|---:|
| คำตอบถูก | 24 | 24 | 8 | 10 |
| SUPPORTED / PARTIAL / NOT / UNABLE | 22 / 2 / 0 / 0 | 23 / 1 / 0 / 0 | 0 / 0 / 0 / 8 | 0 / 2 / 0 / 8 |
| Strict support rate | 22/24 = 91.7% | 23/24 = 95.8% | — (ประเมินไม่ได้) | 0/2 |

- คำตอบเด็ดขาดที่ถูก: ทั้งสองระบบมีหลักฐานรองรับครบเกือบทุกข้อ (ต่างกัน 1 ข้อ)
- คำตอบ INSUFFICIENT ที่ถูก: เกือบทั้งหมด UNABLE เพราะไม่มี citation **ไม่ได้แปลว่าไม่มีหลักฐานจริง** การงดตอบต้องใช้เกณฑ์ประเมินอีกแบบ (ตรวจว่าเอกสารไม่มีข้อมูลพอจริง) ซึ่งไม่ได้ทำ

## 6. Paired EGC (คู่ที่ประเมินได้ทั้งสองฝั่ง)

จับคู่ด้วย claim id ใช้เฉพาะ 37 คู่ที่ทั้งสองระบบประเมินได้

**Strict**

| | A3v2_2e success | A3v2_2e failure |
|---|---:|---:|
| **A2 success** | n11 = 21 | n10 = 1 |
| **A2 failure** | n01 = 2 | n00 = 13 |

- A2 22/37 (59.5%) เทียบ A3v2_2e 23/37 (62.2%); **paired difference (A3 − A2) = +2.7 จุด (1 claim สุทธิ)**
- discordant 3 คู่; exploratory McNemar exact p = 1.0

**Lenient**: n11 22, n10 2, n01 3, n00 10 → A2 64.9% เทียบ A3v2_2e 67.6%, difference +2.7 จุด, discordant 5 คู่, exploratory p = 1.0

**ทำไม discordant ของ lenient (5) ต่างจาก strict (3):** lenient นับ PARTIALLY_SUPPORTED เป็น success จึงเปลี่ยนสถานะของ 4 claims
- AAPL-02 ออกจาก discordant: A2 ตอบถูกและได้ PARTIAL จึงกลายเป็น success ทั้งสองฝั่ง
- META-11, MSFT-14 เข้ามา (ฝั่ง A3): A3 งดตอบถูกและได้ PARTIAL ส่วน A2 ตอบผิด
- META-15 เข้ามา (ฝั่ง A2): A2 ตอบถูกและได้ PARTIAL ส่วน A3 ถอยไปตอบ INSUFFICIENT ผิด
- META-06 และ NVDA-06 เป็น discordant ทั้งสองแบบ; สุทธิ strict 3 − 1 + 3 = 5 คู่

**Discordant pairs**

| Claim | หมวด | เฉลย | A2 (คำตอบ / judgment) | A3v2_2e (คำตอบ / judgment) | สำเร็จฝ่ายเดียว | คำอธิบาย |
|---|---|---|---|---|---|---|
| GOLD-AAPL-02 | ตัวเลข | S | S / PARTIAL | S / SUPPORTED | A3 (strict) | ตอบถูกทั้งคู่ หลักฐานของ A3 ถูกประเมินว่าครบกว่า |
| GOLD-META-06 | ตีความ | S | C / NOT | S / SUPPORTED | A3 (strict, lenient) | A3 แก้คำตอบผิดของ A2 ด้วยหลักฐานที่รองรับ (ตรงกับ correction ในเอกสาร 13) |
| GOLD-NVDA-06 | ตีความ | S | S / SUPPORTED | I / NOT | A2 (strict, lenient) | A3 ถอยไปตอบ INSUFFICIENT ทั้งที่มีหลักฐาน (regression แบบ over-abstention ในเอกสาร 13) |
| GOLD-META-11 | กำกวม | I | S / PARTIAL | I / PARTIAL | A3 (lenient) | A3 งดตอบถูก หลักฐานรองรับบางส่วน |
| GOLD-MSFT-14 | กำกวม | I | C / PARTIAL | I / PARTIAL | A3 (lenient) | A3 งดตอบถูก หลักฐานรองรับบางส่วน |
| GOLD-META-15 | กำกวม | S | S / PARTIAL | I / NOT | A2 (lenient) | A3 ถอยไปตอบ INSUFFICIENT (regression D-sup ในเอกสาร 13) |

## 7. Evidence Support Better / Equal / Worse (ไม่สนความถูกของคำตอบ)

เทียบระดับ SUPPORTED > PARTIAL > NOT ของ judgment ใน 37 คู่ที่ประเมินได้ทั้งสองฝั่ง

| A3v2_2e ดีกว่า | เท่ากัน | A3v2_2e แย่กว่า |
|---:|---:|---:|
| 3 | 32 | 2 |

| A2 \ A3v2_2e | SUPPORTED | PARTIAL | NOT |
|---|---:|---:|---:|
| SUPPORTED | 22 | 0 | 1 |
| PARTIAL | 2 | 7 | 1 |
| NOT | 1 | 0 | 3 |

- 30 ใน 37 คู่ทั้งสองระบบให้คำตอบเดียวกัน และหลักฐานมักเหมือนกันด้วย (A3 เริ่มจากคำตอบของ A2) ความต่างจึงเกิดในคู่ส่วนน้อย
- A3 ดีกว่า 3 คู่ แย่กว่า 2 คู่: **ไม่มีหลักฐานเชิงพรรณนาว่าคุณภาพหลักฐานของ A3 ดีกว่าอย่างเป็นระบบ**

## 8. Missingness Analysis

| รูปแบบ | จำนวน claims |
|---|---:|
| ประเมินได้ทั้งสองฝั่ง | 37 |
| A2 อย่างเดียว | 0 |
| A3v2_2e อย่างเดียว | 1 |
| ประเมินไม่ได้ทั้งสองฝั่ง | 12 |

| หมวด | ทั้งสองฝั่ง | A3 อย่างเดียว | ไม่ได้ทั้งคู่ |
|---|---:|---:|---:|
| ตัวเลข (16) | 13 | 1 | 2 |
| ตีความ (17) | 17 | 0 | 0 |
| กำกวม (17) | 7 | 0 | 10 |

- **UNABLE สัมพันธ์กับคำตอบ INSUFFICIENT_EVIDENCE โดยสมบูรณ์:** แถว UNABLE ทั้ง 25 แถวคือคำตอบ INSUFFICIENT ที่ไม่มี citation (A2 13/13 คำตอบ I; A3v2_2e 12 จาก 17 คำตอบ I ส่วนอีก 5 มี citation จึงประเมินได้)
- Missingness กระจุกในหมวด**กำกวม** (10 จาก 17 claims ประเมินไม่ได้ทั้งคู่) ซึ่งเป็นหมวดที่การงดตอบมีบทบาทมากที่สุด
- ในแถว UNABLE มีคำตอบถูกเฉลย A2 8/13 และ A3v2_2e 8/12 การตัดแถวเหล่านี้จึงตัดคำตอบที่ถูกจำนวนมากออกจากทั้งสองระบบ

**ผลกระทบ**
- EGC บน assessable rows วัดเกือบเฉพาะ**คำตอบเด็ดขาด**และไม่สะท้อนความสามารถในการงดตอบ ซึ่งเป็นจุดที่ A3v2_2e ต่างจาก A2 มากที่สุดบน Gold (over-abstention)
- ตัวหารของสองระบบต่างกัน (37 กับ 38) การเทียบ 22/37 กับ 23/38 ตรงๆ จึงไม่ใช่ paired comparison; เมื่อจับคู่เหลือ 22/37 กับ 23/37
- **22/37 เทียบ 23/38 ไม่พอสรุปว่า A3 ดีกว่า** เพราะ: ต่างกัน 1 claim สุทธิ (discordant 3 คู่, exploratory p = 1.0); ช่วง bounds ซ้อนทับกัน; ตัวอย่าง 50 claims นี้ A3 บังเอิญตอบถูกมากกว่า A2 (34 เทียบ 32) ซึ่งกลับทิศกับ Gold ทั้งชุด (98 เทียบ 103); และผู้ประเมินคนเดียวไม่อิสระ (หัวข้อ 2)

## 9. Interpretation and Threats to Validity

**การตีความ**
- เมื่อคำตอบถูก ทั้งสองระบบอ้างหลักฐานที่รองรับได้ในระดับใกล้กันมาก (strict 91.7% กับ 88.5%; ในคำตอบเด็ดขาด 91.7% กับ 95.8%)
- ความต่างของ EGC ระหว่างสองระบบมาจาก**ความถูกของคำตอบ**ในไม่กี่ claims (META-06 ฝั่ง A3, NVDA-06 / META-15 ฝั่ง A2) มากกว่าจากคุณภาพหลักฐาน
- รูปแบบที่เห็นตรงกับ error analysis เดิม: A3 ช่วยได้เมื่อค้นเจอหลักฐานใหม่ (META-06) แต่เสียเมื่อถอยไปงดตอบ (NVDA-06, META-15)

**Threats to validity**
1. ผู้ประเมินคนเดียวซึ่งเป็นผู้วิจัยเอง (ไม่อิสระ, ไม่มี adjudication)
2. post-hoc บน Gold ที่ exposed แล้ว; เลือกวิเคราะห์หลังเห็นผลหลัก
3. n เล็ก (37 คู่, discordant 3–5) การทดสอบทั้งหมด exploratory และไม่มี power
4. UNABLE 25 แถวเป็นการขาดข้อมูลแบบไม่สุ่ม (คำตอบ INSUFFICIENT ที่ไม่มี citation, กระจุกในหมวดกำกวม)
5. ตัวอย่าง 50 claims ไม่เป็นตัวแทนผลรวม (accuracy ในตัวอย่างกลับทิศกับ Gold 150)
6. EGC ผูกกับเฉลยที่มีความกำกวม (α หมวดกำกวม 0.377)

## 10. Conclusion for IS Chapter 4–5

**ข้อสรุป:** จากการวิเคราะห์เชิงพรรณนาแบบ post-hoc บน 50 claims **ไม่พบหลักฐานว่า A3v2_2e มี evidence-grounded correctness หรือคุณภาพหลักฐานดีกว่า A2** ผลต่างที่เห็น (+1 claim สุทธิใน paired strict, A3 ดีกว่า 3 คู่ / แย่กว่า 2 คู่ในคุณภาพหลักฐาน) เล็กเกินกว่าจะแยกจากความแปรปรวนของตัวอย่าง และจาก missingness ที่สัมพันธ์กับการงดตอบ

**ประโยคร่างสำหรับเล่ม**
- "ในการวิเคราะห์เพิ่มเติมเชิงพรรณนาหลังการประเมินผล (post-hoc exploratory) บนตัวอย่าง 50 claims เมื่อจับคู่เฉพาะ claims ที่ประเมินหลักฐานได้ทั้งสองระบบ (37 คู่) A2 และ A3v2_2e มี evidence-grounded correctness แบบเข้มงวด 59.5% และ 62.2% ตามลำดับ ต่างกันสุทธิ 1 claim (discordant 3 คู่) จึงไม่พบหลักฐานว่า A3v2_2e มีคุณภาพหลักฐานดีกว่า A2"
- "ในคำตอบที่ถูกต้อง ทั้งสองระบบอ้างหลักฐานที่รองรับคำตอบได้ครบในสัดส่วนสูงใกล้เคียงกัน (91.7% และ 88.5%) ความแตกต่างของระบบจึงอยู่ที่การตัดสินคำตอบ ไม่ใช่การค้นหาหลักฐาน"
- "คำตอบ INSUFFICIENT_EVIDENCE ที่ไม่มีการอ้างอิง (25 จาก 100 แถว) ประเมินไม่ได้ด้วยวิธีนี้ จึงยังไม่ได้ประเมินความถูกต้องของการงดตอบ ซึ่งเป็นจุดอ่อนหลักของ A3v2_2e"
- "การประเมินหลักฐานทำโดยผู้วิจัยแบบไม่เห็นชื่อระบบและเฉลย โดยผู้ประเมินคนเดียว จึงเป็นผลเชิงสำรวจ"

---

## ภาคผนวก: การทำซ้ำ

```
research/.venv/bin/python research/scripts/posthoc_paired_egc.py
```
ต้องมีไฟล์ mapping ส่วนตัวในเครื่อง (ไม่อยู่ใน git) จึงจะรันได้ input / output hash อยู่ใน `paired_egc_summary.json`
