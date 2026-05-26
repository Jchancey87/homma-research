-- Migration: Add No-News Pump Classifier support
-- Run: psql $DATABASE_URL -f migrate_add_catalyst.sql

-- 1. Add `catalyst` column to daily_gainers
ALTER TABLE daily_gainers
  ADD COLUMN IF NOT EXISTS catalyst TEXT;

COMMENT ON COLUMN daily_gainers.catalyst IS
  'Catalyst classification: Confirmed Catalyst | Technical / No News | Speculative';

-- 2. Create pump_classifications history table
CREATE TABLE IF NOT EXISTS pump_classifications (
    id             SERIAL PRIMARY KEY,
    ticker         TEXT        NOT NULL,
    date           DATE        NOT NULL,
    catalyst_tag   TEXT        NOT NULL,   -- 'Confirmed Catalyst' | 'Technical / No News' | 'Speculative'
    gap_pct        NUMERIC(8,2),
    rvol           NUMERIC(8,2),
    float_shares   BIGINT,
    classified_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    news_source    TEXT,                   -- 'lightweight_check' | 'yfinance_verify' | 'ingest_pipeline'
    UNIQUE (ticker, date)                  -- one classification per ticker per day
);

CREATE INDEX IF NOT EXISTS idx_pump_class_date   ON pump_classifications (date DESC);
CREATE INDEX IF NOT EXISTS idx_pump_class_ticker ON pump_classifications (ticker);
CREATE INDEX IF NOT EXISTS idx_pump_class_tag    ON pump_classifications (catalyst_tag);

COMMENT ON TABLE pump_classifications IS
  'Historical log of No-News Pump classifications for backtesting and pattern analysis.';
