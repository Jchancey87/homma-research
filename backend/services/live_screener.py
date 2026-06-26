"""
Live Gainer Screener — flat, clean pipeline.

Data flow:
  1. _fetch_candidates()  — Schwab Movers (primary) + TradingView (enrichment)
  2. _fetch_quotes()      — bulk Schwab quotes for real-time price/vol/spread
  3. _filter_and_rank()   — apply screening filters, sort by gap_pct desc
  4. _enrich_ticker()     — per-ticker: minute candles → mom_2m, VWAP, ATR, sparkline
  5. refresh_cache()      — assembles result, writes to _cache

Market session labels (Eastern time):
  PRE_MARKET   04:00 – 09:29
  OPEN         09:30 – 15:59
  AFTER_HOURS  16:00 – 19:59
  CLOSED       20:00 – 03:59
"""

import threading
import time
import logging
import concurrent.futures
from datetime import datetime, date as date_cls
from typing import Optional, List, Dict

import pytz

from validation import EASTERN_TZ

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
EASTERN          = EASTERN_TZ
CACHE_TTL_SECONDS = 15       # Background refresh interval
PERSIST_HOUR_ET  = 20        # 8 PM ET — trigger EOD persist
PERSIST_MINUTE_ET = 0

# Screening thresholds
MIN_GAP_PCT    = 5.0          # % gain vs prev close
MIN_PRICE      = 0.50         # floor price
MAX_PRICE      = 100.00       # ceiling price
TOP_N          = 25           # rows returned to frontend
ENRICH_WORKERS = 12           # parallel threads for minute-bar enrichment

# ── In-process state ───────────────────────────────────────────────────────────
_cache_lock = threading.RLock()
_cache: dict = {
    'gainers':         [],
    'fetched_at':      None,
    'session':         None,
    'persisted_dates': set(),
}

# Per-ticker caches (avoid re-fetching within short windows)
_minute_cache: Dict[str, tuple] = {}   # ticker -> (ts, metrics_dict)
_minute_cache_lock = threading.Lock()
_daily_cache: Dict[str, tuple]  = {}   # ticker -> (ts, data_dict)
_daily_cache_lock  = threading.Lock()

_last_auth_alert_ts = 0.0
_auth_alert_lock    = threading.Lock()

_last_session: str  = 'closed'   # Track session transitions for cache flushing
_session_lock       = threading.Lock()

# Maximum age (seconds) for a candle to be valid for mom_2m calculation.
# If the best-matching candle is older than this, mom_2m is set to None.
MAX_MOM_CANDLE_AGE_S = 300   # 5 minutes


# ── Market session ─────────────────────────────────────────────────────────────

def get_market_session(now_et: Optional[datetime] = None) -> str:
    if now_et is None:
        now_et = datetime.now(EASTERN)
    if now_et.weekday() >= 5:
        return 'closed'
    hm = now_et.hour * 60 + now_et.minute
    if   4 * 60 <= hm < 9 * 60 + 30:  return 'pre_market'
    elif 9 * 60 + 30 <= hm < 16 * 60: return 'open'
    elif 16 * 60 <= hm < 20 * 60:     return 'after_hours'
    else:                               return 'closed'

def get_session_label(session: str) -> str:
    return {
        'pre_market':  '🌅 Pre-Market',
        'open':        '🟢 Market Open',
        'after_hours': '🌙 After-Hours',
        'closed':      '⏸ Market Closed',
    }.get(session, session)


# ── Step 1: Candidate discovery ────────────────────────────────────────────────

def _fetch_schwab_movers() -> Dict[str, dict]:
    """Pull top movers from Schwab (NASDAQ, NYSE, EQUITY_ALL). Real-time, no lag."""
    from services.schwab_client import get_movers
    candidates = {}
    for exch in ['NASDAQ', 'NYSE', 'EQUITY_ALL']:
        try:
            for m in get_movers(exch):
                sym = (m.get('symbol') or '').upper()
                if not sym or len(sym) > 5:
                    continue
                change = round((m.get('netPercentChange') or 0) * 100, 2)
                if sym not in candidates or abs(change) > abs(candidates[sym]['change']):
                    candidates[sym] = {
                        'change':      change,
                        'price':       m.get('lastPrice') or 0,
                        'volume':      m.get('volume') or 0,
                        'float_shares': None,
                        'market_cap':  None,
                        'sector':      None,
                    }
        except Exception as e:
            log.warning(f"[Screener] Schwab movers {exch} failed: {e}")
    log.info(f"[Screener] Schwab movers: {len(candidates)} candidates")
    return candidates


def _fetch_tradingview_candidates() -> Dict[str, dict]:
    """Pull gainers from TradingView for float/sector/market_cap metadata."""
    import requests
    url     = "https://scanner.tradingview.com/america/scan"
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    candidates = {}

    scans = [
        ("regular",   "change",           "close",           "volume",           ["change","close","volume","market_cap_basic","float_shares_outstanding","sector"]),
        ("premarket",  "premarket_change", "premarket_close", "premarket_volume", ["premarket_change","premarket_close","premarket_volume","market_cap_basic","float_shares_outstanding","sector"]),
        ("postmarket", "postmarket_change","postmarket_close","postmarket_volume",["postmarket_change","postmarket_close","postmarket_volume","market_cap_basic","float_shares_outstanding","sector"]),
    ]

    for label, change_col, price_col, vol_col, cols in scans:
        payload = {
            "filter": [
                {"left": change_col, "operation": "greater", "right": 5},
                {"left": vol_col,    "operation": "greater", "right": 5000},
                {"left": "type",     "operation": "in_range","right": ["stock","dr","fund"]},
            ],
            "options": {"active_symbols_only": True},
            "markets": ["america"],
            "symbols": {"query": {"types": []}},
            "sort":    {"sortBy": change_col, "sortOrder": "desc"},
            "columns": ["name"] + cols,
            "range":   [0, 150],
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=10)
            if r.status_code != 200:
                log.warning(f"[Screener] TradingView {label} HTTP {r.status_code}")
                continue
            for row in r.json().get("data", []):
                d   = row.get("d", [])
                sym = (d[0] or '').upper() if d else ''
                if not sym or len(sym) > 5:
                    continue
                change = d[1] or 0
                price  = d[2] or 0
                volume = d[3] or 0
                mcap   = d[4]
                flt    = d[5]
                sector = d[6] if len(d) > 6 else None
                if sym not in candidates or abs(change) > abs(candidates[sym]['change']):
                    candidates[sym] = {
                        'change':      change,
                        'price':       price,
                        'volume':      volume,
                        'float_shares': flt,
                        'market_cap':  mcap,
                        'sector':      sector,
                    }
        except Exception as e:
            log.warning(f"[Screener] TradingView {label} error: {e}")

    log.info(f"[Screener] TradingView: {len(candidates)} candidates")
    return candidates


def _merge_candidates(schwab: dict, tv: dict) -> Dict[str, dict]:
    """
    Merge Schwab (primary) with TradingView (enrichment).
    TV never overwrites Schwab change/price unless TV's % is strictly higher.
    TV always fills missing float/sector/market_cap.
    """
    merged = dict(schwab)
    for sym, tv_data in tv.items():
        if sym not in merged:
            merged[sym] = tv_data
        else:
            c = merged[sym]
            # Always fill metadata gaps
            if c.get('float_shares') is None: c['float_shares'] = tv_data.get('float_shares')
            if c.get('market_cap')   is None: c['market_cap']   = tv_data.get('market_cap')
            if c.get('sector')       is None: c['sector']       = tv_data.get('sector')
            # Only upgrade change if TV is meaningfully higher
            if abs(tv_data.get('change', 0) or 0) > abs(c.get('change', 0) or 0):
                c['change'] = tv_data['change']
    return merged


def _fetch_watchlist_tickers() -> List[str]:
    """Fetch pinned watchlist tickers from DB (always included in quote fetch)."""
    try:
        from database import get_connection
        with get_connection() as conn:
            rows = conn.execute("SELECT ticker FROM watchlist").fetchall()
            return [r['ticker'].upper() for r in rows if r.get('ticker')]
    except Exception as e:
        log.warning(f"[Screener] Watchlist fetch failed: {e}")
        return []


# ── Step 2: Bulk quote fetch ───────────────────────────────────────────────────

def _fetch_quotes(symbols: List[str]) -> Dict[str, dict]:
    """Fetch Schwab quotes in chunks of 50. Returns {sym: quote_dict}."""
    from services.schwab_client import get_quotes
    all_quotes = {}
    for i in range(0, len(symbols), 50):
        chunk = symbols[i:i+50]
        try:
            all_quotes.update(get_quotes(chunk))
        except Exception as e:
            log.warning(f"[Screener] Quote chunk {chunk[:3]}… failed: {e}")
    return all_quotes


# ── Step 3: Filter & rank ──────────────────────────────────────────────────────

def _build_gainer_rows(quotes: Dict[str, dict], candidate_meta: Dict[str, dict],
                        watchlist: set) -> List[dict]:
    """
    Build flat gainer dicts from live Schwab quotes + candidate metadata.
    Applies price and gap filters. Always includes watchlist tickers (no filter).
    """
    rows = []
    for sym, data in quotes.items():
        q    = data.get('quote', {}) or {}
        fund = data.get('fundamental', {}) or {}
        meta = candidate_meta.get(sym, {})

        last_price = q.get('lastPrice')
        prev_close = q.get('closePrice')  # previous session close from Schwab

        if not last_price or not prev_close or prev_close <= 0:
            if sym not in watchlist:
                continue
            # watchlist tickers kept even with incomplete data
            gap_pct = 0.0
        else:
            gap_pct = round(((last_price - prev_close) / prev_close) * 100, 2)

        in_watchlist = sym in watchlist

        # Price filter (skip for watchlist)
        if not in_watchlist:
            if last_price < MIN_PRICE or last_price > MAX_PRICE:
                continue
            if gap_pct < MIN_GAP_PCT:
                continue

        high_price = q.get('highPrice') or last_price
        open_price = q.get('openPrice')
        low_price  = q.get('lowPrice')
        ask        = q.get('askPrice')
        bid        = q.get('bidPrice')
        total_vol  = q.get('totalVolume') or meta.get('volume') or 0
        avg_vol    = fund.get('avg10DaysVolume') or fund.get('avg1YearVolume') or 0
        rvol       = round(total_vol / avg_vol, 2) if avg_vol and avg_vol > 0 else None
        spread_pct = round(((ask - bid) / bid) * 100, 2) if ask and bid and bid > 0 else None
        is_hod     = (last_price >= high_price * 0.995) if high_price and high_price > 0 else False

        rows.append({
            'ticker':        sym,
            'gap_pct':       gap_pct,
            'last_price':    round(last_price, 4) if last_price else None,
            'high_price':    round(high_price, 4) if high_price else None,
            'low_price':     round(low_price, 4) if low_price else None,
            'open_price':    round(open_price, 4) if open_price else None,
            'prev_close':    round(prev_close, 4) if prev_close else None,
            'volume':        int(total_vol),
            'rvol_15m':      rvol,
            'float_shares':  meta.get('float_shares'),
            'market_cap':    meta.get('market_cap'),
            'sector':        meta.get('sector'),
            'ask':           ask,
            'bid':           bid,
            'spread_pct':    spread_pct,
            'is_hod':        is_hod,
            'in_watchlist':  in_watchlist,
            'news_headline': None,
            'news_fresh':    None,
        })

    # Sort: watchlist first, then by gap_pct descending
    rows.sort(key=lambda x: (not x['in_watchlist'], -x['gap_pct']))
    return rows


# ── Step 4: Per-ticker minute-level enrichment ─────────────────────────────────

def _compute_minute_metrics(ticker: str, last_price: Optional[float],
                             high_price: Optional[float],
                             bid: Optional[float], ask: Optional[float]) -> dict:
    """
    Fetch intraday 1-min candles and compute:
      - mom_2m  : % change from close of candle nearest to 2 min ago → current price
      - vwap    : volume-weighted average price (intraday)
      - atr_14  : 14-period average true range
      - atr_hod : distance to HOD in ATR units
      - atr_sprd: bid-ask spread in ATR units
      - atr_vwap: distance to VWAP in ATR units
      - zen_v   : 5-candle price slope / ATR (momentum direction indicator)
      - intraday_sparkline: sampled list of closes (max 30 points)
    """
    now = time.time()

    # 30-second cache — return stale data with fresh price updates applied inline
    with _minute_cache_lock:
        if ticker in _minute_cache:
            ts, cached = _minute_cache[ticker]
            if now - ts < 30:
                if last_price is not None:
                    # Refresh price-derived fields without a full re-fetch
                    atr = cached.get('atr_14') or 0
                    if atr > 0:
                        if high_price is not None:
                            cached['atr_hod']  = round(max(0, (high_price - last_price) / atr), 2)
                        if bid is not None and ask is not None:
                            cached['atr_sprd'] = round((ask - bid) / atr, 2)
                        if cached.get('vwap') is not None:
                            cached['atr_vwap'] = round((last_price - cached['vwap']) / atr, 2)
                    # Update mom_2m inline with cached base price
                    base = cached.get('price_2min_ago')
                    if base and base > 0:
                        cached['mom_2m'] = round(((last_price - base) / base) * 100, 2)
                    # Append latest price to sparkline tail
                    if cached.get('intraday_sparkline'):
                        cached['intraday_sparkline'][-1] = last_price
                    if cached.get('sparkline_1h'):
                        cached['sparkline_1h'][-1] = last_price
                return cached

    try:
        from services.schwab_client import get_minute_bars
        candles = get_minute_bars(ticker)
    except Exception as e:
        log.warning(f"[Screener] get_minute_bars({ticker}) failed: {e}")
        candles = []

    empty = {
        'mom_2m': None, 'price_2min_ago': None,
        'atr_14': None, 'vwap': None,
        'atr_hod': None, 'atr_sprd': None, 'atr_vwap': None,
        'zen_v': None, 'intraday_sparkline': [], 'sparkline_1h': [], 'hod': high_price or last_price,
    }

    if not candles:
        with _minute_cache_lock:
            _minute_cache[ticker] = (now, empty)
        return empty

    curr_p = last_price if last_price is not None else (candles[-1].get('c') or 0.0)

    # ── ATR(14) ──
    tr_vals = []
    for i in range(1, len(candles)):
        h = candles[i].get('h') or candles[i].get('c') or 0
        l = candles[i].get('l') or candles[i].get('c') or 0
        pc = candles[i-1].get('c') or 0
        if h and l and pc:
            tr_vals.append(max(h - l, abs(h - pc), abs(l - pc)))
    periods = min(14, len(tr_vals))
    atr = (sum(tr_vals[-periods:]) / periods) if periods > 0 else (curr_p * 0.001 or 0.001)

    # ── mom_2m: find candle closest to 2 min ago, use its close as base ──
    now_ms     = int(time.time() * 1000)
    target_ts  = now_ms - 120_000   # exactly 2 minutes ago
    best       = min(candles, key=lambda c: abs((c.get('t') or 0) - target_ts))
    best_ts    = best.get('t') or 0
    candle_age_s = abs(now_ms - best_ts) / 1000.0 if best_ts else float('inf')

    # Guard: if the closest candle is too far from the 2-min-ago target,
    # it's stale data (e.g. yesterday's candles at morning start).
    if candle_age_s > MAX_MOM_CANDLE_AGE_S:
        price_2min_ago = None
        mom_2m = None
        log.debug(f"[Screener] {ticker}: best candle for mom_2m is {candle_age_s:.0f}s old — marking as None")
    else:
        price_2min_ago = best.get('c')
        mom_2m = 0.0
        if price_2min_ago and price_2min_ago > 0 and curr_p:
            mom_2m = round(((curr_p - price_2min_ago) / price_2min_ago) * 100, 2)

    # ── VWAP (intraday, cumulative) ──
    total_vol = sum(c.get('v') or 0 for c in candles)
    if total_vol > 0:
        sum_pv = sum(
            ((c.get('h') or c.get('c') or 0) + (c.get('l') or c.get('c') or 0) + (c.get('c') or 0)) / 3
            * (c.get('v') or 0)
            for c in candles
        )
        vwap = sum_pv / total_vol
    else:
        vwap = curr_p

    # ── ZenV: 5-candle linear slope / ATR ──
    zen_v = 0.0
    n = min(5, len(candles))
    if n >= 2:
        y = [c.get('c') or 0.0 for c in candles[-n:]]
        xs = list(range(1, n + 1))
        sx  = sum(xs)
        sx2 = sum(x * x for x in xs)
        sy  = sum(y)
        sxy = sum(xs[i] * y[i] for i in range(n))
        denom = n * sx2 - sx * sx
        slope = (n * sxy - sx * sy) / denom if denom > 0 else 0.0
        zen_v = round(slope / atr, 2) if atr > 0 else 0.0

    # ── ATR distances ──
    candle_hod = max((c.get('h') or c.get('c') or 0) for c in candles)
    hod        = max(high_price or 0, candle_hod, curr_p)
    atr_hod    = round(max(0, (hod - curr_p) / atr), 2) if atr > 0 else 0.0
    atr_sprd   = round((ask - bid) / atr, 2) if atr > 0 and bid is not None and ask is not None else None
    atr_vwap   = round((curr_p - vwap) / atr, 2) if atr > 0 else 0.0

    # ── Intraday sparkline (≤30 sampled close prices) ──
    closes = [c.get('c') for c in candles if c.get('c') is not None]
    if len(closes) > 30:
        sparkline = [closes[int(i * (len(closes) - 1) / 29)] for i in range(30)]
    else:
        sparkline = list(closes)
    if sparkline and curr_p:
        sparkline[-1] = curr_p

    # ── Sparkline of the last 1 hour (minute data, up to 60 points) ──
    one_hour_ago_ms = now_ms - 3_600_000
    last_1h_candles = [c for c in candles if (c.get('t') or 0) >= one_hour_ago_ms]
    if not last_1h_candles:
        last_1h_candles = candles[-60:]
    closes_1h = [c.get('c') for c in last_1h_candles if c.get('c') is not None]
    if len(closes_1h) > 60:
        sparkline_1h = [closes_1h[int(i * (len(closes_1h) - 1) / 59)] for i in range(60)]
    else:
        sparkline_1h = list(closes_1h)
    if sparkline_1h and curr_p:
        sparkline_1h[-1] = curr_p

    metrics = {
        'mom_2m':            mom_2m,
        'price_2min_ago':    price_2min_ago,
        'atr_14':            atr,
        'vwap':              vwap,
        'atr_hod':           atr_hod,
        'atr_sprd':          atr_sprd,
        'atr_vwap':          atr_vwap,
        'zen_v':             zen_v,
        'intraday_sparkline': sparkline,
        'sparkline_1h':      sparkline_1h,
        'hod':               hod,
    }

    with _minute_cache_lock:
        _minute_cache[ticker] = (now, metrics)
    return metrics


def _compute_daily_metrics(ticker: str) -> dict:
    """Fetch daily candles, compute SMA20/50/100 and 5-day sparkline. 1-hour cache."""
    now = time.time()
    with _daily_cache_lock:
        if ticker in _daily_cache:
            ts, data = _daily_cache[ticker]
            if now - ts < 3600:
                return data

    empty = {'sparkline_5d': [], 'sma20': None, 'sma50': None, 'sma100': None}
    try:
        from services.schwab_client import get_price_history_every_day
        raw = get_price_history_every_day(ticker)
        closes = [c.get('close') for c in raw if c.get('close') is not None]
        if not closes:
            data = empty
        else:
            def sma(n): return round(sum(closes[-n:]) / n, 2) if len(closes) >= n else None
            data = {
                'sparkline_5d': closes[-5:],
                'sma20':  sma(20),
                'sma50':  sma(50),
                'sma100': sma(100),
            }
    except Exception as e:
        log.warning(f"[Screener] Daily metrics for {ticker} failed: {e}")
        data = empty

    with _daily_cache_lock:
        _daily_cache[ticker] = (now, data)
    return data


def _enrich_ticker(g: dict) -> dict:
    """Apply minute-level and daily metrics to a gainer row in-place. Returns g."""
    ticker     = g['ticker']
    last_price = g.get('last_price')
    high_price = g.get('high_price')
    bid        = g.get('bid')
    ask        = g.get('ask')

    # Minute metrics
    mm = _compute_minute_metrics(ticker, last_price, high_price, bid, ask)
    g['mom_2m']            = mm['mom_2m']
    g['atr_hod']           = mm['atr_hod']
    g['atr_sprd']          = mm['atr_sprd']
    g['atr_vwap']          = mm['atr_vwap']
    g['zen_v']             = mm['zen_v']
    g['vwap']              = round(mm['vwap'], 4) if mm.get('vwap') else None
    g['sparkline_intraday'] = mm['intraday_sparkline']
    g['sparkline_1h'] = mm['sparkline_1h']
    if mm.get('hod'):
        g['high_price'] = round(mm['hod'], 4)

    # Daily metrics
    dm = _compute_daily_metrics(ticker)
    live = last_price
    sparkline = dm['sparkline_5d']
    if live is not None and sparkline:
        sparkline = sparkline[-4:] + [live]
    g['sparkline_5d'] = sparkline
    g['sma20']        = dm['sma20']
    g['sma50']        = dm['sma50']
    g['sma100']       = dm['sma100']
    g['above_sma20']  = (live > dm['sma20'])  if live and dm['sma20']  else False
    g['above_sma50']  = (live > dm['sma50'])  if live and dm['sma50']  else False
    g['above_sma100'] = (live > dm['sma100']) if live and dm['sma100'] else False

    return g


def _enrich_all(gainers: List[dict]) -> List[dict]:
    """Parallel enrichment of all gainers. Skips tickers that time out."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=ENRICH_WORKERS) as ex:
        futures = {ex.submit(_enrich_ticker, g): g for g in gainers}
        try:
            for fut in concurrent.futures.as_completed(futures, timeout=45):
                g = futures[fut]
                try:
                    fut.result()
                except Exception as e:
                    log.warning(f"[Screener] Enrich failed for {g['ticker']}: {e}")
        except concurrent.futures.TimeoutError:
            log.error("[Screener] Enrichment timed out — some tickers may be missing metrics")
    return gainers


def _check_repeat_history(tickers: List[str]) -> Dict[str, dict]:
    """Check if tickers appeared in daily_gainers previously (repeat runner / follow-through)."""
    try:
        from database import get_connection
        today_et = datetime.now(EASTERN).strftime('%Y-%m-%d')
        with get_connection() as conn:
            row = conn.execute("SELECT MAX(date) as d FROM daily_gainers WHERE date < %s", (today_et,)).fetchone()
            recent = row['d'] if row else None
            if not recent:
                return {}
            rows = conn.execute(
                """SELECT ticker,
                          COUNT(*) as total,
                          SUM(CASE WHEN date = %s THEN 1 ELSE 0 END) as yesterday
                   FROM daily_gainers
                   WHERE ticker = ANY(%s) AND date < %s
                   GROUP BY ticker""",
                (recent, list(tickers), today_et)
            ).fetchall()
            return {r['ticker']: {
                'is_repeat_runner':   r['total'] > 0,
                'is_follow_through':  r['yesterday'] > 0,
            } for r in rows}
    except Exception as e:
        log.warning(f"[Screener] Repeat history check failed: {e}")
        return {}


# ── Main refresh pipeline ──────────────────────────────────────────────────────

def refresh_cache(force: bool = False) -> dict:
    """
    Run the full screener pipeline and update the in-memory cache.
    If cache is fresh and force=False, returns immediately.
    """
    # Fast path: serve from cache
    if not force:
        with _cache_lock:
            if _cache['gainers']:
                return dict(_cache)

    # ── 1. Candidate discovery ──
    try:
        schwab_candidates = _fetch_schwab_movers()
    except Exception as e:
        log.error(f"[Screener] Schwab movers failed: {e}")
        schwab_candidates = {}

    try:
        tv_candidates = _fetch_tradingview_candidates()
    except Exception as e:
        log.warning(f"[Screener] TradingView candidates failed: {e}")
        tv_candidates = {}

    candidates = _merge_candidates(schwab_candidates, tv_candidates)

    watchlist = set(_fetch_watchlist_tickers())

    # Ensure watchlist tickers are in the quote-fetch pool
    for sym in watchlist:
        if sym not in candidates:
            candidates[sym] = {'change': 0, 'price': 0, 'volume': 0,
                                'float_shares': None, 'market_cap': None, 'sector': None}

    # Sort by absolute change descending, watchlist always first
    watchlist_syms = [s for s in candidates if s in watchlist]
    other_syms     = sorted(
        [s for s in candidates if s not in watchlist],
        key=lambda s: abs(candidates[s].get('change', 0) or 0),
        reverse=True
    )
    to_quote = watchlist_syms + other_syms[:150]

    # ── 2. Bulk quotes ──
    try:
        quotes = _fetch_quotes(to_quote)
    except Exception as e:
        log.error(f"[Screener] Quote fetch failed: {e}")
        quotes = {}

    # ── 3. Filter & rank ──
    gainers = _build_gainer_rows(quotes, candidates, watchlist)

    if not gainers:
        log.warning("[Screener] No gainers after filter — checking fallback DB")
        gainers = _load_fallback_from_db()

    # Limit before expensive enrichment
    gainers = gainers[:TOP_N * 2]

    # ── 4. Repeat-runner history ──
    history = _check_repeat_history([g['ticker'] for g in gainers])
    for g in gainers:
        h = history.get(g['ticker'], {})
        g['is_repeat_runner']  = h.get('is_repeat_runner', False)
        g['is_follow_through'] = h.get('is_follow_through', False)

    # ── 5. Per-ticker enrichment (minute metrics + daily SMAs) ──
    try:
        from services.schwab_client import get_http_client
        get_http_client()
        gainers = _enrich_all(gainers)
    except Exception as e:
        log.error(f"[Screener] Schwab unavailable for enrichment: {e}")
        _maybe_send_auth_alert(e)
        for g in gainers:
            g.update({
                'mom_2m': None, 'atr_hod': None, 'atr_sprd': None,
                'atr_vwap': None, 'zen_v': None, 'vwap': None,
                'sparkline_intraday': [], 'sparkline_5d': [], 'sparkline_1h': [],
                'sma20': None, 'sma50': None, 'sma100': None,
                'above_sma20': False, 'above_sma50': False, 'above_sma100': False,
            })

    # ── 6. Catalyst tags ──
    try:
        from services.pump_classifier import stamp_catalyst_tags
        gainers = stamp_catalyst_tags(gainers)
    except Exception as e:
        log.warning(f"[Screener] Catalyst tagging failed: {e}")

    session = get_market_session()
    with _cache_lock:
        _cache['gainers']    = gainers[:TOP_N]
        _cache['fetched_at'] = datetime.utcnow()
        _cache['session']    = session
        return dict(_cache)


def _maybe_send_auth_alert(err: Exception):
    global _last_auth_alert_ts
    now = time.time()
    with _auth_alert_lock:
        if now - _last_auth_alert_ts < 3600:
            return
        _last_auth_alert_ts = now
    try:
        from fastapi_app.tasks.alerts import send_telegram_message
        send_telegram_message(
            "🚨 *[Schwab Auth Failure]*\nLive screener enrichment failed — Schwab client unavailable.\n"
            f"Error: `{err}`\nRun `python schwab_auth_setup.py` to refresh token."
        )
    except Exception:
        pass


def _load_fallback_from_db() -> List[dict]:
    """Return last day's gainers from DB when live fetch yields nothing."""
    try:
        from database import get_connection
        today_et = datetime.now(EASTERN).strftime('%Y-%m-%d')
        with get_connection() as conn:
            row = conn.execute("SELECT MAX(date) as d FROM daily_gainers").fetchone()
            recent = row['d'] if row else None
            if not recent:
                return []
            rows = conn.execute(
                "SELECT * FROM daily_gainers WHERE date=%s AND gap_pct>=%s ORDER BY gap_pct DESC LIMIT %s",
                (recent, MIN_GAP_PCT, TOP_N)
            ).fetchall()
            gainers = []
            for r in rows:
                lp = r.get('close_price')
                hp = r.get('high_price')
                gainers.append({
                    'ticker':       r.get('ticker'),
                    'gap_pct':      r.get('gap_pct', 0),
                    'last_price':   lp,
                    'high_price':   hp,
                    'low_price':    None,
                    'open_price':   r.get('open_price'),
                    'prev_close':   r.get('prev_close'),
                    'volume':       int(r.get('volume') or 0),
                    'rvol_15m':     r.get('rvol_15m'),
                    'float_shares': r.get('float_shares'),
                    'market_cap':   r.get('market_cap'),
                    'sector':       r.get('sector'),
                    'ask': None, 'bid': None, 'spread_pct': None,
                    'is_hod': False, 'in_watchlist': False,
                    'news_headline': r.get('news_headline'),
                    'news_fresh':   r.get('news_fresh'),
                })
            return gainers
    except Exception as e:
        log.error(f"[Screener] Fallback DB load failed: {e}", exc_info=True)
        return []


# ── Public API ─────────────────────────────────────────────────────────────────

def get_live_gainers(force: bool = False) -> dict:
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


# ── Background threads ─────────────────────────────────────────────────────────

def _background_refresh_loop():
    log.info("[Screener] Background refresh loop started")
    time.sleep(2)
    failures = 0

    try:
        log.info("[Screener] Initial cache load...")
        refresh_cache(force=True)
        failures = 0
    except Exception as e:
        log.exception("[Screener] Initial refresh failed")

    while True:
        try:
            time.sleep(CACHE_TTL_SECONDS)
            session = get_market_session()

            # ── Session transition: flush per-ticker caches ──
            # This prevents stale yesterday data from leaking into
            # the first refresh of a new pre-market/open session.
            global _last_session
            with _session_lock:
                prev = _last_session
                _last_session = session
            if prev != session:
                log.info(f"[Screener] Session transition: {prev} → {session} — flushing per-ticker caches")
                with _minute_cache_lock:
                    _minute_cache.clear()
                with _daily_cache_lock:
                    _daily_cache.clear()

            if session != 'closed':
                log.info(f"[Screener] Auto-refresh (session={session})")
                refresh_cache(force=True)
                if failures > 0:
                    log.info(f"[Screener] Recovered after {failures} failures")
                failures = 0
        except Exception as e:
            failures += 1
            log.exception(f"[Screener] Refresh loop error (#{failures})")
            if failures == 3:
                try:
                    from fastapi_app.tasks.alerts import send_telegram_message
                    send_telegram_message(
                        f"⚠️ *[Screener]* Refresh loop failing (#{failures})\n`{e}`"
                    )
                except Exception:
                    pass


def _auto_persist_loop():
    log.info("[Screener] Auto-persist watchdog started")
    while True:
        try:
            now_et = datetime.now(EASTERN)
            today  = now_et.strftime('%Y-%m-%d')
            if now_et.weekday() < 5:
                hm = now_et.hour * 60 + now_et.minute
                target_hm = PERSIST_HOUR_ET * 60 + PERSIST_MINUTE_ET
                with _cache_lock:
                    done = today in _cache['persisted_dates']
                if hm >= target_hm and not done:
                    _do_persist(today)
            time.sleep(60)
        except Exception:
            log.exception("[Screener] Auto-persist loop error")
            time.sleep(60)


def _do_persist(target_date: str):
    log.info(f"[Screener] Starting EOD persist for {target_date}")
    try:
        from jobs.ingest_gainers import fetch_gainers, write_gainers
        gainers = fetch_gainers(target_date)
        if gainers:
            inserted, skipped = write_gainers(gainers, target_date)
            log.info(f"[Screener] EOD persist done — inserted={inserted} skipped={skipped}")
        else:
            log.warning("[Screener] EOD persist: no qualified gainers")
    except Exception:
        log.exception(f"[Screener] EOD persist failed for {target_date}")
    with _cache_lock:
        _cache['persisted_dates'].add(target_date)


def start_auto_persist():
    """Launch background refresh, EOD persist, and news enrichment threads."""
    threading.Thread(target=_auto_persist_loop,     name='screener-persist', daemon=True).start()
    threading.Thread(target=_background_refresh_loop, name='screener-refresh', daemon=True).start()
    log.info("[Screener] Background threads launched")

    try:
        from services.pump_classifier import start_news_enrichment_loop
        def _current_gainers():
            with _cache_lock:
                return _cache['gainers']
        start_news_enrichment_loop(_current_gainers, interval_seconds=180)
    except Exception as e:
        log.warning(f"[Screener] News enrichment loop failed to start: {e}")
