# Quant Model

> **Skills:** `data:statistical-analysis` (method choice for z-scores, regression, significance), `data:analyze` (reading results), `data:validate-data` (check numbers before showing them), `engineering:testing-strategy` (look-ahead and synthetic tests). This doc fixes the protocol; skills may suggest methods but may not change the protocol.

This is the part judges will scrutinize hardest. Keep it simple, correct and honest.

## 1. Normalization
Convert every settlement price to **INR per gram of 999-purity gold**.

```
px_per_gram_999 = (close / quote_grams) * (999 / purity)
```
| Symbol | quote_grams | purity | Formula |
|--------|-------------|--------|---------|
| GOLDM | 10 | 995 | close / 10 * 999/995 |
| GOLDTEN | 10 | 999 | close / 10 |
| GOLDGUINEA | 8 | 999 | close / 8 |
| GOLDPETAL | 1 | 999 | close / 1 |

**Verify against the MCX spec page before trusting.** Tests must check hand-computed values (TESTING.md).

## 2. The expiry trap and pairing
GOLDM expires around the 3rd-5th. The other three expire around the 27th-31st. A GOLDM November contract is therefore not the same-date peer of a GOLDPETAL October contract. Comparing by contract month injects carry into the spread and produces false signals.

**Pairing rule:** for contracts A and B on date t, pair each expiry of A with the expiry of B nearest in calendar days. Record `expiry_gap_days`. Reject pairs with gap above a configurable max (default 10 days).

**Carry adjustment:** estimate daily carry rate from the term structure of a single family (for example consecutive GOLDPETAL expiries), then adjust:
```
carry_adj_spread = px_a - px_b * (1 + r_daily * expiry_gap_days_signed)
```
Estimate `r_daily` only from data up to t. If it can't be estimated stably, fall back to excluding wide-gap pairs rather than guessing.

## 3. Term structure and carry (P1)
- Build the curve per symbol per date from all live expiries.
- Decompose daily change in a contract's price into: (a) mechanical roll-down (price converging toward spot as days_to_expiry shrinks, at the constant carry rate), (b) curve shift (parallel change), (c) slope change. Only (b) and (c) are "genuine" curve moves.

## 4. Signal
For each pair, daily:
1. `s_t = carry_adj_spread_t`
2. Rolling mean and std over a lookback L using data up to and including t (no future data).
3. `z_t = (s_t - mean) / std`
4. Candidate signal if `|z_t| >= z_entry`, filtered by:
   - liquidity bucket of both legs not 'thin' (based on volume and open interest percentile, not volume alone)
   - both contracts outside tender period and outside the last N days before expiry
   - minimum expiry gap and maximum expiry gap rules from section 2
5. Direction: long the cheap leg, short the rich leg.
6. Exit when `|z|` falls below `z_exit`, on stop at `z_stop`, on max holding days, or before the calendar exit date, whichever comes first.

## 5. Position sizing (lot granularity matters)
Lot sizes differ (GOLDM 100 g, GOLDTEN 10 g, GOLDGUINEA 8 g, GOLDPETAL 1 g). To match notional, a GOLDM lot corresponds to about 100 GOLDPETAL lots. Consequences:
- Matching exactly can mean many small-lot orders, so per-lot and per-order costs matter.
- Residual unhedged grams are real directional exposure. Report them.
- Compute and report `hedge_residual_grams` per trade.

## 6. Cost model (config, not constants)
All values live in `costs.yaml` and must be verified against current exchange and broker schedules before the demo. [Guessing] on exact current rates, so none are hard-coded here.
Components per fill: brokerage (per order or per lot), exchange transaction charge (bps of turnover), commodity transaction tax on the applicable side, GST on fees, stamp duty, and a **slippage haircut**.

Slippage haircut by liquidity bucket:
```
slip_bps = base_bps[bucket] + k * (order_grams / avg_daily_volume_grams)
```
Settlement price is not a fill price, so every entry and exit is priced at settlement +/- slippage in the adverse direction. Sensitivity table: show results at 0.5x, 1x, 2x costs.

## 7. Walk-forward backtest
- Expanding train window, fixed test window (for example train 12 months, test 3 months, step 3 months). Adjust to data length.
- Parameters (L, z_entry, z_exit, z_stop) chosen from a **small** grid on the train window only.
- **Locked hold-out:** the last chunk of data is never touched until final reporting. Its results are reported once.
- Day loop: decisions at close of day t use data <= t, fills happen at day t+1 settlement (conservative), not t.
- Prices used for PnL are those of the contracts actually held (symbol, expiry), marked daily.
- Overlapping trades limited by a max-positions config.

## 8. Attribution (strategy vs gold)
Daily strategy returns regressed on gold returns:
```
strategy_ret_t = alpha + beta * gold_ret_t + eps_t
```
- `gold_ret` from the most liquid same-day settlement, marked per-gram-999 (define it explicitly, do not use a continuous near-month series).
- Report beta, annualized alpha, R^2, and the PnL of a gold-beta-neutralized version.
- A strategy with large beta and weak alpha is just gold exposure.

## 9. Metrics reported
Gross PnL, total costs, net PnL, hit rate, average trade, max drawdown, turnover, exposure days, alert days / total days, beta, alpha, R^2, sensitivity to 0.5x/1x/2x costs, per-pair results, hold-out vs train results side by side.

## 10. Known limits (state these in the demo)
- Daily settlement data cannot show intraday executability.
- GOLDTEN has a short history, so results involving it have wide error bars.
- Multiple-testing risk: the more pairs and parameters tried, the more likely a false positive. Report how many combinations were tested.
- Thin contracts may show spreads that exist only on paper.
- Regime dependence: results from one period may not hold in another.

## 11. A null result is valid
If no pair survives costs on hold-out data, publish that plainly with the evidence: cost waterfall, hold-out equity curve, per-pair breakdown, and the multiple-testing count. The problem statement explicitly accepts this.

## 12. Hashing and reproducibility
A run is identified by three values. They are only useful if the same inputs always produce the same hash, so serialization is specified here and implemented once.

### 12.1 What gets hashed
| Value | Input | Stored as |
|-------|-------|-----------|
| `snapshot_hash` | The set of raw data files used (12.4) | `sha256:v1:<64 hex chars>` |
| `config_hash` | The full backtest config after defaults are applied | `sha256:v1:<64 hex chars>` |
| `code_version` | Git commit SHA, plus `-dirty` if the working tree has uncommitted changes | string |

A run with a `-dirty` code version is marked non-reproducible in the UI and must not be used for headline results.

### 12.2 Canonical serialization (`model/canonical.py`)
All hashing of structured data goes through `canonical_bytes(obj)` and `hash_obj(obj)`. Nothing else calls `json.dumps` and `hashlib` directly.
1. JSON, encoded as UTF-8, no BOM.
2. Object keys sorted recursively. Separators `,` and `:` with no whitespace.
3. Integers as integers. Floats via Python's shortest round-trip form, with `-0.0` normalized to `0.0`. **Reject** NaN and infinity (raise an error).
4. Dates and datetimes as ISO 8601 strings (`2026-10-09`). Datetimes must be UTC.
5. Sets and unordered collections converted to sorted lists. Ordered lists keep their order.
6. Nulls are written explicitly. A missing key and a null value hash differently, so apply defaults before hashing.
7. No machine-specific values: no absolute paths, hostnames, usernames or timestamps of the run itself.
8. The `v1` in the stored string is the canonicalization version. Any change to these rules bumps it to `v2`, so old and new hashes are never compared as equal by accident.

### 12.3 Algorithms
- SHA-256 for integrity hashing of data, configs and files. Fast hashes like this are correct for integrity and **wrong for passwords** (see AUTH.md for password hashing).
- Files are hashed by streaming in fixed-size chunks.

### 12.4 Snapshot hash
1. For every raw partition file, record: relative POSIX path, SHA-256 of the file bytes, row count.
2. Sort entries by path.
3. Canonicalize the list (12.2) and hash it.

**Parquet caveat:** [Likely] writing the same rows twice can produce different file bytes (metadata such as writer version and creation info). So the hash is taken **when the file is first written**, the file is then treated as immutable, and ingestion must never rewrite an existing partition (re-fetching an existing date is a no-op, per DATA_PIPELINE.md). The snapshot hash therefore identifies the stored files, not the abstract data.

### 12.5 What these hashes do and do not prove
- They detect accidental drift: a changed file, a changed config, a different code version.
- They do **not** prove authenticity. Anyone with write access to both the data and the database can recompute matching hashes. State this plainly if asked.
- A matching hash proves the same inputs, not that the inputs were correct.
