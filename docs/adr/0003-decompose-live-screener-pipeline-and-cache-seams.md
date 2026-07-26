# ADR 0003: Decompose Live Screener Pipeline and Cache Seams

## Status
Accepted

## Context
`live_screener.py` in `backend/services/live_screener.py` was a 1,202-line procedural monolith. It mixed candidate REST sourcing (Schwab Movers + TradingView HTTP), technical indicator calculations (ATR, VWAP, EMA, sparklines, Ross Cameron scanner metrics), 5 global dictionary caches, 4 thread locks, fast (2s) Redis tick overlays, slow (60s) REST refreshes, and background thread lifecycle management.

As a result, pure technical calculations could not be unit-tested without locking thread caches, and thread safety across fast/slow refreshes was hard to reason about.

## Decision
We decompose the live screener into three distinct modules with clean seams:
1. **Stateless Metrics (`backend/services/screener_metrics.py`)**: Pure functions for ATR14, EMA9, sparkline sampling, and Ross Cameron momentum metrics. Zero I/O, zero thread locks, zero state.
2. **Encapsulated Cache (`backend/services/screener_cache.py`)**: A thread-safe `ScreenerCache` class encapsulating all dictionary caches and lock discipline behind explicit methods (`get_gainers()`, `update_gainers()`, `overlay_streaming_ticks()`).
3. **Candidate Sourcing (`backend/services/screener_source.py`)**: A `ScreenerCandidateSource` adapter isolating Schwab Movers REST and TradingView HTTP fetches.
4. **Thin Orchestrator (`backend/services/live_screener.py`)**: Shrinks to ~150 lines, orchestrating candidate sourcing → metrics → cache while maintaining public functions (`refresh_cache()`, `get_live_gainers()`) for 100% backward compatibility.

## Consequences
### Positive
- All technical indicator math can be tested as fast, pure unit tests without thread state.
- Lock discipline and cache race-condition handling concentrate in a single `ScreenerCache` class.
- Candidate API fetching isolates from UI response formatting.

### Negative / Trade-offs
- Refactors 1,202 lines of `live_screener.py` across 3 new focused modules (`screener_metrics.py`, `screener_cache.py`, `screener_source.py`).
