# Frontend

> **Skills:** `dataviz` (every chart; read before writing chart code), `anthropic-skills:ui-ux-pro-max` (layout and interaction), `frontend-design` (aesthetic direction), `design:accessibility-review`, `design:ux-copy`, `design:design-critique` (before the demo). Optional: `superdesign:superdesign` for exploring variants, `data:build-dashboard` for a quick static prototype. Precedence and limits: AGENTS.md section 5.2. The principles in section 2 below override any skill's styling advice.

## 1. Stack
React 18 + TypeScript + Vite, Tailwind CSS, Recharts (or visx/ECharts if more control is needed), TanStack Query for data fetching.

**Fallback:** if the team has no React experience, Streamlit gets P0 on screen in a fraction of the time. Decide in the first hour and don't switch later.

## 2. Design principles
- **Quiet by default.** The home screen leads with "No actionable signal today" when that is true, plus the reason (for example, "best z = 1.4, threshold 2.0" or "candidate blocked: thin liquidity").
- **Show the work.** Every number links to raw prices, normalization steps and calendar position.
- **Honesty panel.** A persistent "What this does not show" section (from MODEL.md section 10).
- **Never plot a continuous near-month line.** Charts always plot individual contracts keyed by expiry.

## 3. Screens

### 3.1 Overview (home)
- Today's signal state (signal or explicit none), with the filter that blocked or passed it.
- Headline net-of-cost result on hold-out data, beta to gold, alpha.
- Dataset health: coverage, last ingest, snapshot hash (shortened, copyable).

### 3.2 Spread Explorer
- Select pair and expiry pairing (default: nearest expiry).
- Chart: normalized per-gram prices of both legs, with raw spread, carry-adjusted spread and z-score panels below.
- Toggle: raw vs carry-adjusted, to show how much of the "gap" was just expiry-date difference.
- Shaded regions: tender period, last N days before expiry, thin-liquidity days.

### 3.3 Term Structure
- Curve per symbol on a chosen date, with a date scrubber.
- Decomposition of a contract's daily move into roll-down vs genuine curve change.

### 3.4 Contract Calendar
- Timeline per contract: listing, liquidity build-up, tender, expiry.
- Overlay of every backtest trade's entry and exit, so the user can see each sits inside a valid window.

### 3.5 Backtest Report
- Config summary and hashes.
- Equity curve: strategy (net) vs gold, with hold-out boundary marked.
- Cost waterfall: gross, then each cost component, then net.
- Attribution card: beta, alpha, R^2, beta-neutral PnL.
- Cost sensitivity table (0.5x, 1x, 2x).
- Per-pair breakdown and number of combinations tested (multiple-testing disclosure).
- Trade table: legs with symbol and expiry, entry and exit prices actually held, costs, exit reason, hedge residual grams.

### 3.6 Alerts
- History of alerts. Empty state is a feature: show the alert rate (alert days / total days).

## 4. Component list
`AppShell`, `SignalBanner`, `HealthStrip`, `PairPicker`, `SpreadChart`, `ZScorePanel`, `CurveChart`, `CalendarTimeline`, `EquityChart`, `CostWaterfall`, `AttributionCard`, `SensitivityTable`, `TradeTable`, `HonestyPanel`, `HashBadge`, `LoginForm` (P2).

## 5. State and data
- TanStack Query keyed by endpoint plus params. Stale time of several minutes, since data is daily.
- URL holds pair, date range and run id, so any view is shareable.
- All dates shown in IST with the trading date explicit.

## 6. UX and accessibility
- Color is never the only signal (use labels and patterns for long/short, thin/ok/deep).
- Keyboard navigable charts tables, readable at projector resolution, dark and light themes.
- Loading skeletons and clear error states with the backend error code visible.

## 7. Demo mode
`?demo=1` loads bundled sample data and a precomputed run, so the demo works with no network, no backend warm-up and no login.
