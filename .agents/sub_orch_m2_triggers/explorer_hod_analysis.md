# HOD Breakout Implementation Analysis & Body-Close Strategy

## 1. Current Implementation Analysis

### Location
`stream_client.py:832-844` — `evaluate_and_fire_alert()` method, Trigger 1: Near HOD Radar

### How It Works (Wick-Based / Tick-Level)
```
prev_session_high[symbol] = Schwab's HIGH_PRICE (session high so far)

On each tick:
  if last_price > prev_session_high:
      old_high = prev_session_high
      prev_session_high = last_price
      if rvol >= 1.5:
          fire NEAR_HOD_RADAR alert
```

**Behavior**: Fires on ANY tick where `last_price > prev_session_high`. This is a "new high detector" — every tick that sets a new session high triggers the alert (subject to cooldown).

### Problems
| Issue | Detail |
|-------|--------|
| Wick noise | A single tick above HOD fires, even if candle closes well below |
| Multiple fires | Alert fires repeatedly as each new tick extends the high |
| No confirmation | No requirement that a candle body closes above HOD |
| False breakouts | Price spikes above HOD, then reverses — but alert already fired |

### Desired Behavior (Body-Close)
Wait for a 1-minute candle to **close** above the previous HOD. Only then fire the alert. This filters out wicks that poke above HOD but fail to hold.

---

## 2. Recommended Implementation Strategy

### Core Idea
Move the HOD breakout check **out of the per-tick path** and into the **candle completion path** (lines 775-817 where `bars_1m` are finalized). When a 1-minute candle completes, compare its `close` against the HOD value at the start of that candle.

### Pseudocode
```python
# Inside the candle-completion block (line 775), after finalizing the previous candle:

# --- HOD Body-Close Breakout Check ---
if not post_halt_suppressed:
    # Use the high at the START of this candle as the reference
    # (prev_session_high was set before this candle began)
    hod_ref = self.prev_session_high.get(symbol, 0.0)
    
    if hod_ref > 0.0 and state['close'] > hod_ref:
        # Body-close confirmed: candle closed above HOD
        if rvol >= 1.5:
            asyncio.create_task(self.check_and_fire_alert(
                symbol, state['close'], total_volume, rvol, gap_pct,
                "NEAR_HOD_RADAR", high_price=hod_ref, low_price=state['low']
            ))
    
    # Update HOD after check (new high is now the candle close or high)
    self.prev_session_high[symbol] = max(
        self.prev_session_high.get(symbol, 0.0),
        state['high']  # Use candle high, not just close
    )
```

### Key Changes
1. **Check fires at candle close, not per-tick** —移到 candle completion block
2. **Compare `state['close']` vs `hod_ref`** — body-close, not wick
3. **Update HOD after the check** — so the reference for the next candle is correct
4. **`prev_session_high` tracking moves** — no longer updated on every tick

### What to Remove
Remove the current per-tick HOD breakout logic at lines 832-844. The HOD update (`self.prev_session_high[symbol] = last_price` on line 842) should only happen at candle boundaries.

---

## 3. Edge Cases & Considerations

### Edge Case 1: Close Exactly at HOD
**Question**: If `close == hod_ref`, is that a breakout?
**Recommendation**: Use strict `>` (close must be ABOVE HOD). Ties at HOD are not breakouts — they indicate indecision, not conviction.

### Edge Case 2: Gaps (Price Opens Above Previous HOD)
If the stock gaps above HOD at open, `prev_session_high` will be initialized to the opening `HIGH_PRICE` (line 836-838), which already reflects the gap. The body-close check will naturally work because the first completed candle will be compared against the session high that already includes the gap.

### Edge Case 3: First Candle of the Day
`prev_session_high` is initialized from Schwab's `HIGH_PRICE` field on first quote (lines 834-838). This is correct — it's the session high at market open. The first completed candle will be checked against this.

### Edge Case 4: HOD Updates Mid-Candle
Currently `prev_session_high` tracks the running high tick-by-tick. In the new approach, HOD only updates at candle boundaries. This is fine because:
- We want to compare candle-close vs the HOD *before* the candle started
- This prevents the reference point from drifting during the candle

### Edge Case 5: Candle Volume / RVOL at Completion
The `rvol` and `total_volume` values used should be the values at candle completion, not at the start. This is already the case since `evaluate_and_fire_alert` receives the current tick's values.

### Edge Case 6: Alert Cooldown Interaction
The existing `should_fire_alert` DB function enforces cooldowns. The body-close change doesn't affect cooldown logic — it still prevents duplicate alerts for the same symbol within the cooldown window.

---

## 4. Code Changes Required

### File: `stream_client.py`

#### Change A: Remove per-tick HOD logic (lines 832-844)
Delete or comment out:
```python
# Trigger 1: Near HOD Radar breakout (more responsive, live tick breakout)
if not post_halt_suppressed:
    if symbol not in self.prev_session_high or self.prev_session_high[symbol] <= 0:
        if high_price > 0:
            self.prev_session_high[symbol] = high_price
        elif last_price > 0:
            self.prev_session_high[symbol] = last_price
    
    if self.prev_session_high.get(symbol, 0.0) > 0.0 and last_price > self.prev_session_high[symbol]:
        old_high = self.prev_session_high[symbol]
        self.prev_session_high[symbol] = last_price
        if rvol >= 1.5:
            await self.check_and_fire_alert(symbol, last_price, total_volume, rvol, gap_pct, "NEAR_HOD_RADAR", high_price=old_high, low_price=low_price)
```

#### Change B: Add body-close check in candle-completion block (after line 806)
Insert after the VOLUME_SPIKE check and candle history append:
```python
# --- HOD Body-Close Breakout Check ---
if not post_halt_suppressed:
    hod_ref = self.prev_session_high.get(symbol, 0.0)
    if hod_ref > 0.0 and state['close'] > hod_ref:
        if rvol >= 1.5:
            asyncio.create_task(self.check_and_fire_alert(
                symbol, state['close'], total_volume, rvol, gap_pct,
                "NEAR_HOD_RADAR", high_price=hod_ref, low_price=state['low']
            ))
    # Update HOD after check
    self.prev_session_high[symbol] = max(
        self.prev_session_high.get(symbol, 0.0),
        state['high']
    )
```

#### Change C: Keep HOD initialization (lines 834-838)
The initialization of `prev_session_high` from Schwab's `HIGH_PRICE` should remain, but move it **before** the candle-completion check block or keep it at the top of `evaluate_and_fire_alert` (before the candle logic). This ensures HOD is set on first tick.

Suggested: Move lines 834-838 to right after the `post_halt_suppressed` check (line 830), before the candle update logic, so HOD is always initialized regardless of which trigger fires.

---

## 5. Performance Impact Assessment

| Metric | Impact |
|--------|--------|
| Per-tick CPU | **Reduced** — one less comparison per tick per symbol |
| Alert latency | **Increased by ~60s** — alerts delayed until candle close instead of firing on tick |
| Noise reduction | **Significant** — wick breakouts eliminated |
| False positive rate | **Reduced** — only confirmed closes above HOD fire |
| Memory | **Neutral** — no new state needed |
| DB load | **Reduced** — fewer alert attempts means fewer `should_fire_alert` queries |

### Latency Trade-off
The main cost is ~60 seconds of additional latency (waiting for candle close). For HOD breakouts, this is acceptable because:
- A body-close confirms buyer conviction (sustained demand above HOD)
- Wick breakouts have high failure rates — filtering them improves signal quality
- The 60s delay is still well within the "actionable" window for momentum plays

### Alternative: Partial Confirmation
If latency is a concern, a hybrid approach could fire on tick above HOD but mark the alert as "unconfirmed" and only promote it to full alert if the candle closes above HOD. This adds complexity but reduces latency.

---

## 6. Summary

| Aspect | Current | Proposed |
|--------|---------|----------|
| Trigger condition | Tick price > HOD | Candle close > HOD |
| Timing | Per-tick (real-time) | Candle completion (~60s delay) |
| Wick noise | High | Eliminated |
| Signal quality | Low (many false positives) | High (confirmed breakouts) |
| Code complexity | Simple | Moderate (moved to candle path) |
| Latency | 0s | ~60s |
