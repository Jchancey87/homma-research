-- Schwab API Momentum Screener Tables
-- Applied on startup via init_db()

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

CREATE TABLE IF NOT EXISTS options_snapshot (
    symbol           VARCHAR(10),
    snapshot_time    TIMESTAMPTZ,
    put_call_ratio   FLOAT,
    atm_iv           FLOAT,
    iv_percentile    FLOAT,
    total_oi         BIGINT,
    PRIMARY KEY (symbol, snapshot_time)
);

CREATE TABLE IF NOT EXISTS screener_alerts (
    id              SERIAL       PRIMARY KEY,
    symbol          VARCHAR(10),
    alert_time      TIMESTAMPTZ  DEFAULT NOW(),
    trigger_price   FLOAT,
    trigger_volume  BIGINT,
    rel_vol         FLOAT,
    gap_pct         FLOAT,
    short_int_float FLOAT,
    float_shares    BIGINT,
    alert_type      VARCHAR(30),
    sent            BOOLEAN      DEFAULT FALSE
);

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
    archived_at     TIMESTAMPTZ  DEFAULT NOW()
);
