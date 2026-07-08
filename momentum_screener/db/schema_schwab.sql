-- Schwab API Momentum Screener Tables
-- Applied on startup via init_db()

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS stock_fundamentals (
    symbol                VARCHAR(10)  PRIMARY KEY,
    company_name          TEXT,
    exchange              VARCHAR(10),

    -- Share structure
    shares_outstanding    BIGINT,
    market_cap_float      BIGINT,       -- float shares
    market_cap            BIGINT,

    -- Short interest
    short_int_float       FLOAT,        -- % of float short
    short_day_cover       FLOAT,        -- days to cover

    -- Valuation
    pe_ratio              FLOAT,
    peg_ratio             FLOAT,
    pb_ratio              FLOAT,
    eps_ttm               FLOAT,
    eps_change_pct_ttm    FLOAT,
    rev_change_yoy        FLOAT,

    -- Balance sheet
    book_value_ps         FLOAT,
    current_ratio         FLOAT,
    total_debt_equity     FLOAT,

    -- Dividends
    dividend_yield        FLOAT,
    dividend_pay_date     DATE,

    -- Volatility & volume profile
    beta                  FLOAT,
    vol_1d_avg            BIGINT,
    vol_10d_avg           BIGINT,
    vol_3m_avg            BIGINT,
    high_52wk             FLOAT,
    low_52wk              FLOAT,

    -- Derived classification
    float_category        VARCHAR(20),  -- 'Micro-Float', 'Low-Float', etc.

    -- Earnings calendar (yfinance supplement)
    next_earnings_date    DATE,
    last_earnings_date    DATE,

    updated_at            TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS price_history_daily (
    symbol   VARCHAR(10),
    date     DATE,
    open     FLOAT,
    high     FLOAT,
    low      FLOAT,
    close    FLOAT,
    volume   BIGINT,
    PRIMARY KEY (symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_phd_symbol_date ON price_history_daily(symbol, date DESC);

CREATE TABLE IF NOT EXISTS price_history_1min (
    symbol      VARCHAR(10),
    timestamp   TIMESTAMPTZ,
    open        FLOAT,
    high        FLOAT,
    low         FLOAT,
    close       FLOAT,
    volume      BIGINT,
    PRIMARY KEY (symbol, timestamp)
);

SELECT create_hypertable('price_history_1min', 'timestamp', if_not_exists => TRUE);

ALTER TABLE price_history_1min SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('price_history_1min', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('price_history_1min', INTERVAL '90 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS options_snapshot (
    symbol           VARCHAR(10),
    snapshot_time    TIMESTAMPTZ,
    put_call_ratio   FLOAT,
    atm_iv           FLOAT,
    iv_percentile    FLOAT,
    total_oi         BIGINT,
    PRIMARY KEY (symbol, snapshot_time)
);

SELECT create_hypertable('options_snapshot', 'snapshot_time', if_not_exists => TRUE);

ALTER TABLE options_snapshot SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('options_snapshot', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('options_snapshot', INTERVAL '30 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS screener_alerts (
    id              SERIAL,
    symbol          VARCHAR(10),
    alert_time      TIMESTAMPTZ  DEFAULT NOW(),
    trigger_price   FLOAT,
    trigger_volume  BIGINT,
    rel_vol         FLOAT,
    gap_pct         FLOAT,
    short_int_float FLOAT,
    float_shares    BIGINT,
    alert_type      VARCHAR(30),
    sent            BOOLEAN      DEFAULT FALSE,
    feedback_score  VARCHAR(10)  DEFAULT NULL,
    feedback_notes  TEXT         DEFAULT NULL,
    priority_score  INTEGER      DEFAULT 0,
    priority_tier   VARCHAR(20)  DEFAULT 'Tier 3',
    PRIMARY KEY (id, alert_time)
);

SELECT create_hypertable('screener_alerts', 'alert_time', if_not_exists => TRUE);

ALTER TABLE screener_alerts SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('screener_alerts', INTERVAL '7 days', if_not_exists => TRUE);
SELECT add_retention_policy('screener_alerts', INTERVAL '365 days', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_alerts_symbol_time ON screener_alerts(symbol, alert_time DESC);

CREATE TABLE IF NOT EXISTS screener_alerts_archive (
    id              SERIAL       PRIMARY KEY,
    symbol          VARCHAR(10),
    alert_time      TIMESTAMPTZ,
    trigger_price   FLOAT,
    trigger_volume  BIGINT,
    rel_vol         FLOAT,
    gap_pct         FLOAT,
    short_int_float FLOAT,
    float_shares    BIGINT,
    alert_type      VARCHAR(30),
    archived_at     TIMESTAMPTZ  DEFAULT NOW(),
    feedback_score  VARCHAR(10)  DEFAULT NULL,
    feedback_notes  TEXT         DEFAULT NULL,
    priority_score  INTEGER      DEFAULT 0,
    priority_tier   VARCHAR(20)  DEFAULT 'Tier 3'
);

-- Continuous Aggregates for price_history_1min
CREATE MATERIALIZED VIEW IF NOT EXISTS price_history_5min
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('5 minutes', timestamp) AS bucket,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume
FROM price_history_1min
GROUP BY symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('price_history_5min',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

CREATE MATERIALIZED VIEW IF NOT EXISTS price_history_15min
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('15 minutes', timestamp) AS bucket,
    first(open, timestamp) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, timestamp) AS close,
    sum(volume) AS volume
FROM price_history_1min
GROUP BY symbol, bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('price_history_15min',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

-- Idempotent migrations for existing databases to add confluence priority columns
ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0;
ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(20) DEFAULT 'Tier 3';
ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0;
ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(20) DEFAULT 'Tier 3';
