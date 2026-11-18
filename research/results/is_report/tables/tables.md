# IS report tables (Gold 150, run `a3v2.2-gold150-20261118T112814Z`)

สร้างจาก `evaluation.json` ที่ freeze แล้วและ predictions / traces ของ run เดียวกัน ไม่มีการคำนวณ metric ใหม่นอกจากการนับเชิงพรรณนาที่ระบุไว้

## ตาราง 4.1 ผลหลัก (n = 150, strict)
| Arm | Correct | Accuracy | 95% CI | Macro-F1 | INSUFF recall | Numerical | Interpretive | Ambiguous |
|---|---|---|---|---|---|---|---|---|
| A1 RAG | 94 | 62.7% | [54.7%, 70.0%] | 0.605 | 21/44 | 38/50 | 31/50 | 25/50 |
| A2 RAG + numeric | 103 | 68.7% | [61.3%, 76.0%] | 0.657 | 21/44 | 47/50 | 30/50 | 26/50 |
| SR self-reflection | 102 | 68.0% | [60.7%, 75.3%] | 0.657 | 27/44 | 47/50 | 34/50 | 21/50 |
| A3 v2.1.1 R | 100 | 66.7% | [59.3%, 74.0%] | 0.621 | 14/44 | 49/50 | 27/50 | 24/50 |
| A3 v2.1.1 RG | 99 | 66.0% | [58.7%, 73.3%] | 0.622 | 19/44 | 48/50 | 26/50 | 25/50 |
| A3v2_2e (final) | 98 | 65.3% | [57.3%, 72.7%] | 0.630 | 26/44 | 48/50 | 25/50 | 25/50 |
| A3 v1 | 96 | 64.0% | [56.0%, 71.3%] | 0.590 | 12/44 | 48/50 | 29/50 | 19/50 |

## ตาราง 4.2 การทดสอบแบบจับคู่ (คอลัมน์แรกเป็นคู่ A vs B ตามที่ evaluator บันทึก ผลต่าง = B − A)
| Comparison (A vs B) | B − A | Bootstrap 95% CI | B right : A right (discordant) | McNemar exact p | Holm p | Role |
|---|---|---|---|---|---|---|
| A3v2_2e vs A2_rag_numeric | -3.3 pp | [-10.0, +3.3] | 10 : 15 | 0.424 | 1.00 | primary |
| A3v2_2e vs SR_self_reflection | -2.7 pp | [-10.0, +4.7] | 13 : 17 | 0.585 | 1.00 | secondary |
| A3v2_2e vs A3v2_1_1_RG | -0.7 pp | [-6.7, +4.7] | 9 : 10 | 1.000 | 1.00 | secondary |
| A3v2_2e vs V1:A3_contradiction_aware | +1.3 pp | [-6.7, +9.3] | 19 : 17 | 0.868 | 1.00 | secondary |
| A2_rag_numeric vs A1_conventional_rag | +6.0 pp | [+2.0, +10.7] | 10 : 1 | 0.012 | — | descriptive |
| SR_self_reflection vs A1_conventional_rag | +5.3 pp | [-3.3, +14.0] | 27 : 19 | 0.302 | — | descriptive |

## ตาราง 4.3 Acceptance criteria (AC7 จาก run status: complete 900/900, ERROR 0, SHA256SUMS ผ่าน)
| Criterion | Result |
|---|---|
| AC1_accuracy_ge_A2_and_ci_low_gt_-8pp | ไม่ผ่าน |
| AC2_accuracy_gt_RG_v2.1.1 | ไม่ผ่าน |
| AC3_accepted_change_precision_ge_70pct | ไม่ผ่าน |
| AC4_regression_vs_A2_le_7pct | ไม่ผ่าน |
| AC5_insufficient_recall_ge_A2_minus_5pp | ผ่าน |
| AC6_numerical_ge_RG_minus_1_claim | ผ่าน |
| AC7_run_complete_and_intact | ผ่าน |

## ตาราง 4.4 การแก้ถูก / ทำพังเทียบ A2
| Arm | Correction vs A2 | Regression vs A2 | Net | Accepted decisive change precision |
|---|---|---|---|---|
| A1 RAG | 1/47 (2.1%) | 10/103 (9.7%) | -9 | 1/3 (33.3%) |
| SR self-reflection | 17/47 (36.2%) | 18/103 (17.5%) | -1 | 4/20 (20.0%) |
| A3 v2.1.1 R | 10/47 (21.3%) | 13/103 (12.6%) | -3 | 9/29 (31.0%) |
| A3 v2.1.1 RG | 3/47 (6.4%) | 7/103 (6.8%) | -4 | 3/12 (25.0%) |
| A3v2_2e (final) | 10/47 (21.3%) | 15/103 (14.6%) | -5 | 4/10 (40.0%) |
| A3 v1 | 8/47 (17.0%) | 15/103 (14.6%) | -7 | 7/27 (25.9%) |

## ตาราง 4.5 ประสิทธิภาพ (ต้นทุนเป็น list price ของทุก call รวมที่อ่านจาก cache; ค่าที่จ่ายจริงของ run คือ $23.24)
| Arm | LLM calls (median) | Input tokens (median) | Output tokens (median) | API latency s (median) | Cost/claim (median, list price) | Cost total (list price) |
|---|---|---|---|---|---|---|
| A1 RAG | 1 | 3,908 | 495 | 9.7 | $0.0195 | $2.93 |
| A2 RAG + numeric | 1 | 3,908 | 495 | 9.7 | $0.0195 | $2.93 |
| SR self-reflection | 3 | 14,224 | 1,899 | 35.2 | $0.0717 | $10.77 |
| A3 v2.1.1 R | 4 | 27,455 | 3,318 | 55.2 | $0.1327 | $20.10 |
| A3 v2.1.1 RG | 4 | 27,455 | 3,318 | 55.2 | $0.1327 | $20.10 |
| A3v2_2e (final) | 5 | 28,964 | 3,568 | 59.8 | $0.1410 | $21.33 |

## ตาราง 4.6 Confusion matrix (นับเชิงพรรณนา)
| Arm | Gold \ Pred | SUPPORTED | CONTRADICTED | INSUFFICIENT |
|---|---|---|---|---|
| A2_rag_numeric | SUPPORTED | 56 | 7 | 5 |
| A2_rag_numeric | CONTRADICTED | 1 | 26 | 11 |
| A2_rag_numeric | INSUFFICIENT_EVIDENCE | 12 | 11 | 21 |
| SR_self_reflection | SUPPORTED | 53 | 5 | 10 |
| SR_self_reflection | CONTRADICTED | 4 | 22 | 12 |
| SR_self_reflection | INSUFFICIENT_EVIDENCE | 7 | 10 | 27 |
| A3v2_2e | SUPPORTED | 52 | 5 | 11 |
| A3v2_2e | CONTRADICTED | 3 | 20 | 15 |
| A3v2_2e | INSUFFICIENT_EVIDENCE | 11 | 7 | 26 |

## ตาราง 5.1 กลไกที่เปลี่ยนคำตอบของ A3v2_2e เทียบ A2 (25 ข้อ, ระบุตำแหน่งไม่ใช่ counterfactual)
| Mechanism (stage where label changed) | Correction | Regression | Net |
|---|---|---|---|
| Reviewer + guard ACCEPT | 3 | 6 | -3 |
| Decidability (D-sup) | 0 | 3 | -3 |
| E1 evidence coverage | 6 | 5 | 1 |
| N1 numeric validity | 1 | 1 | 0 |

## ตาราง 5.2 ผลบน dev เทียบ Gold
| Set | A2 correct | A3v2_2e correct | Difference | Share labelled INSUFFICIENT |
|---|---|---|---|---|
| dev-v0.2 (n = 72, used for development) | 53 (73.6%) | 64 (88.9%) | +11 | 27/72 |
| Gold 150 (preregistered) | 103 (68.7%) | 98 (65.3%) | -5 | 44/150 |

