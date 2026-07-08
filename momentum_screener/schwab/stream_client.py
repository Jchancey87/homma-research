import os
import sys
import asyncio
import logging
import json
import time
from datetime import datetime, timedelta
import pytz
import redis
import asyncpg
import httpx

# Try loading environment variables from .env file for standalone execution
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from momentum_screener.schwab.auth import get_client
from schwab.streaming import StreamClient

logger = logging.getLogger(__name__)

# Decoupled database and configuration defaults from backend
ALERT_MIN_PCT_INCREASE = float(os.getenv("ALERT_MIN_PCT_INCREASE", "0.03"))
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://journal:journal1@192.168.0.201:5432/trading_journal"
)
ALERT_MIN_TIME_COOLDOWN_MINS = int(os.getenv("ALERT_MIN_TIME_COOLDOWN_MINUTES", "2"))

# Parse Redis URL
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
# Create redis connection pool
redis_client = redis.Redis.from_url(redis_url)

STRATEGY_LABELS = {
    "HOD_BREAKOUT": "HOD Breakout",
    "VOLUME_SPIKE": "Volume Spike",
    "PREV_DAY_BREAKOUT": "Prev Day High Breakout",
    "VWAP_CROSSOVER": "VWAP Crossover",
    "VWAP_BOUNCE": "VWAP Bounce",
    "RUNNING_UP": "Running Up",
    "BULL_FLAG": "Bull Flag",
    "VWAP_RECLAIM": "VWAP Reclaim",
    "MULTI_TF_CONFLUENCE": "Multi-TF Confluence",
    "HALT_RESUME_MOMENTUM": "Halt Resume Momentum",
    "VOLATILITY_HALT": "Volatility Halt",
    "VOLATILITY_RESUME": "Volatility Resume"
}

# Decoupled Celery app for task dispatch without backend dependencies
try:
    from celery import Celery
    celery_app = Celery("homma_screener_tasks", broker=redis_url)
except ImportError:
    class DummyCelery:
        def send_task(self, name, args=None, kwargs=None, **other_kwargs):
            logger.warning(f"Celery not installed. Task {name} dispatch skipped. Args: {args}")
    celery_app = DummyCelery()

class SchwabStreamer:
    """
    Stateful Schwab Level 1 WebSocket Streamer Daemon.
    Handles dynamic subscription pooling, real-time technical indicators (VWAP, HOD),
    momentum filter evaluation, database logging, and Redis Pub/Sub broadcasting.
    """
    def __init__(self):
        self.client = get_client()
        self.stream_client = StreamClient(self.client)
        self.db_pool = None
        self.subscribed_symbols = set()
        
        # In-memory states
        self.fundamentals_cache = {}  # symbol -> dict
        self.vwap_state = {}          # symbol -> {'cum_vp': float, 'cum_vol': int, 'last_price': float, 'last_total_vol': int}
        self.price_history_1m = {}    # symbol -> list of float prices (rolling 1m window)
        self.completed_bars_1m = {}   # symbol -> list of dict of completed 1m candles
        self.bars_1m = {}             # symbol -> current 1m candle dict
        self.last_known_price = {}    # symbol -> last known price
        self.prev_day_breakout_fired = set()  # set of symbols that fired breakout today
        self.current_date = None      # tracking current ET date
        self.cooldowns = {}           # symbol -> datetime of last alert
        self.halted_tickers = {}      # symbol -> timestamp of last halt alert
        self.halt_resume_times = {}   # symbol -> timestamp of last volatility resume (for post-halt suppression)
        self.watchlist_symbols = set()
        self.watchlist_tags = {}
        self.catalyst_tags = {}
        self.last_hod_breakout_time = {}
        self.global_config = None
        self.configs = None
        self.config_service = "placeholder"

        
    async def init_db(self):
        dsn = os.getenv('DATABASE_URL', DATABASE_URL)
        # Convert postgresql:// to postgres:// for asyncpg if necessary
        if dsn.startswith("postgresql://"):
            dsn = dsn.replace("postgresql://", "postgres://", 1)
        # Remove query parameters from DSN for asyncpg compatibility
        if "?" in dsn:
            dsn = dsn.split("?")[0]
            
        logger.info(f"Connecting to database via asyncpg: {dsn}")
        self.db_pool = await asyncpg.create_pool(
            dsn=dsn,
            ssl=False,
            min_size=1,
            max_size=5
        )
        from services.alert_config_service import AlertConfigService
        self.config_service = AlertConfigService(self.db_pool)
        logger.info("Database pool established.")

    async def load_fundamentals(self, symbols):
        """Load fundamentals and technical indicators from Postgres to memory cache.
        If missing from DB, fetches from Schwab API on-the-fly and saves to DB.
        """
        if not symbols:
            return
        
        async with self.db_pool.acquire() as conn:
            today_et = datetime.now(pytz.timezone('US/Eastern')).date()
            daily_rows = await conn.fetch("""
                SELECT symbol, high, close
                FROM (
                    SELECT symbol, date, high, close,
                           ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                    FROM price_history_daily
                    WHERE symbol = ANY($1) AND date < $2
                ) t
                WHERE rn = 1
            """, list(symbols), today_et)
            yesterday_highs = {r['symbol']: r['high'] for r in daily_rows}
            yesterday_closes = {r['symbol']: r['close'] for r in daily_rows}

            rows = await conn.fetch("""
                SELECT symbol, shares_outstanding, market_cap, pe_ratio, dividend_yield,
                       vol_10d_avg, high_52wk, low_52wk, float_category, short_int_float
                FROM stock_fundamentals
                WHERE symbol = ANY($1)
            """, list(symbols))
            
            for r in rows:
                sym = r['symbol']
                self.fundamentals_cache[sym] = {
                    'shares_outstanding': r['shares_outstanding'] or 0,
                    'market_cap': r['market_cap'] or 0,
                    'pe_ratio': r['pe_ratio'] or 0.0,
                    'dividend_yield': r['dividend_yield'] or 0.0,
                    'vol_10d_avg': r['vol_10d_avg'] or 1,
                    'high_52wk': r['high_52wk'] or 0.0,
                    'low_52wk': r['low_52wk'] or 0.0,
                    'float_category': r['float_category'] or 'Unknown',
                    'short_int_float': r['short_int_float'] or 0.0,
                    'yesterday_high': yesterday_highs.get(sym, 0.0),
                    'yesterday_close': yesterday_closes.get(sym, 0.0)
                }

        # Identify missing symbols and fetch them from Schwab API on-the-fly
        missing = set(symbols) - set(self.fundamentals_cache.keys())
        if missing:
            logger.info(f"Fundamentals missing for {len(missing)} symbols: {missing}. Fetching from Schwab API...")
            from momentum_screener.schwab.http_client import get_instruments
            missing_list = list(missing)
            # Fetch in batches of 50 to prevent URI length limit issues
            for i in range(0, len(missing_list), 50):
                batch = missing_list[i:i+50]
                batch_str = ",".join(batch)
                loop = asyncio.get_event_loop()
                try:
                    data = await loop.run_in_executor(None, get_instruments, batch_str)
                    if data:
                        instruments_dict = {}
                        if 'instruments' in data:
                            for inst in data['instruments']:
                                sym = inst.get('symbol')
                                if sym:
                                    instruments_dict[sym] = inst

                        async with self.db_pool.acquire() as conn:
                            for sym in batch:
                                inst = instruments_dict.get(sym)
                                if not inst or 'fundamental' not in inst:
                                    # Cache dummy values so we don't spam API requests for invalid symbols
                                    self.fundamentals_cache[sym] = {
                                        'shares_outstanding': 0,
                                        'market_cap': 0,
                                        'pe_ratio': 0.0,
                                        'dividend_yield': 0.0,
                                        'vol_10d_avg': 1,
                                        'high_52wk': 0.0,
                                        'low_52wk': 0.0,
                                        'float_category': 'Unknown',
                                        'yesterday_high': yesterday_highs.get(sym, 0.0)
                                    }
                                    continue
                                
                                fund = inst['fundamental']
                                co_name = inst.get('description', '')
                                mkt_cap = int(fund.get('marketCap', 0))
                                shares_out = int(fund.get('sharesOutstanding', 0))
                                div_yield = fund.get('dividendYield', 0.0)
                                pe_ratio = fund.get('peRatio', 0.0)
                                pb_ratio = fund.get('pbRatio', 0.0)
                                beta = fund.get('beta', 0.0)
                                vol_1d = int(fund.get('vol1DayAverage', 0))
                                vol_10d = int(fund.get('vol10DayAverage', 0))
                                vol_3m = int(fund.get('vol3MonthAverage', 0))
                                high_52w = fund.get('high52Week', 0.0)
                                low_52w = fund.get('low52Week', 0.0)
                                
                                float_cat = "Unknown"
                                if shares_out:
                                    if shares_out <= 10_000_000: float_cat = "Micro-Float"
                                    elif shares_out <= 20_000_000: float_cat = "Low-Float"
                                    elif shares_out <= 50_000_000: float_cat = "Mid-Float"
                                    else: float_cat = "High-Float"
                                
                                await conn.execute("""
                                    INSERT INTO stock_fundamentals (
                                        symbol, company_name, shares_outstanding, market_cap,
                                        pe_ratio, pb_ratio, dividend_yield, beta,
                                        vol_1d_avg, vol_10d_avg, vol_3m_avg, high_52wk, low_52wk,
                                        float_category, updated_at
                                    ) VALUES (
                                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW()
                                    ) ON CONFLICT (symbol) DO UPDATE SET
                                        company_name = EXCLUDED.company_name,
                                        shares_outstanding = EXCLUDED.shares_outstanding,
                                        market_cap = EXCLUDED.market_cap,
                                        pe_ratio = EXCLUDED.pe_ratio,
                                        pb_ratio = EXCLUDED.pb_ratio,
                                        dividend_yield = EXCLUDED.dividend_yield,
                                        beta = EXCLUDED.beta,
                                        vol_1d_avg = EXCLUDED.vol_1d_avg,
                                        vol_10d_avg = EXCLUDED.vol_10d_avg,
                                        vol_3m_avg = EXCLUDED.vol_3m_avg,
                                        high_52wk = EXCLUDED.high_52wk,
                                        low_52wk = EXCLUDED.low_52wk,
                                        float_category = EXCLUDED.float_category,
                                        updated_at = NOW()
                                """, sym, co_name, shares_out, mkt_cap,
                                    pe_ratio, pb_ratio, div_yield, beta,
                                    vol_1d, vol_10d, vol_3m, high_52w, low_52w,
                                    float_cat)
                                
                                self.fundamentals_cache[sym] = {
                                    'shares_outstanding': shares_out,
                                    'market_cap': mkt_cap,
                                    'pe_ratio': pe_ratio,
                                    'dividend_yield': div_yield,
                                    'vol_10d_avg': vol_10d or 1,
                                    'high_52wk': high_52w,
                                    'low_52wk': low_52w,
                                    'float_category': float_cat,
                                    'yesterday_high': yesterday_highs.get(sym, 0.0)
                                }
                                logger.info(f"Successfully loaded and cached fundamentals for {sym}")
                except Exception as e:
                    logger.error(f"Error fetching fundamentals from Schwab: {e}")
                
    async def get_candidate_symbols(self):
        """Fetch watchlist tickers and pre-market/active movers from database."""
        candidates = set()
        watchlist_tickers = set()
        self.watchlist_tags = {}
        self.catalyst_tags = {}
        self.last_hod_breakout_time = {}
        
        # 1. Active Watchlist Tickers
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT ticker, tags FROM watchlist")
            for r in rows:
                candidates.add(r['ticker'])
                watchlist_tickers.add(r['ticker'])
                tags_raw = r.get('tags')
                if isinstance(tags_raw, str):
                    try:
                        tags = json.loads(tags_raw)
                    except Exception:
                        tags = []
                elif isinstance(tags_raw, list):
                    tags = tags_raw
                else:
                    tags = []
                self.watchlist_tags[r['ticker']] = tags
        self.watchlist_symbols = watchlist_tickers

        # Fetch today's pump classifications
        today_date = datetime.now(pytz.timezone('US/Eastern')).date()
        try:
            async with self.db_pool.acquire() as conn:
                rows_pump = await conn.fetch("SELECT ticker, catalyst_tag FROM pump_classifications WHERE date = $1", today_date)
                for r in rows_pump:
                    self.catalyst_tags[r['ticker']] = r['catalyst_tag']
        except Exception as e:
            logger.error(f"Failed to fetch pump classifications: {e}")
                
        # 2. Daily runners (top daily gainers from today)
        today_str = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT ticker FROM daily_gainers WHERE date = $1", today_str)
            for r in rows:
                candidates.add(r['ticker'])
                
        # 3. Active movers from Live Gainers API (real-time HOD / momentum candidates)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://127.0.0.1:5000/api/gainers/live")
                if response.status_code == 200:
                    data = response.json()
                    gainers_list = data.get('gainers', [])
                    for g in gainers_list:
                        ticker = g.get('ticker')
                        if ticker:
                            candidates.add(ticker)
                    logger.info(f"Added {len(gainers_list)} tickers from live gainers API.")
        except Exception as e:
            logger.error(f"Failed to fetch live gainers API candidates: {e}")

        # 4. Fallback: Add some default high volume tickers if candidates list is still empty
        if not candidates:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT symbol FROM stock_fundamentals 
                    WHERE vol_10d_avg > 500000 AND market_cap < 10000000000
                    ORDER BY vol_10d_avg DESC LIMIT 50
                """)
                for r in rows:
                    candidates.add(r['symbol'])
                    
        return candidates

    async def update_subscriptions(self):
        """Dynamic subscription worker running every 5 minutes."""
        while True:
            try:
                candidates = await self.get_candidate_symbols()
                
                # Filter out candidates with missing fundamentals
                missing_fundamentals = [s for s in candidates if s not in self.fundamentals_cache]
                if missing_fundamentals:
                    await self.load_fundamentals(missing_fundamentals)
                
                # Calculate diffs
                to_sub = candidates - self.subscribed_symbols
                to_unsub = self.subscribed_symbols - candidates
                
                if to_sub:
                    logger.info(f"Subscribing to new symbols: {to_sub}")
                    # Subscribe Level 1 Quotes
                    # Fields: 0: LAST_PRICE, 1: BID_PRICE, 2: ASK_PRICE, 3: TOTAL_VOLUME, 4: HIGH_PRICE, 5: LOW_PRICE, 6: OPEN_PRICE
                    await self.stream_client.level_one_equity_add(list(to_sub))
                    self.subscribed_symbols.update(to_sub)
                    
                if to_unsub:
                    logger.info(f"Unsubscribing from cold symbols: {to_unsub}")
                    # Unsubscribe
                    await self.stream_client.level_one_equity_unsubs(list(to_unsub))
                    self.subscribed_symbols.difference_update(to_unsub)
                    for s in to_unsub:
                        self.fundamentals_cache.pop(s, None)
                        self.vwap_state.pop(s, None)
                        self.price_history_1m.pop(s, None)
                        
            except Exception as e:
                logger.error(f"Error in dynamic subscription task: {e}")
                
            await asyncio.sleep(300) # run every 5 minutes

    def calculate_confluence_score(self, symbol: str, alert_type: str, rvol: float = 0.0, now_et=None) -> tuple[int, str]:
        """Compute confluence score (0-100). Returns (score, tier)."""
        config = self.global_config or {}
        if now_et is None:
            now_et = datetime.now(pytz.timezone('America/New_York'))
        score = 0

        # 1. Watchlist presence bonus (NOT a gate — just a score boost)
        in_watchlist = symbol in self.watchlist_symbols
        if in_watchlist:
            score += config.get("watchlist_presence_weight", 20)

        # 2. Priority Tag (+20 points if watchlist item has a 'priority' tag)
        tags = self.watchlist_tags.get(symbol, [])
        has_priority_tag = False
        for t in tags:
            if 'priority' in str(t).lower():
                has_priority_tag = True
                break
        if has_priority_tag:
            score += config.get("watchlist_priority_tag_weight", 20)

        # 3. Catalyst tag quality
        cat_tag = self.catalyst_tags.get(symbol)
        if cat_tag == 'Confirmed Catalyst':
            score += config.get("catalyst_confirmed_weight", 25)
        elif cat_tag == 'Speculative':
            score += config.get("catalyst_speculative_weight", 15)
        elif cat_tag == 'Technical / No News':
            score += config.get("catalyst_technical_weight", 10)

        # 4. Float category
        fund = self.fundamentals_cache.get(symbol, {})
        float_cat = fund.get('float_category')
        if float_cat == 'Micro-Float':
            score += config.get("float_micro_weight", 20)
        elif float_cat == 'Low-Float':
            score += config.get("float_low_weight", 15)
        elif float_cat == 'Mid-Float':
            score += config.get("float_mid_weight", 10)

        # 5. Market session
        mkt_start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        mkt_end   = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        if mkt_start <= now_et <= mkt_end:
            score += config.get("session_regular_weight", 15)   # Regular session
        elif now_et < mkt_start:
            score += config.get("session_pre_weight", 10)   # Pre-market
        else:
            score += config.get("session_post_weight", 5)    # Post-market

        # 6. Alert type weight
        if alert_type in ('HOD_BREAKOUT', 'VWAP_CROSSOVER', 'PREV_DAY_BREAKOUT',
                          'RUNNING_UP', 'BULL_FLAG', 'VWAP_RECLAIM'):
            score += config.get("alert_high_weight", 15)
        elif alert_type in ('VOLUME_SPIKE', 'MULTI_TF_CONFLUENCE'):
            score += config.get("alert_mid_weight", 10)
        elif alert_type in ('VOLATILITY_HALT', 'VOLATILITY_RESUME', 'HALT_RESUME_MOMENTUM'):
            score += config.get("alert_low_weight", 5)

        # 7. RVOL strength
        if rvol >= 5.0:
            score += config.get("rvol_high_weight", 15)
        elif rvol >= 3.0:
            score += config.get("rvol_mid_weight", 10)
        elif rvol >= 1.5:
            score += config.get("rvol_low_weight", 5)

        # Tier assignment
        t1_thresh = config.get("tier_1_threshold", 75)
        t2_thresh = config.get("tier_2_threshold", 45)
        if score >= t1_thresh:
            tier = 'Tier 1'
        elif score >= t2_thresh:
            tier = 'Tier 2'
        else:
            tier = 'Tier 3'

        return score, tier

    async def check_and_fire_alert(self, symbol, last_price, total_volume, rvol, gap_pct, alert_type, high_price=0.0, low_price=0.0):
        """Helper to run standard filters, cooldown DB checks, DB persistence, Redis broadcast, and Telegram alert."""
        config = self.global_config or {}
        # 0. Check if alert is enabled in config
        enabled_alerts = config.get("enabled_alerts", {})
        if not enabled_alerts.get(alert_type, True):
            logger.info(f"Refusing to fire alert: {alert_type} is disabled in global config.")
            return False

        fund = self.fundamentals_cache.get(symbol)
        if not fund:
            return False

        # Apply momentum filters (price $1.00 - $30.00, float < 100M shares to match dashboard scanner)
        price_ok = 1.00 <= last_price <= 30.00
        float_ok = fund['shares_outstanding'] < 100_000_000 # Using shares out as float proxy

        if not (price_ok and float_ok):
            return False

        # Determine adaptive price increase threshold based on price buckets
        min_pct_increase_config = config.get("alert_min_pct_increase", 0.03)
        if last_price < 2.0:
            min_pct = 0.08  # 8%
        elif last_price < 5.0:
            min_pct = 0.05  # 5%
        elif last_price < 15.0:
            min_pct = min_pct_increase_config  # wired from config
        else:
            min_pct = 0.02  # 2%

        cooldown_mins = config.get("alert_min_time_cooldown_mins", 2)
        try:
            async with self.db_pool.acquire() as conn:
                result = await conn.fetchval(
                    "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5, $6, $7, $8, $9)",
                    symbol, alert_type, last_price, timedelta(minutes=10), timedelta(seconds=10), 5,
                    min_pct, timedelta(minutes=cooldown_mins), 'percent'
                )
        except Exception as e:
            logger.error(f"Error querying should_fire_alert for {symbol}: {e}")
            result = 'ERROR'

        if result == 'OK':
            priority_score, priority_tier = self.calculate_confluence_score(symbol, alert_type, rvol=rvol)
            
            if alert_type == "HOD_BREAKOUT":
                self.last_hod_breakout_time[symbol] = time.time()

            v_state = self.vwap_state.get(symbol, {})
            vwap_ref = v_state['cum_vp'] / v_state['cum_vol'] if v_state.get('cum_vol', 0) > 0 else 0.0

            # Calculate context fields
            vwap_dist_pct = ((last_price - vwap_ref) / vwap_ref * 100.0) if vwap_ref > 0 else 0.0
            hod_val = high_price if high_price > 0 else last_price
            hod_dist_pct = ((last_price - hod_val) / hod_val * 100.0) if hod_val > 0 else 0.0
            catalyst_val = self.catalyst_tags.get(symbol, "Technical / No News")
            
            stop_price = last_price * 0.97
            if last_price > vwap_ref > 0 and vwap_ref >= last_price * 0.90:
                stop_price = vwap_ref
            elif low_price > 0 and low_price >= last_price * 0.90:
                stop_price = low_price
            stop_risk_pct = ((last_price - stop_price) / last_price * 100.0) if last_price > 0 else 0.0
                
            if priority_tier == 'Tier 3':
                await self.save_alert_to_db(
                    symbol=symbol,
                    price=last_price,
                    volume=total_volume,
                    rvol=rvol,
                    gap_pct=gap_pct,
                    float_shares=fund['shares_outstanding'],
                    alert_type=alert_type,
                    priority_score=priority_score,
                    priority_tier=priority_tier,
                    short_int_float=fund.get('short_int_float', 0.0),
                    vwap_dist_pct=vwap_dist_pct,
                    hod_dist_pct=hod_dist_pct,
                    catalyst=catalyst_val,
                    stop_price=stop_price,
                    stop_risk_pct=stop_risk_pct
                )
                logger.info(f"💾 Alert {alert_type} for {symbol} saved to DB only (Tier 3)")
                return True
                
            now = datetime.utcnow()
            alert_db_row = await self.save_alert_to_db(
                symbol=symbol,
                price=last_price,
                volume=total_volume,
                rvol=rvol,
                gap_pct=gap_pct,
                float_shares=fund['shares_outstanding'],
                alert_type=alert_type,
                priority_score=priority_score,
                priority_tier=priority_tier,
                short_int_float=fund.get('short_int_float', 0.0),
                vwap_dist_pct=vwap_dist_pct,
                hod_dist_pct=hod_dist_pct,
                catalyst=catalyst_val,
                stop_price=stop_price,
                stop_risk_pct=stop_risk_pct
            )

            bar_state = self.bars_1m.get(symbol)
            open_price_ref = bar_state['open'] if bar_state and bar_state.get('open') else 0.0
            daily_pct = ((last_price - open_price_ref) / open_price_ref * 100.0) if open_price_ref > 0 else 0.0

            history = self.completed_bars_1m.get(symbol, [])
            if history:
                avg_candle_vol = int(sum(c['volume'] for c in history) / len(history))
                last_candle_vol = history[-1]['volume'] if history else 0
            else:
                avg_candle_vol = 0
                last_candle_vol = bar_state['last_volume'] - bar_state.get('start_volume', 0) if bar_state else 0

            alert_payload = {
                'symbol': symbol,
                'price': last_price,
                'volume': total_volume,
                'rvol': round(rvol, 2),
                'gap_pct': round(gap_pct, 2),
                'float_shares': fund['shares_outstanding'],
                'float_category': fund.get('float_category', ''),
                'market_cap': fund.get('market_cap', 0),
                'daily_pct': round(daily_pct, 2),
                'candle_vol': last_candle_vol,
                'avg_candle_vol': avg_candle_vol,
                'vwap': round(vwap_ref, 4),
                'yesterday_high': fund.get('yesterday_high', 0.0),
                'alert_type': alert_type,
                'time': now.isoformat(),
                'priority_score': priority_score,
                'priority_tier': priority_tier,
                'alert_db_id': alert_db_row['id'] if alert_db_row else None,
                'alert_db_time': alert_db_row['alert_time'].isoformat() if alert_db_row else None,
                'strategy_label': STRATEGY_LABELS.get(alert_type, "Unknown"),
                'vwap_dist_pct': round(vwap_dist_pct, 2),
                'hod_dist_pct': round(hod_dist_pct, 2),
                'catalyst': catalyst_val,
                'stop_price': round(stop_price, 2),
                'stop_risk_pct': round(stop_risk_pct, 2)
            }
            redis_client.publish('screener:alerts', json.dumps(alert_payload))
            logger.info(f"🚨 ALERT FIRED: {symbol} @ ${last_price} ({alert_type}) | RVOL: {rvol:.2f}x | Tier: {priority_tier} (Score: {priority_score})")

            if priority_tier == 'Tier 1':
                try:
                    celery_app.send_task(
                        "fastapi_app.tasks.alerts.send_telegram_alert_task",
                        args=[alert_payload]
                    )
                except Exception as e:
                    logger.error(f"Failed to dispatch Telegram Celery task for {symbol}: {e}")
            return True
        else:
            if result != 'ERROR':
                logger.info(f"🔇 Alert {alert_type} for {symbol} suppressed: {result}")
            return False

    async def load_initial_config(self):
        try:
            async with self.db_pool.acquire() as conn:
                from fastapi_app.db.alert_config import fetch_alert_configs, fetch_alert_scoring_configs
                configs = await fetch_alert_configs(conn)
                scoring = await fetch_alert_scoring_configs(conn)
                
                self.configs = {cfg["alert_type"]: cfg for cfg in configs}
                
                new_config = {}
                enabled = {}
                for cfg in configs:
                    at = cfg["alert_type"]
                    enabled[at] = cfg.get("enabled", True)
                    if "rvol_min" in cfg:
                        new_config[f"rvol_min_{at}"] = cfg["rvol_min"]
                    if "cooldown_mins" in cfg:
                        new_config[f"cooldown_mins_{at}"] = cfg["cooldown_mins"]
                new_config["enabled_alerts"] = enabled
                for k, v in scoring.items():
                    new_config[k] = v
                self.global_config = new_config
                logger.info("Initial global config loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load initial config: {e}")

    async def refresh_config(self):
        if self.config_service is not None:
            try:
                configs = await self.config_service.get_alert_configs()
                scoring = await self.config_service.get_scoring_configs()
                
                self.configs = {cfg["alert_type"]: cfg for cfg in configs}
                
                new_config = {}
                enabled = {}
                for cfg in configs:
                    at = cfg["alert_type"]
                    enabled[at] = cfg.get("enabled", True)
                    if "rvol_min" in cfg:
                        new_config[f"rvol_min_{at}"] = cfg["rvol_min"]
                    if "cooldown_mins" in cfg:
                        new_config[f"cooldown_mins_{at}"] = cfg["cooldown_mins"]
                new_config["enabled_alerts"] = enabled
                for k, v in scoring.items():
                    new_config[k] = v
                self.global_config = new_config
            except Exception as e:
                logger.error(f"Failed to refresh config from service: {e}")
        else:
            await self.load_initial_config()

    async def poll_alert_config(self):
        while True:
            try:
                if self.db_pool is not None or self.config_service is not None:
                    await self.refresh_config()
            except Exception as e:
                logger.error(f"Error polling alert config: {e}")
            await asyncio.sleep(30)

    async def evaluate_and_fire_alert(self, symbol, last_price, total_volume, high_price, low_price, open_price):
        """Evaluate hybrid momentum filters and fire alerts via Postgres and Redis Pub/Sub."""
        fund = self.fundamentals_cache.get(symbol)
        if not fund:
            return

        candle_history = self.completed_bars_1m.get(symbol, [])

        # Reset previous day breakout set if date changed (Eastern Time)
        today_et = datetime.now(pytz.timezone('US/Eastern')).date()
        if self.current_date != today_et:
            self.current_date = today_et
            self.prev_day_breakout_fired.clear()

        # 1. Update VWAP
        vwap = 0.0
        v_state = self.vwap_state.setdefault(symbol, {'cum_vp': 0.0, 'cum_vol': 0, 'last_total_vol': 0})
        v_state.setdefault('status', None)
        
        # Calculate volume delta
        if v_state['last_total_vol'] > 0 and total_volume > v_state['last_total_vol']:
            delta_vol = total_volume - v_state['last_total_vol']
            v_state['cum_vp'] += last_price * delta_vol
            v_state['cum_vol'] += delta_vol
            
        v_state['last_total_vol'] = total_volume
        if v_state['cum_vol'] > 0:
            vwap = v_state['cum_vp'] / v_state['cum_vol']

        # Calculate Relative Volume (RVOL)
        # Using a simple daily elapsed time factor
        now_et = datetime.now(pytz.timezone('America/New_York'))
        mkt_start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        mkt_end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        if now_et < mkt_start:
            elapsed_pct = 0.05 # Premarket baseline
        elif now_et > mkt_end:
            elapsed_pct = 1.0
        else:
            elapsed_pct = (now_et - mkt_start).total_seconds() / (6.5 * 3600)
            
        rvol = total_volume / max(fund['vol_10d_avg'] * elapsed_pct, 1)

        # Gap calculation
        gap_pct = 0.0
        prev_close = fund.get('yesterday_close')
        if open_price and prev_close:
            gap_pct = ((open_price - prev_close) / prev_close) * 100.0

        # Update 1-minute volume candle
        current_min = int(time.time() / 60)
        state = self.bars_1m.get(symbol)
        if not state:
            self.bars_1m[symbol] = {
                'minute': current_min,
                'open': last_price,
                'high': last_price,
                'low': last_price,
                'close': last_price,
                'start_volume': total_volume,
                'last_volume': total_volume,
            }
        else:
            if current_min > state['minute']:
                # Finalize previous candle values using the boundary tick
                state['close'] = last_price
                state['last_volume'] = max(state['last_volume'], total_volume)
                
                # Candle is completed!
                candle_volume = state['last_volume'] - state['start_volume']
                if candle_volume < 0:
                    candle_volume = 0
                
                # Check if we have enough previous completed candles to evaluate
                history = self.completed_bars_1m.setdefault(symbol, [])
                if len(history) == 20:
                    avg_vol = sum(c['volume'] for c in history) / 20.0
                    price_rise_pct = 0.0
                    if state['open'] > 0:
                        price_rise_pct = (state['close'] - state['open']) / state['open']
                    
                    if avg_vol > 0 and candle_volume >= 5.0 * avg_vol and price_rise_pct >= 0.01:
                        # Trigger VOLUME_SPIKE
                        asyncio.create_task(self.check_and_fire_alert(
                            symbol, state['close'], total_volume, rvol, gap_pct, "VOLUME_SPIKE"
                        ))
                
                # Append current completed candle to history
                history.append({
                    'volume': candle_volume,
                    'open': state['open'],
                    'close': state['close']
                })
                if len(history) > 20:
                    history.pop(0)
                
                # Start new candle
                self.bars_1m[symbol] = {
                    'minute': current_min,
                    'open': last_price,
                    'high': last_price,
                    'low': last_price,
                    'close': last_price,
                    'start_volume': total_volume,
                    'last_volume': total_volume,
                }
            else:
                # Update current candle
                state['high'] = max(state['high'], last_price)
                state['low'] = min(state['low'], last_price)
                state['close'] = last_price
                state['last_volume'] = total_volume

        # Post-halt suppression: skip momentum triggers for 2 min after volatility resume
        post_halt_suppressed = False
        resume_ts = self.halt_resume_times.get(symbol)
        if resume_ts is not None and (time.time() - resume_ts) < 120:
            post_halt_suppressed = True
            logger.debug(f"Post-halt suppression active for {symbol} ({120 - (time.time() - resume_ts):.0f}s remaining)")

        # Trigger 1: High of Day Breakout (requires completed candle BODY close above session HOD)
        # A wick touching the HOD is not sufficient — we need a closed candle where close > high_price.
        if not post_halt_suppressed:
            if candle_history and rvol >= 1.5:
                last_candle = candle_history[-1]
                # Confirm close > open (bullish body) AND close broke above session high_price
                if (last_candle['close'] > last_candle['open'] and
                        last_candle['close'] >= high_price and
                        last_candle['close'] > open_price):
                    await self.check_and_fire_alert(symbol, last_candle['close'], total_volume, rvol, gap_pct, "HOD_BREAKOUT", high_price=high_price, low_price=low_price)

        # Trigger 2: VWAP Crossing (ATR-based dynamic hysteresis to prevent chatter)
        # Estimate ATR from last 10 completed candles (candle range = high - low, approximated here
        # via open/close since we only store open/close in the bar history).
        if vwap > 0 and not post_halt_suppressed:
            if len(candle_history) >= 5:
                recent = candle_history[-10:] if len(candle_history) >= 10 else candle_history
                avg_range = sum(abs(c['close'] - c['open']) for c in recent) / len(recent)
                # ATR buffer: half the average candle range as a % of vwap, floored at 0.5% capped at 3%
                atr_buffer = max(0.005, min(0.03, (avg_range / vwap) * 0.5))
            else:
                atr_buffer = 0.015  # default 1.5% until we have enough candle history

            if v_state.get('status') is None:
                if last_price <= vwap * (1.0 - atr_buffer):
                     v_state['status'] = 'below'
                elif last_price >= vwap * (1.0 + atr_buffer):
                     v_state['status'] = 'above'
            else:
                if v_state['status'] == 'below' and last_price >= vwap * (1.0 + atr_buffer):
                    if rvol >= 2.0:
                        await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "VWAP_CROSSOVER", high_price=high_price, low_price=low_price)
                    v_state['status'] = 'above'
                elif v_state['status'] == 'above' and last_price <= vwap * (1.0 - atr_buffer):
                    v_state['status'] = 'below'

        # Trigger 3: Previous Day High Breakout
        yesterday_high = fund.get('yesterday_high', 0.0)
        if yesterday_high > 0.0 and last_price > yesterday_high and symbol not in self.prev_day_breakout_fired:
            fired = await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "PREV_DAY_BREAKOUT", high_price=high_price, low_price=low_price)
            if fired:
                self.prev_day_breakout_fired.add(symbol)

        # Trigger: RUNNING_UP
        if len(candle_history) >= 5:
            lowest_close = min(c['close'] for c in candle_history[-5:])
            if last_price >= lowest_close * 1.03:
                avg_vol = sum(c['volume'] for c in candle_history[-20:]) / len(candle_history[-20:])
                curr_bar = self.bars_1m.get(symbol, {})
                curr_vol = curr_bar.get('last_volume', total_volume) - curr_bar.get('start_volume', total_volume)
                if curr_vol >= 1.5 * avg_vol and avg_vol > 0:
                    if last_price < high_price:
                        await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "RUNNING_UP", high_price=high_price, low_price=low_price)

        # Trigger: BULL_FLAG
        if len(candle_history) >= 9:
            move_start = candle_history[-9]['close']
            move_end = candle_history[-5]['close']
            strong_move = move_start > 0 and (move_end - move_start) / move_start >= 0.05
            if strong_move:
                consolidation = candle_history[-4:-1]
                declining_vol = consolidation[2]['volume'] <= consolidation[1]['volume'] <= consolidation[0]['volume']
                max_p = max(max(c['open'], c['close']) for c in consolidation)
                min_p = min(min(c['open'], c['close']) for c in consolidation)
                price_range_ok = min_p > 0 and (max_p - min_p) / min_p <= 0.02
                if declining_vol and price_range_ok:
                    consolidation_high = max_p
                    curr_bar = self.bars_1m.get(symbol, {})
                    curr_vol = curr_bar.get('last_volume', total_volume) - curr_bar.get('start_volume', total_volume)
                    avg_vol = sum(c['volume'] for c in candle_history[-20:]) / len(candle_history[-20:])
                    if last_price > consolidation_high and curr_vol >= 1.5 * avg_vol and avg_vol > 0:
                        await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "BULL_FLAG", high_price=high_price, low_price=low_price)

        # Trigger: VWAP_RECLAIM
        if vwap > 0 and not post_halt_suppressed:
            prev_vwap = v_state.get('prev_vwap')
            if prev_vwap is not None and vwap > prev_vwap:
                if v_state.get('status') == 'below' and last_price >= vwap:
                    if rvol >= 1.5:
                        await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "VWAP_RECLAIM", high_price=high_price, low_price=low_price)
            v_state['prev_vwap'] = vwap

        # Trigger: MULTI_TF_CONFLUENCE
        if len(candle_history) >= 5:
            open_5m = candle_history[-5]['open']
            close_5m = candle_history[-1]['close']
            if open_5m > 0 and (close_5m - open_5m) / open_5m >= 0.01:
                last_hod = self.last_hod_breakout_time.get(symbol, 0)
                if time.time() - last_hod <= 60:
                    await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "MULTI_TF_CONFLUENCE", high_price=high_price, low_price=low_price)

        # Trigger 4: VWAP Support Hold & Bounce (Disabled: vwap bounces are noise)
        # if vwap > 0:
        #     completed_bars = self.completed_bars_1m.get(symbol, [])
        #     
        #     declining_volume = True
        #     expanding_volume = True
        #     if len(completed_bars) >= 2:
        #         declining_volume = completed_bars[-1]['volume'] <= completed_bars[-2]['volume']
        #         expanding_volume = completed_bars[-1]['volume'] > completed_bars[-2]['volume']
        # 
        #     v_state.setdefault('vwap_test', False)
        #     v_state.setdefault('vwap_low', None)
        # 
        #     if last_price < vwap:
        #         v_state['vwap_test'] = False
        #         v_state['vwap_low'] = None
        #     else:
        #         if vwap < last_price <= vwap * 1.005:
        #             if declining_volume:
        #                 if not v_state.get('vwap_test'):
        #                     v_state['vwap_test'] = True
        #                     v_state['vwap_low'] = last_price
        #                     logger.info(f"VWAP test activated for {symbol} at low {last_price}")
        #                 else:
        #                     v_state['vwap_low'] = min(v_state['vwap_low'], last_price)
        #         
        #         if v_state.get('vwap_test') and v_state.get('vwap_low') is not None:
        #             if last_price >= v_state['vwap_low'] * 1.01:
        #                 if expanding_volume:
        #                     await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "VWAP_BOUNCE")
        #                     v_state['vwap_test'] = False
        #                     v_state['vwap_low'] = None

    async def save_alert_to_db(self, symbol, price, volume, rvol, gap_pct, float_shares, alert_type, priority_score=0, priority_tier='Tier 3', short_int_float=None, vwap_dist_pct=0.0, hod_dist_pct=0.0, catalyst='Technical / No News', stop_price=0.0, stop_risk_pct=0.0):
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    INSERT INTO screener_alerts (
                        symbol, trigger_price, total_volume, rvol, gap_pct,
                        short_int_float, float_shares, alert_type, priority_score, priority_tier,
                        vwap_dist_pct, hod_dist_pct, catalyst, stop_price, stop_risk_pct
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                    RETURNING id, alert_time
                """, symbol, price, volume, rvol, gap_pct, short_int_float, float_shares, alert_type, priority_score, priority_tier, vwap_dist_pct, hod_dist_pct, catalyst, stop_price, stop_risk_pct)
                return row
        except Exception as e:
            logger.error(f"Failed to save alert for {symbol} to database: {e}")

    async def save_halt_to_db(self, symbol):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO volatility_halts (ticker, halt_time, status)
                    VALUES ($1, NOW(), 'halted')
                """, symbol)
        except Exception as e:
            logger.error(f"Failed to save halt for {symbol} to database: {e}")

    async def save_resume_to_db(self, symbol):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE volatility_halts
                    SET resume_time = NOW(), status = 'resumed'
                    WHERE ticker = $1 AND status = 'halted' AND resume_time IS NULL
                """, symbol)
        except Exception as e:
            logger.error(f"Failed to save resume for {symbol} to database: {e}")

    def on_level1_equity_message(self, message):
        """Callback for incoming quote updates from schwab-py StreamClient."""
        try:
            content = message.get('content', [])
            for item in content:
                symbol = item.get('key')
                if not symbol:
                    continue
                
                last_price = item.get('LAST_PRICE')
                total_volume = item.get('TOTAL_VOLUME')
                high_price = item.get('HIGH_PRICE')
                low_price = item.get('LOW_PRICE')
                open_price = item.get('OPEN_PRICE')
                
                if last_price is not None:
                    self.last_known_price[symbol] = last_price
                
                # Check for trading status / halts
                trading_status = item.get('TRADING_STATUS')
                if trading_status is not None:
                    status_str = str(trading_status).strip().upper()
                    if status_str == 'H':
                        # Check cooldown / state to avoid duplicate insert spam
                        now = time.time()
                        last_halt = self.halted_tickers.get(symbol)
                        if last_halt is None or (now - last_halt > 300):
                            self.halted_tickers[symbol] = now
                            asyncio.create_task(self.save_halt_to_db(symbol))
                            logger.info(f"⏸️ VOLATILITY HALT DETECTED: {symbol}")
                            
                            now_dt = datetime.utcnow()
                            lp = last_price if last_price is not None else self.last_known_price.get(symbol, 0.0)
                            vol = total_volume if total_volume is not None else 0
                            fund = self.fundamentals_cache.get(symbol, {})
                            float_shares = fund.get('shares_outstanding', 0)
                            halt_payload = {
                                'symbol': symbol,
                                'price': lp,
                                'volume': vol,
                                'rvol': 0.0,
                                'gap_pct': 0.0,
                                'float_shares': float_shares,
                                'alert_type': 'VOLATILITY_HALT',
                                'time': now_dt.isoformat()
                            }
                            redis_client.publish('screener:alerts', json.dumps(halt_payload))
                            try:
                                celery_app.send_task(
                                    "fastapi_app.tasks.alerts.send_telegram_alert_task",
                                    args=[halt_payload]
                                )
                            except Exception as e:
                                logger.error(f"Failed to dispatch Volatility Halt Celery task for {symbol}: {e}")
                    elif status_str in ('T', 'Q', 'ACTIVE', 'NORMAL') or status_str == '':
                        # If it was halted, mark it as resumed
                        if symbol in self.halted_tickers:
                            self.halted_tickers.pop(symbol, None)
                            # Record resume time for post-halt suppression window
                            self.halt_resume_times[symbol] = time.time()
                            asyncio.create_task(self.save_resume_to_db(symbol))
                            logger.info(f"▶️ VOLATILITY RESUME DETECTED: {symbol} (2-min HOD/VWAP suppression activated)")
                            
                            # Schedule 30s check for HALT_RESUME_MOMENTUM
                            resume_price = lp
                            asyncio.create_task(self.schedule_halt_resume_momentum_check(symbol, resume_price))
                            
                            now_dt = datetime.utcnow()
                            lp = last_price if last_price is not None else self.last_known_price.get(symbol, 0.0)
                            vol = total_volume if total_volume is not None else 0
                            fund = self.fundamentals_cache.get(symbol, {})
                            float_shares = fund.get('shares_outstanding', 0)
                            resume_payload = {
                                'symbol': symbol,
                                'price': lp,
                                'volume': vol,
                                'rvol': 0.0,
                                'gap_pct': 0.0,
                                'float_shares': float_shares,
                                'alert_type': 'VOLATILITY_RESUME',
                                'time': now_dt.isoformat()
                            }
                            redis_client.publish('screener:alerts', json.dumps(resume_payload))
                            try:
                                celery_app.send_task(
                                    "fastapi_app.tasks.alerts.send_telegram_alert_task",
                                    args=[resume_payload]
                                )
                            except Exception as e:
                                logger.error(f"Failed to dispatch Volatility Resume Celery task for {symbol}: {e}")
                
                # Skip if core quote fields are missing
                if last_price is None or total_volume is None:
                    continue

                # Publish price tick for live_screener streaming fast-path
                try:
                    redis_client.publish('screener:quotes', json.dumps({
                        's': symbol,
                        'p': last_price,
                        'v': total_volume,
                        'h': high_price,
                        'l': low_price,
                        'o': open_price,
                        'b': item.get('BID_PRICE'),
                        'a': item.get('ASK_PRICE'),
                        't': time.time(),
                    }))
                except Exception:
                    pass  # Non-critical — fast-path degrades gracefully

                asyncio.create_task(self.evaluate_and_fire_alert(
                    symbol, last_price, total_volume,
                    high_price or last_price,
                    low_price or last_price,
                    open_price or last_price
                ))
        except Exception as e:
            logger.error(f"Error handling quote update: {e}")


    async def run(self):
        # 1. Establish DB pool
        await self.init_db()
        
        # Load initial config
        await self.load_initial_config()
        
        # 2. Get initial subscription symbols
        candidates = await self.get_candidate_symbols()
        logger.info(f"Initial subscription candidates: {candidates}")
        
        # 3. Load fundamentals
        await self.load_fundamentals(candidates)
        
        # 4. Login to streaming server
        logger.info("Logging into streaming server...")
        await self.stream_client.login()
        
        # 5. Subscribe to initial list
        # Fields: LAST_PRICE, BID_PRICE, ASK_PRICE, TOTAL_VOLUME, HIGH_PRICE, LOW_PRICE, OPEN_PRICE
        self.stream_client.add_level_one_equity_handler(self.on_level1_equity_message)
        await self.stream_client.level_one_equity_subs(list(candidates))
        self.subscribed_symbols.update(candidates)
        
        # 6. Launch background tasks
        asyncio.create_task(self.update_subscriptions())
        asyncio.create_task(self.poll_alert_config())
        
        # 7. Start the stream loop (runs indefinitely)
        logger.info("Starting Level 1 streaming client...")
        while True:
            await self.stream_client.handle_message()

    async def schedule_halt_resume_momentum_check(self, symbol, resume_price):
        # Record resume time for post-halt suppression window
        self.halt_resume_times[symbol] = time.time()
        await self.save_resume_to_db(symbol)
        logger.info(f"▶️ VOLATILITY RESUME DETECTED: {symbol} (2-min HOD/VWAP suppression activated)")
        
        await asyncio.sleep(30)
        fund = self.fundamentals_cache.get(symbol)
        if not fund or resume_price <= 0:
            return
        
        last_price = self.last_known_price.get(symbol, 0.0)
        if last_price <= 0:
            return
            
        history = self.completed_bars_1m.get(symbol, [])
        avg_20_vol = sum(c['volume'] for c in history[-20:]) / len(history[-20:]) if history else 0.0
        
        state = self.bars_1m.get(symbol)
        current_candle_vol = 0
        total_volume = self.vwap_state.get(symbol, {}).get('last_total_vol', 0)
        if state:
            current_candle_vol = total_volume - state['start_volume']
            
        rvol = 0.0
        if total_volume > 0:
            now_et = datetime.now(pytz.timezone('America/New_York'))
            mkt_start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
            mkt_end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
            if now_et < mkt_start:
                elapsed_pct = 0.05
            elif now_et > mkt_end:
                elapsed_pct = 1.0
            else:
                elapsed_pct = (now_et - mkt_start).total_seconds() / (6.5 * 3600)
            rvol = total_volume / max(fund['vol_10d_avg'] * elapsed_pct, 1)

        gap_pct = 0.0
        prev_close = fund.get('yesterday_close')
        if prev_close:
            open_price = state['open'] if state else last_price
            gap_pct = ((open_price - prev_close) / prev_close) * 100.0

        if last_price >= resume_price * 1.01 and current_candle_vol >= 1.5 * max(avg_20_vol, 1):
            await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "HALT_RESUME_MOMENTUM", high_price=last_price, low_price=resume_price)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    streamer = SchwabStreamer()
    try:
        asyncio.run(streamer.run())
    except KeyboardInterrupt:
        logger.info("Streamer stopped by user.")
