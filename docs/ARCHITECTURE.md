# Architecture

> **Skills:** `engineering:system-design`, `engineering:architecture`, `engineering:documentation`.

## 1. Overview
```
 MCX Bhavcopy (live)  ─┐
                       ├─► Ingestion adapters ─► Validation ─► Raw store (Parquet, immutable)
 Local files (fallback)┘                                          │
                                                                  ▼
                                              Normalization + expiry pairing
                                                                  │
                                              ┌───────────────────┴────────────────┐
                                              ▼                                    ▼
                                   Signal engine (z-scores)              Term structure / carry
                                              │                                    │
                                              └──────────────┬─────────────────────┘
                                                             ▼
                                            Walk-forward backtester + cost model
                                                             │
                                                             ▼
                                                 DuckDB analytics DB
                                                             │
                                                             ▼
                                                    FastAPI backend
                                                             │
                                                             ▼
                                                    React dashboard
```

## 2. Components and docs
| Component | Doc | Language / tool |
|-----------|-----|-----------------|
| Ingestion + validation | DATA_PIPELINE.md | Python, httpx, pandas |
| Storage | DATABASE.md | Parquet + DuckDB, SQLite for app state |
| Quant model | MODEL.md | Python, numpy, pandas, statsmodels |
| API | BACKEND.md | FastAPI, pydantic |
| UI | FRONTEND.md | React, TypeScript, Vite, Recharts |
| Auth (P2) | AUTH.md | Username/password + JWT |
| Quality | TESTING.md | pytest, hypothesis, Playwright |
| Run / deploy | DEPLOYMENT.md | Docker Compose |

## 3. Design principles
1. **Immutable raw layer.** Raw Bhavcopy rows are never edited. All cleaning produces new tables.
2. **Contract identity = (symbol, expiry_date).** No continuous series anywhere in the pipeline.
3. **Point-in-time everything.** Every feature carries an `as_of` date and is computed only from rows with date <= as_of.
4. **Deterministic runs.** A backtest run is fully defined by (data snapshot hash, config hash, code version). Same inputs give identical outputs.
5. **Adapters over assumptions.** Data source is behind an interface so a blocked MCX endpoint doesn't kill the project.
6. **Quiet by default.** Absence of a signal is a first-class UI state.

## 4. Repository layout
```
goldspread/
├── data/            raw/ (parquet, immutable), processed/, samples/
├── ingestion/       adapters, parsers, validators
├── model/           normalize.py, pairing.py, signals.py, carry.py, costs.py, backtest.py, attribution.py
├── api/             main.py, routers/, schemas.py, deps.py
├── web/             React app
├── tests/
├── docs/            these markdown files
└── docker-compose.yml
```

## 5. Data flow for one backtest run
1. Load raw snapshot, compute SHA-256 of the snapshot manifest.
2. Normalize prices, build expiry-aware pairs.
3. For each walk-forward fold: fit thresholds on the train window, trade the test window.
4. Apply costs and liquidity haircut to every fill.
5. Compute attribution against gold.
6. Persist run (config, snapshot hash, metrics, trades) to DuckDB.

## 6. Non-functional requirements
- A full backtest should finish in under 60 seconds on a laptop (daily data, four symbols, a few years).
- The dashboard must work from cached data with no internet, which makes the demo robust.
- Everything runs via `docker compose up`.
