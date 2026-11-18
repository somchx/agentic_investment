# Offline guard / policy replay on A3 v2.1.1 dev-v0.2 traces

> **IN-SAMPLE DIAGNOSTIC: rules designed after reading these claims' errors and gold labels; not a performance claim.**

Labels sha256 7dccc43ae5c1; 72 claims; guard 0.1 replay reproduced the recorded decision on 72/72 claims. No LLM call.

| Arm | Correct | Acc | Macro-F1 | INSUFF recall | Accepted decisive precision | Δ vs A2 | Δ vs R | McNemar p vs RG-0.1 | num / amb / int |
|---|---|---|---|---|---|---|---|---|---|
| A2 | 53/72 | 73.6% | 0.739 | 19/27 | 0/0 (—) | +0 | +5 | 0.774 | 17/20 / 22/30 / 14/22 |
| R | 48/72 | 66.7% | 0.642 | 8/27 | 7/21 (33.3%) | -5 | +0 | 0.508 | 19/20 / 15/30 / 14/22 |
| RG-0.1 | 51/72 | 70.8% | 0.705 | 13/27 | 4/11 (36.4%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 14/22 |
| RG-G3 | 51/72 | 70.8% | 0.709 | 14/27 | 3/9 (33.3%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 14/22 |
| RG-G6 | 50/72 | 69.4% | 0.693 | 13/27 | 3/10 (30.0%) | -3 | +2 | 1.000 | 18/20 / 19/30 / 13/22 |
| RG-0.2 | 51/72 | 70.8% | 0.709 | 14/27 | 3/9 (33.3%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 14/22 |
| RG-0.1+C-system | 56/72 | 77.8% | 0.779 | 18/27 | 4/6 (66.7%) | +3 | +8 | 0.062 | 18/20 / 22/30 / 16/22 |
| RG-0.2+C-system | 55/72 | 76.4% | 0.767 | 18/27 | 3/5 (60.0%) | +2 | +7 | 0.219 | 18/20 / 22/30 / 15/22 |
| RG-0.1+C-category | 56/72 | 77.8% | 0.781 | 20/27 | 2/2 (100.0%) | +3 | +8 | 0.180 | 18/20 / 23/30 / 15/22 |
| RG-0.3 (G3b) | 52/72 | 72.2% | 0.721 | 14/27 | 4/10 (40.0%) | -1 | +4 | 1.000 | 18/20 / 19/30 / 15/22 |
| RG-0.3+G6 | 51/72 | 70.8% | 0.709 | 14/27 | 3/9 (33.3%) | -2 | +3 | 1.000 | 18/20 / 19/30 / 14/22 |
| RG-0.1+Q1.1 | 52/72 | 72.2% | 0.718 | 13/27 | 5/12 (41.7%) | -1 | +4 | 1.000 | 18/20 / 19/30 / 15/22 |
| RG-0.3+Q1.1 | 53/72 | 73.6% | 0.734 | 14/27 | 5/11 (45.5%) | +0 | +5 | 0.500 | 18/20 / 19/30 / 16/22 |
| RG-0.3+Q1.1+C-system | 57/72 | 79.2% | 0.793 | 18/27 | 5/7 (71.4%) | +4 | +9 | 0.031 | 18/20 / 22/30 / 17/22 |
| V22: RG-0.3+Q1.1+G1 | 56/72 | 77.8% | 0.779 | 17/27 | 5/8 (62.5%) | +3 | +8 | 0.062 | 18/20 / 22/30 / 16/22 |
| V22: +G1+G4 | 57/72 | 79.2% | 0.793 | 18/27 | 5/7 (71.4%) | +4 | +9 | 0.031 | 18/20 / 23/30 / 16/22 |
| V22: +G1+D | 58/72 | 80.6% | 0.811 | 21/27 | 5/8 (62.5%) | +5 | +10 | 0.065 | 18/20 / 24/30 / 16/22 |
| V22: +G1+G4+D | 59/72 | 81.9% | 0.824 | 22/27 | 5/7 (71.4%) | +6 | +11 | 0.039 | 18/20 / 25/30 / 16/22 |
| V22: +G1+G4+D-sup (post hoc) | 60/72 | 83.3% | 0.837 | 21/27 | 5/7 (71.4%) | +7 | +12 | 0.004 | 18/20 / 26/30 / 16/22 |

## Claims whose label differs from RG-0.1

- **RG-G3**: DEV-AAPL-06, DEV-CAT-07
- **RG-G6**: DEV-AAPL-06
- **RG-0.2**: DEV-AAPL-06, DEV-CAT-07
- **RG-0.1+C-system**: DEV-AAPL-07, DEV-CAT-03, DEV-CAT-07, DEV-PG-05, DEV-PG-08
- **RG-0.2+C-system**: DEV-AAPL-06, DEV-AAPL-07, DEV-CAT-03, DEV-CAT-07, DEV-PG-05, DEV-PG-08
- **RG-0.1+C-category**: DEV-AAPL-06, DEV-AAPL-07, DEV-CAT-01, DEV-CAT-03, DEV-CAT-07, DEV-INTC-04, DEV-PG-02, DEV-PG-05, DEV-PG-08
- **RG-0.3 (G3b)**: DEV-CAT-07
- **RG-0.3+G6**: DEV-AAPL-06, DEV-CAT-07
- **RG-0.1+Q1.1**: DEV-MSFT-05
- **RG-0.3+Q1.1**: DEV-CAT-07, DEV-MSFT-05
- **RG-0.3+Q1.1+C-system**: DEV-AAPL-07, DEV-CAT-03, DEV-CAT-07, DEV-MSFT-05, DEV-PG-05, DEV-PG-08
- **V22: RG-0.3+Q1.1+G1**: DEV-CAT-01, DEV-CAT-03, DEV-CAT-07, DEV-MSFT-05, DEV-PG-02
- **V22: +G1+G4**: DEV-CAT-01, DEV-CAT-03, DEV-CAT-07, DEV-MSFT-05, DEV-PG-02, DEV-PG-08
- **V22: +G1+D**: DEV-ADBE-03, DEV-ADBE-04, DEV-CAT-01, DEV-CAT-02, DEV-CAT-03, DEV-CAT-05, DEV-CAT-07, DEV-INTC-02, DEV-MSFT-05, DEV-MSFT-07, DEV-PG-02
- **V22: +G1+G4+D**: DEV-ADBE-03, DEV-ADBE-04, DEV-CAT-01, DEV-CAT-02, DEV-CAT-03, DEV-CAT-05, DEV-CAT-07, DEV-INTC-02, DEV-MSFT-05, DEV-MSFT-07, DEV-PG-02, DEV-PG-08
- **V22: +G1+G4+D-sup (post hoc)**: DEV-ADBE-03, DEV-CAT-01, DEV-CAT-02, DEV-CAT-03, DEV-CAT-07, DEV-INTC-02, DEV-MSFT-05, DEV-PG-02, DEV-PG-08
