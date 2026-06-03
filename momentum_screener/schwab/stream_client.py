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

# Add paths
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from config import Config
from momentum_screener.schwab.auth import get_client
from schwab.streaming import StreamClient
from fastapi_app.celery_app import celery_app

logger = logging.getLogger(__name__)

# Parse Redis URL
redis_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
# Create redis connection pool
redis_client = redis.Redis.from_url(redis_url)

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
        self.cooldowns = {}           # symbol -> datetime of last alert
        self.halted_tickers = {}      # symbol -> timestamp of last halt alert

        
    async def init_db(self):
        dsn = os.getenv('DATABASE_URL', Config.DATABASE_URL)
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
        logger.info("Database pool established.")

    async def load_fundamentals(self, symbols):
        """Load fundamentals and technical indicators from Postgres to memory cache.
        If missing from DB, fetches from Schwab API on-the-fly and saves to DB.
        """
        if not symbols:
            return
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT symbol, shares_outstanding, market_cap, pe_ratio, dividend_yield,
                       vol_10d_avg, high_52wk, low_52wk, float_category
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
                    'float_category': r['float_category'] or 'Unknown'
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
                                        'float_category': 'Unknown'
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
                                    'float_category': float_cat
                                }
                                logger.info(f"Successfully loaded and cached fundamentals for {sym}")
                except Exception as e:
                    logger.error(f"Error fetching fundamentals from Schwab: {e}")
                
    async def get_candidate_symbols(self):
        """Fetch watchlist tickers and pre-market/active movers from database."""
        candidates = set()
        
        # 1. Active Watchlist Tickers
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("SELECT ticker FROM watchlist")
            for r in rows:
                candidates.add(r['ticker'])
                
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
                    await self.stream_client.level_one_equity_subs(list(to_sub))
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

    async def evaluate_and_fire_alert(self, symbol, last_price, total_volume, high_price, low_price, open_price):
        """Evaluate hybrid momentum filters and fire alerts via Postgres and Redis Pub/Sub."""
        fund = self.fundamentals_cache.get(symbol)
        if not fund:
            return

        # 1. Update VWAP
        vwap = 0.0
        v_state = self.vwap_state.setdefault(symbol, {'cum_vp': 0.0, 'cum_vol': 0, 'last_total_vol': 0})
        
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
        # If open_price is not available, default gap to 0.0
        gap_pct = 0.0
        # If we have 52wk low/prev close, we can calculate gap pct. Net change percent is also available.
        # Let's check net change pct or assume gap_pct based on open vs prev_close if we can resolve it.
        # We can approximate gap_pct using open_price if available:
        prev_close = fund.get('low_52wk') # default placeholder
        if open_price and prev_close:
            gap_pct = ((open_price - prev_close) / prev_close) * 100.0

        # Evaluate Triggers
        triggered = False
        alert_type = ""
        
        # Trigger 1: High of Day Breakout
        # If the price breaks above the previous high_price (or today's high)
        if last_price >= high_price and last_price > open_price and rvol >= 1.5:
            triggered = True
            alert_type = "HOD_BREAKOUT"
            
        # Trigger 2: VWAP Crossing
        # If price crosses above VWAP and rvol is high
        if vwap > 0 and last_price > vwap and rvol >= 2.0:
            triggered = True
            alert_type = "VWAP_CROSSOVER"

        # Apply momentum filters (price $1.00 - $30.00, float < 100M shares to match dashboard scanner)
        price_ok = 1.00 <= last_price <= 30.00
        float_ok = fund['shares_outstanding'] < 100_000_000 # Using shares out as float proxy
        
        if triggered and price_ok and float_ok:
            # Query alerts.should_fire_alert from database to check cooldown & macro-market suppressions
            try:
                async with self.db_pool.acquire() as conn:
                    should_fire = await conn.fetchval(
                        "SELECT alerts.should_fire_alert($1, $2, $3, $4, $5, $6, $7)",
                        symbol, last_price, timedelta(minutes=10), timedelta(seconds=10), 5,
                        Config.ALERT_MIN_PCT_INCREASE, timedelta(minutes=Config.ALERT_MIN_TIME_COOLDOWN_MINS)
                    )
            except Exception as e:
                logger.error(f"Error querying should_fire_alert for {symbol}: {e}")
                should_fire = False

            if should_fire:
                now = datetime.utcnow()
                # 1. Save alert in DB
                await self.save_alert_to_db(
                    symbol, last_price, total_volume, rvol, gap_pct,
                    fund['shares_outstanding'], alert_type
                )
                
                # 2. Publish JSON alert payload to Redis
                alert_payload = {
                    'symbol': symbol,
                    'price': last_price,
                    'volume': total_volume,
                    'rvol': round(rvol, 2),
                    'gap_pct': round(gap_pct, 2),
                    'float_shares': fund['shares_outstanding'],
                    'alert_type': alert_type,
                    'time': now.isoformat()
                }
                redis_client.publish('screener:alerts', json.dumps(alert_payload))
                logger.info(f"🚨 ALERT FIRED: {symbol} @ ${last_price} ({alert_type}) | RVOL: {rvol:.2f}x")

                # 3. Trigger Celery task asynchronously using celery_app.send_task
                try:
                    celery_app.send_task(
                        "fastapi_app.tasks.alerts.send_telegram_alert_task",
                        args=[alert_payload]
                    )
                except Exception as e:
                    logger.error(f"Failed to dispatch Telegram Celery task for {symbol}: {e}")

    async def save_alert_to_db(self, symbol, price, volume, rvol, gap_pct, float_shares, alert_type):
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO screener_alerts (
                        symbol, alert_time, trigger_price, trigger_volume,
                        rel_vol, gap_pct, float_shares, alert_type, sent
                    ) VALUES ($1, NOW(), $2, $3, $4, $5, $6, $7, FALSE)
                """, symbol, price, volume, rvol, gap_pct, float_shares, alert_type)
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
                    elif status_str in ('T', 'Q', 'ACTIVE', 'NORMAL') or status_str == '':
                        # If it was halted, mark it as resumed
                        if symbol in self.halted_tickers:
                            self.halted_tickers.pop(symbol, None)
                            asyncio.create_task(self.save_resume_to_db(symbol))
                            logger.info(f"▶️ VOLATILITY RESUME DETECTED: {symbol}")

                # Fetch fields
                last_price = item.get('LAST_PRICE')
                total_volume = item.get('TOTAL_VOLUME')
                high_price = item.get('HIGH_PRICE')
                low_price = item.get('LOW_PRICE')
                open_price = item.get('OPEN_PRICE')
                
                # Skip if core quote fields are missing
                if last_price is None or total_volume is None:
                    continue
                    
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
        
        # 6. Launch background dynamic subscription loop
        asyncio.create_task(self.update_subscriptions())
        
        # 7. Start the stream loop (runs indefinitely)
        logger.info("Starting Level 1 streaming client...")
        while True:
            await self.stream_client.handle_message()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    streamer = SchwabStreamer()
    try:
        asyncio.run(streamer.run())
    except KeyboardInterrupt:
        logger.info("Streamer stopped by user.")
