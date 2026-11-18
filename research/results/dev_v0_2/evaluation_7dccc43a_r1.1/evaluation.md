# A3 v2.1.1 dev-v0.2 evaluation

Labels: 72/72 approved ({'AGREED': 54, 'ADJUDICATED': 18}), sha256 7dccc43ae5c1

| Approach | Accuracy | 95% CI | Macro-F1 |
|---|---|---|---|
| A2 | 73.6% | 62.5%–83.3% | 0.739 |
| R | 66.7% | 55.6%–77.8% | 0.642 |
| RG | 70.8% | 61.1%–80.6% | 0.705 |

| Claim type | n | A2 | R | RG |
|---|---|---|---|---|
| ambiguous | 30 | 73.3% | 50.0% | 63.3% |
| interpretive | 22 | 63.6% | 63.6% | 63.6% |
| numerical | 20 | 85.0% | 95.0% | 90.0% |

| Pair | Acc diff (2nd − 1st) | 95% CI | McNemar exact p | discordant |
|---|---|---|---|---|
| A2_vs_R | -6.9% | -19.4%–5.6% | 0.383 | 21 |
| A2_vs_RG | -2.8% | -12.5%–6.9% | 0.774 | 12 |
| R_vs_RG | 4.2% | -4.2%–12.5% | 0.508 | 9 |

| vs A2 | Correction (A2 wrong → right) | Regression (A2 right → wrong) | Changed |
|---|---|---|---|
| R | 8/19 (42.1%) | 13/53 (24.5%) | 22 |
| RG | 5/19 (26.3%) | 7/53 (13.2%) | 12 |

Guard on 22 R changes: {'helpful_accept': 5, 'harmful_accept': 7, 'helpful_block': 6, 'harmful_block': 3, 'neutral_block': 1}
- RG − R (blocks: helpful − harmful): +3 claims
- RG − A2 (accepts: helpful − harmful): -2 claims
- Accepted-change precision: 5/12 (41.7%)
- (legacy sum of both, not a single comparison: +1)

RG correct vs unanimity (Fisher exact): {'table': [[40, 10], [11, 11]], 'p_value': 0.022384486858741035, 'odds_ratio_haldane': 3.857142857142857}
