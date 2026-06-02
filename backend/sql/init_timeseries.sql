-- =============================================================================
-- TimescaleDB Time-Series Schema Init
-- Phase 1 of the TimescaleDB implementation plan
--
-- This script creates NET-NEW tables only. It does NOT modify existing tables
-- (daily_gainers, watchlist, observations, etc.).
--
-- Existing time-series tables already in place:
--   - price_history_1min  (hypertable ✓, empty)
--   - price_history_daily (regular table, empty)
--   - options_snapshot    (hypertable ✓)
--   - screener_alerts     (hypertable ✓)
--
-- Run with:
--   psql -h 192.168.0.201 -U journal -d trading_journal -f init_timeseries.sql
-- =============================================================================

BEGIN;

-- ─── 1. Strategies ──────────────────────────────────────────────────────────
-- Central registry for trading strategies. Referenced by signals & backtests.

CREATE TABLE IF NOT EXISTS strategies (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(128) NOT NULL UNIQUE,
    description  TEXT,
    version      VARCHAR(32) DEFAULT '1.0.0',
    author       VARCHAR(64) DEFAULT 'jack',
    asset_class  VARCHAR(32),        -- 'equity', 'futures', 'crypto'
    timeframes   TEXT[],             -- ARRAY['1m','5m','1D']
    parameters   JSONB NOT NULL DEFAULT '{}',
    is_active    BOOLEAN DEFAULT FALSE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_strategies_active
    ON strategies (is_active) WHERE is_active = TRUE;


-- ─── 2. Backtest Runs ───────────────────────────────────────────────────────
-- Stores results of historical backtests, linked to a strategy.

CREATE TABLE IF NOT EXISTS backtest_runs (
    id              SERIAL PRIMARY KEY,
    strategy_id     INTEGER REFERENCES strategies(id) ON DELETE CASCADE,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    symbol          VARCHAR(32) NOT NULL,
    timeframe       VARCHAR(16) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}',
    -- Core metrics
    total_trades    INTEGER,
    win_rate        NUMERIC(5,4),
    profit_factor   NUMERIC(8,4),
    net_pnl         NUMERIC(14,4),
    max_drawdown    NUMERIC(8,4),
    sharpe_ratio    NUMERIC(8,4),
    sortino_ratio   NUMERIC(8,4),
    avg_win         NUMERIC(14,4),
    avg_loss        NUMERIC(14,4),
    -- Detailed results
    trades          JSONB,
    equity_curve    JSONB,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_strategy
    ON backtest_runs (strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_symbol
    ON backtest_runs (symbol);


-- ─── 3. Indicators Hypertable ───────────────────────────────────────────────
-- Computed technical indicator values (EMA, RSI, ATR, MACD, etc.)
-- Partitioned by time for fast range scans.

CREATE TABLE IF NOT EXISTS indicators (
    ts              TIMESTAMPTZ  NOT NULL,
    symbol          VARCHAR(10)  NOT NULL,
    timeframe       VARCHAR(8)   NOT NULL,
    indicator_name  VARCHAR(64)  NOT NULL,   -- 'EMA_20', 'RSI_14', 'ATR_14'
    value           DOUBLE PRECISION,
    value2          DOUBLE PRECISION,        -- multi-output (e.g., MACD signal)
    value3          DOUBLE PRECISION
);

-- Convert to hypertable (idempotent check via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'indicators'
    ) THEN
        PERFORM create_hypertable('indicators', 'ts');
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_ind_sym_name
    ON indicators (symbol, indicator_name, ts DESC);
CREATE INDEX IF NOT EXISTS idx_ind_sym_tf
    ON indicators (symbol, timeframe, ts DESC);


-- ─── 4. Signals ─────────────────────────────────────────────────────────────
-- Strategy-generated trade signals. Real FK to strategies table.

CREATE TABLE IF NOT EXISTS signals (
    id              SERIAL PRIMARY KEY,
    ts              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    symbol          VARCHAR(10)  NOT NULL,
    strategy_id     INTEGER      REFERENCES strategies(id) ON DELETE SET NULL,
    signal_type     VARCHAR(32)  NOT NULL,   -- 'ENTRY_LONG', 'ENTRY_SHORT', 'EXIT', 'ALERT'
    timeframe       VARCHAR(8),
    price           DOUBLE PRECISION,
    stop_loss       DOUBLE PRECISION,
    take_profit     DOUBLE PRECISION,
    confidence      REAL,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_signals_sym_ts
    ON signals (symbol, ts DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy
    ON signals (strategy_id);


-- ─── 5. Convert price_history_daily to hypertable ───────────────────────────
-- It exists as a regular table. Converting it enables chunk-based partitioning,
-- compression, and time_bucket() resampling.
--
-- NOTE: This is safe because the table is currently empty (0 rows).

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'price_history_daily'
    ) THEN
        -- The table uses 'date' column (DATE type) instead of TIMESTAMPTZ,
        -- which works fine as a hypertable partition column.
        PERFORM create_hypertable('price_history_daily', 'date',
            migrate_data => TRUE
        );
    END IF;
END $$;


-- ─── 6. Compression Policies ───────────────────────────────────────────────
-- Enable compression on time-series hypertables for storage efficiency.
-- ~90%+ compression on historical OHLCV data.

-- price_history_1min: compress chunks older than 7 days
ALTER TABLE price_history_1min SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'timestamp'
);
SELECT add_compression_policy('price_history_1min', INTERVAL '7 days',
    if_not_exists => TRUE);

-- price_history_daily: compress chunks older than 90 days
ALTER TABLE price_history_daily SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'date'
);
SELECT add_compression_policy('price_history_daily', INTERVAL '90 days',
    if_not_exists => TRUE);

-- indicators: compress chunks older than 14 days
ALTER TABLE indicators SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, timeframe, indicator_name',
    timescaledb.compress_orderby = 'ts'
);
SELECT add_compression_policy('indicators', INTERVAL '14 days',
    if_not_exists => TRUE);


COMMIT;

-- ─── Verification ───────────────────────────────────────────────────────────
-- Run these after the script to verify everything is in place.

SELECT hypertable_name, num_dimensions, num_chunks, compression_enabled
FROM timescaledb_information.hypertables
ORDER BY hypertable_name;

SELECT hypertable_name, policy_status
FROM timescaledb_information.jobs j
JOIN timescaledb_information.hypertables h
    ON j.hypertable_name = h.hypertable_name
WHERE j.proc_name = 'policy_compression';
