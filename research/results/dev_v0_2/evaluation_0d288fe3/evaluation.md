# A3 v2.1.1 dev-v0.2 evaluation

Labels: 72/72 approved ({'AGREED': 55, 'ADJUDICATED': 17}), sha256 0d288fe3606a

| Approach | Accuracy | 95% CI | Macro-F1 |
|---|---|---|---|
| A2 | 72.2% | 61.1%–81.9% | 0.724 |
| R | 65.3% | 54.2%–76.4% | 0.630 |
| RG | 69.4% | 58.3%–79.2% | 0.692 |

| Claim type | n | A2 | R | RG |
|---|---|---|---|---|
| ambiguous | 30 | 73.3% | 50.0% | 63.3% |
| interpretive | 22 | 59.1% | 59.1% | 59.1% |
| numerical | 20 | 85.0% | 95.0% | 90.0% |

| Pair | Acc diff (2nd − 1st) | 95% CI | McNemar exact p | discordant |
|---|---|---|---|---|
| A2_vs_R | -6.9% | -19.4%–5.6% | 0.383 | 21 |
| A2_vs_RG | -2.8% | -12.5%–6.9% | 0.774 | 12 |
| R_vs_RG | 4.2% | -4.2%–12.5% | 0.508 | 9 |

| vs A2 | Correction (A2 wrong → right) | Regression (A2 right → wrong) | Changed |
|---|---|---|---|
| R | 8/20 (40.0%) | 13/52 (25.0%) | 22 |
| RG | 5/20 (25.0%) | 7/52 (13.5%) | 12 |

Guard on 22 R changes: {'helpful_accept': 5, 'harmful_accept': 7, 'helpful_block': 6, 'harmful_block': 3, 'neutral_block': 1} (net helpful 1)

RG correct vs unanimity (Fisher exact): {'table': [[39, 11], [11, 11]], 'p_value': 0.026175158831210573, 'odds_ratio_haldane': 3.4347826086956523}
