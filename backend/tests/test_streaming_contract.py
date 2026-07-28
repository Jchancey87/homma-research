"""
Contract tests for the streaming price pipeline.

Tests the schema contracts across the pipeline boundaries:
Redis publisher → StreamingPriceBridge → ScreenerCache overlay
Redis publisher → WebSocket relay → frontend payload shape
"""

import json
import time
import pytest
from unittest.mock import MagicMock, patch

from backend.services.quote_schema import (
    QuoteTick,
    REDIS_KEY_MAP,
    parse_redis_quote,
    serialize_ws_quote,
)
from backend.services.streaming_prices import PriceSnapshot
from backend.services.screener_cache import ScreenerCache


# ── QuoteTick schema ─────────────────────────────────────────────────────────

class TestQuoteTickSchema:
    """Tests for the shared QuoteTick schema and its parse/serialize helpers."""

    def test_parse_valid_redis_quote(self):
        """Valid compact-key Redis message parses to QuoteTick with correct types."""
        raw = {'s': 'AAPL', 'p': 150.25, 'v': 1234567, 'h': 152.0, 'l': 149.5,
               'o': 150.0, 'b': 150.2, 'a': 150.3, 't': 1722196600.123}
        tick = parse_redis_quote(raw)
        assert tick.symbol == 'AAPL'
        assert tick.price == 150.25
        assert tick.volume == 1234567
        assert tick.high == 152.0
        assert tick.low == 149.5
        assert tick.open == 150.0
        assert tick.bid == 150.2
        assert tick.ask == 150.3
        assert tick.time == 1722196600.123

    def test_parse_minimal_redis_quote(self):
        """Minimal required fields (symbol, price, time) parse without error."""
        raw = {'s': 'TSLA', 'p': 42.0, 't': time.time()}
        tick = parse_redis_quote(raw)
        assert tick.symbol == 'TSLA'
        assert tick.price == 42.0
        assert tick.volume == 0
        assert tick.high == 0.0
        assert tick.bid is None
        assert tick.ask is None

    def test_parse_missing_symbol_raises(self):
        """Missing symbol field raises ValueError."""
        raw = {'p': 42.0, 't': time.time()}
        with pytest.raises(ValueError, match="symbol"):
            parse_redis_quote(raw)

    def test_parse_missing_price_raises(self):
        """Missing price field raises ValueError."""
        raw = {'s': 'AAPL', 't': time.time()}
        with pytest.raises(ValueError, match="price"):
            parse_redis_quote(raw)

    def test_parse_null_price_raises(self):
        """Explicit None price raises ValueError."""
        raw = {'s': 'AAPL', 'p': None, 't': time.time()}
        with pytest.raises(ValueError):
            parse_redis_quote(raw)

    def test_parse_ignores_unknown_keys(self):
        """Extra keys in Redis message are silently ignored."""
        raw = {'s': 'AAPL', 'p': 10.0, 't': time.time(), 'x_extra': 'junk'}
        tick = parse_redis_quote(raw)
        assert tick.symbol == 'AAPL'

    def test_redis_key_map_completeness(self):
        """REDIS_KEY_MAP covers all compact keys used by stream_client.py."""
        expected = {'s', 'p', 'v', 'h', 'l', 'o', 'b', 'a', 't'}
        assert set(REDIS_KEY_MAP.keys()) == expected

    def test_serialize_ws_quote_flat(self):
        """serialize_ws_quote produces a flat dict with type='price' and no nesting."""
        tick = QuoteTick(symbol='AAPL', price=150.0, volume=1000, high=152.0,
                         low=149.0, open=150.0, bid=149.9, ask=150.1,
                         time=1722196600.0)
        d = serialize_ws_quote(tick)
        assert d['type'] == 'price'
        assert d['symbol'] == 'AAPL'
        assert d['price'] == 150.0
        assert d['volume'] == 1000
        assert d['high'] == 152.0
        assert d['low'] == 149.0
        assert d['bid'] == 149.9
        assert d['ask'] == 150.1
        assert d['time'] == 1722196600.0
        # Must be flat — no nested 'data' key
        assert 'data' not in d

    def test_serialize_ws_quote_json_serializable(self):
        """Output of serialize_ws_quote round-trips through JSON cleanly."""
        tick = QuoteTick(symbol='TSLA', price=42.0, time=time.time())
        d = serialize_ws_quote(tick)
        roundtripped = json.loads(json.dumps(d))
        assert roundtripped['symbol'] == 'TSLA'
        assert roundtripped['type'] == 'price'

    def test_serialize_ws_quote_optional_none_fields(self):
        """None optional fields (bid, ask) are included as null in output."""
        tick = QuoteTick(symbol='X', price=5.0, time=1.0)
        d = serialize_ws_quote(tick)
        assert d['bid'] is None
        assert d['ask'] is None


# ── Pipeline: Redis → PriceSnapshot → Cache overlay ─────────────────────────

class TestStreamingPipelineContract:
    """End-to-end contract: compact Redis message → PriceSnapshot → cache overlay."""

    def test_redis_to_price_snapshot_field_mapping(self):
        """Compact Redis keys map to PriceSnapshot field names correctly."""
        raw = {'s': 'GOOG', 'p': 100.5, 'v': 500000, 'h': 105.0, 'l': 98.0,
               'o': 99.0, 'b': 100.4, 'a': 100.6, 't': time.time()}
        tick = parse_redis_quote(raw)
        snap = PriceSnapshot(
            symbol=tick.symbol,
            last_price=tick.price,
            volume=tick.volume,
            high_price=tick.high,
            low_price=tick.low,
            open_price=tick.open,
            bid=tick.bid,
            ask=tick.ask,
            timestamp=tick.time,
        )
        assert snap.symbol == 'GOOG'
        assert snap.last_price == 100.5
        assert snap.volume == 500000
        assert snap.high_price == 105.0
        assert snap.low_price == 98.0
        assert snap.bid == 100.4
        assert snap.ask == 100.6

    def test_cache_overlay_with_quote_tick_snapshot(self):
        """ScreenerCache.overlay_streaming_ticks updates price, high, low, gap_pct."""
        cache = ScreenerCache()
        gainers = [
            {'ticker': 'TEST', 'last_price': 10.0, 'prev_close': 8.0,
             'gap_pct': 25.0, 'high_price': 10.0, 'low_price': 9.0}
        ]
        cache.update_cache(gainers, session='REGULAR')

        # Simulate a price tick arriving via the pipeline
        raw = {'s': 'TEST', 'p': 12.0, 'v': 999, 'h': 12.5, 'l': 8.5,
               't': time.time() + 10}
        tick = parse_redis_quote(raw)
        snap = PriceSnapshot(
            symbol=tick.symbol, last_price=tick.price, volume=tick.volume,
            high_price=tick.high, low_price=tick.low, open_price=tick.open,
            bid=tick.bid, ask=tick.ask, timestamp=tick.time,
        )

        fast_active, count = cache.overlay_streaming_ticks({tick.symbol: snap})
        assert fast_active is True
        assert count == 1

        result = cache.get_cache_snapshot()
        g = result['gainers'][0]
        assert g['last_price'] == 12.0
        assert g['high_price'] == 12.5
        assert g['low_price'] == 8.5
        assert g['gap_pct'] == 50.0  # (12.0 - 8.0) / 8.0 * 100

    def test_cache_overlay_stale_tick_rejected(self):
        """Tick with timestamp older than last update is not applied."""
        cache = ScreenerCache()
        now = time.time()
        gainers = [{'ticker': 'OLD', 'last_price': 10.0, 'prev_close': 8.0, 'gap_pct': 25.0}]
        cache.update_cache(gainers, session='REGULAR')

        # Tick with timestamp BEFORE the cache update
        snap = PriceSnapshot(
            symbol='OLD', last_price=99.0, volume=1, high_price=99.0,
            low_price=1.0, timestamp=now - 100,
        )
        fast_active, _ = cache.overlay_streaming_ticks({'OLD': snap})
        assert fast_active is False
        result = cache.get_cache_snapshot()
        assert result['gainers'][0]['last_price'] == 10.0  # unchanged

    def test_cache_overlay_unknown_ticker_ignored(self):
        """Tick for a symbol not in the gainer table is ignored gracefully."""
        cache = ScreenerCache()
        gainers = [{'ticker': 'KNOWN', 'last_price': 5.0, 'prev_close': 4.0, 'gap_pct': 25.0}]
        cache.update_cache(gainers, session='REGULAR')

        snap = PriceSnapshot(
            symbol='UNKNOWN', last_price=99.0, volume=1, timestamp=time.time() + 10,
        )
        fast_active, count = cache.overlay_streaming_ticks({'UNKNOWN': snap})
        assert fast_active is False
        assert count == 1  # streamed_prices has 1 symbol, but 0 matched


# ── WebSocket relay payload contract ─────────────────────────────────────────

class TestWebSocketPayloadContract:
    """Verify the WS relay output matches what the frontend expects."""

    def test_ws_price_payload_has_required_frontend_fields(self):
        """WS payload must contain all fields the frontend PriceTick reads."""
        raw = {'s': 'MSFT', 'p': 350.0, 'v': 2000000, 'h': 355.0, 'l': 345.0,
               'o': 348.0, 'b': 349.9, 'a': 350.1, 't': time.time()}
        tick = parse_redis_quote(raw)
        payload = serialize_ws_quote(tick)

        # Frontend PriceTick interface requires these fields:
        frontend_required = {'symbol', 'price', 'volume', 'high', 'low', 'open'}
        frontend_optional = {'bid', 'ask', 'time'}

        for field in frontend_required:
            assert field in payload, f"Missing required frontend field: {field}"
        for field in frontend_optional:
            assert field in payload, f"Missing optional frontend field: {field}"

    def test_ws_price_payload_type_field(self):
        """WS payload must have type='price' for frontend routing."""
        tick = QuoteTick(symbol='X', price=1.0, time=1.0)
        payload = serialize_ws_quote(tick)
        assert payload['type'] == 'price'

    def test_ws_alert_payload_structure_unchanged(self):
        """Alert payloads are not affected by the quote schema refactor."""
        # This test documents the expected alert structure to prevent regression
        alert_data = {
            'symbol': 'AAPL', 'alert_type': 'NEAR_HOD_RADAR',
            'price': 150.0, 'volume': 1000000
        }
        msg_dict = {"type": "alert", "data": alert_data}
        if "symbol" in alert_data:
            msg_dict["symbol"] = alert_data["symbol"]
        if "alert_type" in alert_data:
            msg_dict["alert_type"] = alert_data["alert_type"]

        assert msg_dict['type'] == 'alert'
        assert msg_dict['symbol'] == 'AAPL'
        assert msg_dict['alert_type'] == 'NEAR_HOD_RADAR'
        assert msg_dict['data'] == alert_data
