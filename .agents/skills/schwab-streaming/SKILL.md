---
name: schwab-streaming
description: Operational rules, Level 1 quote streaming schemas, Redis bridge mechanisms, and caching rules for Schwab streaming.
---

# Schwab Streaming & Quotes Architecture

## Core Mechanics
* **Singleton Client:** `SchwabStreamer` in `momentum_screener/schwab/stream_client.py`.
* **Thread Safety:** REST calls via `get_http_client()` use `threading.local()`. Never share instances across threads.
* **Subscription Management:** Dynamic 5m worker `update_subscriptions()`. Subscribes via `level_one_equity_add(list(to_sub))` and unsubscribes via `level_one_equity_unsubs(list(to_unsub))`.
* **Streaming Bridge:** `StreamingPriceBridge` in `services/streaming_prices.py`. Subscribes to Redis `screener:quotes` channel, maintains `_prices: dict[str, PriceSnapshot]` with 60s staleness expiry.

## Pipeline Refresh Strategy
* **Fast Path (2s):** `_fast_refresh()` in `live_screener.py` overlays WebSocket-streamed quotes from Redis without REST calls. Only overlays if streamed snapshot timestamp is strictly newer than cached gainer row `_last_update_ts`.
* **Slow Path (60s):** Full REST pipeline (Schwab Movers + Quotes + enrichment).
