"""
Pure Screener Metrics Engine.

Stateless technical calculation functions for ATR, VWAP, EMA, sparkline downsampling,
and Ross Cameron scanner metrics. Zero I/O, zero locks, zero state.
"""

import math
from typing import List, Optional, Tuple


def calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """Calculate Exponential Moving Average for a series of close prices."""
    if not prices or len(prices) < period:
        return None
    sma = sum(prices[:period]) / period
    multiplier = 2 / (period + 1)
    ema = sma
    for price in prices[period:]:
        ema = (price - ema) * multiplier + ema
    return round(ema, 2)


def calculate_atr(candles: List[dict], period: int = 14) -> Optional[float]:
    """Calculate Average True Range over completed candles."""
    if len(candles) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(candles)):
        h = candles[i].get('high', candles[i]['close'])
        l = candles[i].get('low', candles[i]['close'])
        prev_c = candles[i-1]['close']
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return None

    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
    return round(atr, 4)


def calculate_vwap(candles: List[dict]) -> Optional[float]:
    """Calculate Volume-Weighted Average Price across candles."""
    if not candles:
        return None
    cum_pv = 0.0
    cum_vol = 0
    for c in candles:
        v = c.get('volume', 0)
        h = c.get('high', c['close'])
        l = c.get('low', c['close'])
        tp = (h + l + c['close']) / 3.0
        cum_pv += tp * v
        cum_vol += v

    if cum_vol <= 0:
        return None
    return round(cum_pv / cum_vol, 4)


def build_sparkline(closes: List[float], max_points: int = 30) -> List[float]:
    """Downsample close prices to a lightweight sparkline list."""
    if not closes:
        return []
    if len(closes) <= max_points:
        return [round(p, 2) for p in closes]

    step = len(closes) / max_points
    sampled = [closes[int(i * step)] for i in range(max_points - 1)]
    sampled.append(closes[-1])
    return [round(p, 2) for p in sampled]


def calculate_ross_metrics(
    ticker: str,
    last_price: float,
    high_price: float,
    candles_1m: List[dict],
    daily_candles: List[dict]
) -> dict:
    """
    Calculate Ross Cameron momentum scanner metrics:
    - consecutive red candles
    - 9 EMA distance %
    - psychological dollar level distance
    - 1m volume ratio & tape acceleration
    """
    if not last_price or last_price <= 0:
        return {}

    # Consecutive red 1m candles
    consec_red = 0
    for c in reversed(candles_1m[-5:]):
        if c['close'] < c['open']:
            consec_red += 1
        else:
            break

    # 9 EMA distance
    closes_1m = [c['close'] for c in candles_1m]
    ema9_1m = calculate_ema(closes_1m, 9)
    ema9_dist_pct = round(((last_price - ema9_1m) / ema9_1m) * 100, 2) if ema9_1m else None

    # Psychological distance (cents to nearest whole or half dollar)
    whole = round(last_price)
    half = math.floor(last_price) + 0.5
    psych_dist_cents = round(min(abs(last_price - whole), abs(last_price - half)) * 100, 1)

    return {
        'consec_red_1m': consec_red,
        'ema9_1m': ema9_1m,
        'ema9_dist_pct': ema9_dist_pct,
        'psych_dist_cents': psych_dist_cents,
    }
