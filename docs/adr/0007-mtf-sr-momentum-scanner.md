# ADR 0007: Multi-Timeframe S/R Momentum Scanner Architecture

## Status
Accepted

## Context
Traders need a real-time "In Play" scanner that identifies stocks actively testing or breaking key Support & Resistance (S/R) levels with multi-indicator momentum confirmation. S/R levels span multiple timeframes: Tier 1 Daily levels (pre-market major boundaries), Tier 2 5-minute levels (intraday micro-structures), and 1-minute execution bars (proximity detection & volume/momentum triggers).

To prevent noise and maintain execution efficiency, 1-minute candles must NOT generate independent S/R levels. Instead, 1-minute price action is evaluated against ATR-scaled proximity windows from Tier 1 & Tier 2 levels.

## Decision
We implement the Multi-Timeframe (MTF) S/R Momentum Scanner following these architectural boundaries:

1. **Terminology**:
   - The scanner state is named **`MTF_IN_PLAY`** (score $\ge 50$) to avoid collision with the session-scoped `AIP` (Already In Play) alert-suppression state.

2. **Single Primary Data Provider**:
   - All historical daily, 5-minute, and streaming 1-minute candles are sourced from our existing **Schwab API facade** (`backend/services/schwab_client.py` and `momentum_screener/schwab/stream_client.py`). External services (Alpaca/Polygon/yfinance) are avoided.

3. **Pivot & Level Engine**:
   - **Tier 1 (Daily)**: Computed pre-market with `left=10, right=10` pivot lookbacks, explicitly augmented with Yesterday's High/Low (YHI/YLO) and 52-week High/Low. Level merge threshold: $0.25 \times \text{ATR}_{\text{daily}}$.
   - **Tier 2 (5-min)**: Refreshed every 5 minutes with `left=5, right=2` pivot lookbacks, augmented with immediate Session High/Low of Day (HOD/LOD). Level merge threshold: $0.50 \times \text{ATR}_{5\text{min}}$.
   - **Coincident Levels**: Flagged when a 5-minute S/R level aligns within $1.0 \times \text{ATR}_{\text{daily}}$ of a Daily S/R level.

4. **100-Point Confluence Scoring Matrix**:
   - Rebalanced matrix summing to exactly 100 points maximum:
     - Tier 1 Daily S/R Proximity ($\le 0.25 \text{ATR}_{\text{daily}}$): **+20**
     - Tier 2 5-min S/R Proximity ($\le 0.50 \text{ATR}_{5\text{min}}$): **+15**
     - Coincident Level Alignment (5-min aligns with Daily): **+10**
     - Level Significance ($\ge 3$ prior touches): **+5**
     - 1-min RVOL Burst ($\ge 3.0\times$ vs 20-bar avg): **+20**
     - 1-min EMA Momentum Cross (EMA 9 > 21): **+10**
     - VWAP Trend Alignment (Price above VWAP for bullish / below for bearish): **+10**
     - 1-min RSI Regime Crossing (RSI crossing 50): **+5**
     - 1-min ATR Volatility Expansion (1-min ATR > 20-bar avg): **+5**
   - **Thresholds**:
     - **`MTF_IN_PLAY`**: Score $\ge 50$ (Dashboard Highlight)
     - **High Conviction Alert**: Score $\ge 75$ (Desktop Notification)
     - **Coincident Audio Alert**: Score $\ge 75$ + Coincident Level Flag (Audio Chiming)

5. **Transport & Delivery**:
   - Broadcast MTF Scanner state updates via our existing WebSocket pipeline (`screener:alerts` / `screener:mtf_scanner` Redis channel to `/ws/alerts`) every 60 seconds.

## Consequences
### Positive
- Unified data architecture relying 100% on Schwab.
- Mathematically capped 100-point scale eliminates ambiguous score overflows.
- Eliminates 1-minute noise by restricting S/R level generation exclusively to Daily and 5-minute timeframes.

### Negative / Trade-offs
- Requires caching and periodically updating 5-minute S/R levels per active symbol in memory.
