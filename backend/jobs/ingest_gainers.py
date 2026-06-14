#!/usr/bin/env python3
"""
Post-close gainer ingestion job.
Triggered by cron at 4:15 PM ET Mon–Fri:
  15 16 * * 1-5 /opt/trading-journal/venv/bin/python /opt/trading-journal/backend/jobs/ingest_gainers.py

Can also be run manually:
  python ingest_gainers.py --date 2026-05-01
  python ingest_gainers.py --dry-run

Data source strategy:
  - Polygon Snapshot API  → top gainers ticker list (incl. extended hours)
  - Polygon Grouped Daily → OHLCV, volume, gap calculation
  - Polygon News API      → news headline
  - FMP /profile          → float_shares, sector (250 calls/day; cached 7 days)
  - yfinance              → float fallback ONLY if FMP returns None
"""
import sys
import os
import argparse
import logging
from datetime import date as date_cls, datetime, timedelta

# Allow imports from backend/ and repo root
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from config import Config
from services.schwab_client import get_gainers_snapshot, get_daily_bars, get_latest_headline, get_price_history_every_minute, get_price_history_every_day

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Screening criteria constants
# ---------------------------------------------------------------------------
MIN_GAP_PCT    = 5.0    # Show anything > 5% gap
MAX_FLOAT_M    = 500.0  # < 500M shares
MIN_RVOL       = 2.0    # > 2x RVOL
MIN_PRICE      = 0.10   # >= $0.10
MAX_PRICE      = 100.00 # <= $100
MAX_MARKET_CAP = 10_000e6 # < $10B

POLYGON_SNAPSHOT_LIMIT = 50   # tickers to pull from Polygon gainers snapshot


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main():
    import pytz
    eastern = pytz.timezone('US/Eastern')
    ny_now  = datetime.now(eastern)

    parser = argparse.ArgumentParser(description='Ingest daily top gainers')
    parser.add_argument('--date',    default=ny_now.strftime('%Y-%m-%d'), help='YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='Fetch data but do not write to DB')
    args = parser.parse_args()

    target_date = args.date
    dry_run     = args.dry_run

    log.info(f"Starting ingestion for {target_date} (NY Time: {ny_now.strftime('%Y-%m-%d %H:%M:%S %Z')})")

    gainers = fetch_gainers(target_date)
    log.info(f"Found {len(gainers)} qualified gainers")

    if not gainers:
        log.warning("No gainers met criteria — exiting")
        return

    if dry_run:
        for g in gainers:
            log.info(f"  DRY RUN: {g}")
        return

    inserted, skipped = write_gainers(gainers, target_date)
    log.info(f"Done — inserted={inserted}, skipped (duplicate)={skipped}")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def fetch_gainers(target_date: str) -> list[dict]:
    """
    Full enrichment pipeline:
      1. Polygon Snapshot → ticker list
      2. Polygon Grouped Daily → OHLCV for all tickers in one call
      3. FMP profile → float, sector (yfinance fallback for float)
      4. Polygon News → headline
      5. Filter and return qualified gainers
    """
    # Step 1 — ticker candidates from Polygon snapshot
    raw_snapshot = _get_polygon_snapshot()
    if not raw_snapshot:
        log.error("Polygon snapshot returned no tickers — aborting")
        return []

    log.info(f"Polygon snapshot: {len(raw_snapshot)} tickers")

    # Step 2 — Schwab "grouped" daily (stub, returns {})
    grouped = _get_schwab_grouped_daily(target_date)
    log.info(f"Schwab grouped daily: {len(grouped)} bars for {target_date}")

    # Step 3–5 — enrich each ticker
    gainers = []
    for snap in raw_snapshot:
        result = _enrich_ticker(snap, grouped, target_date)
        if result:
            gainers.append(result)

    # Sort descending by extended change percent
    gainers.sort(key=lambda x: x['extended_change_pct'], reverse=True)
    return gainers


# ---------------------------------------------------------------------------
# Step 1 — Polygon Snapshot (top gainers, extended hours aware)
# ---------------------------------------------------------------------------

def _get_polygon_snapshot() -> list[dict]:
    """Fetch top gainers from Polygon Snapshot API via the official SDK."""
    snaps = get_gainers_snapshot(include_otc=False)
    return snaps[:POLYGON_SNAPSHOT_LIMIT]


# ---------------------------------------------------------------------------
# Step 2 — Schwab Daily Bars (Per-ticker fallback)
# ---------------------------------------------------------------------------

def _get_schwab_grouped_daily(date: str) -> dict[str, dict]:
    """
    Schwab does not support broad grouped daily snapshots. 
    This is kept as a stub for the enrichment logic to check.
    """
    return {}


# ---------------------------------------------------------------------------
# Step 3 — Per-ticker enrichment
# ---------------------------------------------------------------------------

def _enrich_ticker(snap: dict, grouped: dict[str, dict], target_date: str) -> dict | None:
    """
    Build a fully enriched gainer row from:
      - Polygon snapshot   (live price, prev close, volume)
      - Polygon grouped daily (authoritative EOD OHLCV: O/H/L/C/V/VWAP)
      - SPY bar from grouped daily (RS vs SPY — zero extra API calls)
      - FMP profile        (float, sector, avg_volume — yfinance float fallback)
      - Polygon news       (latest headline)
    Returns None if the ticker doesn't meet screening criteria.
    """
    ticker = snap.get('ticker', '')
    if not ticker or len(ticker) > 5:
        return None

    # ── Price & Gap ────────────────────────────────────────────────────────
    # Snapshot fields vary by SDK version; support both dict and attr access.
    def _gf(obj, *keys):
        """Get first truthy value from a nested snapshot object/dict."""
        for k in keys:
            v = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
            if v:
                return v
        return None

    day_obj     = snap.get('day', {}) if isinstance(snap, dict) else getattr(snap, 'day', {})
    prev_obj    = snap.get('prevDay', {}) if isinstance(snap, dict) else getattr(snap, 'prevDay', {})
    last_trade_obj = snap.get('lastTrade', {}) if isinstance(snap, dict) else getattr(snap, 'lastTrade', {})
    day_obj     = day_obj or {}
    prev_obj    = prev_obj or {}
    last_trade_obj = last_trade_obj or {}

    prev_close = _gf(prev_obj, 'c', 'vw')
    last_price = _gf(last_trade_obj, 'p') or _gf(day_obj, 'c', 'vw')

    if not prev_close or not last_price or prev_close <= 0:
        return None

    # ── Gap & Change Pre-filter ────────────────────────────────────────────
    # Generous pre-filter: check if either the last price change or estimated gap change
    # is at least half of MIN_GAP_PCT.
    quick_gap = ((last_price - prev_close) / prev_close) * 100
    open_px_est = _gf(day_obj, 'o') or last_price
    approx_gap = ((open_px_est - prev_close) / prev_close) * 100
    if quick_gap < MIN_GAP_PCT * 0.5 and approx_gap < MIN_GAP_PCT * 0.5:
        return None

    # ── Price Filter ───────────────────────────────────────────────────────
    if last_price < MIN_PRICE or last_price > MAX_PRICE:
        return None

    # ── OHLCV from Grouped Daily (authoritative EOD bars) ─────────────────
    bar = grouped.get(ticker, {})
    if not bar:
        # Fallback: Fetch per-ticker daily bars from Schwab
        bars = get_daily_bars(ticker, target_date, target_date)
        if bars:
            bar = bars[-1] # use latest bar for that date
    
    open_px = bar.get('o') or _gf(day_obj, 'o') or prev_close
    high_px = bar.get('h') or _gf(day_obj, 'h')
    low_px  = bar.get('l') or _gf(day_obj, 'l')
    vwap    = bar.get('vw') or _gf(day_obj, 'vw')
    volume  = bar.get('v') or _gf(day_obj, 'v') or 0

    # ── Authoritative gap and extended change checks ─────────────────────
    gap_pct = round(((open_px - prev_close) / prev_close) * 100, 2)
    extended_change_pct = round(((last_price - prev_close) / prev_close) * 100, 2)
    if gap_pct < MIN_GAP_PCT and extended_change_pct < MIN_GAP_PCT:
        return None

    # ── FMP Profile → float, sector, avg_volume, shares_outstanding ────────
    float_shares, sector, market_cap, shares_out, avg_vol = _get_profile(ticker)

    if float_shares and float_shares > MAX_FLOAT_M * 1e6:
        return None
    if market_cap and market_cap > MAX_MARKET_CAP:
        return None

    # ── RVOL — use FMP avg_volume if available, else prev-day proxy ────────
    prev_vol = prev_obj.get('v') or 0
    rvol_base = avg_vol or prev_vol or 0
    rvol = round(volume / rvol_base, 2) if rvol_base > 0 else None
    if rvol is not None and rvol < MIN_RVOL:
        return None

    # ── Derived fields ─────────────────────────────────────────────────────
    dollar_volume = round(last_price * volume, 0) if volume else None

    # Close location: where in the day's range did it close? (1.0 = HOD, 0.0 = LOD)
    if high_px and low_px and high_px > low_px:
        close_location = round((last_price - low_px) / (high_px - low_px), 3)
    else:
        close_location = None

    # RS vs SPY: stock's move minus SPY's move on the same day (zero extra calls)
    spy_bar = grouped.get('SPY', {})
    if spy_bar and spy_bar.get('o') and spy_bar.get('c') and spy_bar['o'] > 0:
        spy_return = ((spy_bar['c'] - spy_bar['o']) / spy_bar['o']) * 100
        rs_vs_spy  = round(gap_pct - spy_return, 2)
    else:
        rs_vs_spy = None

    # ── News headline from NewsAggregator (YFinance fallback since Schwab has no news) ──
    try:
        from services.news_aggregator import get_default_aggregator
        aggregator = get_default_aggregator()
        articles   = aggregator.get_news(ticker, hours_back=24)
        headline   = articles[0]['title'] if articles else None
    except Exception as e:
        log.warning(f"Failed to fetch news headline for {ticker} via NewsAggregator: {e}")
        headline   = None

    news_fresh = _classify_news(headline)

    # ── Catalyst classification ──────────────────────────────────
    try:
        from services.pump_classifier import classify_catalyst
        _partial = {
            'news_headline': headline,
            'gap_pct':       gap_pct,
            'rvol_15m':      rvol,
        }
        catalyst = classify_catalyst(_partial)
    except Exception:
        catalyst = None

    try:
        metrics = _enrich_metrics(ticker, target_date)
    except Exception as e:
        log.warning(f"Failed to enrich metrics for {ticker}: {e}")
        metrics = {}

    return {
        'ticker':               ticker,
        'gap_pct':              gap_pct,
        'extended_change_pct':  extended_change_pct,
        'float_shares':         float_shares,
        'rvol_15m':             rvol,
        'sector':               sector,
        'market_cap':           market_cap,
        'news_headline':        headline,
        'news_fresh':           news_fresh,
        'catalyst':             catalyst,
        'close_price':          round(last_price, 4),
        'open_price':           round(open_px, 4),
        # new enrichment fields
        'high_price':           round(high_px, 4) if high_px else None,
        'low_price':            round(low_px, 4) if low_px else None,
        'prev_close':           round(prev_close, 4),
        'vwap':                 round(vwap, 4) if vwap else None,
        'dollar_volume':        dollar_volume,
        'close_location':       close_location,
        'rs_vs_spy':            rs_vs_spy,
        'shares_outstanding':   shares_out,
        'avg_volume':           avg_vol,
        **metrics
    }


# ---------------------------------------------------------------------------
# Profile — FMP primary, yfinance fallback for float
# ---------------------------------------------------------------------------

def _get_profile(ticker: str) -> tuple[float | None, str | None, float | None, float | None, float | None]:
    """
    Return (float_shares, sector, market_cap, shares_outstanding, avg_volume).

    Priority:
      1. FMP /profile  — primary source, covers most fields
      2. yfinance      — fallback for float, sector, market_cap, shares_outstanding, avg_volume
      3. None          — store null, display '—' in UI
    """
    from services.fmp_service import get_company_profile

    profile = get_company_profile(ticker)

    float_shares        = profile.get('float_shares')
    sector              = profile.get('sector') or profile.get('industry')
    market_cap          = profile.get('market_cap')
    shares_outstanding  = profile.get('shares_outstanding')
    avg_volume          = profile.get('avg_volume')

    # Fallback to yfinance if any key fields are missing from FMP/Schwab profile
    if float_shares is None or sector is None or market_cap is None or shares_outstanding is None or avg_volume is None:
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info or {}
            if float_shares is None:
                float_shares = info.get('floatShares')
            if sector is None:
                sector = info.get('sector') or info.get('industry')
            if market_cap is None:
                market_cap = info.get('marketCap')
            if shares_outstanding is None:
                shares_outstanding = info.get('sharesOutstanding')
            if avg_volume is None:
                avg_volume = info.get('averageVolume') or info.get('averageDailyVolume10Day')
            log.debug(f"[{ticker}] yfinance fallback used for missing profile fields")
        except Exception as e:
            log.warning(f"[{ticker}] yfinance fallback enrichment failed: {e}")

    return float_shares, sector, market_cap, shares_outstanding, avg_volume


def _yf_float_fallback(ticker: str) -> float | None:
    """
    Lightweight yfinance call for float shares only.
    Used exclusively as a fallback when FMP returns None.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return info.get('floatShares')
    except Exception as e:
        log.debug(f"[{ticker}] yfinance float fallback failed: {e}")
        return None


# (News fetching is now handled by services/schwab_client.py → get_latest_headline)


# ---------------------------------------------------------------------------
# News freshness classification (LLM)
# ---------------------------------------------------------------------------

def _classify_news(headline: str | None) -> bool:
    """Call LLM to classify news freshness. Returns False if LLM unavailable."""
    if not headline:
        return False
    try:
        from llm.llm_client import classify_news_fresh
        return classify_news_fresh(headline)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Schwab & YFinance Enrichment Metrics
# ---------------------------------------------------------------------------

def _enrich_metrics(ticker: str, target_date: str) -> dict:
    import datetime as dt_module
    from datetime import datetime, timedelta
    import pandas as pd
    import yfinance as yf
    
    metrics = {
        'premarket_high': None,
        'premarket_low': None,
        'premarket_volume': None,
        'pct_above_vwap': None,
        'atr_14': None,
        'sma_20': None,
        'sma_50': None,
        'cash': None,
        'net_income': None,
        'operating_cash_flow': None,
        'runway_months': None,
        'dilution_risk': 'Low'
    }
    
    # 1. Schwab 1-min history
    try:
        start_dt = datetime.strptime(target_date, '%Y-%m-%d')
        end_dt = start_dt + timedelta(days=1)
        min_candles = get_price_history_every_minute(ticker, start_datetime=start_dt, end_datetime=end_dt)
        if min_candles:
            df_min = pd.DataFrame(min_candles)
            if not df_min.empty:
                df_min['dt'] = df_min['datetime'].apply(lambda ts: datetime.fromtimestamp(ts / 1000.0, tz=dt_module.timezone.utc).astimezone(dt_module.timezone(dt_module.timedelta(hours=-4))))
                
                pre_df = df_min[df_min['dt'].dt.time < dt_module.time(9, 30)]
                reg_df = df_min[(df_min['dt'].dt.time >= dt_module.time(9, 30)) & (df_min['dt'].dt.time <= dt_module.time(16, 0))]
                
                if not pre_df.empty:
                    metrics['premarket_high'] = float(pre_df['high'].max())
                    metrics['premarket_low'] = float(pre_df['low'].min())
                    metrics['premarket_volume'] = float(pre_df['volume'].sum())
                    
                if not reg_df.empty:
                    reg_df['typical_price'] = (reg_df['high'] + reg_df['low'] + reg_df['close']) / 3
                    total_vp = (reg_df['typical_price'] * reg_df['volume']).sum()
                    total_v = reg_df['volume'].sum()
                    vwap_val = total_vp / total_v if total_v > 0 else None
                    if vwap_val:
                        above_vwap_count = (reg_df['close'] > vwap_val).sum()
                        metrics['pct_above_vwap'] = float(above_vwap_count / len(reg_df))
    except Exception as e:
        log.warning(f"[{ticker}] failed to enrich 1-min metrics: {e}")
        
    # 2. Schwab Daily history (for ATR and SMA)
    try:
        daily_candles = get_price_history_every_day(ticker)
        if daily_candles:
            df_daily = pd.DataFrame(daily_candles)
            if not df_daily.empty:
                df_daily['prev_close'] = df_daily['close'].shift(1)
                df_daily['h_l'] = df_daily['high'] - df_daily['low']
                df_daily['h_pc'] = (df_daily['high'] - df_daily['prev_close']).abs()
                df_daily['l_pc'] = (df_daily['low'] - df_daily['prev_close']).abs()
                df_daily['tr'] = df_daily[['h_l', 'h_pc', 'l_pc']].max(axis=1)
                
                df_daily['atr_14'] = df_daily['tr'].rolling(window=14).mean()
                df_daily['sma_20'] = df_daily['close'].rolling(window=20).mean()
                df_daily['sma_50'] = df_daily['close'].rolling(window=50).mean()
                
                latest = df_daily.iloc[-1]
                metrics['atr_14'] = float(latest['atr_14']) if not pd.isna(latest['atr_14']) else None
                metrics['sma_20'] = float(latest['sma_20']) if not pd.isna(latest['sma_20']) else None
                metrics['sma_50'] = float(latest['sma_50']) if not pd.isna(latest['sma_50']) else None
    except Exception as e:
        log.warning(f"[{ticker}] failed to enrich daily indicators: {e}")
        
    # 3. YFinance Fundamentals
    try:
        t = yf.Ticker(ticker)
        bs = t.quarterly_balance_sheet
        fin = t.quarterly_financials
        cf = t.quarterly_cashflow
        
        cash_val = None
        if bs is not None and not bs.empty:
            for k in ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents', 'Cash Financial', 'Cash']:
                if k in bs.index:
                    val = bs.loc[k].dropna()
                    if not val.empty:
                        cash_val = float(val.iloc[0])
                        break
        metrics['cash'] = cash_val
        
        net_income_val = None
        if fin is not None and not fin.empty:
            for k in ['Net Income', 'Net Income Common Stockholders']:
                if k in fin.index:
                    val = fin.loc[k].dropna()
                    if not val.empty:
                        net_income_val = float(val.iloc[0])
                        break
        metrics['net_income'] = net_income_val

        ocf_val = None
        if cf is not None and not cf.empty:
            for k in ['Operating Cash Flow', 'Cash Flow From Operating Activities']:
                if k in cf.index:
                    val = cf.loc[k].dropna()
                    if not val.empty:
                        ocf_val = float(val.iloc[0])
                        break
        metrics['operating_cash_flow'] = ocf_val

        # Runway
        burn = None
        if ocf_val and ocf_val < 0:
            burn = abs(ocf_val)
        elif net_income_val and net_income_val < 0:
            burn = abs(net_income_val)
            
        runway_months = None
        if cash_val is not None and burn:
            runway_months = float((cash_val / burn) * 3)
            metrics['runway_months'] = runway_months
            
        # Dilution Risk Level
        shares_history = {}
        if bs is not None and not bs.empty:
            for k in ['Ordinary Shares Number', 'Share Issued']:
                if k in bs.index:
                    row = bs.loc[k].dropna()
                    for d_idx, val in row.items():
                        shares_history[str(d_idx).split()[0]] = float(val)
                    break
                    
        dilution = 'Low'
        if runway_months and runway_months < 6:
            dilution = '🔴 HIGH'
        elif len(shares_history) > 1:
            dates_sorted = sorted(list(shares_history.keys()))
            first_shares = shares_history[dates_sorted[0]]
            last_shares = shares_history[dates_sorted[-1]]
            if last_shares > first_shares * 1.10:
                dilution = '🔴 HIGH'
            elif last_shares > first_shares * 1.02:
                dilution = '🟡 MODERATE'
        metrics['dilution_risk'] = dilution
    except Exception as e:
        log.warning(f"[{ticker}] failed to enrich yfinance metrics: {e}")
        
    return metrics


# ---------------------------------------------------------------------------
# Database write
# ---------------------------------------------------------------------------

def write_gainers(gainers: list[dict], target_date: str) -> tuple[int, int]:
    from database import get_connection

    inserted = 0
    skipped  = 0

    with get_connection() as conn:
        for g in gainers:
            try:
                conn.execute(
                    """INSERT INTO daily_gainers
                       (date, ticker, gap_pct, float_shares, rvol_15m, sector,
                        market_cap, news_headline, news_fresh, catalyst,
                        close_price, open_price,
                        high_price, low_price, prev_close, vwap,
                        dollar_volume, close_location, rs_vs_spy,
                        shares_outstanding, avg_volume,
                        premarket_high, premarket_low, premarket_volume,
                        pct_above_vwap, atr_14, sma_20, sma_50,
                        cash, net_income, operating_cash_flow,
                        runway_months, dilution_risk, extended_change_pct)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (date, ticker) DO UPDATE SET
                        gap_pct = EXCLUDED.gap_pct,
                        float_shares = EXCLUDED.float_shares,
                        rvol_15m = EXCLUDED.rvol_15m,
                        sector = EXCLUDED.sector,
                        market_cap = EXCLUDED.market_cap,
                        news_headline = EXCLUDED.news_headline,
                        news_fresh = EXCLUDED.news_fresh,
                        catalyst = EXCLUDED.catalyst,
                        close_price = EXCLUDED.close_price,
                        open_price = EXCLUDED.open_price,
                        high_price = EXCLUDED.high_price,
                        low_price = EXCLUDED.low_price,
                        prev_close = EXCLUDED.prev_close,
                        vwap = EXCLUDED.vwap,
                        dollar_volume = EXCLUDED.dollar_volume,
                        close_location = EXCLUDED.close_location,
                        rs_vs_spy = EXCLUDED.rs_vs_spy,
                        shares_outstanding = EXCLUDED.shares_outstanding,
                        avg_volume = EXCLUDED.avg_volume,
                        premarket_high = EXCLUDED.premarket_high,
                        premarket_low = EXCLUDED.premarket_low,
                        premarket_volume = EXCLUDED.premarket_volume,
                        pct_above_vwap = EXCLUDED.pct_above_vwap,
                        atr_14 = EXCLUDED.atr_14,
                        sma_20 = EXCLUDED.sma_20,
                        sma_50 = EXCLUDED.sma_50,
                        cash = EXCLUDED.cash,
                        net_income = EXCLUDED.net_income,
                        operating_cash_flow = EXCLUDED.operating_cash_flow,
                        runway_months = EXCLUDED.runway_months,
                        dilution_risk = EXCLUDED.dilution_risk,
                        extended_change_pct = EXCLUDED.extended_change_pct,
                        created_at = NOW()""",
                    (
                        target_date,
                        g['ticker'],
                        g['gap_pct'],
                        g['float_shares'],
                        g['rvol_15m'],
                        g['sector'],
                        g['market_cap'],
                        g['news_headline'],
                        g['news_fresh'],
                        g.get('catalyst'),
                        g['close_price'],
                        g['open_price'],
                        g.get('high_price'),
                        g.get('low_price'),
                        g.get('prev_close'),
                        g.get('vwap'),
                        g.get('dollar_volume'),
                        g.get('close_location'),
                        g.get('rs_vs_spy'),
                        g.get('shares_outstanding'),
                        g.get('avg_volume'),
                        g.get('premarket_high'),
                        g.get('premarket_low'),
                        g.get('premarket_volume'),
                        g.get('pct_above_vwap'),
                        g.get('atr_14'),
                        g.get('sma_20'),
                        g.get('sma_50'),
                        g.get('cash'),
                        g.get('net_income'),
                        g.get('operating_cash_flow'),
                        g.get('runway_months'),
                        g.get('dilution_risk'),
                        g.get('extended_change_pct'),
                    ),
                )
                inserted += 1

                # Also persist to pump_classifications for historical tracking
                _persist_pump_classification(conn, g, target_date)

            except Exception as e:
                log.error(f"DB error for {g['ticker']}: {e}")

    return inserted, skipped


def _persist_pump_classification(conn, gainer: dict, target_date: str):
    """Upsert a pump_classifications row for EOD historical tracking."""
    try:
        conn.execute(
            """
            INSERT INTO pump_classifications
                (ticker, date, catalyst_tag, gap_pct, rvol, float_shares, news_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, date) DO UPDATE
                SET catalyst_tag  = EXCLUDED.catalyst_tag,
                    gap_pct       = EXCLUDED.gap_pct,
                    rvol          = EXCLUDED.rvol,
                    float_shares  = EXCLUDED.float_shares,
                    classified_at = now(),
                    news_source   = EXCLUDED.news_source
            """,
            (
                gainer['ticker'],
                target_date,
                gainer.get('catalyst', 'Speculative'),
                gainer.get('gap_pct'),
                gainer.get('rvol_15m'),
                gainer.get('float_shares'),
                'ingest_pipeline',
            ),
        )
    except Exception as e:
        log.warning(f"[Ingest] pump_classifications persist failed for {gainer.get('ticker')}: {e}")


if __name__ == '__main__':
    main()
