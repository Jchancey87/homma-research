"""
backend/tests/test_pattern_detector.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for pattern_detector.py module (Bull Flag, VWAP Reclaim, Micro Pullback, Psych Levels).
"""
import pytest
from services.pattern_detector import (
    calculate_ema,
    detect_bull_flag,
    detect_vwap_reclaim,
    detect_micro_pullback,
    detect_psych_breakout,
    analyze_stock_patterns
)

def test_calculate_ema():
    prices = [10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8]
    ema = calculate_ema(prices, 9)
    assert ema is not None
    assert ema > 10.0

def test_detect_bull_flag_positive():
    # Construct an impulse pole followed by tight consolidation
    candles = [
        {'o': 10.0, 'c': 10.5, 'h': 10.6, 'l': 10.0, 'v': 50000},
        {'o': 10.5, 'c': 11.2, 'h': 11.3, 'l': 10.4, 'v': 80000},
        {'o': 11.2, 'c': 11.8, 'h': 12.0, 'l': 11.1, 'v': 120000}, # Peak high 12.0
        {'o': 11.8, 'c': 11.6, 'h': 11.9, 'l': 11.5, 'v': 20000}, # Consolidation red
        {'o': 11.6, 'c': 11.5, 'h': 11.7, 'l': 11.4, 'v': 15000}, # Consolidation red
        {'o': 11.5, 'c': 11.9, 'h': 12.1, 'l': 11.5, 'v': 90000}, # Breakout
    ]
    assert detect_bull_flag(candles) is True

def test_detect_vwap_reclaim_positive():
    # Price below VWAP ($10.00), then reclaims VWAP with volume surge
    vwap = 10.00
    candles = [
        {'o': 9.80, 'c': 9.70, 'h': 9.85, 'l': 9.65, 'v': 10000},
        {'o': 9.70, 'c': 9.85, 'h': 9.90, 'l': 9.68, 'v': 12000},
        {'o': 9.85, 'c': 10.25, 'h': 10.30, 'l': 9.80, 'v': 45000}, # Volume surge reclaim
    ]
    assert detect_vwap_reclaim(candles, vwap) is True

def test_detect_micro_pullback():
    ema9 = 10.00
    candles = [
        {'o': 10.20, 'c': 10.50, 'h': 10.60, 'l': 10.15, 'v': 30000}, # Up
        {'o': 10.50, 'c': 10.20, 'h': 10.55, 'l': 10.10, 'v': 15000}, # Red 1
        {'o': 10.20, 'c': 10.05, 'h': 10.25, 'l': 10.02, 'v': 12000}, # Red 2 (near 9 EMA)
        {'o': 10.05, 'c': 10.40, 'h': 10.45, 'l': 10.03, 'v': 40000}, # Green reversal
    ]
    assert detect_micro_pullback(candles, ema9) is True

def test_detect_psych_breakout():
    has_breakout, level = detect_psych_breakout(5.15, 4.85)
    assert has_breakout is True
    assert level == 5.0

def test_analyze_stock_patterns_master():
    candles = [
        {'o': 4.50, 'c': 4.80, 'h': 4.90, 'l': 4.45, 'v': 25000},
        {'o': 4.80, 'c': 5.25, 'h': 5.30, 'l': 4.75, 'v': 85000},
    ]
    res = analyze_stock_patterns(candles, vwap=4.75, curr_price=5.25)
    assert res['pattern_score'] > 0
    assert 'PSYCH_BREAKOUT' in res['active_patterns']
