# Backend

> **Skills:** `anthropic-skills:fastapi-expert` (endpoints, pydantic, async), `anthropic-skills:api-designer` (contracts, pagination, errors), `anthropic-skills:secure-code-guardian` (validation, CORS, auth code), `engineering:code-review` (before merging).

## 1. Stack
Python 3.11+, FastAPI, pydantic v2, DuckDB, SQLite (SQLAlchemy or plain sqlite3), uvicorn. Model code lives in `model/` and is imported by the API as a library. The API never re-implements quant logic.

## 2. Principles
- Read-mostly. Heavy computation (ingest, backtest) runs as background jobs, and the API serves stored results.
- Every response that includes a metric also includes `snapshot_hash`, `config_hash`, `run_id` where applicable, so numbers are traceable.
- Public read endpoints need no auth, so a judge can open the demo with no setup. Write and job endpoints require a role (AUTH.md).

## 3. API surface (prefix `/api/v1`)

### Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/contracts` | Contract metadata (lot, quote base, purity, expiry window) |
| GET | `/prices?symbol=&expiry=&from=&to=` | Normalized per-gram prices for one contract, keyed by expiry |
| GET | `/curve?symbol=&as_of=` | Term structure on a date |
| GET | `/calendar?from=&to=` | Contract lifecycle events (listing, liquidity, tender, expiry) |
| GET | `/coverage` | Missing days and quarantined partitions per contract |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| GET | `/pairs` | Valid pairs with expiry gap on a date |
| GET | `/spread?pair=&from=&to=` | Raw and carry-adjusted spread, z-score |
| GET | `/signals?as_of=` | Current signals after filters, or an explicit `{"signals": [], "reason": "no_signal"}` |
| GET | `/alerts?from=&to=` | Alert history (quiet by default) |

### Backtest
| Method | Path | Description |
|--------|------|-------------|
| POST | `/backtests` | Start a run with a config (analyst role), returns `run_id` |
| GET | `/backtests/{run_id}` | Metrics, status, hashes |
| GET | `/backtests/{run_id}/trades` | Trade list with prices actually held and cost breakdown |
| GET | `/backtests/{run_id}/equity` | Daily strategy vs gold series |
| GET | `/backtests/{run_id}/attribution` | Beta, alpha, R^2, beta-neutral PnL |
| GET | `/backtests/{run_id}/sensitivity` | Results at 0.5x / 1x / 2x costs |

### Ingestion (admin)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Start ingest for a date range, source selectable |
| GET | `/ingest/{job_id}` | Progress and validation reason counts |

### Auth (P2)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Username and password, returns JWT |
| GET | `/auth/me` | Current user and role |

## 4. Response conventions
```json
{
  "data": { ... },
  "meta": { "snapshot_hash": "...", "run_id": "...", "generated_at": "..." }
}
```
Errors: `{ "error": { "code": "DATE_MISMATCH", "message": "...", "details": {} } }` with proper HTTP status.

## 5. Jobs
- Simple in-process job runner with a thread pool is enough. Persist job status in SQLite.
- One backtest at a time per user to avoid CPU contention.
- All jobs log a structured line per step, which also feeds the demo's "how it works" panel.

## 6. Validation and safety
- Pydantic models validate all query params, including date ranges and symbol allow-lists.
- Cap the date range and result sizes. Paginate trade lists.
- CORS restricted to the frontend origin.
- Rate limit write endpoints.
- No endpoint accepts raw SQL or file paths.

## 7. Configuration
`.env` keys: `DATA_DIR`, `DUCKDB_PATH`, `SQLITE_PATH`, `JWT_SECRET`, `ALLOWED_ORIGINS`, `INGEST_SOURCE`. No secrets in the repo; provide `.env.example`.

## 8. Observability
Structured JSON logs, request id per call, `/healthz` and `/readyz` endpoints, and a `/version` endpoint returning code version and snapshot hash.
