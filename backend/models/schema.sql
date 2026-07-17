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
    premarket_high      DOUBLE PRECISION,
    premarket_low       DOUBLE PRECISION,
    premarket_volume    DOUBLE PRECISION,
    pct_above_vwap      DOUBLE PRECISION,
    atr_14              DOUBLE PRECISION,
    sma_20              DOUBLE PRECISION,
    sma_50              DOUBLE PRECISION,
    cash                DOUBLE PRECISION,
    net_income          DOUBLE PRECISION,
    operating_cash_flow  DOUBLE PRECISION,
    runway_months       DOUBLE PRECISION,
    dilution_risk       TEXT,
    extended_change_pct DOUBLE PRECISION,
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
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_high      DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_low       DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS premarket_volume    DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS pct_above_vwap      DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS atr_14              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS sma_20              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS sma_50              DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS cash                DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS net_income          DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS operating_cash_flow  DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS runway_months       DOUBLE PRECISION;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS dilution_risk       TEXT;
ALTER TABLE daily_gainers ADD COLUMN IF NOT EXISTS extended_change_pct DOUBLE PRECISION;

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

CREATE TABLE IF NOT EXISTS watchlist_groups (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlist: tickers of interest saved between research sessions
CREATE TABLE IF NOT EXISTS watchlist (
    id             SERIAL PRIMARY KEY,
    ticker         TEXT    NOT NULL,
    sector         TEXT,
    notes          TEXT,
    tags           TEXT    DEFAULT '[]',     -- JSON array of string labels
    alert_threshold DOUBLE PRECISION,        -- optional gap% drop threshold for auto-expiry
    added_at       TIMESTAMPTZ DEFAULT NOW(),
    last_viewed_at TIMESTAMPTZ,
    group_id       INTEGER REFERENCES watchlist_groups(id) ON DELETE CASCADE,
    runway_months  DOUBLE PRECISION,
    dilution_risk  TEXT,
    upcoming_catalyst TEXT,
    catalyst_date  DATE
);

ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS alert_threshold DOUBLE PRECISION;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS group_id INTEGER REFERENCES watchlist_groups(id) ON DELETE CASCADE;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS runway_months DOUBLE PRECISION;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS dilution_risk TEXT;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS upcoming_catalyst TEXT;
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS catalyst_date DATE;

-- Drop constraint if exists on older setups
ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS watchlist_ticker_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_group_ticker ON watchlist(group_id, ticker) WHERE group_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_watchlist_null_group_ticker ON watchlist(ticker) WHERE group_id IS NULL;

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
    -- Performance tracking
    close_d0        DOUBLE PRECISION,
    d1_open         DOUBLE PRECISION,
    d1_high         DOUBLE PRECISION,
    d1_low          DOUBLE PRECISION,
    d1_close        DOUBLE PRECISION,
    d1_volume       DOUBLE PRECISION,
    d2_open         DOUBLE PRECISION,
    d2_high         DOUBLE PRECISION,
    d2_low          DOUBLE PRECISION,
    d2_close        DOUBLE PRECISION,
    d2_volume       DOUBLE PRECISION,
    d3_open         DOUBLE PRECISION,
    d3_high         DOUBLE PRECISION,
    d3_low          DOUBLE PRECISION,
    d3_close        DOUBLE PRECISION,
    d3_volume       DOUBLE PRECISION,
    -- Fundamental metrics
    market_cap      DOUBLE PRECISION,
    shares_outstanding DOUBLE PRECISION,
    cash            DOUBLE PRECISION,
    net_income      DOUBLE PRECISION,
    operating_cash_flow DOUBLE PRECISION,
    runway_months   DOUBLE PRECISION,
    dilution_risk   TEXT,
    news_headline   TEXT,
    news_fresh      BOOLEAN,
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

-- Volatility Halts: tracks Limit Up/Limit Down trading halts
CREATE TABLE IF NOT EXISTS volatility_halts (
    id            SERIAL PRIMARY KEY,
    ticker        TEXT NOT NULL,
    halt_time     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resume_time   TIMESTAMPTZ,
    status        TEXT DEFAULT 'halted', -- 'halted' or 'resumed'
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_volatility_halts_ticker ON volatility_halts(ticker);
CREATE INDEX IF NOT EXISTS idx_volatility_halts_time   ON volatility_halts(halt_time DESC);

-- Migrations for continuation_picks (added 2026-06)
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS close_d0 DOUBLE PRECISION;

ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d1_open DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d1_high DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d1_low DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d1_close DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d1_volume DOUBLE PRECISION;

ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d2_open DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d2_high DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d2_low DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d2_close DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d2_volume DOUBLE PRECISION;

ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d3_open DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d3_high DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d3_low DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d3_close DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS d3_volume DOUBLE PRECISION;

ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS market_cap DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS shares_outstanding DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS cash DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS net_income DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS operating_cash_flow DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS runway_months DOUBLE PRECISION;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS dilution_risk TEXT;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS news_headline TEXT;
ALTER TABLE continuation_picks ADD COLUMN IF NOT EXISTS news_fresh BOOLEAN;

-- ── RSS CURATION TABLES (Added 2026-06) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS rss_sources (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    feed_url      TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL CHECK(category IN ('biotech', 'tech', 'general')),
    is_active     BOOLEAN DEFAULT TRUE,
    last_polled_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rss_sources_active ON rss_sources(is_active);

CREATE TABLE IF NOT EXISTS rss_feed_pool (
    id                SERIAL PRIMARY KEY,
    source_id         INTEGER REFERENCES rss_sources(id) ON DELETE CASCADE,
    guid              TEXT UNIQUE NOT NULL,
    title             TEXT NOT NULL,
    description       TEXT,
    link              TEXT NOT NULL,
    published_at      TIMESTAMPTZ NOT NULL,
    detected_tickers  TEXT[] DEFAULT '{}',
    sector            TEXT,
    status            TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feed_pool_status ON rss_feed_pool(status);
CREATE INDEX IF NOT EXISTS idx_feed_pool_tickers ON rss_feed_pool USING GIN(detected_tickers);

CREATE TABLE IF NOT EXISTS curated_rss_items (
    id                SERIAL PRIMARY KEY,
    pool_item_id      INTEGER REFERENCES rss_feed_pool(id) ON DELETE SET NULL,
    guid              TEXT NOT NULL UNIQUE,
    title             TEXT NOT NULL,
    description       TEXT NOT NULL,
    link              TEXT NOT NULL,
    published_at      TIMESTAMPTZ NOT NULL,
    curated_at        TIMESTAMPTZ DEFAULT NOW(),
    curated_by        TEXT,
    associated_tickers TEXT[] DEFAULT '{}',
    curated_notes     TEXT,
    telegram_sent     BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_curated_rss_pub ON curated_rss_items(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_curated_rss_tickers ON curated_rss_items USING GIN(associated_tickers);
CREATE INDEX IF NOT EXISTS idx_curated_rss_tele ON curated_rss_items(telegram_sent);


