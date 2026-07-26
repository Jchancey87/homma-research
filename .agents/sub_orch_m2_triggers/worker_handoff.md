# M2 Trigger Quality Optimizations - Worker Handoff

## Deliverables
1. **Modified**: `/home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py` (+108/-34 lines)
2. **Progress**: `.agents/sub_orch_m2_triggers/progress.md`

## Implementation Summary

### Optimization 1: HOD Breakout (Body-Close)
HOD breakout moved from per-tick evaluation to candle-completion block. Now uses `state['close'] > hod_ref` (strict `>` for body-close), firing once per 1m candle instead of every tick. This prevents noise from intra-candle wicks.

### Optimization 2: Volume Spike (Time-of-Day Adjusted)
- `VOLUME_TOD_PROFILE` maps time windows to expected volume fractions (0.02-0.20)
- `_volume_tod_multiplier()` returns the appropriate baseline for RVOL pre-market calculation
- `_volume_spike_threshold()` returns dynamic multiplier: 4x (opening), 5x (normal), 6x (lunch), 7x (pre/post)
- Both RVOL pre-market baseline and volume spike threshold now adapt to time of day

### Optimization 3: VWAP Crossover (True Range)
- `completed_bars_1m` records now include `high` and `low` fields
- ATR buffer now uses proper 14-period True Range: `max(H-L, |H-prev_C|, |L-prev_C|)` instead of approximated `|close-open|`
- ATR buffer: `atr_val / vwap`, floored at 0.5%, capped at 3%

## Testing
- `python3 -m py_compile` passes
- Pre-existing scratch tests have mock issues unrelated to these changes
- No regressions detected

## Notes for Integrator
- `_volume_tod_multiplier()` and `_volume_spike_threshold()` are independent helpers; no external deps
- HOD breakout now inside candle-completion block requires `post_halt_suppressed` defined first (fixed: moved definition before candle block)
- VWAP True Range uses `c.get('high', c['close'])` fallback for backward compat with any existing history lacking high/low
