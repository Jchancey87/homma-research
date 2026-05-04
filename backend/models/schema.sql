-- Trading Journal SQLite Schema
-- Apply with: python database.py (called on app startup via init_db())

CREATE TABLE IF NOT EXISTS daily_gainers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    ticker        TEXT    NOT NULL,
    gap_pct       REAL,
    float_shares  REAL,
    rvol_15m      REAL,
    sector        TEXT,
    market_cap    REAL,
    news_headline TEXT,
    news_fresh    BOOLEAN,
    close_price   REAL,
    open_price    REAL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, ticker)
);

CREATE INDEX IF NOT EXISTS idx_gainers_date   ON daily_gainers(date);
CREATE INDEX IF NOT EXISTS idx_gainers_ticker ON daily_gainers(ticker);

CREATE TABLE IF NOT EXISTS chart_captures (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
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
    gemini_imported_at  TIMESTAMP,
    -- Reserved for future local LLM use
    llm_annotation      TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Watchlist: tickers of interest saved between research sessions
CREATE TABLE IF NOT EXISTS watchlist (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker         TEXT    NOT NULL UNIQUE,
    sector         TEXT,
    notes          TEXT,
    tags           TEXT    DEFAULT '[]',     -- JSON array of string labels
    added_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_viewed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watchlist_ticker ON watchlist(ticker);

-- Observations: standalone markdown notes per ticker
CREATE TABLE IF NOT EXISTS observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT    NOT NULL,
    date            TEXT    NOT NULL,        -- YYYY-MM-DD (trading date being referenced)
    title           TEXT,
    body            TEXT    NOT NULL,        -- markdown
    sentiment       TEXT    DEFAULT 'neutral' CHECK(sentiment IN ('bullish','bearish','neutral')),
    tags            TEXT    DEFAULT '[]',    -- JSON array
    linked_chart_id INTEGER REFERENCES chart_captures(id) ON DELETE SET NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_observations_ticker ON observations(ticker);
CREATE INDEX IF NOT EXISTS idx_observations_date   ON observations(date);
