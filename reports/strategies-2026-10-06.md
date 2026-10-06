# Strategy families — 2026-10-06

GC=F 1h, 13688 bars up to the sealed holdout (2026-10-05), $10k, real costs. Random = same exits/sizing/costs with random entries (150 runs); p = share of random runs ≥ real. WF = 4 walk-forward OOS folds. Robust = guardrails + p ≤ 0.05 + PF > 1.1 at 2× costs + ≥3/4 folds positive.

| Config | Return % | Max DD % | Trades | PF | Win % | Random median % | p | Return 2× cost % | PF 2× | WF score | WF fold returns % | Longs $ | Shorts $ | Robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout | 50.65 | 11.66 | 356 | 1.5 | 49.7 | 7.99 | 0.0 | 43.76 | 1.44 | 1.6994 | [2.24, 11.0, -1.53, 5.82] | 4028.97 | 1036.51 | ✅ |
| squeeze | 40.32 | 6.3 | 265 | 1.49 | 46.4 | 0.92 | 0.013 | 39.05 | 1.48 | 0.3053 | [-3.64, 2.56, 1.93, 0.21] | 3948.9 | 82.87 | ✅ |
| overnight | 8.27 | 10.21 | 234 | 1.17 | 55.1 | 17.02 | 0.82 | 4.75 | 1.1 | -0.0958 | [-1.79, 0.23, -0.73, -0.15] | 827.28 | 0 | — |
| spike | -2.53 | 12.58 | 125 | 0.96 | 40.8 | 1.32 | 0.733 | -7.26 | 0.89 | -0.1249 | [-2.36, -7.91, 3.91, 0.45] | -349.07 | 95.85 | — |
| meanrev | -9.26 | 10.12 | 164 | 0.78 | 53.7 | -1.71 | 0.793 | -10.4 | 0.76 | -0.4106 | [-1.04, -1.19, -0.81, -2.0] | -237.73 | -687.94 | — |
| spike follow | -16.91 | 18.47 | 125 | 0.74 | 32.8 | -1.36 | 0.993 | -18.58 | 0.63 | -0.0181 | [-3.78, 6.63, 1.0, -8.06] | -1051.11 | -640.35 | — |
| ensemble: all | 52.24 | 8.38 | 580 | 1.28 | 49.3 | 13.5 | 0.033 | 50.06 | 1.28 | 0.9765 | [1.45, 7.19, 5.47, 2.59] | 4023.7 | 1200.54 | ✅ |
| ensemble: breakout+squeeze | 63.57 | 7.14 | 433 | 1.49 | 49.0 | 4.43 | 0.007 | 54.72 | 1.44 | 1.7838 | [-1.31, 7.58, 2.51, 9.04] | 5258.38 | 1098.22 | ✅ |
| ensemble: breakout+meanrev | 40.06 | 9.44 | 429 | 1.34 | 50.1 | 5.22 | 0.02 | 27.63 | 1.24 | 1.8956 | [2.01, 11.23, -2.11, 6.32] | 3287.09 | 719.39 | ✅ |
| ensemble: all + vol-scaled risk | 63.49 | 11.77 | 537 | 1.31 | 49.9 | 15.29 | 0.047 | 46.47 | 1.24 | 1.1968 | [3.74, 12.09, 3.43, 4.24] | 5774.62 | 574.14 | ✅ |
| breakout + vol-scaled risk | 57.3 | 13.01 | 327 | 1.5 | 49.8 | 8.2 | 0.013 | 41.4 | 1.38 | 2.6603 | [5.69, 16.45, -0.43, 7.34] | 5187.63 | 541.9 | ✅ |
| current + confluence tiers | 69.94 | 12.8 | 422 | 1.47 | 49.5 | 4.71 | 0.0 | 65.71 | 1.45 | 1.0427 | [-0.81, 10.75, 1.56, 6.14] | 5169.71 | 1824.5 | ✅ |
| current + tiers downsize-only (1/1/0.5) | 57.23 | 8.41 | 421 | 1.47 | 49.2 | 6.45 | 0.0 | 54.48 | 1.47 | 0.8272 | [-0.83, 8.89, -0.72, 6.16] | 4548.95 | 1173.57 | — |
| current + tiers mild (1.25/1/0.5) | 64.88 | 10.69 | 422 | 1.49 | 49.5 | 7.23 | 0.0 | 57.08 | 1.43 | 1.036 | [-1.17, 11.01, 2.08, 5.42] | 4737.16 | 1751.18 | ✅ |
| current + no-chase (2.5 ATR) | 18.32 | 7.38 | 265 | 1.26 | 45.7 | -2.0 | 0.06 | 14.88 | 1.21 | 0.4164 | [-0.01, 1.71, -1.29, 3.86] | 1625.14 | 206.73 | — |

## Confluence score vs realised R (breakout+squeeze, equal sizing)

Does a higher quality score predict better trades? (If not, tiers only add variance.)

| Score bucket | Trades | Avg R | Win % | Sum R |
|---|---|---|---|---|
| ≥0.75 | 130 | 0.163 | 53.8 | 21.2 |
| 0.5–0.75 | 234 | 0.156 | 48.3 | 36.5 |
| <0.5 | 59 | 0.032 | 42.4 | 1.9 |

## Concurrent positions (one per family, no hedging, total open risk capped)

| Config | Return % | Max DD % | Return/DD | Trades | PF | Sharpe | WF fold returns % |
|---|---|---|---|---|---|---|---|
| 1 position (current) | 63.57 | 7.14 | 8.9 | 433 | 1.49 | 1.93 | [-1.31, 7.58, 2.51, 9.04] |
| 2 positions b+s, 2% total | 89.71 | 13.13 | 6.83 | 624 | 1.4 | 1.7 | [-1.16, 12.06, 0.03, 5.7] |
| 2 positions b+s, 3% total | 89.71 | 13.13 | 6.83 | 624 | 1.4 | 1.7 | [-1.16, 12.06, 0.03, 5.7] |
| 3 positions all families, 3% total | 110.41 | 18.15 | 6.08 | 945 | 1.29 | 1.65 | [-5.12, 11.21, 0.56, 3.66] |

## Per-family attribution inside ensembles

- **ensemble: all**: breakout: 249 trades, $1816.14, win 45.8%, spike: 56 trades, $561.2, win 46.4%, squeeze: 142 trades, $2656.67, win 48.6%, overnight: 96 trades, $393.82, win 58.3%, meanrev: 37 trades, $-203.58, win 56.8%
- **ensemble: breakout+squeeze**: breakout: 260 trades, $2657.1, win 48.8%, squeeze: 173 trades, $3699.49, win 49.1%
- **ensemble: breakout+meanrev**: breakout: 342 trades, $4310.06, win 48.8%, meanrev: 87 trades, $-303.58, win 55.2%
- **ensemble: all + vol-scaled risk**: breakout: 223 trades, $1401.5, win 47.5%, spike: 57 trades, $414.34, win 47.4%, squeeze: 140 trades, $4474.39, win 49.3%, overnight: 84 trades, $86.71, win 54.8%, meanrev: 33 trades, $-28.18, win 60.6%
- **current + confluence tiers**: breakout: 260 trades, $3282.43, win 49.2%, squeeze: 162 trades, $3711.79, win 50.0%
- **current + tiers downsize-only (1/1/0.5)**: breakout: 261 trades, $2895.85, win 49.0%, squeeze: 160 trades, $2826.67, win 49.4%
- **current + tiers mild (1.25/1/0.5)**: breakout: 260 trades, $3175.67, win 49.2%, squeeze: 162 trades, $3312.67, win 50.0%
- **current + no-chase (2.5 ATR)**: breakout: 137 trades, $-310.12, win 43.1%, squeeze: 128 trades, $2141.99, win 48.4%
