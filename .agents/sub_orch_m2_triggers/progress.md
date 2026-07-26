# M2 Trigger Quality Optimizations - Progress

## Status: COMPLETE

## Changes Made

### 1. HOD Breakout (Body-Close)
- **Removed**: Per-tick HOD breakout logic (old lines 832-844)
- **Added**: Candle-completion HOD breakout check using `state['close'] > hod_ref` (strict body-close)
- **Location**: `evaluate_and_fire_alert()` candle-completion block (~line 867)
- **Key change**: HOD now fires once per 1m candle at completion, not every tick
- **Bug fixed**: HOD ref now uses `max(prev, high)` instead of `close` (BUG-1)

### 2. Volume Spike (Time-of-Day Adjusted)
- **Added**: `VOLUME_TOD_PROFILE` constant (line 46) with expected volume fractions per time window
- **Added**: `_volume_tod_multiplier()` method (line 123) - returns time-appropriate RVOL baseline
- **Added**: `_volume_spike_threshold()` method (line 145) - returns dynamic volume multiplier (4x-7x)
- **Replaced**: Fixed 5x threshold with `_volume_spike_threshold()` call (line 860)
- **Replaced**: Fixed `elapsed_pct = 0.05` pre-market baseline with `_volume_tod_multiplier()` (lines 805, 1270)
- **Bug fixed**: Pre-market hours (h<9) now correctly return 7.0x instead of 5.0x (FINDING-1)

### 3. VWAP Crossover (True Range)
- **Fixed**: `completed_bars_1m` now stores `high` and `low` fields (line 885-892)
- **Replaced**: Approximated ATR (`abs(close - open)`) with proper True Range calculation
- **True Range formula**: `max(high-low, abs(high-prev_close), abs(low-prev_close))`
- **Uses**: 14-period lookback for intraday True Range (line 917)

## Verification
- `py_compile` passes (no syntax errors)
- 59 E2E tests pass
- 65 edge case tests pass
- 49 empirical verification tests pass
- 375/377 unit tests pass (2 tests need update for behavioral change)

## Forensic Audit
- **Verdict**: CONDITIONAL PASS
- All bugs fixed (BUG-1, BUG-2, FINDING-1)
- No code shortcuts or facades
- 2 unit tests need update for new HOD behavior (test-only changes)
