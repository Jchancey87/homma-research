# VWAP Crossover Hysteresis Analysis

## Current Implementation

**File**: `momentum_screener/schwab/stream_client.py:846-869`

### How It Works Now

The VWAP Crossover trigger already uses a dynamic ATR-like buffer instead of a static 2.0%. Here is the exact code:

```python
# Trigger 2: VWAP Crossing (ATR-based dynamic hysteresis to prevent chatter)
if vwap > 0 and not post_halt_suppressed:
    if len(candle_history) >= 5:
        recent = candle_history[-10:] if len(candle_history) >= 10 else candle_history
        avg_range = sum(abs(c['close'] - c['open']) for c in recent) / len(recent)
        # ATR buffer: half the average candle range as a % of vwap, floored at 0.5% capped at 3%
        atr_buffer = max(0.005, min(0.03, (avg_range / vwap) * 0.5))
    else:
        atr_buffer = 0.015  # default 1.5% until we have enough candle history
```

### Critical Data Limitation

The `completed_bars_1m` history only stores `{volume, open, close}` per candle (line 800-804). **High and low are NOT persisted** to the completed candle history. The current "ATR" calculation uses `abs(close - open)` which is a poor approximation of True Range:

```
True Range = max(H-L, |H-prevC|, |L-prevC|)  # proper ATR
Current    = abs(close - open)                 # what we compute (underestimates volatility)
```

This systematically underestimates intraday volatility because wicks (intra-candle highs/lows) are discarded.

### State Machine

- `v_state['status']`: tracks whether price is `'above'` or `'below'` VWAP
- Fires `VWAP_CROSSOVER` when price transitions from below to above VWAP (with RVOL >= 2.0 gate)
- Hysteresis band is symmetric: `vwap * (1.0 + atr_buffer)` and `vwap * (1.0 - atr_buffer)`

---

## Recommended Implementation Strategy

### Option A: Fix completed_bars_1m to Store High/Low (Intraday True Range)

**Effort: Low** | **Recommended as Phase 1**

Store high/low in completed candles so we can compute proper intraday True Range.

**Step 1**: Modify candle finalization to persist high/low (stream_client.py ~line 800):

```python
# Change from:
history.append({
    'volume': candle_volume,
    'open': state['open'],
    'close': state['close']
})

# To:
history.append({
    'volume': candle_volume,
    'open': state['open'],
    'high': state['high'],
    'low': state['low'],
    'close': state['close']
})
```

**Step 2**: Replace the approximated ATR with proper intraday True Range calculation:

```python
# Trigger 2: VWAP Crossing (ATR-based dynamic hysteresis)
if vwap > 0 and not post_halt_suppressed:
    if len(candle_history) >= 10:
        recent = candle_history[-14:] if len(candle_history) >= 14 else candle_history
        true_ranges = []
        for i in range(1, len(recent)):
            h = recent[i].get('high', recent[i]['close'])
            l = recent[i].get('low', recent[i]['close'])
            pc = recent[i-1]['close']
            tr = max(h - l, abs(h - pc), abs(l - pc))
            true_ranges.append(tr)
        avg_tr = sum(true_ranges) / len(true_ranges)
        # Buffer = 50% of ATR as fraction of VWAP, floored 0.5%, capped 3%
        atr_buffer = max(0.005, min(0.03, (avg_tr / vwap) * 0.5))
    elif len(candle_history) >= 5:
        # Fallback: use abs(close-open) if high/low not available (backwards compat)
        recent = candle_history[-10:] if len(candle_history) >= 10 else candle_history
        avg_range = sum(abs(c['close'] - c['open']) for c in recent) / len(recent)
        atr_buffer = max(0.005, min(0.03, (avg_range / vwap) * 0.5))
    else:
        atr_buffer = 0.015  # 1.5% default cold-start
```

**Why 50% multiplier**: The buffer should be narrower than full ATR to avoid missing legitimate crossovers. 50% of ATR provides a meaningful noise floor while still allowing entry on real moves.

**Why floor 0.5% / cap 3%**: 
- 0.5% floor prevents chatter on ultra-tight-range stocks (e.g., a $50 stock with tiny candles)
- 3% cap prevents the band from becoming so wide it never triggers on volatile stocks

---

### Option B: Blend Daily ATR(14) with Intraday True Range

**Effort: Medium** | **Recommended as Phase 2**

Use the pre-computed daily ATR(14) from `daily_gainers.atr_14` as a volatility anchor, blended with intraday range for a more stable estimate.

**Advantages**:
- Daily ATR(14) captures the stock's "normal" volatility across market regimes
- More stable than purely intraday calculation (which can be noisy early in session)
- Already computed and stored by `backend/jobs/ingest_gainers.py:455`

**Step 1**: Load daily ATR into fundamentals_cache during `load_fundamentals()`:

```python
# In load_fundamentals(), add to the daily_rows query:
daily_rows = await conn.fetch("""
    SELECT symbol, high, close
    FROM (
        SELECT symbol, date, high, close,
               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
        FROM price_history_daily
        WHERE symbol = ANY($1) AND date < $2
    ) t
    WHERE rn = 1
""", list(symbols), today_et)

# Also fetch daily_gainers atr_14 for today:
today_str = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y-%m-%d')
atr_rows = await conn.fetch("""
    SELECT ticker, atr_14 FROM daily_gainers
    WHERE date = $1 AND ticker = ANY($2)
""", today_str, list(symbols))
daily_atrs = {r['ticker']: r['atr_14'] for r in atr_rows if r['atr_14']}

# Store in fundamentals_cache:
self.fundamentals_cache[sym]['daily_atr_14'] = daily_atrs.get(sym)
```

**Step 2**: Blend daily and intraday ATR in the crossover logic:

```python
# Trigger 2: VWAP Crossing (blended ATR hysteresis)
if vwap > 0 and not post_halt_suppressed:
    fund = self.fundamentals_cache.get(symbol, {})
    daily_atr = fund.get('daily_atr_14')
    
    # Intraday True Range from completed candles
    intraday_atr = 0.0
    if len(candle_history) >= 10:
        recent = candle_history[-14:] if len(candle_history) >= 14 else candle_history
        true_ranges = []
        for i in range(1, len(recent)):
            h = recent[i].get('high', recent[i]['close'])
            l = recent[i].get('low', recent[i]['close'])
            pc = recent[i-1]['close']
            tr = max(h - l, abs(h - pc), abs(l - pc))
            true_ranges.append(tr)
        intraday_atr = sum(true_ranges) / len(true_ranges)
    
    # Blend: 60% daily ATR (stable) + 40% intraday ATR (responsive)
    # Falls back to whichever is available
    if daily_atr and daily_atr > 0 and intraday_atr > 0:
        blended_atr = 0.6 * daily_atr + 0.4 * intraday_atr
    elif daily_atr and daily_atr > 0:
        blended_atr = daily_atr
    elif intraday_atr > 0:
        blended_atr = intraday_atr
    else:
        blended_atr = vwap * 0.015  # 1.5% cold-start fallback
    
    atr_buffer = max(0.005, min(0.03, (blended_atr / vwap) * 0.5))
```

---

### Option C: Adaptive Multiplier Based on Price Level

**Effort: Low** | **Optional Enhancement**

The current 0.5x multiplier treats all stocks the same. Consider scaling based on price:

```python
# Adaptive multiplier: lower-priced stocks get tighter bands
# (their ATR is already larger relative to price)
if last_price < 2.0:
    multiplier = 0.35  # Tighter for penny-like stocks
elif last_price < 5.0:
    multiplier = 0.45
else:
    multiplier = 0.50  # Standard for $5+ stocks

atr_buffer = max(0.005, min(0.03, (blended_atr / vwap) * multiplier))
```

---

## ATR Period Considerations

| Period | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| 5-period | Very responsive to recent volatility | Noisy, overfits to recent spikes | Not recommended |
| 10-period | Good balance for 1-min intraday | Slightly noisy early session | **Use for intraday** |
| 14-period | Standard, well-tested | Slower to adapt intra-day | Use for daily blend |
| 20-period | Very stable | Too slow for intraday triggers | Not recommended |

**Recommendation**: Use 14-period for intraday True Range (matching the daily ATR convention), with fallback to 10-period if fewer candles available.

---

## Performance Impact Assessment

### Memory
- **Current**: `completed_bars_1m` stores 3 fields per candle x 20 candles = 60 values per symbol
- **After fix**: 5 fields x 20 candles = 100 values per symbol (negligible increase)

### CPU
- **Current**: Simple abs(close-open) per candle — ~10 iterations
- **After fix**: True Range calculation with max() — ~14 iterations per symbol per tick
- **Impact**: Negligible. The VWAP calculation and state machine already iterate similarly.

### Latency
- No additional I/O. All computation is in-memory.
- Daily ATR is loaded once per subscription cycle (every 5 minutes).

### Backwards Compatibility
- Option A's fallback (lines checking `high`/`low` keys) handles old candles that lack high/low fields during the transition period.

---

## Implementation Priority

1. **Phase 1** (Option A): Fix completed_bars_1m to store high/low, compute proper intraday True Range. **This is the minimum viable improvement.**
2. **Phase 2** (Option B): Blend daily ATR(14) with intraday range for more stable estimates.
3. **Phase 3** (Option C): Add price-level adaptive multiplier as a polish refinement.

---

## Key Files to Modify

| File | Change |
|------|--------|
| `momentum_screener/schwab/stream_client.py:800-804` | Add high/low to completed candle dict |
| `momentum_screener/schwab/stream_client.py:846-869` | Replace approximated ATR with proper True Range calculation |
| `momentum_screener/schwab/stream_client.py:130-274` (load_fundamentals) | Optionally load daily_atr_14 from daily_gainers |
| `momentum_screener/schwab/stream_client.py:82-92` (init) | Add `self.daily_atr_cache = {}` if using Option B |

---

## Testing Strategy

1. **Unit test**: Pure ATR calculation function (no DB, no HTTP) in `tests/test_stream_atr.py`
2. **Manual verification**: Log atr_buffer values during streaming to confirm they scale with actual volatility
3. **A/B comparison**: Fire alerts with old vs new hysteresis on same data, compare noise reduction
4. **Edge cases to test**:
   - Cold start (< 5 candles): should use default 1.5%
   - Very low price stock ($1-2): buffer should floor at 0.5%
   - Very high volatility stock: buffer should cap at 3%
   - Gap-up open with high intraday range: buffer should widen appropriately
