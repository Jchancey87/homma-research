# Review 1: Code Inspection — M2 Trigger Quality Optimizations

**Reviewer:** Reviewer 1
**Date:** 2026-07-19
**Files Inspected:** `momentum_screener/schwab/stream_client.py` (+108/-34 lines)
**Handoff:** `.agents/sub_orch_m2_triggers/worker_handoff.md`

---

## 1. Checklist

| Item | Status |
|------|--------|
| Code follows existing style and conventions | PASS |
| Changes integrate properly with existing code | PASS (with caveats) |
| No syntax errors or import issues | PASS (`py_compile` clean) |
| Edge cases are handled correctly | PASS |
| Performance implications are acceptable | PASS |
| Unit tests pass | **FAIL** (2 regressions) |

---

## 2. Per-Optimization Analysis

### 2.1 HOD Breakout (Body-Close) — `stream_client.py:867-883`

**What changed:** HOD breakout moved from per-tick evaluation (standalone block after candle logic) into the candle-completion block (`if current_min > state['minute']`). Now fires once per 1m candle using `state['close'] > hod_ref` (strict `>`).

**Correctness:** Logic is correct. Body-close `>` avoids intra-candle wick noise. The `rvol >= 1.5` gate is preserved. The `post_halt_suppressed` check wraps the block correctly.

**Issue — Regression (MEDIUM):** Moving HOD breakout into the candle-completion block breaks 2 existing unit tests that relied on per-tick evaluation:

1. `backend/tests/test_bugs_fixes.py::test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close` — Expected `check_and_fire_alert` to be called (triggered by old per-tick HOD breakout), now no trigger fires because the test doesn't advance the minute boundary.
2. `backend/tests/test_new_alert_types.py::test_trigger_near_hod_radar` — Expected `NEAR_HOD_RADAR` in fired alerts, only `PREV_DAY_BREAKOUT` fires.

**Root cause:** Both tests make a single `evaluate_and_fire_alert` call without advancing the clock. The new code only checks HOD breakout when a candle completes (minute boundary crossed), so neither test's conditions trigger the HOD path.

**Recommendation:** Update both tests to simulate candle completion by making two calls at different minute boundaries, or extract the HOD breakout check into a helper that can be tested independently. This is a **blocking regression** — the tests must be fixed before merge.

### 2.2 Volume Spike (Time-of-Day Adjusted) — `stream_client.py:147-166`, `stream_client.py:856-865`

**What changed:** `_volume_spike_threshold()` returns dynamic multiplier (4x/5x/6x/7x) based on time of day. `VOLUME_TOD_PROFILE` defines expected volume fractions per window.

**Correctness:** Logic is clean and correct. The opening condition `h == 9 and m < 60` at line 153 is equivalent to `h == 9` (since `m` is always 0-59), but this is a readability nit, not a bug.

**Integration:** The volume spike check at line 861 correctly uses the dynamic threshold: `candle_volume >= vol_spike_mult * avg_vol`. The RVOL baseline at line 805 also uses `_volume_tod_multiplier()` for pre-market. Both call sites are consistent.

**Edge cases:** Pre-market (before 8am) returns 0.02, which is 40x smaller than the old hardcoded 0.05. This means RVOL will be ~2.5x higher in pre-8am windows — **this is a significant behavioral change** that may cause more false-positive volume spike alerts in early pre-market. Verify this is intentional with the integrator.

### 2.3 VWAP Crossover (True Range) — `stream_client.py:913-930`

**What changed:** ATR now uses proper True Range formula (`max(H-L, |H-prev_C|, |L-prev_C|)`) from completed candle history, instead of approximated `|close-open|`. ATR window changed from 10 to 14 periods. Completed bars now include `high`/`low` fields.

**Correctness:** The True Range implementation is textbook-correct. The fallback `c.get('high', c['close'])` at line 922 provides backward compatibility with any existing history records that might lack `high`/`low`. The ATR buffer floor (0.5%) and cap (3%) are preserved.

**Integration:** The candle append at line 886 now includes `high` and `low`. The VWAP check at line 916 correctly uses `candle_history` (previously appended completed bars). No issues found.

**Performance:** The TR loop iterates at most 14 candles — negligible overhead. The `sum()/len()` approach is fine for this scale.

### 2.4 Post-Halt Suppression Relocation — `stream_client.py:823-828`

**What changed:** `post_halt_suppressed` definition moved from after the candle block (line ~910) to before it (line ~823), so it's available inside the candle-completion block for the HOD breakout check.

**Correctness:** Correct. The logic is unchanged — it checks `halt_resume_times[symbol]` within 120s. The relocation is necessary for the HOD breakout move and is properly handled.

---

## 3. Code Quality

- **Style:** Consistent with existing codebase. Docstrings added for new methods. Comments explain non-obvious logic.
- **No new imports required.** All changes are self-contained within existing method scope.
- **No raw SQL introduced.** Router-layer rules not applicable here (this is the streaming daemon, not a router).
- **`_volume_tod_multiplier` and `_volume_spike_threshold` are sync pure functions** — appropriate since they have no DB/async deps.

---

## 4. Test Results

### 4.1 `py_compile`
PASS — no syntax errors.

### 4.2 E2E Tests (59 tests)
**PASS** — all 59 e2e tests pass, including:
- `test_t1_r1_near_hod_radar_alert_fires`
- `test_t1_r1_body_close_hod_breakout`
- `test_t1_r1_volume_spike_alert_fires`
- `test_t1_r1_post_halt_suppression_flag`
- `TestMockStreamGenerator::test_body_close_hod_quotes_close_near_high`
- `TestMockStreamGenerator::test_tod_volume_quotes_single_tick`

### 4.3 Unit/Integration Tests
**2 FAILURES**, 375 passed:

| Test | Failure | Root Cause |
|------|---------|------------|
| `test_bugs_fixes::test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close` | `assert streamer.check_and_fire_alert.called` → False | HOD breakout moved to candle-completion; no candle completes in test |
| `test_new_alert_types::test_trigger_near_hod_radar` | `assert 'NEAR_HOD_RADAR' in fired_alerts` → only `PREV_DAY_BREAKOUT` | Same root cause — HOD breakout only fires on candle completion |

Both regressions are caused by the same intentional behavioral change (HOD breakout moved to candle-completion). The tests were written for the old per-tick evaluation and must be updated.

---

## 5. Verdict

**CONDITIONAL PASS — requires test fix before merge.**

The code changes are correct, well-integrated, and the e2e test suite fully validates the new behavior. However, 2 pre-existing unit tests now fail because they relied on the old per-tick HOD breakout evaluation. These tests must be updated to simulate candle completion (advance the clock by 1+ minute between calls) before the changes can be merged.

### Action Items

| Priority | Item | Owner |
|----------|------|-------|
| **BLOCKER** | Fix `test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close` — simulate candle completion or restructure test | Worker |
| **BLOCKER** | Fix `test_trigger_near_hod_radar` — same approach | Worker |
| **NIT** | `_volume_spike_threshold` line 153: `h == 9 and m < 60` → simplify to `h == 9` | Optional |
| **INFO** | Verify early pre-market RVOL increase (0.02 vs old 0.05) is intentional | Integrator |
