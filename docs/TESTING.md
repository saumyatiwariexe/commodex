# Testing

> **Skills:** `engineering:testing-strategy` (plans and test architecture), `data:validate-data` and `data:statistical-analysis` (synthetic-data and attribution checks), `engineering:code-review`, `engineering:debug` (failing tests).

Rigor is the product. Tests are part of the demo: show the no-look-ahead test passing.

## 1. Tools
pytest, hypothesis (property tests), pytest-cov, httpx test client for FastAPI, Playwright for a small end-to-end suite, ruff and mypy in CI.

## 2. Unit tests: data layer
| Test | Asserts |
|------|---------|
| Request date format | DD/MM/YYYY produced from a date |
| Response date parse | `03/25/2026` parses as 25 March, not an error or swap |
| Ambiguous dates | `04/05/2026` parses as April 5 (MM/DD), never May 4 |
| Expiry parse | `04SEP2026` gives 2026-09-04 |
| Symbol cleaning | `"GOLDM    "` becomes `GOLDM` |
| Date echo | Response with Date != requested is discarded with `DATE_MISMATCH` |
| Holiday / future date | Mocked "latest trading day" response is rejected |
| Duplicate rows | Duplicate (date, symbol, expiry) handled deterministically |
| Immutable raw | Attempted update of `bhav_raw` fails |

## 3. Unit tests: normalization and pairing
- Hand-computed vectors, for example: GOLDM close 100,000 per 10 g gives `100000/10*999/995` per gram; GOLDGUINEA close 80,000 per 8 g gives 10,000 per gram. Check each symbol.
- Property: scaling a contract's price and quote base by the same factor leaves per-gram price unchanged.
- Pairing picks the nearest expiry, records the signed gap, and rejects gaps above the max.
- Regression test for the trap: a GOLDM (5 Nov) vs GOLDPETAL (30 Oct and 30 Nov) case must pair with 30 Oct, not by month name.

## 4. The look-ahead tests (most important)
1. **Future-shuffle test:** for a random date t, compute the signal at t. Randomly permute or replace all data after t. Recompute the signal at t. They must be identical.
2. **Truncation test:** compute signals on the full dataset, then on data truncated at t. Signals for all dates <= t must match exactly.
3. **Fill timing:** assert every fill price date is strictly after its decision date.
4. **Parameter isolation:** assert hyperparameters for a test fold are chosen only from rows dated before the fold start.
5. **Hold-out lock:** assert hold-out rows are never read during tuning (use a data access guard that raises).

## 5. Cost and attribution tests
- Zero-cost config makes net PnL equal gross PnL.
- Costs are monotonic: higher cost multiplier never increases net PnL.
- Cost components sum to total cost for every trade.
- A synthetic strategy that is exactly 1.0x gold returns gives beta close to 1 and alpha close to 0.
- A synthetic market-neutral series with a known alpha is recovered within tolerance.

## 6. Synthetic data tests
Generate fake contracts where the true spread is pure noise (no edge): the backtest must show net PnL near or below zero after costs across many seeds. Generate data with an injected mean-reverting spread of known strength: the model should detect it. This shows the backtester can find an edge when one exists and does not invent one when absent.

## 7. API tests
Status codes, schema validation, pagination, date range caps, role gating (anonymous, viewer, analyst, admin), error code format, `meta` hashes present on analytics responses, no endpoint returns a continuous near-month series.

## 8. Auth tests
See AUTH.md section 6.

## 9. End-to-end (Playwright)
1. Open `?demo=1`. Overview shows a signal state and headline metrics.
2. Spread Explorer renders; toggling raw/carry-adjusted changes the series.
3. Backtest Report lists trades; each row opens its raw prices.
4. Calendar shows entries and exits inside windows.

## 10. CI
On every push: ruff, mypy, pytest with coverage threshold on `model/` (target 90%), frontend type-check and build, Playwright against the built demo mode.

## 11. Hashing and reproducibility tests
Spec: MODEL.md section 12.
1. **Key-order invariance:** the same config built with keys inserted in different orders (including nested dicts) gives the same `config_hash`.
2. **Known-answer vector:** a fixed config must hash to a fixed hex string stored in the test. If this fails, canonicalization changed and the version must be bumped.
3. **Float and null rules:** `-0.0` and `0.0` hash the same. NaN and infinity raise an error. A missing key and an explicit null hash differently.
4. **Process independence:** compute the hash in two separate processes with different `PYTHONHASHSEED` values. Results must match.
5. **Snapshot ordering:** shuffling manifest entries does not change `snapshot_hash`.
6. **Snapshot tamper detection:** changing one byte in a partition file changes `snapshot_hash`, and verification reports which file failed.
7. **No rewrite on re-ingest:** re-fetching an existing date leaves file bytes and `snapshot_hash` unchanged.
8. **Run reproducibility:** two runs with identical snapshot, config and code produce identical metrics and an identical trade table.
9. **Dirty code flag:** a run from a dirty working tree gets a `-dirty` suffix and is flagged non-reproducible.
10. **Single entry point:** a lint or grep test fails if `hashlib` or `json.dumps` is used for run hashing outside `model/canonical.py`.

## 12. Definition of done for the demo
- Look-ahead tests pass and are shown live.
- Synthetic no-edge and known-edge tests pass.
- A judge-selected trade can be traced from raw rows to costs to net PnL.