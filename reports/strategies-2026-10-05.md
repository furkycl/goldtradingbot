# Strategy families — 2026-10-05

GC=F 1h, 13739 bars up to the sealed holdout (2026-10-05), $10k, real costs. Random = same exits/sizing/costs with random entries (150 runs); p = share of random runs ≥ real. WF = 4 walk-forward OOS folds. Robust = guardrails + p ≤ 0.05 + PF > 1.1 at 2× costs + ≥3/4 folds positive.

| Config | Return % | Max DD % | Trades | PF | Win % | Random median % | p | Return 2× cost % | PF 2× | WF score | WF fold returns % | Longs $ | Shorts $ | Robust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| breakout | 58.21 | 8.46 | 339 | 1.63 | 51.6 | 5.21 | 0.0 | 52.67 | 1.59 | 1.6684 | [2.21, 10.5, -0.88, 5.82] | 4405.95 | 1415.17 | ✅ |
| squeeze | 36.44 | 5.17 | 260 | 1.51 | 46.9 | -0.73 | 0.007 | 32.54 | 1.45 | 0.3175 | [-1.15, 2.02, 2.02, 0.21] | 3597.73 | 45.79 | ✅ |
| overnight | 8.8 | 9.75 | 229 | 1.2 | 55.0 | 14.62 | 0.727 | 5.49 | 1.12 | -0.0788 | [-1.12, 0.23, -0.33, -0.16] | 879.79 | 0 | — |
| spike | 2.2 | 12.11 | 112 | 1.04 | 42.9 | 0.07 | 0.38 | -1.33 | 0.98 | -0.0851 | [-1.4, -6.94, 3.92, 0.45] | -461.69 | 681.54 | — |
| meanrev | -6.24 | 9.01 | 127 | 0.83 | 44.1 | -0.01 | 0.827 | -7.11 | 0.81 | -0.105 | [-1.97, -2.93, 2.19, 0.37] | 3.31 | -627.29 | — |
| spike follow | -17.25 | 18.8 | 116 | 0.72 | 31.9 | 0.28 | 1.0 | -18.6 | 0.7 | 0.0299 | [-2.6, 6.63, 1.0, -8.06] | -1808.6 | 83.54 | — |
| ensemble: all | 91.07 | 8.38 | 558 | 1.5 | 51.1 | 8.37 | 0.0 | 66.2 | 1.38 | 1.0601 | [1.21, 7.34, 5.91, 3.02] | 5647.36 | 3459.69 | ✅ |
| ensemble: breakout+squeeze | 65.85 | 7.39 | 417 | 1.58 | 50.8 | 6.38 | 0.0 | 55.41 | 1.51 | 1.8315 | [1.32, 7.2, 2.82, 9.04] | 5209.45 | 1375.42 | ✅ |
| ensemble: breakout+meanrev | 53.68 | 9.19 | 401 | 1.5 | 50.6 | 6.04 | 0.0 | 42.26 | 1.41 | 1.9438 | [0.16, 8.54, -0.69, 8.38] | 3574.88 | 1793.17 | ✅ |
| ensemble: all + vol-scaled risk | 110.02 | 13.0 | 516 | 1.52 | 52.3 | 7.7 | 0.0 | 87.45 | 1.44 | 1.1961 | [2.74, 11.53, 3.99, 4.96] | 8630.99 | 2370.68 | ✅ |
| breakout + vol-scaled risk | 82.84 | 10.3 | 314 | 1.75 | 51.6 | 6.89 | 0.0 | 67.13 | 1.64 | 2.3773 | [4.48, 15.32, -0.26, 7.33] | 6988.91 | 1295.5 | ✅ |

## Per-family attribution inside ensembles

- **ensemble: all**: breakout: 252 trades, $4497.13, win 49.6%, spike: 51 trades, $1171.51, win 49.0%, squeeze: 129 trades, $3033.23, win 48.8%, overnight: 87 trades, $119.81, win 58.6%, meanrev: 39 trades, $285.37, win 53.8%
- **ensemble: breakout+squeeze**: breakout: 245 trades, $3169.51, win 51.4%, squeeze: 172 trades, $3415.36, win 50.0%
- **ensemble: breakout+meanrev**: breakout: 323 trades, $5115.84, win 50.5%, meanrev: 78 trades, $252.21, win 51.3%
- **ensemble: all + vol-scaled risk**: breakout: 216 trades, $3508.47, win 50.5%, spike: 52 trades, $1083.69, win 50.0%, squeeze: 131 trades, $5302.18, win 51.1%, overnight: 84 trades, $591.36, win 59.5%, meanrev: 33 trades, $515.97, win 54.5%
