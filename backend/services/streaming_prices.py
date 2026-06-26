"""
services/streaming_prices.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
StreamingPriceBridge — connects live_screener to Schwab WebSocket
price stream via Redis pub/sub.

The SchwabStreamer (stream_client.py) publishes Level 1 ticks to
Redis channel ``screener:quotes``. This module subscribes in a
background thread and maintains an in-memory dict of latest prices.

The live_screener fast-path reads from this dict every ~2 s to
overlay real-time prices onto cached gainer rows — zero REST calls.
"""

import json
import os
import time
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional

log = logging.getLogger(__name__)

STALE_THRESHOLD_S = 60  # Ignore prices older than this
CHANNEL = 'screener:quotes'


@dataclass
class PriceSnapshot:
    """Latest streamed price fields for a single symbol."""
    symbol: str
    last_price: float
    volume: int = 0
    high_price: float = 0.0
    low_price: float = 0.0
    open_price: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


class StreamingPriceBridge:
    """
    Redis subscriber that maintains an in-memory price dict from
    the Schwab WebSocket streamer.

    Usage::

        bridge = StreamingPriceBridge()
        bridge.start()  # launches subscriber thread

        prices = bridge.get_all_prices()   # {symbol: PriceSnapshot}
        snap   = bridge.get_price("AAPL")  # PriceSnapshot | None
    """

    def __init__(self, redis_url: str = None):
        self._prices: Dict[str, PriceSnapshot] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._redis_url = redis_url
        self._connected = False

    # ── public API ────────────────────────────────────────────────────────

    def start(self):
        """Launch the Redis subscriber thread. Idempotent."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._subscribe_loop,
            name='streaming-price-bridge',
            daemon=True,
        )
        self._thread.start()
        log.info("[StreamingPriceBridge] Subscriber thread started")

    def stop(self):
        self._running = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def symbol_count(self) -> int:
        """Number of symbols with live price data."""
        with self._lock:
            return len(self._prices)

    def get_all_prices(self) -> Dict[str, PriceSnapshot]:
        """Return a snapshot copy of all non-stale prices (thread-safe)."""
        now = time.time()
        with self._lock:
            return {
                sym: snap for sym, snap in self._prices.items()
                if now - snap.timestamp < STALE_THRESHOLD_S
            }

    def get_price(self, symbol: str) -> Optional[PriceSnapshot]:
        """Return the latest price for a symbol, or None if stale/missing."""
        with self._lock:
            snap = self._prices.get(symbol)
        if snap is None:
            return None
        if time.time() - snap.timestamp > STALE_THRESHOLD_S:
            return None
        return snap

    # ── subscriber loop ───────────────────────────────────────────────────

    def _subscribe_loop(self):
        """Connect to Redis and listen for price messages. Auto-reconnects."""
        import redis as redis_lib

        url = self._redis_url or os.getenv(
            'CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0',
        )

        while self._running:
            try:
                client = redis_lib.Redis.from_url(url)
                pubsub = client.pubsub()
                pubsub.subscribe(CHANNEL)
                self._connected = True
                log.info(f"[StreamingPriceBridge] Subscribed to {CHANNEL}")

                for message in pubsub.listen():
                    if not self._running:
                        break
                    if message['type'] != 'message':
                        continue
                    try:
                        data = json.loads(message['data'])
                        sym = data.get('s')
                        if not sym:
                            continue
                        snap = PriceSnapshot(
                            symbol=sym,
                            last_price=data.get('p', 0.0),
                            volume=int(data.get('v') or 0),
                            high_price=data.get('h', 0.0),
                            low_price=data.get('l', 0.0),
                            open_price=data.get('o', 0.0),
                            bid=data.get('b'),
                            ask=data.get('a'),
                            timestamp=data.get('t', time.time()),
                        )
                        with self._lock:
                            self._prices[sym] = snap
                    except (json.JSONDecodeError, TypeError, ValueError) as exc:
                        log.debug("[StreamingPriceBridge] Bad message: %s", exc)

            except Exception as exc:
                self._connected = False
                log.warning(
                    "[StreamingPriceBridge] Redis error: %s — reconnecting in 5 s",
                    exc,
                )
                time.sleep(5)

        self._connected = False


# ── Module-level singleton ────────────────────────────────────────────────

_bridge: Optional[StreamingPriceBridge] = None
_bridge_lock = threading.Lock()


def get_bridge() -> StreamingPriceBridge:
    """Get or create the module-level StreamingPriceBridge singleton."""
    global _bridge
    with _bridge_lock:
        if _bridge is None:
            _bridge = StreamingPriceBridge()
        return _bridge


def start_streaming_bridge():
    """Start the streaming price bridge. Idempotent."""
    bridge = get_bridge()
    bridge.start()


def get_streamed_prices() -> Dict[str, PriceSnapshot]:
    """Get all current streamed prices (non-stale)."""
    bridge = get_bridge()
    return bridge.get_all_prices()


def get_streamed_price(symbol: str) -> Optional[PriceSnapshot]:
    """Get the latest streamed price for a symbol."""
    bridge = get_bridge()
    return bridge.get_price(symbol)
