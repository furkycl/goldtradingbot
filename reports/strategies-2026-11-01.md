# Strategy families — 2026-11-01

GC=F 1h, 13271 bars up to the sealed holdout (2026-10-05), $10k, real costs. Random = same exits/sizing/costs with random entries (150 runs); p = share of random runs ≥ real. WF = 4 walk-forward OOS folds. Robust = guardrails + p ≤ 0.05 + PF > 1.1 at 2× costs + ≥3/4 folds positive.

| Config | Return % | Max DD % | Trades | PF | Win % | Random median % | p | Return 2× cost % | PF 2× | WF score | WF fold returns % | Longs $ | Shorts $ | Robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout | 51.78 | 11.51 | 348 | 1.52 | 50.0 | 6.25 | 0.027 | 46.5 | 1.47 | 1.8717 | [2.88, 6.57, 0.99, 6.16] | 4011.68 | 1166.5 | ✅ |
| squeeze | 42.29 | 6.42 | 257 | 1.52 | 46.7 | 3.34 | 0.0 | 40.01 | 1.49 | 0.3307 | [-3.31, 2.23, 4.09, -0.74] | 4072.28 | 156.85 | — |
| overnight | 10.05 | 10.14 | 231 | 1.21 | 55.0 | 15.74 | 0.753 | 6.47 | 1.13 | -0.0374 | [-0.3, 0.13, -0.87, -0.14] | 1004.63 | 0 | — |
| spike | 2.15 | 13.49 | 120 | 1.03 | 42.5 | 1.92 | 0.487 | -3.8 | 0.94 | -0.1991 | [-4.05, -4.47, 2.11, -0.42] | -348.56 | 563.22 | — |
| meanrev | -9.1 | 10.58 | 162 | 0.78 | 53.7 | -1.69 | 0.847 | -9.54 | 0.77 | -0.4471 | [-1.72, -0.4, -1.26, -1.69] | -50.97 | -859.35 | — |
| spike follow | -14.87 | 16.64 | 119 | 0.76 | 33.6 | -2.25 | 0.967 | -16.38 | 0.74 | 0.1074 | [-2.09, 4.03, 1.9, -6.22] | -402.56 | -1084.25 | — |
| ensemble: all | 57.28 | 8.15 | 565 | 1.29 | 49.7 | 14.96 | 0.033 | 52.79 | 1.29 | 1.1446 | [1.11, 5.35, 7.8, 2.18] | 4093.76 | 1634.96 | ✅ |
| ensemble: breakout+squeeze | 65.43 | 7.13 | 422 | 1.51 | 49.1 | 8.77 | 0.0 | 55.87 | 1.45 | 1.7911 | [-0.66, 4.28, 5.69, 6.52] | 5423.14 | 1120.23 | ✅ |
| ensemble: breakout+meanrev | 39.72 | 9.41 | 416 | 1.35 | 50.2 | 6.47 | 0.04 | 27.78 | 1.25 | 1.9704 | [2.0, 7.9, 0.46, 6.65] | 3199.43 | 773.48 | ✅ |
| ensemble: all + vol-scaled risk | 70.6 | 11.81 | 525 | 1.33 | 50.1 | 13.29 | 0.02 | 48.21 | 1.23 | 1.2093 | [3.33, 10.03, 6.54, 3.72] | 5960.1 | 1100.34 | ✅ |
| breakout + vol-scaled risk | 58.64 | 13.64 | 321 | 1.51 | 50.2 | 8.36 | 0.013 | 47.91 | 1.44 | 2.2564 | [5.85, 10.25, 2.6, 7.09] | 5104.56 | 759.68 | ✅ |
| current + confluence tiers | 68.45 | 12.06 | 408 | 1.48 | 49.0 | 7.48 | 0.007 | 64.61 | 1.46 | 1.3909 | [0.7, 6.24, 6.7, 4.83] | 4708.52 | 2137.16 | ✅ |
| current + tiers downsize-only (1/1/0.5) | 57.3 | 8.18 | 407 | 1.49 | 48.6 | 3.84 | 0.0 | 52.53 | 1.46 | 1.2479 | [-0.4, 5.48, 3.45, 4.87] | 4225.62 | 1505.38 | ✅ |
| current + tiers mild (1.25/1/0.5) | 63.57 | 10.8 | 408 | 1.49 | 49.0 | 5.0 | 0.0 | 56.7 | 1.44 | 1.2745 | [0.33, 6.89, 6.09, 3.61] | 4302.27 | 2055.62 | ✅ |
| current + no-chase (2.5 ATR) | 22.61 | 7.75 | 257 | 1.32 | 45.5 | 2.38 | 0.067 | 18.42 | 1.26 | 0.3621 | [-1.86, 1.55, 0.66, 2.18] | 1895.79 | 365.64 | — |
| breakout touch-entry | 53.37 | 9.04 | 452 | 1.39 | 45.4 | 30.76 | 0.16 | 48.35 | 1.36 | 1.0772 | [2.24, 7.02, -0.02, 5.83] | 4089.02 | 1248.43 | — |
| current + touch-entry | 67.73 | 7.46 | 506 | 1.42 | 46.2 | 22.89 | 0.027 | 57.67 | 1.37 | 1.5236 | [-1.77, 5.34, 6.94, 5.28] | 5417.23 | 1357.02 | ✅ |

## Confluence score vs realised R (breakout+squeeze, equal sizing)

Does a higher quality score predict better trades? (If not, tiers only add variance.)

| Score bucket | Trades | Avg R | Win % | Sum R |
|---|---|---|---|---|
| ≥0.75 | 125 | 0.155 | 53.6 | 19.4 |
| 0.5–0.75 | 227 | 0.165 | 48.0 | 37.5 |
| <0.5 | 57 | 0.015 | 40.4 | 0.8 |

## Concurrent positions (one per family, no hedging, total open risk capped)

| Config | Return % | Max DD % | Return/DD | Trades | PF | Sharpe | WF fold returns % |
|---|---|---|---|---|---|---|---|
| 1 position (current) | 65.43 | 7.13 | 9.18 | 422 | 1.51 | 2.02 | [-0.66, 4.28, 5.69, 6.52] |
| 2 positions b+s, 2% total | 98.27 | 13.41 | 7.33 | 608 | 1.43 | 1.89 | [0.31, 7.2, 5.74, 4.45] |
| 2 positions b+s, 3% total | 98.27 | 13.41 | 7.33 | 608 | 1.43 | 1.89 | [0.31, 7.2, 5.74, 4.45] |
| 3 positions all families, 3% total | 131.84 | 18.1 | 7.28 | 923 | 1.32 | 1.9 | [-2.86, 6.42, 9.74, 0.15] |

## Per-family attribution inside ensembles

- **ensemble: all**: breakout: 243 trades, $1878.95, win 46.5%, overnight: 95 trades, $447.44, win 57.9%, squeeze: 139 trades, $2795.64, win 48.2%, spike: 54 trades, $729.39, win 48.1%, meanrev: 34 trades, $-122.69, win 58.8%
- **ensemble: breakout+squeeze**: breakout: 253 trades, $2796.6, win 49.0%, squeeze: 169 trades, $3746.77, win 49.1%
- **ensemble: breakout+meanrev**: breakout: 334 trades, $4335.89, win 49.1%, meanrev: 82 trades, $-362.98, win 54.9%
- **ensemble: all + vol-scaled risk**: breakout: 218 trades, $1554.24, win 48.2%, overnight: 83 trades, $270.36, win 54.2%, squeeze: 138 trades, $4707.53, win 48.6%, spike: 55 trades, $663.66, win 49.1%, meanrev: 31 trades, $-135.35, win 61.3%
- **current + confluence tiers**: breakout: 251 trades, $3136.1, win 48.6%, squeeze: 157 trades, $3709.58, win 49.7%
- **current + tiers downsize-only (1/1/0.5)**: breakout: 251 trades, $2786.05, win 48.2%, squeeze: 156 trades, $2944.95, win 49.4%
- **current + tiers mild (1.25/1/0.5)**: breakout: 251 trades, $2950.3, win 48.6%, squeeze: 157 trades, $3407.59, win 49.7%
- **current + no-chase (2.5 ATR)**: breakout: 132 trades, $-29.1, win 43.2%, squeeze: 125 trades, $2290.53, win 48.0%
- **current + touch-entry**: breakout: 404 trades, $5252.02, win 46.3%, squeeze: 102 trades, $1522.22, win 46.1%
