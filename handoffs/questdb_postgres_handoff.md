# QuestDB + PostgreSQL Dual-Database Architecture
## AI Agent Implementation Handoff — Algorithmic Trading System

**Project Owner:** Jack Chancey  
**Stack Context:** Proxmox homelab, Python, n8n, TradeStation/TradingView data feeds  
**Architecture Decision:** QuestDB for all time-series data (OHLCV, ticks, indicators, signals) · PostgreSQL for everything else (users, strategies, config, metadata, backtest results)

---

## 1. Architecture Overview

The system uses two purpose-built databases in a **polyglot persistence** pattern. No single DB does everything; each does what it's best at.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Trading System Services                      │
│                                                                  │
│   Data Ingestor   Strategy Engine   Backtest Runner   Dashboard  │
│       │                │                  │               │      │
│       ▼                ▼                  ▼               ▼      │
│  ┌─────────┐     ┌──────────┐     ┌──────────────────────────┐  │
│  │ QuestDB │     │QuestDB + │     │      PostgreSQL           │  │
│  │  :9000  │     │Postgres  │     │        :5432             │  │
│  │  :8812  │     │  (join)  │     │                          │  │
│  │  :9009  │     └──────────┘     └──────────────────────────┘  │
│  └─────────┘                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### Data Routing Rules

| Data Type | Database | Reason |
|-----------|----------|--------|
| OHLCV bars (1m, 5m, daily) | QuestDB | High-volume, time-partitioned, SIMD queries |
| Tick/trade data | QuestDB | Ultra-high write throughput via ILP |
| Technical indicators | QuestDB | Time-indexed, bulk append, columnar reads |
| Signal events / alerts | QuestDB | Timestamped events with fast range queries |
| Strategy definitions | PostgreSQL | Relational, versioned, low-write CRUD |
| Backtest run results | PostgreSQL | JSONB config, relational metrics, FK integrity |
| User/account settings | PostgreSQL | Transactional, referential integrity required |
| Watchlists / symbols master | PostgreSQL | Metadata, joins with strategies |
| n8n workflow state | PostgreSQL | Third-party integration, existing PG connector |
| Discord webhook configs | PostgreSQL | Config store, rarely updated |

---

## 2. QuestDB Setup

### 2.1 Docker Deployment (Recommended for Homelab)

```yaml
# docker-compose.questdb.yml
version: "3.9"
services:
  questdb:
    image: questdb/questdb:latest
    container_name: questdb
    restart: unless-stopped
    ports:
      - "9000:9000"   # HTTP REST API + Web Console
      - "9009:9009"   # InfluxDB Line Protocol (ILP) TCP
      - "8812:8812"   # PostgreSQL wire protocol (queries only)
    volumes:
      - questdb_data:/var/lib/questdb
    environment:
      - QDB_CAIRO_COMMIT_LAG=1000         # ms — tune for ingestion latency
      - QDB_CAIRO_MAX_UNCOMMITTED_ROWS=500000
      - QDB_LINE_TCP_MAINTENANCE_JOB_INTERVAL=100
      - QDB_HTTP_WORKER_COUNT=2
      - QDB_PG_WORKER_COUNT=2
    mem_limit: 4g

volumes:
  questdb_data:
```

**Key Ports:**
- `9000` → Web Console UI + REST HTTP API (queries via `/exec?query=...`)
- `9009` → ILP TCP ingestion (highest throughput — use for live data feeds)
- `8812` → PostgreSQL wire protocol **for reads only** — connect with `psycopg2` or `asyncpg`

### 2.2 QuestDB Core Concepts

- **Designated Timestamp**: Every QuestDB table MUST have one timestamp column declared as the `DESIGNATED TIMESTAMP`. This is the partition key — not optional for performance.
- **Partitioning**: Declare `PARTITION BY DAY` (intraday) or `PARTITION BY MONTH` (historical). QuestDB physically separates data into partition folders.
- **WAL Tables**: Default as of v7+. Write-Ahead Log ensures durability. Use `WAL` mode (default) for all production tables.
- **Symbol Type**: Use `SYMBOL` (not `STRING`) for low-cardinality repeating strings like ticker symbols. It's dictionary-encoded and indexed.
- **ILP vs PostgreSQL Wire**: ILP (port 9009/HTTP) is for **ingestion**. The PostgreSQL wire (port 8812) is for **queries**. Never mix them.

### 2.3 Schema: OHLCV Bars

```sql
-- Run in QuestDB Web Console (http://localhost:9000)
CREATE TABLE IF NOT EXISTS ohlcv_bars (
    ts          TIMESTAMP,
    symbol      SYMBOL CAPACITY 512 CACHE,
    timeframe   SYMBOL CAPACITY 16 CACHE,   -- '1m', '5m', '1h', '1D'
    open        DOUBLE,
    high        DOUBLE,
    low         DOUBLE,
    close       DOUBLE,
    volume      LONG,
    vwap        DOUBLE,
    num_trades  INT
) TIMESTAMP(ts) PARTITION BY DAY WAL;

-- Index for fast symbol + range lookups
CREATE INDEX ON ohlcv_bars(symbol);
```

### 2.4 Schema: Tick Data

```sql
CREATE TABLE IF NOT EXISTS ticks (
    ts          TIMESTAMP,
    symbol      SYMBOL CAPACITY 512 CACHE,
    price       DOUBLE,
    size        INT,
    side        SYMBOL CAPACITY 4 CACHE,   -- 'B', 'S', 'U'
    exchange    SYMBOL CAPACITY 32 CACHE
) TIMESTAMP(ts) PARTITION BY DAY WAL;
```

### 2.5 Schema: Indicator Values

```sql
CREATE TABLE IF NOT EXISTS indicators (
    ts              TIMESTAMP,
    symbol          SYMBOL CAPACITY 512 CACHE,
    timeframe       SYMBOL CAPACITY 16 CACHE,
    indicator_name  SYMBOL CAPACITY 256 CACHE,  -- 'EMA_20', 'RSI_14', 'ATR_14'
    value           DOUBLE,
    value2          DOUBLE,   -- for indicators with multiple outputs (MACD signal)
    value3          DOUBLE
) TIMESTAMP(ts) PARTITION BY DAY WAL;
```

### 2.6 Schema: Trade Signals / Alerts

```sql
CREATE TABLE IF NOT EXISTS signals (
    ts              TIMESTAMP,
    symbol          SYMBOL CAPACITY 512 CACHE,
    strategy_id     LONG,       -- FK to PostgreSQL strategies.id (soft reference)
    signal_type     SYMBOL CAPACITY 32 CACHE,  -- 'ENTRY_LONG', 'ENTRY_SHORT', 'EXIT', 'ALERT'
    timeframe       SYMBOL CAPACITY 16 CACHE,
    price           DOUBLE,
    stop_loss       DOUBLE,
    take_profit     DOUBLE,
    confidence      FLOAT,
    metadata        VARCHAR     -- JSON string for extra fields
) TIMESTAMP(ts) PARTITION BY DAY WAL;
```

> **Note on `strategy_id`**: This is a soft foreign key — QuestDB does not enforce FK constraints. Join logic must be handled at the application layer by querying PostgreSQL for strategy metadata separately.

---

## 3. PostgreSQL Setup

### 3.1 Docker Deployment

```yaml
# docker-compose.postgres.yml  (or add to existing stack)
version: "3.9"
services:
  postgres:
    image: postgres:16-alpine
    container_name: trading_postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: trading_db
    mem_limit: 2g

volumes:
  postgres_data:
```

### 3.2 Schema: Strategies

```sql
-- init.sql or Alembic migration
CREATE TABLE strategies (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(128) NOT NULL UNIQUE,
    description     TEXT,
    version         VARCHAR(32) DEFAULT '1.0.0',
    author          VARCHAR(64) DEFAULT 'jack',
    asset_class     VARCHAR(32),   -- 'equity', 'futures', 'crypto'
    timeframes      TEXT[],        -- ARRAY: ARRAY['1m','5m']
    parameters      JSONB NOT NULL DEFAULT '{}',
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_strategies_active ON strategies(is_active);
```

### 3.3 Schema: Backtest Results

```sql
CREATE TABLE backtest_runs (
    id              SERIAL PRIMARY KEY,
    strategy_id     INT REFERENCES strategies(id) ON DELETE CASCADE,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    symbol          VARCHAR(32) NOT NULL,
    timeframe       VARCHAR(16) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    parameters      JSONB NOT NULL DEFAULT '{}',   -- snapshot of params used
    -- Core metrics
    total_trades    INT,
    win_rate        NUMERIC(5,4),
    profit_factor   NUMERIC(8,4),
    net_pnl         NUMERIC(14,4),
    max_drawdown    NUMERIC(8,4),
    sharpe_ratio    NUMERIC(8,4),
    sortino_ratio   NUMERIC(8,4),
    avg_win         NUMERIC(14,4),
    avg_loss        NUMERIC(14,4),
    -- Full trade log
    trades          JSONB,
    equity_curve    JSONB,   -- [{ts, equity}, ...] — or store in QuestDB for large sets
    notes           TEXT
);

CREATE INDEX idx_backtest_strategy ON backtest_runs(strategy_id);
CREATE INDEX idx_backtest_symbol ON backtest_runs(symbol);
```

### 3.4 Schema: Watchlists & Symbols

```sql
CREATE TABLE symbols (
    id          SERIAL PRIMARY KEY,
    ticker      VARCHAR(32) NOT NULL UNIQUE,
    name        VARCHAR(256),
    exchange    VARCHAR(32),
    asset_type  VARCHAR(32),   -- 'stock', 'etf', 'future', 'crypto'
    sector      VARCHAR(64),
    is_active   BOOLEAN DEFAULT TRUE,
    metadata    JSONB DEFAULT '{}'
);

CREATE TABLE watchlists (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(128) NOT NULL,
    description TEXT,
    symbol_ids  INT[],         -- ARRAY of symbol IDs
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.5 Schema: Alert / Notification Config

```sql
CREATE TABLE alert_configs (
    id              SERIAL PRIMARY KEY,
    strategy_id     INT REFERENCES strategies(id),
    channel         VARCHAR(32) NOT NULL,   -- 'discord', 'email', 'sms'
    webhook_url     TEXT,
    template        TEXT,
    is_enabled      BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Python Client Implementation

### 4.1 Install Dependencies

```bash
pip install questdb                  # Official QuestDB ILP client
pip install psycopg2-binary          # QuestDB queries via PG wire
pip install asyncpg                  # Async PostgreSQL driver
pip install sqlalchemy[asyncio]      # ORM + async engine
pip install alembic                  # PostgreSQL migrations
pip install pandas                   # DataFrame support
```

### 4.2 QuestDB Ingestion Client (ILP)

```python
# db/questdb_writer.py
from questdb.ingress import Sender, IngressError, TimestampNanos
from datetime import datetime, timezone
import pandas as pd
from typing import Optional

QUESTDB_ILP_HOST = "localhost"
QUESTDB_ILP_PORT = 9009

class QuestDBWriter:
    """
    High-throughput ingestion to QuestDB via ILP.
    Use this for all WRITES. Never use the PG wire for writes.
    """
    def __init__(self, host: str = QUESTDB_ILP_HOST, port: int = QUESTDB_ILP_PORT):
        self.conf = f"tcp::addr={host}:{port};"

    def write_ohlcv(self, symbol: str, timeframe: str, bars: list[dict]) -> None:
        """
        bars: list of dicts with keys: ts, open, high, low, close, volume
        ts must be a timezone-aware datetime or a nanosecond int.
        """
        with Sender.from_conf(self.conf) as sender:
            for bar in bars:
                sender.row(
                    "ohlcv_bars",
                    symbols={"symbol": symbol, "timeframe": timeframe},
                    columns={
                        "open": float(bar["open"]),
                        "high": float(bar["high"]),
                        "low": float(bar["low"]),
                        "close": float(bar["close"]),
                        "volume": int(bar["volume"]),
                    },
                    at=bar["ts"]  # datetime with tzinfo=UTC or ns int
                )
            sender.flush()

    def write_signal(
        self,
        symbol: str,
        strategy_id: int,
        signal_type: str,
        timeframe: str,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        confidence: Optional[float] = None,
        ts: Optional[datetime] = None
    ) -> None:
        if ts is None:
            ts = datetime.now(tz=timezone.utc)
        with Sender.from_conf(self.conf) as sender:
            sender.row(
                "signals",
                symbols={
                    "symbol": symbol,
                    "signal_type": signal_type,
                    "timeframe": timeframe,
                },
                columns={
                    "strategy_id": strategy_id,
                    "price": price,
                    "stop_loss": stop_loss or 0.0,
                    "take_profit": take_profit or 0.0,
                    "confidence": confidence or 0.0,
                },
                at=ts
            )
            sender.flush()

    def write_dataframe(self, table: str, df: pd.DataFrame, ts_col: str = "ts") -> None:
        """
        Bulk-write a pandas DataFrame to a QuestDB table.
        DataFrame must have a column named ts_col with UTC-aware timestamps.
        Column names must match the QuestDB schema exactly.
        """
        with Sender.from_conf(self.conf) as sender:
            sender.dataframe(df, table_name=table, at=ts_col)
            sender.flush()
```

### 4.3 QuestDB Query Client (PostgreSQL Wire)

```python
# db/questdb_reader.py
import psycopg2
import pandas as pd
from contextlib import contextmanager

QUESTDB_PG_HOST = "localhost"
QUESTDB_PG_PORT = 8812
QUESTDB_PG_USER = "admin"
QUESTDB_PG_PASS = ""       # empty string by default
QUESTDB_PG_DB   = "qdb"

@contextmanager
def questdb_conn():
    conn = psycopg2.connect(
        host=QUESTDB_PG_HOST,
        port=QUESTDB_PG_PORT,
        user=QUESTDB_PG_USER,
        password=QUESTDB_PG_PASS,
        database=QUESTDB_PG_DB,
    )
    try:
        yield conn
    finally:
        conn.close()

def get_ohlcv(
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    limit: int = 10000
) -> pd.DataFrame:
    """
    Fetch OHLCV bars for a symbol/timeframe between start and end (ISO 8601 strings).
    Uses QuestDB's designated timestamp range filtering — extremely fast.
    """
    query = """
        SELECT ts, open, high, low, close, volume
        FROM ohlcv_bars
        WHERE symbol = %(symbol)s
          AND timeframe = %(timeframe)s
          AND ts BETWEEN %(start)s AND %(end)s
        ORDER BY ts ASC
        LIMIT %(limit)s
    """
    with questdb_conn() as conn:
        return pd.read_sql_query(
            query,
            conn,
            params={"symbol": symbol, "timeframe": timeframe, "start": start, "end": end, "limit": limit},
            parse_dates=["ts"],
            index_col="ts"
        )

def get_latest_signals(symbol: str, limit: int = 50) -> pd.DataFrame:
    query = """
        SELECT ts, signal_type, timeframe, price, stop_loss, take_profit, confidence, strategy_id
        FROM signals
        WHERE symbol = %(symbol)s
        ORDER BY ts DESC
        LIMIT %(limit)s
    """
    with questdb_conn() as conn:
        return pd.read_sql_query(query, conn, params={"symbol": symbol, "limit": limit})

def run_sample_agg(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    QuestDB SAMPLE BY — resamples to a higher timeframe natively.
    Example: aggregate 1m bars to 1h.
    """
    query = """
        SELECT
            ts,
            first(open)  AS open,
            max(high)    AS high,
            min(low)     AS low,
            last(close)  AS close,
            sum(volume)  AS volume
        FROM ohlcv_bars
        WHERE symbol = %(symbol)s
          AND timeframe = %(timeframe)s
        SAMPLE BY 1h ALIGN TO CALENDAR
    """
    with questdb_conn() as conn:
        return pd.read_sql_query(query, conn, params={"symbol": symbol, "timeframe": timeframe})
```

### 4.4 PostgreSQL Async Client (SQLAlchemy)

```python
# db/postgres.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Numeric, Text, ARRAY
from sqlalchemy.sql import func
import os

PG_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql+asyncpg://trading:password@localhost:5432/trading_db"
)

engine = create_async_engine(PG_URL, echo=False, pool_size=10, max_overflow=20)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# --- ORM Models ---

class Strategy(Base):
    __tablename__ = "strategies"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(128), nullable=False, unique=True)
    description = Column(Text)
    version     = Column(String(32), default="1.0.0")
    asset_class = Column(String(32))
    timeframes  = Column(ARRAY(String))
    parameters  = Column(JSON, default={})
    is_active   = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id           = Column(Integer, primary_key=True)
    strategy_id  = Column(Integer, nullable=False)
    symbol       = Column(String(32), nullable=False)
    timeframe    = Column(String(16), nullable=False)
    start_date   = Column(String(16))
    end_date     = Column(String(16))
    parameters   = Column(JSON, default={})
    total_trades = Column(Integer)
    win_rate     = Column(Numeric(5, 4))
    profit_factor= Column(Numeric(8, 4))
    net_pnl      = Column(Numeric(14, 4))
    max_drawdown = Column(Numeric(8, 4))
    sharpe_ratio = Column(Numeric(8, 4))
    trades       = Column(JSON)
    run_at       = Column(DateTime(timezone=True), server_default=func.now())

# --- Session Helper ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# --- Example Usage ---
async def save_backtest(data: dict) -> int:
    async with get_db_session() as session:
        run = BacktestRun(**data)
        session.add(run)
        await session.flush()
        return run.id

async def get_active_strategies() -> list[dict]:
    from sqlalchemy import select
    async with get_db_session() as session:
        result = await session.execute(
            select(Strategy).where(Strategy.is_active == True)
        )
        strategies = result.scalars().all()
        return [{"id": s.id, "name": s.name, "parameters": s.parameters} for s in strategies]
```

---

## 5. Alembic Migrations (PostgreSQL)

```bash
# Initialize Alembic in your project root
alembic init alembic

# Edit alembic/env.py — add this near the top:
# from db.postgres import Base
# target_metadata = Base.metadata

# Edit alembic.ini — set sqlalchemy.url:
# sqlalchemy.url = postgresql+asyncpg://trading:password@localhost:5432/trading_db

# Generate initial migration from models
alembic revision --autogenerate -m "initial schema"

# Apply migration
alembic upgrade head

# Roll back one step
alembic downgrade -1
```

> **Note:** Alembic requires a synchronous URL for migration generation. In `env.py` use `postgresql://` (not `+asyncpg`) for the `run_migrations_offline` path, and configure the async runner for `run_migrations_online`. See: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

---

## 6. QuestDB SQL Reference Cheatsheet

QuestDB is SQL-compatible with PostgreSQL extensions, but has unique time-series functions.

```sql
-- SAMPLE BY: resample time series to any interval
SELECT ts, avg(close) AS avg_close
FROM ohlcv_bars
WHERE symbol = 'AAPL' AND timeframe = '1m'
SAMPLE BY 5m FILL(PREV)       -- fill missing bars with previous value
ALIGN TO CALENDAR;             -- align to clock boundaries

-- LATEST ON: get the most recent row per symbol group
SELECT * FROM ohlcv_bars
LATEST ON ts PARTITION BY symbol;

-- ASOF JOIN: join two time series on nearest timestamp
SELECT
    b.ts, b.symbol, b.close,
    i.value AS rsi
FROM ohlcv_bars b
ASOF JOIN indicators i ON (b.symbol = i.symbol)
WHERE b.timeframe = '5m' AND i.indicator_name = 'RSI_14';

-- LT JOIN: join where time series B is strictly BEFORE A
SELECT b.ts, b.close, s.signal_type
FROM ohlcv_bars b
LT JOIN signals s ON (b.symbol = s.symbol);

-- Timestamp range filtering (use ISO 8601 strings)
SELECT * FROM ohlcv_bars
WHERE ts IN '2025-01-01T09:30:00Z;6h'   -- from 09:30 UTC for 6 hours
  AND symbol = 'SPY';

-- Dynamic partition pruning (fast)
SELECT * FROM ohlcv_bars
WHERE ts >= dateadd('d', -7, now())     -- last 7 days
  AND symbol = 'QQQ'
  AND timeframe = '1D';
```

**Key SQL differences from standard PostgreSQL:**
- `SAMPLE BY` — unique to QuestDB, replaces `DATE_TRUNC` + `GROUP BY` for resampling
- `LATEST ON ... PARTITION BY` — replaces `DISTINCT ON` in PostgreSQL
- `ASOF JOIN` / `LT JOIN` — time-aware joins not available in standard SQL
- Timestamp literals: use single quotes `'2025-01-01T00:00:00Z'` or `dateadd()`
- No `UPDATE` or `DELETE` on WAL tables (append-only). Use `ALTER TABLE DROP PARTITION BY` to purge old data.

---

## 7. Data Pipeline Patterns

### 7.1 Live Feed Ingestor (TradeStation / TradingView Webhook)

```python
# ingestor/webhook_handler.py
# Receives TradingView alert webhooks and writes to QuestDB

from fastapi import FastAPI, Request
from db.questdb_writer import QuestDBWriter
from db.postgres import get_db_session
from datetime import datetime, timezone
import json

app = FastAPI()
writer = QuestDBWriter()

@app.post("/webhook/signal")
async def receive_signal(request: Request):
    body = await request.json()
    # Expected body from TradingView alert:
    # {"symbol": "AAPL", "action": "BUY", "price": 195.50, "strategy": "EMA_Cross"}
    
    symbol      = body["symbol"]
    signal_type = "ENTRY_LONG" if body["action"] == "BUY" else "ENTRY_SHORT"
    price       = float(body["price"])
    ts          = datetime.now(tz=timezone.utc)

    # Get strategy_id from PostgreSQL (soft FK)
    strategy_id = await get_strategy_id(body.get("strategy", "unknown"))

    # Write signal to QuestDB
    writer.write_signal(
        symbol=symbol,
        strategy_id=strategy_id,
        signal_type=signal_type,
        timeframe=body.get("timeframe", "unknown"),
        price=price,
        ts=ts
    )
    return {"status": "ok", "ts": ts.isoformat()}

async def get_strategy_id(name: str) -> int:
    from sqlalchemy import select
    from db.postgres import Strategy
    async with get_db_session() as session:
        result = await session.execute(select(Strategy).where(Strategy.name == name))
        strategy = result.scalar_one_or_none()
        return strategy.id if strategy else -1
```

### 7.2 Historical Data Backfill

```python
# scripts/backfill_ohlcv.py
# Backfill historical OHLCV from yfinance or a CSV export

import yfinance as yf
import pandas as pd
from db.questdb_writer import QuestDBWriter
from datetime import timezone

def backfill_symbol(symbol: str, period: str = "2y", interval: str = "1d"):
    writer = QuestDBWriter()
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True)
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "ts"
    df.columns = [c.lower() for c in df.columns]
    df = df.rename(columns={"adj close": "close"})[["open", "high", "low", "close", "volume"]]
    df["symbol"]    = symbol
    df["timeframe"] = interval.replace("d", "1D").replace("h", "1h")
    df = df.reset_index()
    writer.write_dataframe("ohlcv_bars", df, ts_col="ts")
    print(f"Backfilled {len(df)} bars for {symbol}")

if __name__ == "__main__":
    symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NQ=F"]
    for sym in symbols:
        backfill_symbol(sym, period="5y", interval="1d")
        backfill_symbol(sym, period="60d", interval="1h")
        backfill_symbol(sym, period="7d", interval="1m")
```

### 7.3 Cross-DB Query Pattern (Application-Side Join)

Since QuestDB and PostgreSQL don't natively join across instances, use this pattern:

```python
# services/strategy_signal_service.py
# Combines QuestDB signals with PostgreSQL strategy metadata

import asyncio
from db.questdb_reader import get_latest_signals
from db.postgres import get_active_strategies

async def get_enriched_signals(symbol: str) -> list[dict]:
    # 1. Fetch signals from QuestDB
    signals_df = get_latest_signals(symbol, limit=100)
    
    # 2. Fetch strategy metadata from PostgreSQL
    strategies = await get_active_strategies()
    strategy_map = {s["id"]: s for s in strategies}
    
    # 3. Merge at application layer
    enriched = []
    for _, row in signals_df.iterrows():
        strategy = strategy_map.get(int(row["strategy_id"]), {})
        enriched.append({
            "ts":            row["ts"].isoformat(),
            "signal_type":   row["signal_type"],
            "price":         row["price"],
            "strategy_name": strategy.get("name", "unknown"),
            "parameters":    strategy.get("parameters", {}),
        })
    return enriched
```

---

## 8. Docker Compose — Full Stack

```yaml
# docker-compose.yml — full trading stack
version: "3.9"

services:

  questdb:
    image: questdb/questdb:latest
    container_name: questdb
    restart: unless-stopped
    ports:
      - "9000:9000"
      - "9009:9009"
      - "8812:8812"
    volumes:
      - questdb_data:/var/lib/questdb
    environment:
      - QDB_CAIRO_COMMIT_LAG=1000
      - QDB_CAIRO_MAX_UNCOMMITTED_ROWS=500000
    mem_limit: 4g

  postgres:
    image: postgres:16-alpine
    container_name: trading_postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: trading_db
    mem_limit: 2g

  trading_api:
    build: .
    container_name: trading_api
    restart: unless-stopped
    ports:
      - "8000:8000"
    depends_on:
      - questdb
      - postgres
    environment:
      - QUESTDB_ILP_HOST=questdb
      - QUESTDB_PG_HOST=questdb
      - POSTGRES_URL=postgresql+asyncpg://trading:${POSTGRES_PASSWORD}@postgres:5432/trading_db
    volumes:
      - ./:/app

volumes:
  questdb_data:
  postgres_data:
```

---

## 9. Environment Variables

```bash
# .env
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_URL=postgresql+asyncpg://trading:your_secure_password_here@localhost:5432/trading_db

QUESTDB_ILP_HOST=localhost
QUESTDB_ILP_PORT=9009
QUESTDB_PG_HOST=localhost
QUESTDB_PG_PORT=8812
QUESTDB_PG_USER=admin
QUESTDB_PG_PASS=

DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## 10. Performance & Operational Notes

### QuestDB Tuning
- **Commit lag**: `QDB_CAIRO_COMMIT_LAG=1000` (1 second) balances write latency vs. throughput. Lower = more visible for queries, higher = better batch ingestion performance.
- **Partition maintenance**: Old partitions can be dropped: `ALTER TABLE ohlcv_bars DROP PARTITION LIST '2020-01-01', '2020-01-02';`
- **No UPDATEs**: QuestDB WAL tables are append-only. For corrections, append a new row with the corrected data and filter in queries by `LATEST ON`.
- **Memory**: QuestDB is JVM-based. Allocate at minimum 2GB, ideally 4GB+ for production workloads.

### PostgreSQL Tuning
- Use `JSONB` (not `JSON`) for all JSON columns — it's indexed and binary-stored.
- Add `GIN` indexes for JSONB columns queried with `->` operators: `CREATE INDEX idx_strategies_params ON strategies USING GIN (parameters);`
- Use `TIMESTAMPTZ` (not `TIMESTAMP`) for all datetimes — always store UTC.

### Connection Pooling
- For production, put **PgBouncer** in front of PostgreSQL to manage connection limits.
- QuestDB's PostgreSQL wire protocol is not compatible with PgBouncer — connect directly or use HTTP REST API for queries.

---

## 11. Key Documentation Links

| Resource | URL |
|---|---|
| QuestDB Official Docs | https://questdb.com/docs/ |
| QuestDB Python Client (ILP) | https://py-questdb-client.readthedocs.io/en/latest/ |
| QuestDB SQL Reference | https://questdb.com/docs/reference/sql/overview/ |
| QuestDB SAMPLE BY | https://questdb.com/docs/reference/sql/sample-by/ |
| QuestDB ASOF JOIN | https://questdb.com/docs/reference/sql/asof-join/ |
| QuestDB Docker Hub | https://hub.docker.com/r/questdb/questdb |
| QuestDB GitHub | https://github.com/questdb/questdb |
| SQLAlchemy Async Docs | https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html |
| asyncpg Docs | https://magicstack.github.io/asyncpg/current/ |
| Alembic Async Cookbook | https://alembic.sqlalchemy.org/en/latest/cookbook.html |
| psycopg2 Docs | https://www.psycopg.org/docs/ |
| FastAPI + SQLAlchemy Guide | https://fastapi.tiangolo.com/tutorial/sql-databases/ |
| QuestDB Community Forum | https://community.questdb.com/ |

---

## 12. Implementation Checklist for AI Agent

### Phase 1 — Infrastructure
- [ ] Deploy QuestDB via Docker Compose, verify Web Console at `:9000`
- [ ] Deploy PostgreSQL via Docker Compose
- [ ] Create `.env` with all credentials
- [ ] Verify QuestDB ILP connection on port `9009`
- [ ] Verify QuestDB PG wire connection on port `8812` (psycopg2)
- [ ] Verify PostgreSQL connection on port `5432` (asyncpg)

### Phase 2 — Schema
- [ ] Create QuestDB tables: `ohlcv_bars`, `ticks`, `indicators`, `signals`
- [ ] Initialize Alembic in project
- [ ] Create PostgreSQL models: `Strategy`, `BacktestRun`, `Symbol`, `Watchlist`, `AlertConfig`
- [ ] Run `alembic upgrade head` to apply migrations

### Phase 3 — Python Clients
- [ ] Implement `QuestDBWriter` (ILP ingestion)
- [ ] Implement `QuestDBReader` (PG wire queries)
- [ ] Implement async PostgreSQL session factory
- [ ] Write unit tests for each client with sample data

### Phase 4 — Data Pipeline
- [ ] Build historical backfill script (yfinance or CSV)
- [ ] Verify backfilled data in QuestDB Web Console
- [ ] Build webhook ingestor (FastAPI) for TradingView alerts
- [ ] Connect alert configs to Discord webhook via PostgreSQL `alert_configs` table

### Phase 5 — Integration
- [ ] Implement cross-DB enrichment service (QuestDB signals + PG strategy metadata)
- [ ] Build n8n workflow to trigger on new signals (n8n has a native PostgreSQL node)
- [ ] Dashboard: query QuestDB via HTTP REST API (`GET /exec?query=...`) for chart data

