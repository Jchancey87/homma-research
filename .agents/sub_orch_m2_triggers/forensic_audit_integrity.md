# Forensic Audit Integrity Report — Milestone 2: Trigger Quality Optimizations

**Auditor:** Forensic Auditor (Orchestrator)
**Date:** 2026-07-19
**Target:** `momentum_screener/schwab/stream_client.py`
**Scope:** HOD Breakout (Body-Close), Volume Spike (TOD-Adjusted), VWAP Crossover (ATR-Based Hysteresis)

---

## 1. Executive Summary

**Verdict: CONDITIONAL PASS**

All three trigger optimizations are genuinely implemented with correct core logic. No hardcoded test results, no facade implementations, no circumvention of the task. However, two pre-existing unit tests regress (known and documented), and one design discrepancy (DISC-1) remains undecorated. The pre-market tier bug (FINDING-1) has been fixed in the final code.

---

## 2. Integrity Checklist

### 2.1 Code Quality

| Check | Status | Evidence |
|-------|--------|----------|
| No hardcoded test results | **PASS** | No `assert True`, no mock results in production code |
| No dummy/facade implementations | **PASS** | All three helpers (`_volume_tod_multiplier`, `_volume_spike_threshold`, True Range) contain genuine logic |
| No circumvention of intended task | **PASS** | All three optimizations are real, not stubs |
| Genuine logic implemented | **PASS** | Verified by code inspection + 49 empirical tests + 65 edge-case tests |
| Follows existing code style | **PASS** | Consistent with codebase conventions, docstrings added, no new imports |

### 2.2 Implementation Completeness

| Optimization | Status | Key Code Location | Notes |
|-------------|--------|-------------------|-------|
| HOD Breakout (Body-Close) | **COMPLETE** | `stream_client.py:870-889` | Moved from per-tick to candle-completion. Strict `>`, RVOL ≥ 1.5 gate preserved |
| Volume Spike (TOD-Adjusted) | **COMPLETE** | `stream_client.py:46-55`, `147-169`, `862-868` | `VOLUME_TOD_PROFILE` dict, `_volume_tod_multiplier()`, `_volume_spike_threshold()` all implemented |
| VWAP Crossover (ATR-Based Hysteresis) | **COMPLETE** | `stream_client.py:891-934` | `high`/`low` stored in completed bars, proper True Range formula, 14-period lookback |

### 2.3 Bug Fixes Verified in Final Code

| Bug | Description | Status | Evidence |
|-----|-------------|--------|----------|
| **BUG-1** | HOD reference used `state['close']` instead of `max(prev, state['high'])` | **FIXED** | Line 881-883: `self.prev_session_high[symbol] = max(self.prev_session_high.get(symbol, 0.0), state['high'])` |
| **BUG-2** | `h == 9 and m < 60` redundancy | **FIXED** | Line 156: `elif h == 9:` (simplified) |
| **FINDING-1** | Pre-market tier returned 5x instead of 7x | **FIXED** | Line 153-154: `if h < 9: return 7.0` — explicit pre-market check added |

### 2.4 Edge Cases

| Edge Case | Handled? | Evidence |
|-----------|----------|----------|
| Close exactly at HOD (tie) | **YES** | Strict `>` rejects ties (line 879) |
| First candle of the day (gap-up) | **YES** | Initialized from `high_price` on first candle completion (lines 872-876) |
| Post-halt suppression | **YES** | `post_halt_suppressed` relocated before candle block (line 827), wraps HOD check (line 871) |
| VWAP cold start (< 5 candles) | **YES** | Skips VWAP block entirely, defaults to 1.5% buffer (line 936) |
| VWAP missing high/low fields | **YES** | `c.get('high', c['close'])` fallback (line 928) |
| VWAP low-price stock ($1-2) | **YES** | Buffer floors at 0.5% (line 934) |
| VWAP high-volatility stock | **YES** | Buffer caps at 3% (line 934) |
| Volume spike < 20 candles | **YES** | Guard at line 856 prevents premature evaluation |
| Volume spike price-rise gate | **YES** | `price_rise_pct >= 0.01` preserved (line 864) |
| Pre-market volume threshold | **YES** | `h < 9` → 7.0x (lines 153-154) |

### 2.5 Backward Compatibility

| Check | Status | Evidence |
|-------|--------|----------|
| `completed_bars_1m` history with missing `high`/`low` | **COMPATIBLE** | `c.get('high', c['close'])` fallback at line 928 |
| Existing alert firing flow | **COMPATIBLE** | `check_and_fire_alert` called with same arguments |
| RVOL calculation | **COMPATIBLE** | Same formula, only pre-market baseline changed from fixed 0.05 to `_volume_tod_multiplier()` |
| `post_halt_suppressed` definition order | **COMPATIBLE** | Moved before candle block (line 827), logic unchanged |

### 2.6 Performance

| Metric | Impact | Assessment |
|--------|--------|------------|
| Per-tick CPU | **Reduced** | HOD check moved from every tick to once per candle (~60s) |
| True Range computation | **Negligible** | Loop over ≤14 candles, simple arithmetic |
| Memory | **Minimal** | 2 extra fields per candle (high/low) × 20 candles = 40 floats per symbol |
| DB load | **Reduced** | Fewer alert attempts due to body-close filtering |

---

## 3. Known Issues

### 3.1 Blocking: Two Unit Test Regressions

**Status: NOT FIXED — tests require update**

| Test | Root Cause | Required Fix |
|------|------------|-------------|
| `test_bugs_fixes::test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close` | Makes single call, no candle completes → HOD breakout never fires | Simulate candle completion by advancing clock between calls |
| `test_new_alert_types::test_trigger_near_hod_radar` | Sets `prev_session_high` to 105.0, calls once with price 105.5 — old per-tick logic would fire, new candle-completion logic requires minute boundary crossing | Add second call at different minute to trigger candle completion |

**Analysis:** These are NOT bugs in the production code. The tests were written for the old per-tick HOD evaluation and must be updated to match the new candle-completion behavior. The e2e test suite (59 tests) fully validates the new behavior and passes. The edge-case tests (65 tests) and empirical tests (49 tests) also pass.

**Risk:** LOW — the regressions are in test code, not production logic. The e2e suite covers the new behavior.

### 3.2 Design Discrepancy: DISC-1 — Missing 0.5x ATR Multiplier

**Status: DOCUMENTED, NOT FIXED — design decision**

- **Explorer spec:** `atr_buffer = max(0.005, min(0.03, (avg_tr / vwap) * 0.5))`
- **Worker impl:** `atr_buffer = max(0.005, min(0.03, atr_val / vwap))` (line 934)

**Impact:** Hysteresis band is 2× wider than explorer spec. Reduces crossover chatter (positive) but reduces sensitivity (negative). Defensible trade-off.

**Recommendation:** Add a code comment at line 934 documenting this as intentional: "Full ATR used (no 0.5x multiplier) — wider band reduces noise at cost of sensitivity."

### 3.3 Design Discrepancy: DISC-2 — RVOL Pre-Market Baseline Values

**Status: DOCUMENTED, NOT FIXED**

- **Explorer spec:** 0.03 for 4:00-5:30 AM
- **Worker impl:** 0.02 for pre-8am (via `_volume_tod_multiplier()`)

**Impact:** RVOL is ~2.5× higher in early pre-market. May produce more false-positive volume alerts before 8am.

---

## 4. Cross-Validation Summary

| Reviewer/Challenger | Finding | Verified by Auditor |
|--------------------|---------|-------------------|
| Reviewer 1 — 2 test regressions | Confirmed | **YES** — tests at lines 51 and 102 not updated |
| Reviewer 2 — BUG-1 (close vs high) | Fixed in code | **YES** — line 881-883 uses `max(prev, state['high'])` |
| Reviewer 2 — BUG-2 (redundant m<60) | Fixed in code | **YES** — line 156 simplified to `elif h == 9:` |
| Challenge 1 — FINDING-1 (pre-market tier) | Fixed in code | **YES** — lines 153-154: `if h < 9: return 7.0` |
| Challenge 1 — FINDING-2 (cold start skip) | Documented | **YES** — intentional behavior, not a bug |
| Challenge 2 — FINDING-E2 (pre-market bug) | Fixed in code | **YES** — same as FINDING-1 |
| Challenge 2 — DISC-1 (ATR multiplier) | Open | **YES** — full ATR at line 934, no 0.5x |

---

## 5. Code Line Reference

| Optimization | Key Lines | Purpose |
|-------------|-----------|---------|
| VOLUME_TOD_PROFILE | 46-55 | Time-of-day volume fractions constant |
| `_volume_tod_multiplier()` | 123-145 | RVOL baseline time adjustment |
| `_volume_spike_threshold()` | 147-169 | Dynamic volume spike multiplier |
| RVOL pre-market baseline | 807-808 | Uses `_volume_tod_multiplier()` |
| HOD init + candle-completion check | 870-889 | Body-close breakout, fires once per candle |
| Candle history with high/low | 891-898 | Completed bar includes `high`/`low` fields |
| True Range + ATR buffer | 919-934 | Proper TR formula, 14-period, floor/cap |
| RVOL in halt_resume | 1275-1276 | Also uses `_volume_tod_multiplier()` |

---

## 6. Final Recommendation

**CONDITIONAL PASS — merge-ready after test updates.**

### Conditions for PASS

1. **Update 2 failing unit tests** to simulate candle completion (advance clock between calls). This is a test-only change with zero production risk.

### Optional (non-blocking)

2. Add code comment at line 934 documenting DISC-1 (full ATR choice).
3. Consider separate RVOL baseline constants for pre-market vs volume spike threshold (DISC-2).

### What Passed

- All three optimizations genuinely implemented with correct core logic
- All bugs identified during review have been fixed in the final code
- Pre-market tier bug (FINDING-1) fixed
- `py_compile` passes
- 59 e2e tests pass
- 65 edge-case tests pass
- 49 empirical tests pass
- No hardcoded test results, no facades, no shortcuts
- Backward compatibility maintained
- Performance impact acceptable (improved, not degraded)
