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

CACHE_TTL_SECONDS = 60           # Re-fetch Polygon every 1 minute
PERSIST_HOUR_ET   = 20           # 8:00 PM Eastern — after-hours close
PERSIST_MINUTE_ET = 0

# Screening thresholds (same as ingest job)
MIN_GAP_PCT    = 5.0     # Show anything > 5% gap
MAX_FLOAT_M    = 500.0   # < 500M shares
MIN_RVOL       = 2.0     # > 2x RVOL
MIN_PRICE      = 0.10    # >= $0.10
MAX_PRICE      = 100.00  # <= $100
MAX_MARKET_CAP = 10_000e6 # < $10B

TOP_N           = 25    # Number of tickers to surface in the live panel
POLYGON_LIMIT   = 100   # How many tickers to pull from Polygon snapshot


# ── In-process state ───────────────────────────────────────────────────────────
_cache_lock    = threading.RLock()
_cache: dict   = {
    'gainers':      [],     # list[dict] — enriched top-N
    'raw_tickers':  [],     # list[str]  — all tickers from Polygon, pre-filter
    'fetched_at':   None,   # datetime (UTC)
    'session':      None,   # str: 'pre_market' | 'open' | 'after_hours' | 'closed'
    'persisted_dates': set(),   # set of date strings already persisted today
}

_ma_cache = {}  # ticker -> (timestamp, data_dict)
_ma_cache_lock = threading.Lock()

_minute_cache = {}  # ticker -> (timestamp, metrics_dict)
_minute_cache_lock = threading.Lock()

def get_cached_sparkline_and_ma(ticker: str) -> dict:
    now = time.time()
    with _ma_cache_lock:
        if ticker in _ma_cache:
            ts, data = _ma_cache[ticker]
            if now - ts < 3600:  # 1 hour cache
                return data

    try:
        from momentum_screener.schwab.http_client import get_price_history_every_day
        candles = get_price_history_every_day(ticker)
        if not candles:
            data = {
                'sparkline_5d': [],
                'sma20': None, 'sma50': None, 'sma100': None
            }
        else:
            closes = [c.get('close') for c in candles if c.get('close') is not None]
            if not closes:
                data = {
                    'sparkline_5d': [],
                    'sma20': None, 'sma50': None, 'sma100': None
                }
            else:
                sparkline_5d = closes[-5:]
                
                def sma(n):
                    if len(closes) < n:
                        return None
                    return sum(closes[-n:]) / n
                
                data = {
                    'sparkline_5d': sparkline_5d,
                    'sma20': round(sma(20), 2) if sma(20) is not None else None,
                    'sma50': round(sma(50), 2) if sma(50) is not None else None,
                    'sma100': round(sma(100), 2) if sma(100) is not None else None,
                }
    except Exception as e:
        log.warning(f"Error computing sparkline & MA for {ticker}: {e}")
        data = {
            'sparkline_5d': [],
            'sma20': None, 'sma50': None, 'sma100': None
        }

    with _ma_cache_lock:
        _ma_cache[ticker] = (now, data)
    return data

def check_tickers_history(tickers: list[str]) -> dict:
    if not tickers:
        return {}
    try:
        from database import get_connection
        today_et = datetime.now(EASTERN).strftime('%Y-%m-%d')
        with get_connection() as conn:
            cur = conn.execute("SELECT MAX(date) as max_date FROM daily_gainers WHERE date < %s", (today_et,))
            row = cur.fetchone()
            recent_date = row['max_date'] if row else None
            
            if not recent_date:
                return {}
            
            cur = conn.execute(
                """
                SELECT ticker, COUNT(*) as total_count,
                       SUM(CASE WHEN date = %s THEN 1 ELSE 0 END) as yesterday_count
                FROM daily_gainers
                WHERE ticker = ANY(%s) AND date < %s
                GROUP BY ticker
                """,
                (recent_date, list(tickers), today_et)
            )
            rows = cur.fetchall()
            
            history = {}
            for r in rows:
                history[r['ticker']] = {
                    'is_repeat_runner': r['total_count'] > 0,
                    'is_follow_through': r['yesterday_count'] > 0
                }
            return history
    except Exception as e:
        log.warning(f"Error checking ticker history: {e}")
        return {}

import concurrent.futures

def get_minute_metrics(ticker: str, last_price: Optional[float], high_price: Optional[float], bid: Optional[float], ask: Optional[float]) -> dict:
    now = time.time()
    with _minute_cache_lock:
        if ticker in _minute_cache:
            ts, data = _minute_cache[ticker]
            if now - ts < 30:
                # Update high-frequency values dynamically if we have a cached base
                if last_price is not None:
                    if data.get('atr_14') and data['atr_14'] > 0:
                        if high_price is not None:
                            data['atr_hod'] = round((high_price - last_price) / data['atr_14'], 2)
                        if bid is not None and ask is not None:
                            data['atr_sprd'] = round((ask - bid) / data['atr_14'], 2)
                        if data.get('vwap') is not None:
                            data['atr_vwap'] = round((last_price - data['vwap']) / data['atr_14'], 2)
                    if 'intraday_sparkline' in data and data['intraday_sparkline']:
                        data['intraday_sparkline'] = list(data['intraday_sparkline'])
                        data['intraday_sparkline'][-1] = last_price
                    # Re-anchor mom_2m to wall-clock now so the cached base price stays correct
                    # even as wall-clock time advances past the 30-second cache window edges
                    if data.get('price_2min_ago') and data['price_2min_ago'] > 0:
                        data['mom_2m'] = round(((last_price - data['price_2min_ago']) / data['price_2min_ago']) * 100, 2)
                        # Invalidate stale base price: if the cached price_2min_ago was set
                        # when the cache was first computed (up to 30s ago), it may now be
                        # older than 2.5 minutes — in that case force a full recalculation
                        # next call by expiring the cache entry.
                        cache_age_s = now - ts
                        if cache_age_s > 28:  # near cache expiry — let it naturally expire
                            pass  # next call will recompute fresh
                return data

    try:
        from services.schwab_client import get_minute_bars
        candles = get_minute_bars(ticker)
        if not candles:
            metrics = {
                'mom_2m': None,
                'price_2min_ago': None,
                'atr_hod': None,
                'atr_sprd': None,
                'atr_vwap': None,
                'zen_v': None,
                'atr_14': None,
                'vwap': None,
                'intraday_sparkline': []
            }
        else:
            # 1. Compute ATR(14)
            tr_values = []
            for i in range(1, len(candles)):
                h = candles[i].get('h') or candles[i].get('c')
                l = candles[i].get('l') or candles[i].get('c')
                prev_c = candles[i-1].get('c')
                if h is not None and l is not None and prev_c is not None:
                    tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                    tr_values.append(tr)
            
            atr = 0.0
            if tr_values:
                periods = min(14, len(tr_values))
                atr = sum(tr_values[-periods:]) / periods
            
            if atr <= 0:
                atr = (last_price or candles[-1].get('c') or 1.0) * 0.001

            # 2. Compute 2Min % change anchored to wall-clock now (not last candle ts)
            # Using wall-clock time avoids skew on slow/gapped tickers where the
            # last candle may itself be several minutes old.
            curr_p = last_price if last_price is not None else (candles[-1].get('c') or 0.0)
            price_2min_ago = None
            if candles:
                # Anchor lookback to now (ms), not the last candle's timestamp
                now_ms = int(time.time() * 1000)
                target_ts = now_ms - 120_000  # 2 minutes ago in ms
                five_min_ago_ts = now_ms - 300_000  # 5-minute window for fallback

                # Walk backwards: find the latest candle at or before 2 min ago
                for c in reversed(candles):
                    c_ts = c.get('t')
                    if c_ts is not None and c_ts <= target_ts:
                        price_2min_ago = c.get('c')
                        break

                # Fallback: use the earliest candle within the last 5 minutes
                # (never fall back all the way to candles[0] / 4 AM pre-market)
                if price_2min_ago is None:
                    for c in candles:
                        c_ts = c.get('t')
                        if c_ts is not None and c_ts >= five_min_ago_ts:
                            price_2min_ago = c.get('c')
                            break

            mom_2m = 0.0
            if price_2min_ago and price_2min_ago > 0:
                mom_2m = round(((curr_p - price_2min_ago) / price_2min_ago) * 100, 2)

            # 3. Compute VWAP
            total_vol = sum(c.get('v') or 0 for c in candles)
            if total_vol > 0:
                sum_pv = 0.0
                for c in candles:
                    h = c.get('h') or c.get('c') or 0.0
                    l = c.get('l') or c.get('c') or 0.0
                    close = c.get('c') or 0.0
                    v = c.get('v') or 0
                    tp = (h + l + close) / 3.0
                    sum_pv += tp * v
                vwap = sum_pv / total_vol
            else:
                vwap = curr_p

            # 4. Compute ZenV (Slope)
            zen_v = 0.0
            if len(candles) >= 5:
                y = [c.get('c') or 0.0 for c in candles[-5:]]
                sum_iy = sum((i + 1) * y[i] for i in range(5))
                sum_y = sum(y)
                slope = (sum_iy - 3.0 * sum_y) / 10.0
                zen_v = round(slope / atr, 2)
            elif len(candles) >= 2:
                n = len(candles)
                y = [c.get('c') or 0.0 for c in candles[-n:]]
                sum_x = sum(range(1, n + 1))
                sum_x2 = sum(i * i for i in range(1, n + 1))
                sum_y = sum(y)
                sum_xy = sum((i + 1) * y[i] for i in range(n))
                denom = (n * sum_x2 - sum_x * sum_x)
                slope = (n * sum_xy - sum_x * sum_y) / denom if denom > 0 else 0.0
                zen_v = round(slope / atr, 2)

            # 5. Compute ATR Distance to High of Day (AtrHoD)
            candle_high = max((c.get('h') or c.get('c') or 0.0) for c in candles) if candles else 0.0
            hod = max(high_price or 0.0, candle_high, curr_p)
            atr_hod = round((hod - curr_p) / atr, 2) if hod and atr > 0 else 0.0
            if atr_hod < 0:
                atr_hod = 0.0

            # 6. Compute ATR Spread
            atr_sprd = None
            if bid is not None and ask is not None:
                atr_sprd = round((ask - bid) / atr, 2)

            # 7. Compute ATR VWAP
            atr_vwap = round((curr_p - vwap) / atr, 2) if atr > 0 else 0.0

            # 8. Compute Detailed Intraday Sparkline
            closes = [c.get('c') for c in candles if c.get('c') is not None]
            intraday_sparkline = []
            if closes:
                target_len = 30
                if len(closes) > target_len:
                    intraday_sparkline = [
                        closes[int(i * (len(closes) - 1) / (target_len - 1))]
                        for i in range(target_len)
                    ]
                else:
                    intraday_sparkline = closes
                if last_price is not None:
                    intraday_sparkline[-1] = last_price

            metrics = {
                'mom_2m': mom_2m,
                'raw_mom_2m': mom_2m,
                'price_2min_ago': price_2min_ago,
                'atr_hod': atr_hod,
                'atr_sprd': atr_sprd,
                'atr_vwap': atr_vwap,
                'zen_v': zen_v,
                'atr_14': atr,
                'vwap': vwap,
                'intraday_sparkline': intraday_sparkline,
                'hod': hod
            }
    except Exception as e:
        log.warning(f"Error computing minute metrics for {ticker}: {e}", exc_info=True)
        metrics = {
            'mom_2m': None,
            'price_2min_ago': None,
            'atr_hod': None,
            'atr_sprd': None,
            'atr_vwap': None,
            'zen_v': None,
            'atr_14': None,
            'vwap': None,
            'intraday_sparkline': [],
            'hod': high_price or last_price
        }

    with _minute_cache_lock:
        _minute_cache[ticker] = (now, metrics)
    return metrics

def enrich_single_gainer(g: dict) -> dict:
    ticker = g['ticker']
    # 1. Daily indicators (1 hour cache)
    ma_data = get_cached_sparkline_and_ma(ticker)
    
    # 2. Minute-level indicators (30 seconds cache)
    last_price = g.get('last_price')
    high_price = g.get('high_price')
    bid = g.get('bid')
    ask = g.get('ask')
    min_metrics = get_minute_metrics(ticker, last_price, high_price, bid, ask)
    
    return {
        'ma': ma_data,
        'min': min_metrics
    }

_last_auth_alert_time = 0.0
_auth_alert_lock = threading.Lock()

def enrich_gainers_with_sparklines_and_history(gainers: list[dict]) -> list[dict]:
    if not gainers:
        return gainers
        
    schwab_available = True
    try:
        from momentum_screener.schwab.http_client import get_http_client
        get_http_client()
    except Exception as e:
        log.error(f"[LiveScreener] Schwab HTTP client initialization failed: {e}", exc_info=True)
        schwab_available = False

        # Rate-limit Telegram alert to once every 1 hour to avoid spamming
        global _last_auth_alert_time
        now = time.time()
        with _auth_alert_lock:
            should_alert = (now - _last_auth_alert_time) > 3600
            if should_alert:
                _last_auth_alert_time = now

        if should_alert:
            try:
                from fastapi_app.tasks.alerts import send_telegram_message
                send_telegram_message(
                    "🚨 *[Schwab Auth Failure]* 🚨\n\n"
                    "Schwab HTTP client failed to initialize! The live screener will run in fallback mode.\n"
                    f"- *Error:* {e}\n"
                    "- *Action:* Please run `python schwab_auth_setup.py` on the host to refresh the token."
                )
            except Exception as alert_err:
                log.error(f"Failed to send Telegram auth alert: {alert_err}")

    tickers = [g['ticker'] for g in gainers]
    history = check_tickers_history(tickers)
    
    if not schwab_available:
        # Populate remaining un-enriched tickers with fallbacks so schema remains consistent
        for g in gainers:
            g.update({
                'sparkline_5d': [],
                'sparkline_intraday': [],
                'above_sma20': False, 'above_sma50': False, 'above_sma100': False,
                'sma20': None, 'sma50': None, 'sma100': None,
                'mom_2m': None, 'atr_hod': None, 'atr_sprd': None, 'atr_vwap': None, 'zen_v': None
            })
            ticker = g['ticker']
            hist = history.get(ticker, {})
            g['is_repeat_runner'] = hist.get('is_repeat_runner', False)
            g['is_follow_through'] = hist.get('is_follow_through', False)
        return gainers
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(enrich_single_gainer, g): g for g in gainers}
        try:
            for future in concurrent.futures.as_completed(futures, timeout=45):
                g = futures[future]
                try:
                    res = future.result()
                    ma_data = res['ma']
                    min_metrics = res['min']
                    
                    # Apply daily metrics
                    live_price = g.get('last_price')
                    sparkline = ma_data['sparkline_5d']
                    if live_price is not None:
                        sparkline = sparkline[-4:] + [live_price]
                    
                    g['sparkline_5d'] = sparkline
                    g['sma20'] = ma_data['sma20']
                    g['sma50'] = ma_data['sma50']
                    g['sma100'] = ma_data['sma100']
                    
                    g['above_sma20'] = live_price > ma_data['sma20'] if live_price is not None and ma_data['sma20'] is not None else False
                    g['above_sma50'] = live_price > ma_data['sma50'] if live_price is not None and ma_data['sma50'] is not None else False
                    g['above_sma100'] = live_price > ma_data['sma100'] if live_price is not None and ma_data['sma100'] is not None else False
                    
                    # Apply minute-level metrics
                    g['mom_2m'] = min_metrics['mom_2m']
                    g['atr_hod'] = min_metrics['atr_hod']
                    g['atr_sprd'] = min_metrics['atr_sprd']
                    g['atr_vwap'] = min_metrics['atr_vwap']
                    g['zen_v'] = min_metrics['zen_v']
                    g['sparkline_intraday'] = min_metrics.get('intraday_sparkline', [])
                    if min_metrics.get('hod'):
                        g['high_price'] = round(min_metrics['hod'], 4)
                    
                except Exception as e:
                    log.warning(f"Failed to enrich {g['ticker']}: {e}")
                    g.update({
                        'sparkline_5d': [],
                        'sparkline_intraday': [],
                        'above_sma20': False, 'above_sma50': False, 'above_sma100': False,
                        'sma20': None, 'sma50': None, 'sma100': None,
                        'mom_2m': None, 'atr_hod': None, 'atr_sprd': None, 'atr_vwap': None, 'zen_v': None
                    })
        except concurrent.futures.TimeoutError:
            log.error("[LiveScreener] Cache enrichment timed out after 45 seconds! Thread pool may have hung.")
            for future in futures:
                future.cancel()
            
            # Populate remaining un-enriched tickers with fallbacks so schema remains consistent
            for g in gainers:
                if 'sparkline_5d' not in g:
                    g.update({
                        'sparkline_5d': [],
                        'sparkline_intraday': [],
                        'above_sma20': False, 'above_sma50': False, 'above_sma100': False,
                        'sma20': None, 'sma50': None, 'sma100': None,
                        'mom_2m': None, 'atr_hod': None, 'atr_sprd': None, 'atr_vwap': None, 'zen_v': None
                    })
                
    for g in gainers:
        ticker = g['ticker']
        hist = history.get(ticker, {})
        g['is_repeat_runner'] = hist.get('is_repeat_runner', False)
        g['is_follow_through'] = hist.get('is_follow_through', False)
        
    return gainers


# ── Market session logic ───────────────────────────────────────────────────────

def get_market_session(now_et: Optional[datetime] = None) -> str:
    """Return the current US market session label."""
    if now_et is None:
        now_et = datetime.now(EASTERN)
    # Check if it's the weekend (Saturday or Sunday)
    if now_et.weekday() >= 5:
        return 'closed'
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

            # Gap % — calculate gap off last vs prev_close so it reflects the current
            # extended-hours move, not just the gap at open or stale regular change
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
                'high_price':    round(t.get('day', {}).get('h', last_price), 4) if t.get('day', {}).get('h') else round(last_price, 4),
                'open_price':    round(open_price, 4) if open_price else None,
                'prev_close':    round(prev_close, 4),
                'volume':        int(volume),
                'rvol_15m':      rvol,
                'float_shares':  t.get('float_shares'),
                'sector':        t.get('sector'),
                'market_cap':    t.get('market_cap'),
                'spread_pct':    t.get('spread_pct'),
                'ask':           t.get('ask'),
                'bid':           t.get('bid'),
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


def _load_fallback_gainers_from_db() -> list[dict]:
    """
    Query the daily_gainers table for the most recent trading day,
    enrich them (including history & sparklines) so they match the
    format expected by the live screener, and return them.
    """
    try:
        from database import get_connection
        with get_connection() as conn:
            # 1. Find the most recent date in daily_gainers
            cur = conn.execute("SELECT MAX(date) as max_date FROM daily_gainers")
            row = cur.fetchone()
            recent_date = row['max_date'] if row else None
            
            if not recent_date:
                log.info("[LiveScreener] Fallback: No historical daily gainers found in DB.")
                return []
                
            log.info(f"[LiveScreener] Fallback: Loading gainers from DB for date {recent_date}")
            
            # 2. Fetch gappers for that date with gap_pct >= MIN_GAP_PCT
            cur = conn.execute(
                """
                SELECT * FROM daily_gainers 
                WHERE date = %s 
                  AND gap_pct >= %s
                ORDER BY gap_pct DESC 
                LIMIT %s
                """,
                (recent_date, MIN_GAP_PCT, TOP_N)
            )
            rows = cur.fetchall()
            
            gainers = []
            for r in rows:
                last_price = r.get('close_price')
                high_price = r.get('high_price')
                is_hod = (last_price >= (high_price * 0.995)) if last_price and high_price and high_price > 0 else False
                
                # Check close_location as fallback for is_hod if high_price was not populated properly
                if not is_hod and r.get('close_location') is not None:
                    is_hod = r.get('close_location') >= 0.995
                
                gainers.append({
                    'ticker':        r.get('ticker'),
                    'gap_pct':       r.get('gap_pct'),
                    'last_price':    last_price,
                    'high_price':    high_price,
                    'open_price':    r.get('open_price'),
                    'prev_close':    r.get('prev_close'),
                    'volume':        int(r.get('volume')) if r.get('volume') is not None else 0,
                    'rvol_15m':      r.get('rvol_15m'),
                    'float_shares':  r.get('float_shares'),
                    'sector':        r.get('sector'),
                    'market_cap':    r.get('market_cap'),
                    'spread_pct':    None,
                    'ask':           None,
                    'bid':           None,
                    'trade_time':    None,
                    'is_hod':        is_hod,
                    'news_headline': r.get('news_headline'),
                    'news_fresh':    r.get('news_fresh'),
                })
            
            gainers = enrich_gainers_with_sparklines_and_history(gainers)
            return gainers
    except Exception as e:
        log.error(f"[LiveScreener] Failed to load fallback gainers from DB: {e}", exc_info=True)
        return []


def refresh_cache(force: bool = False) -> dict:
    """
    Refresh the live gainer cache from Polygon if stale.
    Returns the current cache contents.
    """
    now_et  = datetime.now(EASTERN)
    session = get_market_session(now_et)

    if not force:
        with _cache_lock:
            # If cache has data, return it immediately to keep API response latency extremely low.
            # The background cache refresh thread is responsible for updating the cache asynchronously.
            if _cache['gainers']:
                return dict(_cache)

    # During deep-closed hours (midnight to 3:59 AM ET) don't burn API calls if we already have data
    hm = now_et.hour * 60 + now_et.minute
    if 0 <= hm < 4 * 60 and not force:
        with _cache_lock:
            if _cache['gainers']:
                _cache['session'] = session
                return dict(_cache)

    raw = _fetch_polygon_snapshot()
    gainers = _enrich_snapshot_tickers(raw)
    gainers = enrich_gainers_with_sparklines_and_history(gainers)

    if not gainers:
        log.info("[LiveScreener] Live fetch returned 0 gainers, falling back to DB.")
        gainers = _load_fallback_gainers_from_db()

    # ── Phase 1 catalyst classification (lightweight, no I/O) ──────────────
    try:
        from services.pump_classifier import stamp_catalyst_tags
        gainers = stamp_catalyst_tags(gainers)
    except Exception as _e:
        log.warning(f"[LiveScreener] Catalyst tagging failed: {_e}")

    with _cache_lock:
        _cache['raw_tickers']  = [t.get('ticker', '') for t in raw] if raw else []
        _cache['gainers']      = gainers[:TOP_N]
        _cache['fetched_at']   = datetime.utcnow()
        _cache['session']      = session
        return dict(_cache)


def get_live_gainers(force: bool = False) -> dict:
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
    snap = refresh_cache(force=force)
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
            log.exception(f"[LiveScreener] Auto-persist loop error: {e}")
            time.sleep(60)


def _background_refresh_loop():
    """Background thread: refreshes the live screener cache every 60 seconds during active sessions."""
    log.info("[LiveScreener] Background cache refresh loop started")
    
    # Wait 2 seconds before the first refresh to let the app start up cleanly
    time.sleep(2)
    
    consecutive_failures = 0
    alerted_failure_state = False

    def handle_loop_failure(error_msg: str):
        nonlocal consecutive_failures, alerted_failure_state
        consecutive_failures += 1
        log.exception(f"[LiveScreener] Background cache refresh failed (consecutive: {consecutive_failures})")
        if consecutive_failures >= 3 and not alerted_failure_state:
            try:
                from fastapi_app.tasks.alerts import send_telegram_message
                alert_text = (
                    "⚠️ *[System Warning]* ⚠️\n\n"
                    "Live Screener cache refresh loop is failing consecutively!\n"
                    f"- *Consecutive Failures:* {consecutive_failures}\n"
                    f"- *Last Error:* {error_msg}\n"
                    "- *Action:* Check logs at `/var/log/trading-journal/fastapi-err.log`."
                )
                send_telegram_message(alert_text)
                alerted_failure_state = True
            except Exception as alert_err:
                log.error(f"Failed to send Telegram alert: {alert_err}")

    # Run initial cache refresh on startup so cache is populated immediately
    try:
        log.info("[LiveScreener] Running initial cache refresh on startup...")
        refresh_cache(force=True)
        consecutive_failures = 0
        alerted_failure_state = False
    except Exception as e:
        handle_loop_failure(str(e))

    while True:
        try:
            time.sleep(CACHE_TTL_SECONDS)
            now_et = datetime.now(EASTERN)
            session = get_market_session(now_et)
            
            # Refresh if market is active (pre-market, open, post-market)
            # If closed, we don't need to refresh because EOD data is static.
            if session != 'closed':
                log.info(f"[LiveScreener] Auto-refreshing live cache (session: {session})...")
                refresh_cache(force=True)
                
                # Successful refresh! Reset failure states.
                if consecutive_failures > 0:
                    log.info(f"[LiveScreener] Cache refresh loop recovered after {consecutive_failures} failures.")
                    if alerted_failure_state:
                        try:
                            from fastapi_app.tasks.alerts import send_telegram_message
                            send_telegram_message("✅ *[System Recovery]*\n\nLive Screener cache refresh loop has recovered and is now running normally.")
                        except Exception:
                            pass
                    consecutive_failures = 0
                    alerted_failure_state = False
        except Exception as e:
            handle_loop_failure(str(e))


def start_auto_persist():
    """
    Launch the EOD auto-persist background thread, the live cache refresh loop,
    and the news enrichment loop.
    """
    # 1. EOD persist watchdog
    t = threading.Thread(target=_auto_persist_loop, name='live-screener-persist', daemon=True)
    t.start()
    log.info("[LiveScreener] Auto-persist thread launched")

    # 2. Live cache refresh loop
    t_refresh = threading.Thread(target=_background_refresh_loop, name='live-screener-refresh', daemon=True)
    t_refresh.start()
    log.info("[LiveScreener] Background cache refresh thread launched")

    # 3. Phase 2: background news verification loop (every 3 min during market hours)
    try:
        from services.pump_classifier import start_news_enrichment_loop

        def _get_current_gainers() -> list[dict]:
            """Return live reference to cached gainers for in-place mutation."""
            with _cache_lock:
                return _cache['gainers']

        start_news_enrichment_loop(_get_current_gainers, interval_seconds=180)
    except Exception as e:
        log.warning(f"[LiveScreener] Failed to start news enrichment loop: {e}")
