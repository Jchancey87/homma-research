# Challenge 1: Edge Case Verification — M2 Trigger Quality Optimizations

**Challenger:** Challenger 1  
**Date:** 2026-07-19  
**Tests:** `backend/tests/test_m2_trigger_edge_cases.py` (65 tests, all PASS)

---

## 1. Test Coverage Summary

| Test Class | Count | Focus |
|------------|-------|-------|
| `TestVolumeTodMultiplier` | 25 | All TOD buckets, boundary values, monotonicity |
| `TestVolumeSpikeThreshold` | 12 | All threshold tiers, boundary transitions |
| `TestHodBreakoutEdgeCases` | 9 | Body-close, candle-completion gate, first candle, post-halt, BUG-1 regression |
| `TestVolumeSpikeEdgeCases` | 8 | Threshold exact/below, TOD tiers, <20 candles, price-rise gate |
| `TestVwapCrossoverEdgeCases` | 8 | Cold start, low/high price, missing fields, True Range, directional, RVOL gate |
| `TestM2Regressions` | 3 | Per-tick→candle-completion regression, next-candle fire, gap_pct |
| **Total** | **65** | |

---

## 2. Findings

### FINDING-1 (BUG — MEDIUM): `_volume_spike_threshold()` Pre-Market Falls to Wrong Tier

**Location:** `stream_client.py:152-166`

**Expected (per review/handoff):** Pre-market (4:00-9:00 AM) → 7.0x threshold  
**Actual:** Pre-market → 5.0x threshold (same as 10-11am)

**Root cause:** The `if/elif` chain:
```python
if h == 9:        # → 4.0x
elif h < 11:      # → 5.0x  ← catches h=4,5,6,7,8!
elif h < 14:      # → 6.0x
elif h < 16:      # → 5.0x
else:             # → 7.0x  ← only h >= 16 (post-market)
```

The `else` clause (7.0x) only applies to post-market (h >= 16). Pre-market hours (h < 9) fall through to `elif h < 11` and get 5.0x.

**Impact:** Pre-market volume spikes fire with 5x threshold instead of 7x — 40% easier to trigger in the 4:00-9:00 AM window. This produces more false-positive VOLUME_SPIKE alerts in low-liquidity pre-market hours.

**Fix:** Add explicit pre-market check before the opening-hour check:
```python
if h < 9:
    return 7.0
elif h == 9:
    return 4.0
elif h < 11:
    return 5.0
...
```

**Verified by:** `test_premarket_4am_falls_to_mid_morning_tier`, `test_premarket_8am_falls_to_mid_morning_tier`, `test_very_early_premarket_uses_5x_not_7x`

---

### FINDING-2 (BUG — LOW): VWAP Crossover Cold Start Doesn't Initialize Status

**Location:** `stream_client.py:918-919`

**Observation:** With < 5 completed candles, the entire VWAP crossover block is skipped (`if len(candle_history) >= 5`). This means `v_state['status']` stays `None` indefinitely until 5 candles accumulate.

**Impact:** Low — the 5-candle gate is intentional to prevent noisy crossovers on thin data. Once 5 candles exist, the default 1.5% buffer applies and status initializes on the first tick. No functional bug, but worth documenting that cold-start behavior is "skip entirely" not "use default buffer."

**Verified by:** `test_cold_start_skips_vwap_check`, `test_5_candles_initializes_status`

---

### FINDING-3 (CORRECTNESS — CONFIRMED): HOD Breakout Candle-Completion Gate Works Correctly

**Verified scenarios:**
- Close exactly at HOD → rejected (strict `>`) ✓
- Close above HOD → fires ✓
- Wick above HOD but close below → rejected ✓
- Same minute (no candle completion) → rejected ✓
- Next completed candle → fires ✓
- First candle with gap-up → initializes from Schwab high_price ✓
- Post-halt suppression within 120s → blocked ✓

**BUG-1 regression (HOD ref uses close vs high):** CONFIRMED FIXED — line 878 correctly uses `max(prev, state['high'])`.

---

### FINDING-4 (CORRECTNESS — CONFIRMED): Volume Spike TOD Adjustment Works Correctly

**Verified scenarios:**
- Opening hour (9am): 4x threshold — fires more easily ✓
- Lunch (11am-2pm): 6x threshold — harder to fire ✓
- Afternoon (2-4pm): 5x threshold ✓
- Volume exactly at threshold → fires (>=) ✓
- Volume just below threshold → rejected ✓
- < 20 candles → no evaluation ✓
- Price must rise >= 1% → enforced ✓

**Design note:** Opening hour uses 4x (lower bar) which is intentional — volume naturally surges at open, so 4x absolute ≈ 1.3x relative to expected open volume.

---

### FINDING-5 (CORRECTNESS — CONFIRMED): VWAP True Range Implementation Correct

**Verified scenarios:**
- Cold start (< 5 candles) → skipped entirely ✓
- Missing high/low fields → falls back to close (backward compat) ✓
- High volatility → ATR buffer caps at 3% ✓
- Low price stock → ATR buffer floors at 0.5% ✓
- True Range formula: `max(H-L, |H-prevC|, |L-prevC|)` — textbook correct ✓
- Only bullish crossover fires (below→above) ✓
- Bearish crossover (above→below) → status changes, no alert ✓
- RVOL >= 2.0 gate enforced ✓

**Design discrepancy (DISC-1):** Full ATR used instead of 0.5x ATR. This doubles the hysteresis band width. Acceptable trade-off (less noise, less sensitivity). Should be documented.

---

## 3. Pre-Existing Regressions (Not Introduced by This Challenge)

These 2 failures exist in the current codebase and are documented in `review_1_code_inspection.md`:

| Test | Root Cause |
|------|------------|
| `test_trigger_near_hod_radar` | HOD breakout moved to candle-completion; test doesn't advance clock |
| `test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close` | Same — check_and_fire_alert never called without candle completion |

---

## 4. Recommendations

### BLOCKER
1. **Fix `_volume_spike_threshold()` pre-market tier** — Add `if h < 9: return 7.0` before the `if h == 9` check. This is a real bug producing false positives in pre-market.

### SHOULD-FIX
2. **Update 2 pre-existing tests** — Simulate candle completion by advancing the clock between `evaluate_and_fire_alert` calls (as identified by Reviewer 1).

### NICE-TO-HAVE
3. **Document DISC-1** — Add comment explaining full ATR (no 0.5x multiplier) was chosen for noise reduction.
4. **Review RVOL pre-market baseline** — `_volume_tod_multiplier()` returns 0.02 for pre-8am (vs explorer's 0.03), making RVOL ~2.5x higher in early pre-market. May need separate constants for RVOL baseline vs volume spike threshold.
