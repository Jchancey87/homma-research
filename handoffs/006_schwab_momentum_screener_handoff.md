# Schwab API Momentum Screener — Coding Agent Handoff

## Overview

This document outlines the full feature set, architecture, database schema, and implementation tasks required to build a **Ross Cameron-style intraday momentum stock screener** using the `schwab-py` library as the primary market data source, replacing Polygon.io. The backend is Python, the database is a locally hosted PostgreSQL instance, and alerts are delivered via Discord/Telegram bot.

---

## Goals

- Eliminate the $40/month Polygon.io cost by using the free Schwab Trader API
- Build a self-hosted, locally cached PostgreSQL database for fundamentals, price history, and derived analytics
- Implement a pre-market morning setup routine that seeds candidates automatically by ~8:45 AM CT
- Stream live Level 1 quotes and 1-min OHLCV candles via WebSocket, applying Ross Cameron criteria in real-time
- Deliver formatted alerts to Discord with full context cards (price, float, rel vol, short interest, gap %)

---

## Dependencies

```txt
schwab-py
asyncio
asyncpg          # async PostgreSQL driver
psycopg2-binary  # sync fallback / migrations
pandas
numpy
requests
yfinance         # supplement: earnings dates, SEC filing dates
python-dotenv
discord.py       # or httpx for webhook calls
apscheduler      # scheduled morning refresh job
```

---

## Environment Variables (`.env`)

```env
SCHWAB_API_KEY=your_api_key
SCHWAB_API_SECRET=your_api_secret
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182
POSTGRES_DSN=postgresql://user:password@localhost:5432/trading
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
TELEGRAM_BOT_TOKEN=optional
TELEGRAM_CHAT_ID=optional
```

---

## PostgreSQL Schema

### `stock_fundamentals` — Refreshed Weekly + On-Demand

```sql
CREATE TABLE IF NOT EXISTS stock_fundamentals (
    symbol                VARCHAR(10)  PRIMARY KEY,
    company_name          TEXT,
    exchange              VARCHAR(10),

    -- Share structure
    shares_outstanding    BIGINT,
    market_cap_float      BIGINT,       -- float shares
    market_cap            BIGINT,

    -- Short interest (key for momentum)
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

    -- Dividends (filter: 0 = pure momentum candidate)
    dividend_yield        FLOAT,
    dividend_pay_date     DATE,

    -- Volatility & volume profile
    beta                  FLOAT,
    vol_1d_avg            BIGINT,
    vol_10d_avg           BIGINT,
    vol_3m_avg            BIGINT,
    high_52wk             FLOAT,
    low_52wk              FLOAT,

    -- Derived float classification (computed by Python layer)
    float_category        VARCHAR(10),  -- 'nano', 'low', 'mid', 'high'

    -- Earnings calendar (from yfinance supplement)
    next_earnings_date    DATE,
    last_earnings_date    DATE,

    updated_at            TIMESTAMPTZ  DEFAULT NOW()
);
```

### `price_history_daily` — 60-Day Rolling Window

```sql
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

-- Index for fast avg volume lookups
CREATE INDEX IF NOT EXISTS idx_phd_symbol_date ON price_history_daily(symbol, date DESC);
```

### `price_history_1min` — Intraday Candles (Current Session + 2 Days)

```sql
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
```

### `options_snapshot` — Morning Pull for High Short-Interest Candidates

```sql
CREATE TABLE IF NOT EXISTS options_snapshot (
    symbol           VARCHAR(10),
    snapshot_time    TIMESTAMPTZ,
    put_call_ratio   FLOAT,
    atm_iv           FLOAT,        -- at-the-money implied volatility
    iv_percentile    FLOAT,        -- derived from historical IV in this table
    total_oi         BIGINT,
    PRIMARY KEY (symbol, snapshot_time)
);
```

### `screener_alerts` — Alert Log (Avoid Duplicate Notifications)

```sql
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
    alert_type      VARCHAR(30),  -- e.g. 'BREAKOUT', 'GAP_UP', 'SQUEEZE'
    sent            BOOLEAN      DEFAULT FALSE
);

-- Prevent re-alerting same symbol within a cooldown window (handled in Python too)
CREATE INDEX IF NOT EXISTS idx_alerts_symbol_time ON screener_alerts(symbol, alert_time DESC);
```

### `watchlist` — Persistent Symbols to Always Monitor

```sql
CREATE TABLE IF NOT EXISTS watchlist (
    symbol       VARCHAR(10)  PRIMARY KEY,
    added_at     TIMESTAMPTZ  DEFAULT NOW(),
    notes        TEXT,
    active       BOOLEAN      DEFAULT TRUE
);
```

---

## Computed / Derived Fields

These are calculated in Python and either stored back to Postgres or held in-memory during the session:

| Field | Formula | Storage |
|-------|---------|---------|
| `relative_volume` | `total_volume / (vol_10d_avg * elapsed_pct_of_day)` | In-memory, updated per tick |
| `gap_pct` | `(today_open - prior_close) / prior_close * 100` | Computed at open, cached in session |
| `atr_14` | 14-day average of `high - low` | Stored in `stock_fundamentals` |
| `dist_from_52wk_high` | `(high_52wk - close) / high_52wk * 100` | Computed on demand |
| `short_squeeze_score` | `short_int_float / short_day_cover` | Computed in morning refresh |
| `float_category` | `<10M=nano, 10-50M=low, 50-100M=mid, >100M=high` | Stored in `stock_fundamentals` |
| `iv_percentile` | `rank(current_atm_iv) over 252-day IV history` | Stored in `options_snapshot` |
| `vwap` | Running sum of `price * volume / cumulative_volume` | In-memory stream accumulator |

---

## Morning Setup Routine (8:45 AM CT)

The morning refresh should run as a scheduled APScheduler job. Tasks run in this sequence:

### Step 1 — Seed Candidate List
```python
# Pull top movers from all major exchanges
movers_nasdaq  = client.get_movers('NASDAQ', sort=PERCENT_CHANGE_UP)
movers_nyse    = client.get_movers('NYSE', sort=PERCENT_CHANGE_UP)
movers_otcbb   = client.get_movers('OTCBB', sort=PERCENT_CHANGE_UP)

# Merge with persistent watchlist symbols from Postgres
watchlist_syms = db.query("SELECT symbol FROM watchlist WHERE active = TRUE")
candidates     = deduplicate(movers + watchlist_syms)
```

### Step 2 — Bulk Fetch Fundamentals
```python
# Batch into groups of 50 (Schwab rate limits)
for batch in chunked(candidates, 50):
    fundamentals = client.get_instruments(batch, projection=FUNDAMENTAL)
    upsert_fundamentals_postgres(fundamentals)
    compute_derived_fields(fundamentals)  # float_category, atr, short_squeeze_score
```

### Step 3 — Pull 60-Day Daily Price History
```python
# Used for: avg volume baseline, gap % calc, 52wk context
for sym in candidates:
    history = client.get_price_history_every_day(sym, period_type=MONTH, period=2)
    upsert_price_history_daily(sym, history)
    cache_avg_volume(sym, history)       # store 10d + 30d avg vol in memory dict
    compute_gap_pct(sym, history)        # today's open vs prior close
```

### Step 4 — Options Snapshot (High Short-Interest Symbols Only)
```python
high_si_syms = db.query("""
    SELECT symbol FROM stock_fundamentals
    WHERE short_int_float > 20
    AND float_category IN ('nano', 'low')
""")
for sym in high_si_syms:
    chain = client.get_option_chain(sym, contract_type=ALL)
    store_options_snapshot(sym, chain)
```

### Step 5 — Supplement with yfinance (Earnings Dates)
```python
# yfinance fills the earnings calendar gap Schwab doesn't provide
for sym in candidates:
    info = yf.Ticker(sym).calendar
    update_earnings_dates(sym, info)
```

### Step 6 — Open WebSocket Stream
```python
# Subscribe to real-time screener (top % gainers, all exchanges, 1-min refresh)
await stream.screener_equity_subs(['EQUITY_ALL_PERCENT_CHANGE_UP_1'])

# Subscribe Level 1 quotes on all candidates
await stream.level_one_equity_subs(candidates, fields=[
    LAST_PRICE, TOTAL_VOLUME, NET_CHANGE_PERCENT,
    HIGH_PRICE, LOW_PRICE, BID_PRICE, ASK_PRICE,
    MARK, IS_SHORTABLE, HARD_TO_BORROW
])

# Subscribe 1-min candles on candidates
await stream.chart_equity_subs(candidates)

# Register handlers
stream.add_level_one_equity_handler(on_quote_update)
stream.add_chart_equity_handler(on_candle_update)
stream.add_screener_equity_handler(on_new_screener_hit)
```

---

## Real-Time Filter Logic

Apply Ross Cameron criteria in `on_quote_update`:

```python
FILTERS = {
    'min_price':      2.0,
    'max_price':      20.0,
    'min_rel_vol':    2.0,
    'max_float':      100_000_000,   # 100M shares
    'min_pct_gain':   10.0,          # minimum % gain from prior close
    'min_volume':     500_000,       # absolute minimum daily volume so far
    'no_dividends':   True,          # skip dividend payers
    'min_gap_pct':    5.0,           # optional: gappers only
}

def on_quote_update(msg):
    for item in msg['content']:
        sym    = item['key']
        price  = item.get('LAST_PRICE', 0)
        volume = item.get('TOTAL_VOLUME', 0)
        pct_chg = item.get('NET_CHANGE_PERCENT', 0)

        fund   = fundamentals_cache[sym]
        avg_vol = avg_volume_cache.get(sym, 1)
        elapsed = get_market_elapsed_pct()   # 0.0 - 1.0 across 6.5hr session
        rel_vol = volume / max(avg_vol * elapsed, 1)

        if (FILTERS['min_price'] <= price <= FILTERS['max_price']
                and rel_vol    >= FILTERS['min_rel_vol']
                and fund['market_cap_float'] <= FILTERS['max_float']
                and pct_chg    >= FILTERS['min_pct_gain']
                and volume     >= FILTERS['min_volume']
                and not (FILTERS['no_dividends'] and fund['dividend_yield'] > 0)):

            if not recently_alerted(sym, cooldown_minutes=15):
                fire_alert(sym, price, volume, rel_vol, pct_chg, fund)
```

---

## Alert Card Format (Discord)

Each alert should post a rich embed with:

```
🚀 $TICKER — MOMENTUM ALERT
──────────────────────────────
Price:        $X.XX  (+XX.X%)
Float:        XX.XM shares  (nano/low/mid)
Rel Volume:   X.Xx  (vs 10d avg)
Gap %:        +XX.X%
Short Float:  XX.X%  (X.X days to cover)
Squeeze Score: X.X
ATR (14d):    $X.XX
52wk Range:   $X.XX – $X.XX
──────────────────────────────
Next Earnings: YYYY-MM-DD
IV Percentile: XX%
```

---

## Dynamic Symbol Management (WebSocket)

The Schwab stream supports live add/remove without reconnecting:

```python
# Add new screener hits to live L1 feed
async def on_new_screener_hit(msg):
    new_symbols = [item['key'] for item in msg['content']]
    await stream.level_one_equity_add(new_symbols, fields=[...])
    await stream.chart_equity_add(new_symbols)

# Prune symbols that have gone cold (low volume, price moved out of range)
async def prune_cold_symbols():
    cold = [s for s in active_symbols if is_cold(s)]
    await stream.level_one_equity_unsubs(cold)
    await stream.chart_equity_unsubs(cold)
```

---

## Additional Features to Implement

### VWAP Tracker (In-Memory)
Accumulate VWAP from the 1-min candle stream. Flag alerts when price breaks above VWAP for the first time (a core Ross Cameron entry signal).

```python
vwap_state = {}  # { symbol: { cum_vol: 0, cum_vol_price: 0 } }

def update_vwap(sym, candle):
    s = vwap_state.setdefault(sym, {'cum_vol': 0, 'cum_vp': 0})
    typical_price = (candle['high'] + candle['low'] + candle['close']) / 3
    s['cum_vp']  += typical_price * candle['volume']
    s['cum_vol'] += candle['volume']
    return s['cum_vp'] / s['cum_vol'] if s['cum_vol'] > 0 else 0
```

### Pre-Market Gap Scanner (8:00 AM CT)
Run a separate lighter refresh at 8:00 AM using pre-market prices from `get_quotes()` to build a gap list before the open. Pre-market volume combined with a >10% gap is the highest-probability Ross Cameron setup.

```python
pre_mkt_quotes = client.get_quotes(watchlist_symbols)
for sym, q in pre_mkt_quotes.items():
    pre_mkt_price = q['quote']['lastPrice']
    prior_close   = q['quote']['closePrice']
    gap_pct       = (pre_mkt_price - prior_close) / prior_close * 100
    pre_mkt_vol   = q['quote']['totalVolume']
    if gap_pct >= 10 and pre_mkt_vol >= 50_000:
        add_to_watchlist(sym, notes=f"Pre-mkt gap {gap_pct:.1f}%")
```

### Halt & Resume Detection
The Schwab L1 stream includes a `TRADING_STATUS` field. Detect halts and resume events and post them to Discord — Ross Cameron frequently trades the resume candle after a circuit-breaker halt.

```python
if item.get('TRADING_STATUS') == 'H':   # Halted
    post_discord(f"⏸️ ${sym} HALTED — watch for resume candle")
elif item.get('TRADING_STATUS') == 'T': # Trading resumed
    post_discord(f"▶️ ${sym} RESUMED — ${price}")
```

### Daily Session Archive
At 4:05 PM CT, archive the day's 1-min candles and alert log:

```python
# Compress old 1-min data beyond 2 sessions to save disk space
db.execute("""
    DELETE FROM price_history_1min
    WHERE timestamp < NOW() - INTERVAL '2 days'
""")

# Archive alert log to a separate table for backtesting
db.execute("""
    INSERT INTO screener_alerts_archive SELECT * FROM screener_alerts
    WHERE DATE(alert_time) = CURRENT_DATE
""")
```

### Backtesting Hook
Since every alert is logged to `screener_alerts`, you can backtest filter changes by replaying alerts against 1-min candle data:

```python
def backtest_filter(date, filters):
    alerts = db.query("""
        SELECT a.*, p.close as close_5min
        FROM screener_alerts_archive a
        JOIN price_history_1min p
          ON a.symbol = p.symbol
         AND p.timestamp = a.alert_time + INTERVAL '5 minutes'
        WHERE DATE(a.alert_time) = %s
    """, [date])
    # compute win rate, avg gain, max drawdown
```

---

## Data Gaps & Supplemental Sources

| Gap | Schwab Provides | Supplement With | Cost |
|-----|----------------|-----------------|------|
| Float (direct) | Shares outstanding only | `yfinance` | Free |
| Earnings dates | ❌ | `yfinance` | Free |
| SEC filings | ❌ | `sec-edgar-downloader` | Free |
| Historical short interest | ❌ | FINRA FTP (bi-monthly) | Free |
| Institutional ownership % | ❌ | Finviz scrape (weekly) | Free |
| News / catalyst feed | ❌ | Benzinga free tier or RSS | Free |
| Level 2 order book | ✅ via `level_two_book_subs` | — | — |
| Pre-market quotes | ✅ via `get_quotes()` | — | — |
| Options chain | ✅ via `get_option_chain()` | — | — |

---

## File / Module Structure

```
momentum_screener/
├── main.py                    # Entry point, APScheduler setup, starts stream
├── config.py                  # Loads .env, constants, filter thresholds
├── db/
│   ├── __init__.py
│   ├── connection.py          # asyncpg pool setup
│   ├── schema.sql             # Full CREATE TABLE statements
│   └── upsert.py              # Upsert helpers for all tables
├── schwab/
│   ├── __init__.py
│   ├── auth.py                # Token management, OAuth flow
│   ├── http_client.py         # Fundamentals, history, movers, options
│   └── stream_client.py       # WebSocket subscriptions + handlers
├── screener/
│   ├── __init__.py
│   ├── filters.py             # Ross Cameron filter logic
│   ├── vwap.py                # In-memory VWAP accumulator
│   └── derived.py             # Rel vol, gap %, squeeze score, ATR
├── alerts/
│   ├── __init__.py
│   ├── discord.py             # Webhook embed formatter + sender
│   └── dedup.py               # Cooldown / deduplication logic
├── morning/
│   ├── __init__.py
│   ├── refresh.py             # Full morning refresh orchestration
│   ├── premarkt_gap.py        # 8:00 AM pre-market gap scanner
│   └── supplement.py          # yfinance, FINRA, Finviz supplemental pulls
└── backtest/
    ├── __init__.py
    └── replay.py              # Alert replay against 1-min candle archive
```

---

## Morning Routine Timeline

| Time (CT) | Task |
|-----------|------|
| 8:00 AM | Pre-market gap scanner runs — identifies gap >10% + pre-mkt vol candidates |
| 8:45 AM | Full morning refresh: movers seeded, fundamentals upserted, avg vol cached |
| 8:50 AM | Options snapshots pulled for high short-interest symbols |
| 8:55 AM | yfinance earnings calendar supplement runs |
| 9:00 AM | WebSocket stream opens, all candidates subscribed |
| 9:30 AM | Market open — real-time filters active, alerts live |
| 9:30–10:30 AM | Primary momentum window (highest alert sensitivity) |
| 10:30 AM | Optional: tighten rel vol threshold to 3.0x for second-hour quality filter |
| 4:05 PM | Session archive + 1-min candle cleanup |
| 4:15 PM | Optional: end-of-day report posted to Discord (top alerts, win rate) |

---

## Notes for Coding Agent

- All Schwab API calls should use `try/except` with exponential backoff — the OAuth token expires every 30 minutes and must be refreshed automatically via `schwab-py`'s built-in token handler
- Batch symbol requests to `get_instruments()` in groups of ≤50 to avoid rate limits
- The WebSocket stream is async — use `asyncio.gather()` to run the stream alongside the APScheduler event loop
- Postgres upserts should use `INSERT ... ON CONFLICT (symbol) DO UPDATE SET ...` for idempotency
- Store all timestamps in UTC, convert to CT only at the display/alert layer
- The `screener_equity_subs` stream gives the **top 10** per category — use it as a seed, not an exhaustive list; the L1 quote stream on your full candidate pool does the real filtering
