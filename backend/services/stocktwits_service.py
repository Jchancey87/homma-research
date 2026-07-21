"""
stocktwits_service.py — StockTwits REST API integration.

Provides live social sentiment, watchers count (crowd size), message streams,
and trending status for stock symbols.
"""
from __future__ import annotations

import logging
import time
import requests
from typing import Any

log = logging.getLogger(__name__)

# Simple in-memory cache with TTL (seconds)
_CACHE: dict[str, tuple[float, Any]] = {}
_CACHE_TTL_SECONDS = 120

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def get_stocktwits_sentiment(ticker: str) -> dict[str, Any]:
    """
    Fetch StockTwits sentiment metrics and message stream for `ticker`.

    Returns a dict with:
        - ticker          (str)
        - title           (str)
        - watchers_count  (int)  — total retail users tracking this symbol
        - message_count   (int)  — number of recent messages fetched (up to 30)
        - bullish_count   (int)  — count of labeled Bullish posts
        - bearish_count   (int)  — count of labeled Bearish posts
        - bullish_ratio   (float | None) — ratio of Bullish / (Bullish + Bearish)
        - is_trending     (bool) — whether the symbol is in StockTwits trending
        - top_messages    (list[dict]) — top engagement posts (body, user, likes, sentiment)
    """
    symbol = ticker.upper().strip()
    cache_key = f"st_sentiment_{symbol}"

    # Check cache
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return data

    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"

    default_response: dict[str, Any] = {
        "ticker": symbol,
        "title": "",
        "watchers_count": 0,
        "message_count": 0,
        "bullish_count": 0,
        "bearish_count": 0,
        "bullish_ratio": None,
        "is_trending": False,
        "top_messages": [],
    }

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            log.warning(f"[StockTwits] {symbol} fetch returned HTTP {resp.status_code}")
            _CACHE[cache_key] = (now, default_response)
            return default_response

        raw_data = resp.json()
        sym_info = raw_data.get("symbol", {})
        messages = raw_data.get("messages", [])

        watchers = sym_info.get("watchlist_count", 0) or 0
        title = sym_info.get("title", "") or ""
        is_trending = bool(sym_info.get("trending", False))

        bullish_cnt = 0
        bearish_cnt = 0
        formatted_messages = []

        for m in messages:
            entities = m.get("entities", {}) or {}
            sentiment_obj = entities.get("sentiment") or {}
            sent_label = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None

            if sent_label == "Bullish":
                bullish_cnt += 1
            elif sent_label == "Bearish":
                bearish_cnt += 1

            user_obj = m.get("user", {}) or {}
            likes_obj = m.get("likes", {}) or {}

            formatted_messages.append({
                "id": m.get("id"),
                "body": m.get("body", ""),
                "created_at": m.get("created_at", ""),
                "username": user_obj.get("username", ""),
                "followers": user_obj.get("followers", 0),
                "likes": likes_obj.get("total", 0),
                "sentiment": sent_label or "Neutral",
            })

        total_labeled = bullish_cnt + bearish_cnt
        bullish_ratio = round(bullish_cnt / total_labeled, 3) if total_labeled > 0 else None

        # Sort top messages by likes descending
        top_messages = sorted(formatted_messages, key=lambda x: x["likes"], reverse=True)[:5]

        result = {
            "ticker": symbol,
            "title": title,
            "watchers_count": watchers,
            "message_count": len(messages),
            "bullish_count": bullish_cnt,
            "bearish_count": bearish_cnt,
            "bullish_ratio": bullish_ratio,
            "is_trending": is_trending,
            "top_messages": top_messages,
        }

        _CACHE[cache_key] = (now, result)
        return result

    except Exception as e:
        log.warning(f"[StockTwits] Failed to fetch sentiment for {symbol}: {e}")
        _CACHE[cache_key] = (now, default_response)
        return default_response


def get_trending_symbols() -> list[dict[str, Any]]:
    """
    Fetch current trending symbols across StockTwits.

    Returns list of dicts with symbol, title, watchlist_count, etc.
    """
    cache_key = "st_trending_symbols"
    now = time.time()
    if cache_key in _CACHE:
        ts, data = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SECONDS:
            return data

    url = "https://api.stocktwits.com/api/2/trending/symbols.json"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            log.warning(f"[StockTwits] Trending fetch returned HTTP {resp.status_code}")
            return []

        raw_data = resp.json()
        symbols = raw_data.get("symbols", [])
        results = []
        for s in symbols:
            results.append({
                "symbol": s.get("symbol"),
                "title": s.get("title"),
                "watchlist_count": s.get("watchlist_count", 0),
                "trending_score": s.get("trending_score"),
            })

        _CACHE[cache_key] = (now, results)
        return results
    except Exception as e:
        log.warning(f"[StockTwits] Failed to fetch trending symbols: {e}")
        return []
