"""
news_aggregator.py — Pluggable news aggregation interface.

Architecture:
  - NewsSource (ABC)          — defines the interface all news providers must implement
  - YFinanceNewsSource        — live implementation using yfinance (free, no API key)
  - BenzingaNewsSource        — stub, ready for your custom aggregator
  - NewsAggregator            — fan-out orchestrator; merges results from all sources

Usage:
    from services.news_aggregator import NewsAggregator, YFinanceNewsSource

    aggregator = NewsAggregator(sources=[YFinanceNewsSource()])
    if aggregator.has_news('YMAT', hours_back=24):
        articles = aggregator.get_news('YMAT', hours_back=24)

To add a new source in the future:
    1. Subclass NewsSource
    2. Implement get_news(ticker, hours_back) -> list[dict]
    3. Append an instance to the NewsAggregator.sources list
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standard article shape
# ---------------------------------------------------------------------------

def _make_article(title: str, published: str, source: str, description: str = '') -> dict:
    """Normalize a raw article into the standard shape used by all sources."""
    return {
        'title':       title,
        'published':   published,   # ISO date string YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ
        'source':      source,
        'description': description,
    }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class NewsSource(ABC):
    """
    Abstract interface that every news provider must implement.

    Implementors must return a list of article dicts with at minimum:
        title       (str)
        published   (str — ISO 8601 date or datetime)
        source      (str — provider name)
        description (str — optional summary)
    """

    @abstractmethod
    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        """
        Fetch news articles for `ticker` published within the last `hours_back` hours.

        Args:
            ticker:     Stock ticker symbol (e.g. 'AAPL')
            hours_back: Lookback window in hours (default 24)

        Returns:
            List of article dicts. Empty list if no news or on error.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable name for logging."""
        return self.__class__.__name__


# ---------------------------------------------------------------------------
# yfinance implementation (live)
# ---------------------------------------------------------------------------

class YFinanceNewsSource(NewsSource):
    """
    Live news source backed by yfinance (free, no API key required).

    Note: yfinance news is scraped from Yahoo Finance and may lag real-time
    by 5–30 minutes. Good enough to confirm whether a catalyst exists.
    """

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        try:
            import yfinance as yf
            from datetime import timezone

            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            t = yf.Ticker(ticker)
            raw_news = t.news or []

            results = []
            for item in raw_news[:30]:
                # --- Title ---
                title = (
                    item.get('title') or
                    (item.get('content') or {}).get('title', '') or
                    ''
                )
                if not title:
                    continue

                # --- Publisher ---
                publisher = (
                    item.get('publisher') or
                    (item.get('content') or {}).get('provider', {}).get('displayName', '') or
                    'yfinance'
                )

                # --- Timestamp (multiple yfinance API shapes) ---
                pub_dt = None

                # Shape 1: providerPublishTime (unix int)
                ts = item.get('providerPublishTime')
                if ts and isinstance(ts, (int, float)) and ts > 1_000_000:
                    pub_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

                # Shape 2: content.pubDate (ISO string)
                if pub_dt is None:
                    pub_date_str = (item.get('content') or {}).get('pubDate', '')
                    if pub_date_str:
                        try:
                            pub_dt = datetime.fromisoformat(
                                pub_date_str.replace('Z', '+00:00')
                            ).astimezone(timezone.utc)
                        except ValueError:
                            pass

                # Shape 3: displayTime
                if pub_dt is None:
                    display_time = item.get('displayTime', '')
                    if display_time:
                        try:
                            pub_dt = datetime.fromisoformat(
                                display_time.replace('Z', '+00:00')
                            ).astimezone(timezone.utc)
                        except ValueError:
                            pass

                # Filter by recency
                if pub_dt is None:
                    continue   # can't verify freshness, skip
                if pub_dt < cutoff:
                    continue   # too old

                results.append(_make_article(
                    title=title,
                    published=pub_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    source=f'yfinance/{publisher}',
                    description='',
                ))

            log.debug(f'[YFinanceNewsSource] {ticker}: found {len(results)} articles in last {hours_back}h')
            return results

        except Exception as e:
            log.warning(f'[YFinanceNewsSource] {ticker}: fetch failed — {e}')
            return []


# ---------------------------------------------------------------------------
# Benzinga stub (future custom aggregator)
# ---------------------------------------------------------------------------

class BenzingaNewsSource(NewsSource):
    """
    Stub implementation for a future Benzinga (or custom in-house) news aggregator.

    To activate:
      1. Set BENZINGA_API_KEY in your .env
      2. Implement get_news() using the Benzinga REST API:
         GET https://api.benzinga.com/api/v2/news?tickers={ticker}&pageSize=10&token={key}
      3. Register it: NewsAggregator(sources=[YFinanceNewsSource(), BenzingaNewsSource()])
    """

    def __init__(self, api_key: str | None = None):
        import os
        self._api_key = api_key or os.environ.get('BENZINGA_API_KEY')

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        raise NotImplementedError(
            'BenzingaNewsSource is a stub. Implement get_news() with your API credentials '
            'or swap in your custom in-house news aggregator.'
        )


# ---------------------------------------------------------------------------
# Aggregator — fan-out orchestrator
# ---------------------------------------------------------------------------

class NewsAggregator:
    """
    Runs multiple NewsSource providers in sequence, merges results, and
    de-duplicates by title prefix (first 40 chars, case-insensitive).

    Usage:
        agg = NewsAggregator(sources=[YFinanceNewsSource()])
        if agg.has_news('YMAT', hours_back=24):
            ...
    """

    def __init__(self, sources: list[NewsSource]):
        if not sources:
            raise ValueError('NewsAggregator requires at least one NewsSource.')
        self.sources = sources

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        """Return merged, de-duplicated articles from all sources."""
        all_articles: list[dict] = []
        seen_prefixes: set[str] = set()

        for source in self.sources:
            try:
                articles = source.get_news(ticker, hours_back=hours_back)
                for article in articles:
                    prefix = (article.get('title', '') or '')[:40].lower().strip()
                    if prefix and prefix not in seen_prefixes:
                        all_articles.append(article)
                        seen_prefixes.add(prefix)
            except NotImplementedError:
                log.debug(f'[NewsAggregator] {source.name} is not implemented, skipping.')
            except Exception as e:
                log.warning(f'[NewsAggregator] {source.name} error for {ticker}: {e}')

        return all_articles

    def has_news(self, ticker: str, hours_back: int = 24) -> bool:
        """
        Returns True if any news article was found for `ticker` in the last `hours_back` hours.
        Short-circuits on the first source that returns a result.
        """
        for source in self.sources:
            try:
                articles = source.get_news(ticker, hours_back=hours_back)
                if articles:
                    log.debug(
                        f'[NewsAggregator] {ticker}: news confirmed via {source.name} '
                        f'({len(articles)} article(s))'
                    )
                    return True
            except NotImplementedError:
                continue
            except Exception as e:
                log.warning(f'[NewsAggregator] {source.name} error for {ticker}: {e}')
                continue

        log.debug(f'[NewsAggregator] {ticker}: no news found in last {hours_back}h across all sources')
        return False


# ---------------------------------------------------------------------------
# Default singleton aggregator (used by pump_classifier)
# ---------------------------------------------------------------------------

def get_default_aggregator() -> NewsAggregator:
    """
    Returns the default NewsAggregator instance for use by the pump classifier.

    To add a new source in the future, append it here:
        return NewsAggregator(sources=[
            YFinanceNewsSource(),
            BenzingaNewsSource(),   # when ready
            MyCustomSource(),
        ])
    """
    return NewsAggregator(sources=[YFinanceNewsSource()])
