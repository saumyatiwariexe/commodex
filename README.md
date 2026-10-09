# GoldSpread Intelligence

Hack in Hills '26, Track 03: Commodity Derivatives Intelligence.

Cross-contract relative-value analytics for MCX gold futures (GOLDM, GOLDTEN, GOLDGUINEA, GOLDPETAL), with walk-forward backtesting, honest cost accounting, gold-beta attribution, and quiet alerts.

## Document index
| Doc | What it covers |
|-----|----------------|
| [PRD.md](PRD.md) | Goals, scope tiers, requirements, risks |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System diagram, components, principles, repo layout |
| [DATA_PIPELINE.md](DATA_PIPELINE.md) | Ingestion adapters, parsing, validation, storage |
| [DATABASE.md](DATABASE.md) | DuckDB and SQLite schemas, integrity rules |
| [MODEL.md](MODEL.md) | Normalization, expiry pairing, signals, costs, backtest, attribution |
| [BACKEND.md](BACKEND.md) | FastAPI endpoints, jobs, config |
| [FRONTEND.md](FRONTEND.md) | Screens, components, demo mode |
| [AUTH.md](AUTH.md) | Login, roles, threats (P2) |
| [TESTING.md](TESTING.md) | Unit, look-ahead, synthetic, API, contract, e2e tests |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker Compose, demo safety, release checklist |
| [DEMO_PLAN.md](DEMO_PLAN.md) | Build order, team split, demo script, cut rules |
| [AGENTS.md](AGENTS.md) | Rules for AI agents: non-negotiables, iteration protocol, skill map |
| [CHANGELOG.md](CHANGELOG.md) | History of changes to the idea and the docs |

AI agents: read `AGENTS.md` first.

## Open items that block the build
1. **MCX data access is untested.** Capture the Bhavcopy request from browser dev tools and confirm it works from code, or download files manually and use the LocalFiles adapter.
2. **Team size, skills and hours are unknown.** DEMO_PLAN.md is expressed in time fractions until these are set.
3. **Cost parameters** (brokerage, exchange charges, taxes) must be filled in `costs.yaml` from current official schedules.
4. **Contract specs** in `contracts_meta.yaml` must be checked against the MCX spec page.

## Non-negotiables
No continuous near-month series. No look-ahead. Net-of-cost results using contracts actually held. Strategy separated from gold. A null result is acceptable if it is rigorous.
