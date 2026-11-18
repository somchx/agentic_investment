# Offline guard / policy replay on A3 v2.1.1 dev-v0.2 traces

> **IN-SAMPLE DIAGNOSTIC: rules designed after reading these claims' errors and gold labels; not a performance claim.**

Labels sha256 0d288fe3606a; 72 claims; guard 0.1 replay reproduced the recorded decision on 72/72 claims. No LLM call.

| Arm | Correct | Acc | Macro-F1 | INSUFF recall | Accepted decisive precision | Δ vs A2 | Δ vs R | McNemar p vs RG-0.1 | num / amb / int |
|---|---|---|---|---|---|---|---|---|---|
| A2 | 52/72 | 72.2% | 0.724 | 19/28 | 0/0 (—) | +0 | +5 | 0.774 | 17/20 / 22/30 / 13/22 |
| R | 47/72 | 65.3% | 0.630 | 8/28 | 7/21 (33.3%) | -5 | +0 | 0.508 | 19/20 / 15/30 / 13/22 |
| RG-0.1 | 50/72 | 69.4% | 0.692 | 13/28 | 4/11 (36.4%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 13/22 |
| RG-G3 | 50/72 | 69.4% | 0.696 | 14/28 | 3/9 (33.3%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 13/22 |
| RG-G6 | 49/72 | 68.1% | 0.680 | 13/28 | 3/10 (30.0%) | -3 | +2 | 1.000 | 18/20 / 19/30 / 12/22 |
| RG-0.2 | 50/72 | 69.4% | 0.696 | 14/28 | 3/9 (33.3%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 13/22 |
| RG-0.1+C-system | 55/72 | 76.4% | 0.766 | 18/28 | 4/6 (66.7%) | +3 | +8 | 0.062 | 18/20 / 22/30 / 15/22 |
| RG-0.2+C-system | 54/72 | 75.0% | 0.753 | 18/28 | 3/5 (60.0%) | +2 | +7 | 0.219 | 18/20 / 22/30 / 14/22 |
| RG-0.1+C-category | 55/72 | 76.4% | 0.767 | 20/28 | 2/2 (100.0%) | +3 | +8 | 0.180 | 18/20 / 23/30 / 14/22 |

## Claims whose label differs from RG-0.1

- **RG-G3**: DEV-AAPL-06, DEV-CAT-07
- **RG-G6**: DEV-AAPL-06
- **RG-0.2**: DEV-AAPL-06, DEV-CAT-07
- **RG-0.1+C-system**: DEV-AAPL-07, DEV-CAT-03, DEV-CAT-07, DEV-PG-05, DEV-PG-08
- **RG-0.2+C-system**: DEV-AAPL-06, DEV-AAPL-07, DEV-CAT-03, DEV-CAT-07, DEV-PG-05, DEV-PG-08
- **RG-0.1+C-category**: DEV-AAPL-06, DEV-AAPL-07, DEV-CAT-01, DEV-CAT-03, DEV-CAT-07, DEV-INTC-04, DEV-PG-02, DEV-PG-05, DEV-PG-08
