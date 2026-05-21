"""
Live Gainer Screener  — in-memory cache, Polygon Snapshot API.

Lifecycle:
  1.  Any call to `get_live_gainers()` triggers a Polygon snapshot fetch if
      the cache is stale (older than CACHE_TTL_SECONDS).
  2.  A background thread launched by `start_auto_persist()` waits until
      8:00 PM Eastern every weekday and then writes the final snapshot to
      the `daily_gainers` PostgreSQL table (same schema as nightly ingest).
  3.  The final persist also enriches the top 100 Polygon tickers with
      float/sector/RVOL via yfinance (same logic as ingest_gainers.py), so
      the end-of-day record is fully enriched.

Market session labels (Eastern time):
  - PRE_MARKET   04:00 – 09:29
  - OPEN         09:30 – 15:59
  - AFTER_HOURS  16:00 – 19:59
  - CLOSED       20:00 – 03:59 (next day)
"""

import threading
import time
import logging
from datetime import datetime, date as date_cls
from typing import Optional

import pytz

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
EASTERN = pytz.timezone('US/Eastern')

CACHE_TTL_SECONDS = 300          # Re-fetch Polygon every 5 minutes
PERSIST_HOUR_ET   = 20           # 8:00 PM Eastern — after-hours close
PERSIST_MINUTE_ET = 0

# Screening thresholds (same as ingest job)
MIN_GAP_PCT    = 5.0    # Show anything > 5% gap
MAX_FLOAT_M    = 200.0  # < 200M shares
MIN_RVOL       = 2.0    # > 2x RVOL
MIN_PRICE      = 0.10    # >= $0.10
MAX_PRICE      = 100.00  # <= $100
MAX_MARKET_CAP = 10_000e6 # < $10B

TOP_N           = 25    # Number of tickers to surface in the live panel
POLYGON_LIMIT   = 100   # How many tickers to pull from Polygon snapshot


# ── In-process state ───────────────────────────────────────────────────────────
_cache_lock    = threading.Lock()
_cache: dict   = {
    'gainers':      [],     # list[dict] — enriched top-N
    'raw_tickers':  [],     # list[str]  — all tickers from Polygon, pre-filter
    'fetched_at':   None,   # datetime (UTC)
    'session':      None,   # str: 'pre_market' | 'open' | 'after_hours' | 'closed'
    'persisted_dates': set(),   # set of date strings already persisted today
}


# ── Market session logic ───────────────────────────────────────────────────────

def get_market_session(now_et: Optional[datetime] = None) -> str:
    """Return the current US market session label."""
    if now_et is None:
        now_et = datetime.now(EASTERN)
    hm = now_et.hour * 60 + now_et.minute
    if   4 * 60 <= hm < 9 * 60 + 30:
        return 'pre_market'
    elif 9 * 60 + 30 <= hm < 16 * 60:
        return 'open'
    elif 16 * 60 <= hm < 20 * 60:
        return 'after_hours'
    else:
        return 'closed'

def get_session_label(session: str) -> str:
    return {
        'pre_market':   '🌅 Pre-Market',
        'open':         '🟢 Market Open',
        'after_hours':  '🌙 After-Hours',
        'closed':       '⏸ Market Closed',
    }.get(session, session)


# ── Polygon Snapshot fetch ─────────────────────────────────────────────────────

def _fetch_polygon_snapshot() -> list[dict]:
    """
    Fetch top gainers from Massive.com (fka Polygon.io) via the official SDK.
    With Standard tier, this includes extended-hours data.
    Returns a list of raw ticker dicts.
    """
    from services import polygon_client as poly
    try:
        snaps = poly.get_gainers_snapshot(include_otc=False)
        log.info(f"[LiveScreener] Massive returned {len(snaps)} raw gainers")
        return snaps[:POLYGON_LIMIT]
    except Exception as e:
        log.warning(f"[LiveScreener] Massive snapshot failed: {e}")
        return []


# ── Per-ticker enrichment (lightweight, no yfinance for live cache) ────────────

def _enrich_snapshot_tickers(raw_tickers: list[dict]) -> list[dict]:
    """
    Build structured gainer dicts from Polygon snapshot data.
    This is intentionally lightweight — we use only Polygon fields so we
    can refresh every 5 min without hammering yfinance.
    """
    gainers = []
    for t in raw_tickers:
        try:
            sym = t.get('ticker', '')
            if not sym or len(sym) > 5:   # skip obvious non-equities
                continue

            day   = t.get('day', {})
            prevd = t.get('prevDay', {})
            snap  = t.get('lastQuote', {}) or {}
            last  = t.get('lastTrade', {}) or {}

            # Gap % — use todaysChangePerc which Polygon calculates vs prev close
            gap_pct = t.get('todaysChangePerc')
            if gap_pct is None:
                prev_close = prevd.get('c') or prevd.get('vw')
                open_price = day.get('o')
                if prev_close and open_price and prev_close > 0:
                    gap_pct = ((open_price - prev_close) / prev_close) * 100
            if gap_pct is None or gap_pct < MIN_GAP_PCT:
                continue

            # Volume & RVOL
            volume     = day.get('v') or 0
            prev_vol   = prevd.get('v') or 0
            # Simple 1-day RVOL proxy until we have moving averages
            rvol = round(volume / prev_vol, 2) if prev_vol > 0 else None

            # Prices
            open_price  = day.get('o') or prevd.get('c')
            # For live price: prefer last trade, then VWAP, then close
            last_price  = (
                last.get('p')
                or day.get('c')
                or day.get('vw')
            )
            prev_close  = prevd.get('c') or prevd.get('vw')

            if not last_price or not prev_close:
                continue

            # Recompute gap off last vs prev_close so it reflects the current
            # extended-hours move, not just the gap at open
            gap_pct = round(((last_price - prev_close) / prev_close) * 100, 2)
            if gap_pct < MIN_GAP_PCT:
                continue

            # ── Price Filter ───────────────────────────────────────────────────────
            if last_price < MIN_PRICE or last_price > MAX_PRICE:
                continue

            gainers.append({
                'ticker':        sym,
                'gap_pct':       gap_pct,
                'last_price':    round(last_price, 4),
                'open_price':    round(open_price, 4) if open_price else None,
                'prev_close':    round(prev_close, 4),
                'volume':        int(volume),
                'rvol_15m':      rvol,
                'float_shares':  t.get('float_shares'),
                'sector':        t.get('sector'),
                'market_cap':    t.get('market_cap'),
                'spread_pct':    t.get('spread_pct'),
                'trade_time':    t.get('trade_time'),
                'is_hod':        t.get('is_hod'),
                'news_headline': None,
                'news_fresh':    None,
            })
        except Exception as e:
            log.debug(f"[LiveScreener] Skipping ticker {t.get('ticker')}: {e}")
            continue

    # Sort descending by gap
    gainers.sort(key=lambda x: x['gap_pct'], reverse=True)
    return gainers[:TOP_N * 3]   # keep a wider pool for the persist step


# ── Public cache API ───────────────────────────────────────────────────────────

def _is_cache_fresh() -> bool:
    with _cache_lock:
        fetched = _cache['fetched_at']
    if fetched is None:
        return False
    age = (datetime.utcnow() - fetched).total_seconds()
    return age < CACHE_TTL_SECONDS


def refresh_cache(force: bool = False) -> dict:
    """
    Refresh the live gainer cache from Polygon if stale.
    Returns the current cache contents.
    """
    if not force and _is_cache_fresh():
        with _cache_lock:
            return dict(_cache)

    now_et  = datetime.now(EASTERN)
    session = get_market_session(now_et)

    # During deep-closed hours (midnight to 3:59 AM ET) don't burn API calls
    hm = now_et.hour * 60 + now_et.minute
    if 0 <= hm < 4 * 60 and not force:
        with _cache_lock:
            _cache['session'] = session
            return dict(_cache)

    raw = _fetch_polygon_snapshot()
    gainers = _enrich_snapshot_tickers(raw)

    with _cache_lock:
        _cache['raw_tickers']  = [t.get('ticker', '') for t in raw]
        _cache['gainers']      = gainers[:TOP_N]
        _cache['fetched_at']   = datetime.utcnow()
        _cache['session']      = session
        return dict(_cache)


def get_live_gainers() -> dict:
    """
    Public entry point for the API route.
    Returns:
      {
        session:      str,
        session_label: str,
        fetched_at:   ISO string | null,
        gainers:      list[dict],
        top_n:        int,
        cache_ttl_s:  int,
      }
    """
    snap = refresh_cache()
    fetched = snap['fetched_at']
    return {
        'session':       snap.get('session', 'closed'),
        'session_label': get_session_label(snap.get('session', 'closed')),
        'fetched_at':    fetched.isoformat() + 'Z' if fetched else None,
        'gainers':       snap['gainers'],
        'top_n':         TOP_N,
        'cache_ttl_s':   CACHE_TTL_SECONDS,
    }


# ── End-of-day persist (8:00 PM ET) ───────────────────────────────────────────

def _do_persist(target_date: str):
    """
    Run the full Polygon+FMP enrichment pipeline and write to daily_gainers.
    Runs in a background thread at 8:00 PM ET.
    """
    log.info(f"[LiveScreener] Starting EOD persist for {target_date}")

    try:
        import sys, os
        sys.path.insert(0, os.path.dirname(__file__))
        from jobs.ingest_gainers import fetch_gainers, write_gainers
        gainers = fetch_gainers(target_date)
        if gainers:
            inserted, skipped = write_gainers(gainers, target_date)
            log.info(f"[LiveScreener] EOD persist done — inserted={inserted} skipped={skipped}")
        else:
            log.warning("[LiveScreener] Enrichment pipeline returned no qualified gainers")
    except Exception as e:
        log.error(f"[LiveScreener] EOD persist failed: {e}", exc_info=True)

    with _cache_lock:
        _cache['persisted_dates'].add(target_date)


def _auto_persist_loop():
    """Background thread: waits for 8:00 PM ET on weekdays, then persists."""
    log.info("[LiveScreener] Auto-persist watchdog started")
    while True:
        try:
            now_et = datetime.now(EASTERN)
            today  = now_et.strftime('%Y-%m-%d')

            # Only run on weekdays
            if now_et.weekday() < 5:
                hm = now_et.hour * 60 + now_et.minute
                persist_hm = PERSIST_HOUR_ET * 60 + PERSIST_MINUTE_ET

                with _cache_lock:
                    already_done = today in _cache['persisted_dates']

                if hm >= persist_hm and not already_done:
                    _do_persist(today)

            # Sleep until next check (every 60 seconds is fine — we only trigger once)
            time.sleep(60)
        except Exception as e:
            log.error(f"[LiveScreener] Auto-persist loop error: {e}")
            time.sleep(60)


def start_auto_persist():
    """
    Launch the EOD auto-persist background thread.
    Called once from app.py during startup.
    """
    t = threading.Thread(target=_auto_persist_loop, name='live-screener-persist', daemon=True)
    t.start()
    log.info("[LiveScreener] Auto-persist thread launched")
