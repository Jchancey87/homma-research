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

# Add paths
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

from config import Config
from .auth import get_client
from schwab.streaming import StreamClient

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
        """Load fundamentals and technical indicators from Postgres to memory cache."""
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
                
        # 3. Fallback: Add some default high volume tickers if candidates list is empty
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
                    await self.stream_client.level1_equity_subs(list(to_sub))
                    self.subscribed_symbols.update(to_sub)
                    
                if to_unsub:
                    logger.info(f"Unsubscribing from cold symbols: {to_unsub}")
                    # Unsubscribe
                    await self.stream_client.level1_equity_unsubs(list(to_unsub))
                    self.subscribed_symbols.difference_update(to_unsub)
                    for s in to_unsub:
                        self.fundamentals_cache.pop(s, None)
                        self.vwap_state.pop(s, None)
                        self.price_history_1m.pop(s, None)
                        
            except Exception as e:
                logger.error(f"Error in dynamic subscription task: {e}")
                
            await asyncio.sleep(300) # run every 5 minutes

    def evaluate_and_fire_alert(self, symbol, last_price, total_volume, high_price, low_price, open_price):
        """Evaluate hybrid momentum filters and fire alerts via Postgres and Redis Pub/Sub."""
        fund = self.fundamentals_cache.get(symbol)
        if not fund:
            return

        # Cooldown check (10 minutes)
        now = datetime.utcnow()
        if symbol in self.cooldowns:
            if now - self.cooldowns[symbol] < timedelta(minutes=10):
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

        # Apply Ross Cameron primary filters
        # Price: $1.00 - $20.00, Float: < 20M shares
        price_ok = 1.00 <= last_price <= 20.00
        float_ok = fund['shares_outstanding'] < 30_000_000 # Using shares out as float proxy
        
        if triggered and price_ok and float_ok:
            # Fire Alert!
            self.cooldowns[symbol] = now
            
            # 1. Save alert in DB (using asyncio-safe runner)
            asyncio.create_task(self.save_alert_to_db(
                symbol, last_price, total_volume, rvol, gap_pct,
                fund['shares_outstanding'], alert_type
            ))
            
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

    def on_level1_equity_message(self, message):
        """Callback for incoming quote updates from schwab-py StreamClient."""
        try:
            content = message.get('content', [])
            for item in content:
                symbol = item.get('key')
                if not symbol:
                    continue
                
                # Fetch fields
                last_price = item.get('LAST_PRICE')
                total_volume = item.get('TOTAL_VOLUME')
                high_price = item.get('HIGH_PRICE')
                low_price = item.get('LOW_PRICE')
                open_price = item.get('OPEN_PRICE')
                
                # Skip if core quote fields are missing
                if last_price is None or total_volume is None:
                    continue
                    
                self.evaluate_and_fire_alert(
                    symbol, last_price, total_volume,
                    high_price or last_price,
                    low_price or last_price,
                    open_price or last_price
                )
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
        
        # 4. Subscribe to initial list
        # Fields: LAST_PRICE, BID_PRICE, ASK_PRICE, TOTAL_VOLUME, HIGH_PRICE, LOW_PRICE, OPEN_PRICE
        self.stream_client.add_level1_equity_handler(self.on_level1_equity_message)
        await self.stream_client.level1_equity_subs(list(candidates))
        self.subscribed_symbols.update(candidates)
        
        # 5. Launch background dynamic subscription loop
        asyncio.create_task(self.update_subscriptions())
        
        # 6. Start the stream loop (runs indefinitely)
        logger.info("Starting Level 1 streaming client...")
        await self.stream_client.run()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    streamer = SchwabStreamer()
    try:
        asyncio.run(streamer.run())
    except KeyboardInterrupt:
        logger.info("Streamer stopped by user.")
