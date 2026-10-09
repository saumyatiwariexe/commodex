# Data Pipeline

> **Skills:** `data:explore-data` (profile each new file or partition), `data:validate-data` (check parsed output), `data:statistical-analysis` (outlier flags). Do not use browser or desktop-control skills to get around MCX blocks (AGENTS.md non-negotiable 10).

## 0. Status of data access
**Unverified.** The MCX Bhavcopy page disallows automated fetchers (robots), and the endpoint behaviour from a script has not been tested. Step one of the project is to capture the real request in browser dev tools (Network tab, "Copy as cURL") and confirm it works from code. Until then, treat the live adapter as a guess and build the LocalFiles adapter first.

## 1. Adapter interface
```python
class BhavcopySource(Protocol):
    def fetch(self, requested: date) -> RawBhavcopy: ...
```
- `MCXLiveSource`: calls the MCX endpoint (details filled in after the cURL capture). Respect rate limits, add a delay between requests, identify yourself in the User-Agent, and stop on repeated 403/429.
- `LocalFilesSource`: reads Bhavcopy CSV/Excel files that a human downloaded through the browser into `data/inbox/`. This is the guaranteed fallback.

## 2. Parsing rules (from the problem statement)
| Field | Rule |
|-------|------|
| Request date | `DD/MM/YYYY` |
| Response `Date` | `MM/DD/YYYY`, parse explicitly with `%m/%d/%Y` |
| `ExpiryDate` | compact like `04SEP2026`, parse with `%d%b%Y` (uppercase month) |
| `Symbol` | strip whitespace, uppercase |
| Prices | Open, High, Low, Close as float, reject <= 0 |
| Volume, OpenInterest | int, null-safe |

## 3. Validation (each rule logs a reason code)
1. **Date echo check:** returned Date must equal requested date, otherwise discard the whole response (`DATE_MISMATCH`). MCX can return the latest trading day for holidays, malformed or future dates.
2. **Symbol filter:** keep GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL only.
3. **Duplicate check:** one row per (symbol, expiry_date, date).
4. **Sanity band:** normalized price within a configurable band of the day's median across contracts (flag, don't silently drop, as `OUTLIER_FLAG`).
5. **Expiry window check:** expiry day-of-month should fall in the expected window (GOLDM 3rd-5th, others 27th-31st). Violations are flagged because holidays shift real expiries.
6. **Coverage check:** report missing business days per contract. GOLDTEN is expected to start only from its 2025 listing.

## 4. Storage
- Raw responses saved as Parquet partitioned by trading date: `data/raw/date=YYYY-MM-DD/part.parquet`.
- A manifest file records source, fetch time, row count, and SHA-256 of each partition.
- The snapshot hash identifies "the data" in every backtest run. Its exact definition is in MODEL.md section 12.4. Each partition's SHA-256 is taken once, when the file is first written, and the file is never rewritten afterwards (Parquet output is not guaranteed to be byte-identical across writes).

## 5. Idempotency and backfill
- Re-fetching a date that already exists is a no-op unless `--force`.
- Backfill runs newest to oldest so a recent demo works even if the run is interrupted.
- Skip weekends client-side, and use a holiday list as a hint only. The date echo check remains the source of truth.

## 6. Contract metadata table (static, verify against MCX spec page)
| Symbol | Lot (g) | Quoted per (g) | Purity | Expiry window |
|--------|---------|----------------|--------|---------------|
| GOLDM | 100 | 10 | 995 | 3rd-5th |
| GOLDTEN | 10 | 10 | 999 | 27th-31st |
| GOLDGUINEA | 8 | 8 | 999 | 27th-31st |
| GOLDPETAL | 1 | 1 | 999 | 27th-31st |

Keep this in `contracts_meta.yaml`, not hard-coded in functions.

## 7. Failure handling
| Failure | Behaviour |
|---------|-----------|
| 403 / 429 / captcha | Stop, log, switch to LocalFiles, do not retry in a loop |
| Schema change | Fail loudly with the column diff |
| Partial day | Quarantine the partition, exclude from backtests |
