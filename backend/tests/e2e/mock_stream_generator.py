"""
mock_stream_generator.py
~~~~~~~~~~~~~~~~~~~~~~~~
Simulates Schwab Level 1 equity quote messages for E2E testing.

Generates quote data matching the Schwab streaming format consumed by
``SchwabStreamer.on_level1_equity_message``. No network I/O — purely
dataclass-based construction.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


@dataclass
class Level1Quote:
    """Schwab Level 1 equity quote message."""
    symbol: str
    last_price: float
    bid: float
    ask: float
    bid_size: int = 100
    ask_size: int = 100
    total_volume: int = 0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    net_change: float = 0.0
    trade_time: int = 0
    sequence: int = 0

    def to_schwab_dict(self) -> dict:
        """Serialize to the dict format Schwab StreamClient emits."""
        return {
            "symbol": self.symbol,
            "lastPrice": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "bidSize": self.bid_size,
            "askSize": self.ask_size,
            "totalVolume": self.total_volume,
            "openPrice": self.open_price,
            "highPrice": self.high_price,
            "lowPrice": self.low_price,
            "closePrice": self.close_price,
            "netChange": self.net_change,
            "tradeTime": self.trade_time,
            "sequence": self.sequence,
        }


@dataclass
class AlertPayload:
    """Payload published to Redis channel ``screener:alerts``."""
    symbol: str
    price: float
    volume: int
    rvol: float
    gap_pct: float
    float_shares: int
    alert_type: str
    time: str
    priority_score: int = 0
    priority_tier: str = "Tier 3"
    strategy_label: str = ""
    hod_dist_pct: float | None = None
    catalyst: str = ""
    stop_price: float = 0.0
    stop_risk_pct: float = 0.0
    daily_pct: float = 0.0
    candle_vol: int = 0
    avg_candle_vol: int = 0
    vwap: float = 0.0
    yesterday_high: float = 0.0
    float_category: str = ""
    market_cap: int = 0

    def to_json_dict(self) -> dict:
        """Serialize to JSON-compatible dict for Redis pub/sub."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Quote sequence builders
# ---------------------------------------------------------------------------

def build_hod_breakout_quotes(
    symbol: str,
    base_price: float = 10.0,
    target_price: float = 11.0,
    num_ticks: int = 5,
    volume_start: int = 100000,
) -> list[Level1Quote]:
    """
    Build a sequence of quotes that approach and break above the high of day.

    Simulates steady buying pressure with increasing volume, culminating in
    a price that exceeds the open/high — the condition for a PREV_DAY_BREAKOUT
    or NEAR_HOD_RADAR alert.
    """
    quotes = []
    step = (target_price - base_price) / max(num_ticks - 1, 1)
    vol = volume_start
    for i in range(num_ticks):
        price = round(base_price + step * i, 2)
        vol += 25000 * (i + 1)
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=price,
            bid=price - 0.01,
            ask=price + 0.01,
            total_volume=vol,
            open_price=base_price,
            high_price=max(base_price, price),
            low_price=base_price,
            close_price=price,
            trade_time=100000 + i,
            sequence=i + 1,
        ))
    return quotes


def build_vwap_crossover_quotes(
    symbol: str,
    base_price: float = 10.0,
    vwap_price: float = 10.50,
    num_ticks: int = 5,
    volume_start: int = 100000,
) -> list[Level1Quote]:
    """
    Build quotes that cross above the VWAP line.

    Starts below VWAP and steadily climbs above it. The stream client
    computes VWAP from cumulative (price * volume) / cumulative volume.
    """
    quotes = []
    below_vwap = vwap_price - 0.30
    above_vwap = vwap_price + 0.30
    step = (above_vwap - below_vwap) / max(num_ticks - 1, 1)
    vol = volume_start
    for i in range(num_ticks):
        price = round(below_vwap + step * i, 2)
        vol += 30000 * (i + 1)
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=price,
            bid=price - 0.01,
            ask=price + 0.01,
            total_volume=vol,
            open_price=base_price,
            high_price=max(base_price, price),
            low_price=base_price,
            close_price=price,
            trade_time=100000 + i,
            sequence=i + 1,
        ))
    return quotes


def build_volume_spike_quotes(
    symbol: str,
    base_price: float = 10.0,
    normal_volume: int = 50000,
    spike_volume: int = 500000,
    num_ticks: int = 5,
) -> list[Level1Quote]:
    """
    Build quotes where the last tick has a massive volume spike.

    The RVOL (relative volume) is computed as current_volume / avg_volume.
    A spike of 10x normal triggers a VOLUME_SPIKE alert.
    """
    quotes = []
    for i in range(num_ticks - 1):
        vol = normal_volume + 10000 * i
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=base_price,
            bid=base_price - 0.01,
            ask=base_price + 0.01,
            total_volume=vol,
            open_price=base_price,
            high_price=base_price,
            low_price=base_price,
            close_price=base_price,
            trade_time=100000 + i,
            sequence=i + 1,
        ))
    # Final tick with spike
    quotes.append(Level1Quote(
        symbol=symbol,
        last_price=base_price + 0.20,
        bid=base_price,
        ask=base_price + 0.40,
        total_volume=spike_volume,
        open_price=base_price,
        high_price=base_price + 0.20,
        low_price=base_price,
        close_price=base_price + 0.20,
        trade_time=100000 + num_ticks - 1,
        sequence=num_ticks,
    ))
    return quotes


def build_halt_resume_quotes(
    symbol: str,
    halt_price: float = 10.0,
    resume_price: float = 12.0,
    num_ticks: int = 5,
    volume_start: int = 100000,
) -> list[Level1Quote]:
    """
    Build quotes simulating a volatility halt and resume.

    First tick triggers VOLATILITY_HALT (price moves > 10% in < 5 min).
    Remaining ticks simulate the resume with a gap up.
    """
    quotes = []
    vol = volume_start
    # Halt tick
    quotes.append(Level1Quote(
        symbol=symbol,
        last_price=halt_price,
        bid=halt_price - 0.01,
        ask=halt_price + 0.01,
        total_volume=vol,
        open_price=halt_price,
        high_price=halt_price,
        low_price=halt_price,
        close_price=halt_price,
        trade_time=100000,
        sequence=1,
    ))
    # Resume ticks
    step = (resume_price - halt_price) / max(num_ticks - 1, 1)
    for i in range(1, num_ticks):
        price = round(halt_price + step * i, 2)
        vol += 50000 * (i + 1)
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=price,
            bid=price - 0.01,
            ask=price + 0.01,
            total_volume=vol,
            open_price=halt_price,
            high_price=max(halt_price, price),
            low_price=halt_price,
            close_price=price,
            trade_time=100010 + i,
            sequence=i + 1,
        ))
    return quotes


def build_no_alert_quotes(
    symbol: str,
    base_price: float = 10.0,
    num_ticks: int = 3,
    volume_start: int = 50000,
) -> list[Level1Quote]:
    """
    Build benign quotes that should NOT trigger any alert.
    Used to verify suppression and negative test cases.
    """
    quotes = []
    vol = volume_start
    for i in range(num_ticks):
        vol += 5000
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=base_price,
            bid=base_price - 0.01,
            ask=base_price + 0.01,
            total_volume=vol,
            open_price=base_price,
            high_price=base_price,
            low_price=base_price,
            close_price=base_price,
            trade_time=100000 + i,
            sequence=i + 1,
        ))
    return quotes


def build_body_close_hod_quotes(
    symbol: str,
    base_price: float = 10.0,
    hod_price: float = 11.0,
    close_pct: float = 0.85,
    num_ticks: int = 5,
    volume_start: int = 100000,
) -> list[Level1Quote]:
    """
    Build quotes where the close is near the HOD (body-close condition).

    The body-close HOD optimization requires the candle's close to be within
    ``close_pct`` of the high range (close >= low + close_pct * (high - low)).
    """
    quotes = []
    low = base_price
    high = hod_price
    close = low + close_pct * (high - low)
    vol = volume_start
    for i in range(num_ticks):
        price = round(close, 2)
        vol += 20000 * (i + 1)
        quotes.append(Level1Quote(
            symbol=symbol,
            last_price=price,
            bid=price - 0.01,
            ask=price + 0.01,
            total_volume=vol,
            open_price=base_price,
            high_price=high,
            low_price=low,
            close_price=price,
            trade_time=100000 + i,
            sequence=i + 1,
        ))
    return quotes


def build_tod_volume_quotes(
    symbol: str,
    base_price: float = 10.0,
    time_of_day: str = "09:35",
    volume: int = 200000,
    avg_volume: int = 500000,
) -> list[Level1Quote]:
    """
    Build quotes with time-of-day adjusted volume.

    TOD-adjusted RVOL uses a multiplier based on the time of day
    (e.g., 09:30-10:00 has higher expected volume).
    """
    hour, minute = map(int, time_of_day.split(":"))
    trade_time = hour * 10000 + minute * 100

    return [Level1Quote(
        symbol=symbol,
        last_price=base_price,
        bid=base_price - 0.01,
        ask=base_price + 0.01,
        total_volume=volume,
        open_price=base_price,
        high_price=base_price,
        low_price=base_price,
        close_price=base_price,
        trade_time=trade_time,
        sequence=1,
    )]
