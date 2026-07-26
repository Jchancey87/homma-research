---
name: warrior-patterns
description: Technical rules, score calculations, and pattern detection logic for Warrior Trading scanners and pattern recognition engine.
---

# Warrior Pattern Detection Engine

## Core Engine
* **Module:** `services/pattern_detector.py`. Pure Python pattern recognition engine.
* **Input:** List of 1m/5m completed OHLCV bars (`bars: list[dict]`), current price, VWAP, 9 EMA.
* **Output:** `PatternResult(active_patterns: list[str], pattern_score: int)`.

## Detected Patterns
1. **Bull Flag (`BULL_FLAG`):**
   * Strong impulse pole (3+ green candles with price gain >= 5.0%).
   * Tight consolidation (1-3 candles holding above 9 EMA).
   * Volume contraction during pullback followed by breakout volume surge.
2. **VWAP Reclaim (`VWAP_RECLAIM`):**
   * Prior price trading below VWAP.
   * Bullish crossover back above VWAP with volume >= 1.5x 20-candle average.
3. **Micro Pullback (`MICRO_PULLBACK`):**
   * 1 to 2 small red candles pulling back to test 9 EMA in established uptrend.
   * Lows hold 9 EMA with immediate green reversal candle.
4. **Psychological Level Breakout (`PSYCH_BREAKOUT`):**
   * Price crossing key dollar boundary ($1.00, $2.50, $5.00, $10.00, $20.00).
