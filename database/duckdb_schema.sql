-- Analytics schema (DuckDB)

-- Static contract metadata
CREATE TABLE IF NOT EXISTS contract_meta (
  symbol            VARCHAR PRIMARY KEY,
  lot_grams         DOUBLE NOT NULL,
  quote_grams       DOUBLE NOT NULL,
  purity            INTEGER NOT NULL,        -- 995 or 999
  expiry_window     VARCHAR NOT NULL
);

-- Raw daily settlement data, one row per (symbol, expiry, date). Immutable.
CREATE TABLE IF NOT EXISTS bhav_raw (
  trade_date     DATE    NOT NULL,
  symbol         VARCHAR NOT NULL,
  expiry_date    DATE    NOT NULL,
  open           DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
  volume         BIGINT,
  open_interest  BIGINT,
  source         VARCHAR NOT NULL,           -- 'mcx_live' | 'local_file'
  ingested_at    TIMESTAMP NOT NULL,
  PRIMARY KEY (trade_date, symbol, expiry_date)
);

-- Normalized price per gram at 999 purity
CREATE TABLE IF NOT EXISTS bhav_norm (
  trade_date     DATE, symbol VARCHAR, expiry_date DATE,
  px_per_gram_999 DOUBLE NOT NULL,
  days_to_expiry INTEGER NOT NULL,
  liquidity_bucket VARCHAR,                  -- 'thin' | 'ok' | 'deep'
  PRIMARY KEY (trade_date, symbol, expiry_date)
);

-- Pairs matched by nearest expiry
CREATE TABLE IF NOT EXISTS pair_spread (
  trade_date DATE, leg_a VARCHAR, expiry_a DATE, leg_b VARCHAR, expiry_b DATE,
  expiry_gap_days INTEGER,
  raw_spread DOUBLE,                         -- px_a - px_b per gram
  carry_adj_spread DOUBLE,                   -- after expiry-gap carry adjustment
  PRIMARY KEY (trade_date, leg_a, expiry_a, leg_b, expiry_b)
);

-- Backtest runs
CREATE TABLE IF NOT EXISTS bt_run (
  run_id          VARCHAR PRIMARY KEY,
  created_at      TIMESTAMP,
  snapshot_hash   VARCHAR NOT NULL,
  config_hash     VARCHAR NOT NULL,
  code_version    VARCHAR NOT NULL,
  config_json     JSON,
  period_start    DATE, period_end DATE,
  holdout_start   DATE,
  gross_pnl DOUBLE, total_cost DOUBLE, net_pnl DOUBLE,
  max_drawdown DOUBLE, sharpe DOUBLE,
  beta_gold DOUBLE, alpha_annual DOUBLE, r2_gold DOUBLE,
  n_trades INTEGER, alert_days INTEGER, total_days INTEGER
);

CREATE TABLE IF NOT EXISTS bt_trade (
  run_id VARCHAR, trade_id INTEGER,
  leg_a VARCHAR, expiry_a DATE, leg_b VARCHAR, expiry_b DATE,
  entry_date DATE, exit_date DATE, exit_reason VARCHAR,   -- 'target' | 'stop' | 'time' | 'calendar'
  qty_a INTEGER, qty_b INTEGER,
  entry_px_a DOUBLE, entry_px_b DOUBLE, exit_px_a DOUBLE, exit_px_b DOUBLE,
  gross_pnl DOUBLE, cost DOUBLE, net_pnl DOUBLE,
  PRIMARY KEY (run_id, trade_id)
);

CREATE TABLE IF NOT EXISTS bt_daily (
  run_id VARCHAR, trade_date DATE,
  strategy_ret DOUBLE, gold_ret DOUBLE, position_notional DOUBLE,
  PRIMARY KEY (run_id, trade_date)
);

-- Contract calendar
CREATE TABLE IF NOT EXISTS contract_calendar (
  symbol VARCHAR, expiry_date DATE,
  listing_date DATE, first_liquid_date DATE, tender_start DATE, last_trade_date DATE,
  PRIMARY KEY (symbol, expiry_date)
);
