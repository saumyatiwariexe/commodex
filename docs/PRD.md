# PRD: Commodex (Track 03, Hack in Hills '26)

> **Skills:** `engineering:documentation` (writing and updating docs), `engineering:architecture` (recording decisions). Rules: see AGENTS.md.

## 1. One-line pitch
A rigorous, quiet-by-default analytics product that measures relative pricing between MCX gold futures contracts (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), and tests whether any gap survives costs.

## 2. Problem
The four contracts track the same metal, so normalized prices should be tightly linked. Gaps exist, but most are artifacts: different expiry dates, purity (995 vs 999), thin liquidity, and settlement prices that are not executable fills. Traders and judges need to know which gaps are real, and whether any survive costs.

## 3. Goals
| ID | Goal | Measure |
|----|------|---------|
| G1 | Correct normalization across contract size, quotation base and purity | Unit tests against hand-computed values |
| G2 | Pair contracts by expiry date, never by continuous near-month series | No artificial jumps at roll in any chart |
| G3 | Walk-forward backtest with zero look-ahead | Passes the future-shuffle test (see TESTING.md) |
| G4 | Net-of-cost results using the prices of contracts actually held | Cost breakdown shown per trade |
| G5 | Separate strategy performance from gold price movement | Beta to gold and alpha reported |
| G6 | Quiet alerts: no signal means no alert | Alert rate reported, with an explicit "no signal today" state |

## 4. Non-goals
- Live trading or order routing.
- Intraday data (only daily Bhavcopy).
- Claiming a profitable edge. A well-evidenced "no persistent edge after costs" result is a valid outcome per the problem statement.

## 5. Users
- **Judge / reviewer:** wants rigor, clear methodology, honest limits.
- **Commodity trader / analyst:** wants a calendar-aware view of spreads and a quiet alert feed.

## 6. Scope tiers
**P0 (must ship)**
- Ingestion with date validation and caching (DATA_PIPELINE.md)
- Normalization and expiry-aware pairing (MODEL.md)
- Walk-forward backtest with costs and gold attribution
- Dashboard: spread chart, contract calendar, backtest report, quiet-alert feed

**P1 (should ship)**
- Term structure and carry view, with mechanical roll-down separated from real curve change
- Liquidity-aware cost haircut by volume and open-interest bucket
- Read-only public API

**P2 (only if P0 and P1 are done)**
- Basic login for analyst and admin endpoints (AUTH.md)

## 7. Functional requirements
1. Fetch Bhavcopy for a date range; discard rows where returned Date != requested date.
2. Parse: request DD/MM/YYYY, response MM/DD/YYYY, ExpiryDate like `04SEP2026`, strip space-padded symbols.
3. Store each contract keyed by (symbol, expiry_date).
4. Compute normalized price per gram at 999 purity.
5. Pair contracts by nearest expiry and adjust for the expiry-day gap.
6. Generate spread z-scores using only data available up to day t.
7. Backtest with walk-forward folds and a locked hold-out period.
8. Report gross PnL, costs, net PnL, drawdown, turnover, beta to gold, alpha.
9. Show a contract lifecycle calendar (listing, liquidity build-up, tender period, expiry) with every entry and exit placed inside it.
10. Alerts fire only when a signal exceeds threshold AND passes liquidity and calendar filters.

## 8. Success criteria for the demo
- A judge can pick any trade and see its raw prices, normalization, costs and calendar position.
- The system states plainly what it does NOT show (see MODEL.md, Known Limits).
- No chart or metric depends on a continuous near-month series.

## 9. Key risks
| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| MCX blocks scripted access | Unknown, test first | LocalFiles adapter: manually download Bhavcopy in browser, ingest from folder |
| GOLDTEN history too short for stats | High | Report it separately, flag low sample size |
| Overfitting thresholds | High | Walk-forward plus locked hold-out, parameter grid kept small |
| Costs wipe out the edge | Likely | This is an acceptable, defensible result |
