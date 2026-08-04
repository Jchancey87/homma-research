"""
Unit tests for Multi-Timeframe S/R Momentum Scanner service (mtf_sr_service.py).
"""

import pytest
from services.mtf_sr_service import (
    detect_pivots,
    merge_levels,
    find_coincident_levels,
    compute_sr_levels,
    score_mtf_momentum,
)


def test_detect_pivots():
    # Construct synthetic candles with known high at index 5 and low at index 10
    candles = [{'close': 10.0, 'high': 10.0, 'low': 10.0} for _ in range(15)]
    candles[5] = {'close': 15.0, 'high': 15.0, 'low': 10.0}  # Pivot high
    candles[10] = {'close': 5.0, 'high': 10.0, 'low': 5.0}   # Pivot low

    highs, lows = detect_pivots(candles, left=3, right=3)
    assert len(highs) == 1
    assert highs[0]['index'] == 5
    assert highs[0]['price'] == 15.0

    assert len(lows) == 1
    assert lows[0]['index'] == 10
    assert lows[0]['price'] == 5.0


def test_merge_levels():
    levels = [
        {'price': 10.00, 'type': 'RESISTANCE', 'touch_count': 1},
        {'price': 10.05, 'type': 'RESISTANCE', 'touch_count': 1},
        {'price': 15.00, 'type': 'RESISTANCE', 'touch_count': 1},
    ]
    # Merge within 0.10
    merged = merge_levels(levels, merge_threshold=0.10)
    assert len(merged) == 2
    assert merged[0]['price'] == 10.025
    assert merged[0]['touch_count'] == 2
    assert merged[1]['price'] == 15.0
    assert merged[1]['touch_count'] == 1


def test_find_coincident_levels():
    daily_levels = [{'price': 10.0, 'touch_count': 2}]
    five_min_levels = [{'price': 10.2, 'touch_count': 1}]
    daily_atr = 0.5

    coincident = find_coincident_levels(daily_levels, five_min_levels, daily_atr)
    assert len(coincident) == 1
    assert coincident[0]['price'] == 10.1
    assert coincident[0]['touch_count'] == 3


def test_score_mtf_momentum():
    # Build synthetic S/R structure
    sr_levels = {
        'daily_atr': 1.0,
        'five_min_atr': 0.20,
        'tier1_daily': [{'price': 10.0, 'type': 'RESISTANCE', 'touch_count': 3}],
        'tier2_5min': [{'price': 10.05, 'type': 'RESISTANCE', 'touch_count': 2}],
        'coincident': [{'price': 10.025, 'touch_count': 5}],
    }

    # 1m candles
    df_1min = []
    for i in range(25):
        df_1min.append({
            'open': 9.8 + (i * 0.01),
            'high': 9.9 + (i * 0.01),
            'low': 9.7 + (i * 0.01),
            'close': 9.85 + (i * 0.01),
            'volume': 1000 if i < 24 else 5000  # RVOL burst on last candle
        })

    last_price = 10.02
    result = score_mtf_momentum("AAPL", sr_levels, df_1min, last_price)

    assert result['ticker'] == "AAPL"
    assert result['score'] >= 50
    assert result['mtf_in_play'] is True
    assert 'DAILY_SR_TEST' in result['signals']
    assert '5MIN_SR_TEST' in result['signals']
    assert 'COINCIDENT_LEVEL' in result['signals']
