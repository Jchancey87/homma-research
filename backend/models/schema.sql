-- Trading Journal PostgreSQL Schema
-- Applied on startup via init_db() — all statements are idempotent.

CREATE TABLE IF NOT EXISTS daily_gainers (
    id                  SERIAL PRIMARY KEY,
    date                TEXT    NOT NULL,
    ticker              TEXT    NOT NULL,
    gap_pct             DOUBLE PRECISION,
    float_shares        DOUBLE PRECISION,
    rvol_15m            DOUBLE PRECISION,
    sector              TEXT,
    market_cap          DOUBLE PRECISION,
    news_headline       TEXT,
    news_fresh          BOOLEAN,
    close_price         DOUBLE PRECISION,
    open_price          DOUBLE PRECISION,
    -- Enrichment fields added 2026-05
    high_price          DOUBLE PRECISION,           -- HOD from Polygon grouped daily
    low_price           DOUBLE PRECISION,           -- LOD from Polygon grouped daily
    prev_close          DOUBLE PRECISION,           -- previous day close (used for gap calc)
    vwap                DOUBLE PRECISION,           -- VWAP from Polygon grouped daily
    dollar_volume       DOUBLE PRECISION,           -- close × volume (liquidity filter)
    close_location      DOUBLE PRECISION,           -- (close-low)/(high-low) 0.0–1.0
    rs_vs_spy           DOUBLE PRECISION,           -- gap_pct minus SPY day return
    shares_outstanding  DOUBLE PRECISION,           -- total shares outstanding (FMP)
    avg_volume          DOUBLE PRECISION,           -- 30-day avg volume (FMP volAvg)
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(date, ticker)
);

-- Idempotent migrations for existing databases
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS high_price         DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS low_price          DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS prev_close         DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS vwap               DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS dollar_volume      DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS close_location     DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS rs_vs_spy          DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS shares_outstanding DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS avg_volume         DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_gainers_date   ON daily_gainers(date);
CREATE INDEX IF NOT EXISTS idx_gainers_ticker ON daily_gainers(ticker);

CREATE TABLE IF NOT EXISTS chart_captures (
    id                  SERIAL PRIMARY KEY,
    ticker              TEXT    NOT NULL,
    capture_date        TEXT    NOT NULL,
    timeframe           TEXT,
    image_path          TEXT    NOT NULL,
    setup_type          TEXT,
    cleanliness_score   INTEGER CHECK(cleanliness_score BETWEEN 1 AND 10),
    tags                TEXT,               -- JSON array string (legacy, kept for compatibility)
    notes               TEXT,
    -- Gemini vision import fields
    gemini_annotation   TEXT,               -- pasted text from Gemini chat
    gemini_image_path   TEXT,               -- optional annotated image re-uploaded from Gemini
    gemini_imported_at  TIMESTAMPTZ,
    -- Reserved for future local LLM use
    llm_annotation      TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_charts_ticker ON chart_captures(ticker);
CREATE INDEX IF NOT EXISTS idx_charts_date   ON chart_captures(capture_date);

-- Normalized tag junction table (replaces JSON string grouping in archetype_service)
CREATE TABLE IF NOT EXISTS chart_tags (
    chart_id  INTEGER NOT NULL REFERENCES chart_captures(id) ON DELETE CASCADE,
    tag       TEXT    NOT NULL,
    PRIMARY KEY (chart_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_chart_tags_tag      ON chart_tags(tag);
CREATE INDEX IF NOT EXISTS idx_chart_tags_chart_id ON chart_tags(chart_id);

CREATE TABLE IF NOT EXISTS llm_jobs (
    id         TEXT    PRIMARY KEY,          -- UUID
    type       TEXT    NOT NULL,             -- 'continuation' | 'sentiment' | 'research' | etc.
    status     TEXT    DEFAULT 'pending',    -- pending | running | done | error
    input_ref  TEXT,                         -- date string or query snippet
    output     TEXT,
    model_used TEXT,                         -- log which LLM_MODEL produced this
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlist: tickers of interest saved between research sessions
CREATE TABLE IF NOT EXISTS watchlist (
    id             SERIAL PRIMARY KEY,
    ticker         TEXT    NOT NULL UNIQUE,
    sector         TEXT,
    notes          TEXT,
    tags           TEXT    DEFAULT '[]',     -- JSON array of string labels
    alert_threshold DOUBLE PRECISION,        -- optional gap% drop threshold for auto-expiry
    added_at       TIMESTAMPTZ DEFAULT NOW(),
    last_viewed_at TIMESTAMPTZ
);

ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS alert_threshold DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker);

-- Continuation Picks: AI-identified top picks from nightly email, auto-expire when conditions weaken
CREATE TABLE IF NOT EXISTS continuation_picks (
    id              SERIAL PRIMARY KEY,
    ticker          TEXT    NOT NULL,
    date            TEXT    NOT NULL,        -- YYYY-MM-DD date of the nightly report
    reason          TEXT,                    -- one-sentence LLM rationale
    gap_pct         DOUBLE PRECISION,        -- gap% on the date of pick
    float_shares    DOUBLE PRECISION,        -- float on the date of pick
    rvol_15m        DOUBLE PRECISION,        -- rvol on the date of pick
    sector          TEXT,
    rank            INTEGER DEFAULT 1,       -- 1=highest priority
    is_active       BOOLEAN DEFAULT TRUE,    -- flipped to FALSE when conditions weaken
    deactivated_at  TIMESTAMPTZ,
    deactivated_reason TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_cont_picks_active ON continuation_picks(is_active);
CREATE INDEX IF NOT EXISTS idx_cont_picks_date   ON continuation_picks(date);
CREATE INDEX IF NOT EXISTS idx_cont_picks_ticker ON continuation_picks(ticker);

-- Observations: standalone markdown notes per ticker
CREATE TABLE IF NOT EXISTS observations (
    id              SERIAL PRIMARY KEY,
    ticker          TEXT    NOT NULL,
    date            TEXT    NOT NULL,        -- YYYY-MM-DD (trading date being referenced)
    title           TEXT,
    body            TEXT    NOT NULL,        -- markdown
    sentiment       TEXT    DEFAULT 'neutral' CHECK(sentiment IN ('bullish','bearish','neutral')),
    tags            TEXT    DEFAULT '[]',    -- JSON array
    linked_chart_id INTEGER REFERENCES chart_captures(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observations_ticker ON observations(ticker);
CREATE INDEX IF NOT EXISTS idx_observations_date   ON observations(date);

-- PIPE Filing Detection: caches 8-K private placement scan results per ticker/event date
CREATE TABLE IF NOT EXISTS pipe_filings (
    id                SERIAL PRIMARY KEY,
    ticker            TEXT    NOT NULL,
    anchor_date       TEXT    NOT NULL,          -- YYYY-MM-DD gainer event date
    filing_date       TEXT,                      -- actual 8-K filing date
    accession_number  TEXT,
    is_pipe           BOOLEAN  DEFAULT FALSE,
    security_type     TEXT,                      -- common_stock | preferred_stock | convertible_note | warrant
    pricing_type      TEXT,                      -- fixed | variable | unknown
    proceeds_amount   DOUBLE PRECISION,          -- gross proceeds in USD
    use_of_proceeds   TEXT,                      -- keyword summary
    investor_names    TEXT,
    toxic_signals     TEXT     DEFAULT '[]',     -- JSON array of matched toxic keywords
    deal_score        INTEGER  CHECK(deal_score BETWEEN 1 AND 5),
    raw_items         TEXT,                      -- raw 8-K item codes e.g. "1.01,3.02"
    filing_url        TEXT,
    scanned_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, anchor_date)
);

CREATE INDEX IF NOT EXISTS idx_pipe_ticker ON pipe_filings(ticker);
CREATE INDEX IF NOT EXISTS idx_pipe_date   ON pipe_filings(anchor_date);
CREATE INDEX IF NOT EXISTS idx_pipe_is_pipe ON pipe_filings(is_pipe);

-- Research Cache: stores versioned LLM analysis reports per ticker/date/type
-- Multiple rows per (ticker, report_type) are allowed — versions are never deleted,
-- allowing the user to scroll back through previous runs.
CREATE TABLE IF NOT EXISTS research_cache (
    id          SERIAL PRIMARY KEY,
    ticker      TEXT    NOT NULL,
    date        TEXT,                         -- YYYY-MM-DD anchor date (null for non-date analyses)
    report_type TEXT    NOT NULL,             -- risk | catalyst | context | deep_research | pipe
    version     INTEGER NOT NULL DEFAULT 1,  -- auto-incremented per ticker+date+type on insert
    output      TEXT    NOT NULL,             -- full markdown report
    model_used  TEXT,
    job_id      TEXT REFERENCES llm_jobs(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ                   -- NULL = never expires (PIPE reports)
);

CREATE INDEX IF NOT EXISTS idx_rcache_ticker      ON research_cache(ticker);
CREATE INDEX IF NOT EXISTS idx_rcache_report_type ON research_cache(report_type);
CREATE INDEX IF NOT EXISTS idx_rcache_expires     ON research_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_rcache_ticker_type ON research_cache(ticker, report_type, created_at DESC);
