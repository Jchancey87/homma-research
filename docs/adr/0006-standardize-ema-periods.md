# Standardize EMA periods to 9/20/55 across all chart views

All chart views (daily-charts mini charts, alerts page, research charts, and the new alert-review page) use EMA periods 9, 20, and 55 plus VWAP. This replaces the previous split configuration: non-mini charts used 8/13/21/34/55 and mini charts used 21/50/100.

The 9/20/55 set is optimized for intraday momentum trading: EMA-9 tracks fast price reaction (entry timing), EMA-20 serves as mean reversion / pullback support, and EMA-55 identifies the session trend. Having one EMA vocabulary across all views means levels read on the alert-review post-mortem are the same levels visible during live scanning — no mental translation between chart contexts.

## Considered Options

- **Keep existing split (8/13/21/34/55 non-mini, 21/50/100 mini):** Rejected — three different EMA configurations across the app creates cognitive overhead and makes alert-review comparisons to daily-charts inconsistent.
- **Configurable per-page EMAs:** Rejected — flexibility without a clear use case; adds UI complexity and makes chart screenshots non-comparable.
