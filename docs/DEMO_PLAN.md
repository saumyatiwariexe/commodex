# Demo Plan and Execution Order

> **Skills:** `anthropic-skills:pptx` (if a .pptx deck is wanted), `superdesign:superdesign` (optional, slide visuals), `design:design-critique` (review screens before presenting), `engineering:standup` (team status), `engineering:deploy-checklist` (night-before check).

Team size and available hours are **not known yet**. The plan below is by fraction of total time so it scales. Adjust once you know both.

## 1. Build order (fraction of total time)
| Phase | Share | Output | Gate to continue |
|-------|-------|--------|------------------|
| 0. Data access test | first 5% | Clean pull of a multi-month history, or LocalFiles fallback working | Switch tracks if neither works within about an hour |
| 1. Ingestion + validation | 20% | Immutable Parquet store, coverage report | Date echo and parsing tests pass |
| 2. Normalization + pairing | 15% | Per-gram prices, expiry-aware pairs | Hand-computed vectors pass |
| 3. Signal + backtest + costs | 25% | Walk-forward run with hold-out and cost waterfall | Look-ahead tests pass |
| 4. Attribution + sensitivity | 5% | Beta, alpha, cost multipliers | Synthetic tests pass |
| 5. API + dashboard | 20% | P0 screens in demo mode | Judge can trace a trade end to end |
| 6. Polish, honesty panel, docs | 5% | README, limits, slides | |
| 7. P2: basic login | Only with leftover time, hard cap | Login and role gating | Skip if phase 5 is shaky |

## 2. Suggested split for a team of three to four
(Adjust to actual skills.)
- **Data and model lead:** phases 1-4.
- **Backend and infrastructure:** API, storage, Docker, CI, tests.
- **Frontend and presentation:** dashboard, demo mode, slides.
- **If there is a fourth person:** own TESTING.md (look-ahead and synthetic-data tests) and the cost-model research. Both are routinely underestimated.

## 3. Demo script (about 5 minutes)
1. **The trap (30 s):** show the four contracts and why naive comparison is wrong (different purity, size, expiry dates).
2. **Normalization (30 s):** one contract's raw price turned into per-gram-999, with the formula visible.
3. **Expiry pairing (45 s):** the Spread Explorer toggle, raw vs carry-adjusted. "Most of the apparent gap was expiry-date difference."
4. **Quiet alerts (30 s):** today's state is "no signal", with the reason. Show the alert rate.
5. **Backtest honesty (90 s):** equity curve with the hold-out boundary, cost waterfall, beta and alpha, cost sensitivity. State the result plainly, whichever way it falls.
6. **Trace a trade (45 s):** pick a trade a judge names, show raw rows, normalization, fills, costs, calendar position.
7. **Limits (30 s):** read the honesty panel aloud.

## 4. What judges are likely to probe
- "How do you know there is no look-ahead?" Run the shuffle test live.
- "Is settlement price executable?" Show the slippage haircut and sensitivity.
- "Is this just gold beta?" Show the regression and beta-neutral PnL.
- "How many things did you try?" Show the multiple-testing count.

## 5. Scope-cut rules
If behind schedule at 60% of time: drop term structure decomposition. At 75%: drop auth entirely. Never cut: date validation, expiry pairing, costs, look-ahead tests, hold-out, attribution, honesty panel.

## 6. Biggest project risks, ranked
1. MCX data access fails and no fallback files were downloaded in time.
2. Time spent on UI polish while the model has bugs.
3. A sloppy cost model that makes a null result look unconvincing.
4. Overfitting through too many parameter and pair combinations.
5. Demo depends on live network.
