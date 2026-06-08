"""
news_aggregator.py — Pluggable news aggregation interface.

Architecture:
  - NewsSource (ABC)          — defines the interface all news providers must implement
  - MassiveNewsSource         — Massive.com (fka Polygon.io) REST API — primary, real-time
  - YFinanceNewsSource        — yfinance scraper — free fallback / supplement
  - BenzingaNewsSource        — stub, ready for future implementation
  - NewsAggregator            — fan-out orchestrator; merges results from all sources

Usage:
    from services.news_aggregator import get_default_aggregator

    agg = get_default_aggregator()
    if agg.has_news('YMAT', hours_back=4):
        articles = agg.get_news('YMAT', hours_back=4)
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
        'published':   published,   # ISO datetime string YYYY-MM-DDTHH:MM:SSZ
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
# Massive.com (fka Polygon.io) — PRIMARY source
# ---------------------------------------------------------------------------

class MassiveNewsSource(NewsSource):
    """
    Live news from Massive.com via the official SDK (polygon-api-client / massive).
    Real-time, indexed within seconds of publication. Requires POLYGON_API_KEY.

    This is the primary source used for live screener catalyst verification
    because it has zero indexing lag and covers all major financial newswires.
    """

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        try:
            from massive import RESTClient
            from config import Config

            if not Config.POLYGON_API_KEY:
                log.debug('[MassiveNewsSource] POLYGON_API_KEY not set, skipping.')
                return []

            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            from_str = cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')

            client   = RESTClient(api_key=Config.POLYGON_API_KEY, pagination=False)
            articles = list(client.list_ticker_news(
                ticker,
                published_utc_gte=from_str,
                order='desc',
                limit=20,
            ))

            results = []
            for a in articles:
                title = getattr(a, 'title', '') or ''
                if not title:
                    continue

                pub_utc = getattr(a, 'published_utc', '') or ''
                pub_dt  = None
                if pub_utc:
                    try:
                        pub_dt = datetime.fromisoformat(
                            pub_utc.replace('Z', '+00:00')
                        ).astimezone(timezone.utc)
                    except ValueError:
                        pass

                if pub_dt and pub_dt < cutoff:
                    continue

                publisher = ''
                pub_obj   = getattr(a, 'publisher', None)
                if isinstance(pub_obj, dict):
                    publisher = pub_obj.get('name', '')
                elif hasattr(pub_obj, 'name'):
                    publisher = pub_obj.name or ''

                description = getattr(a, 'description', '') or ''

                results.append(_make_article(
                    title=title,
                    published=pub_dt.strftime('%Y-%m-%dT%H:%M:%SZ') if pub_dt else pub_utc,
                    source=f'massive/{publisher}' if publisher else 'massive',
                    description=(description or '')[:400],
                ))

            log.debug(f'[MassiveNewsSource] {ticker}: {len(results)} articles in last {hours_back}h')
            return results

        except Exception as e:
            log.warning(f'[MassiveNewsSource] {ticker}: fetch failed — {e}')
            return []


# ---------------------------------------------------------------------------
# yfinance — FALLBACK / supplement
# ---------------------------------------------------------------------------

class YFinanceNewsSource(NewsSource):
    """
    Live news source backed by yfinance (free, no API key required).

    Note: yfinance news is scraped from Yahoo Finance and may lag real-time
    by 5–30 minutes. Used as fallback when Massive is unavailable or returns nothing.
    """

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        try:
            import yfinance as yf

            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            t      = yf.Ticker(ticker)
            raw    = t.news or []

            results = []
            for item in raw[:30]:
                title = (
                    item.get('title') or
                    (item.get('content') or {}).get('title', '') or
                    ''
                )
                if not title:
                    continue

                publisher = (
                    item.get('publisher') or
                    (item.get('content') or {}).get('provider', {}).get('displayName', '') or
                    'yfinance'
                )

                pub_dt = None

                # Shape 1: providerPublishTime (unix int)
                ts = item.get('providerPublishTime')
                if ts and isinstance(ts, (int, float)) and ts > 1_000_000:
                    pub_dt = datetime.fromtimestamp(ts, tz=timezone.utc)

                # Shape 2: content.pubDate (ISO string)
                if pub_dt is None:
                    s = (item.get('content') or {}).get('pubDate', '')
                    if s:
                        try:
                            pub_dt = datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)
                        except ValueError:
                            pass

                # Shape 3: displayTime
                if pub_dt is None:
                    s = item.get('displayTime', '')
                    if s:
                        try:
                            pub_dt = datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(timezone.utc)
                        except ValueError:
                            pass

                if pub_dt is None:
                    continue
                if pub_dt < cutoff:
                    continue

                results.append(_make_article(
                    title=title,
                    published=pub_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
                    source=f'yfinance/{publisher}',
                ))

            log.debug(f'[YFinanceNewsSource] {ticker}: {len(results)} articles in last {hours_back}h')
            return results

        except Exception as e:
            log.warning(f'[YFinanceNewsSource] {ticker}: fetch failed — {e}')
            return []


# ---------------------------------------------------------------------------
# Benzinga stub (future)
# ---------------------------------------------------------------------------

class BenzingaNewsSource(NewsSource):
    """
    Stub implementation for a future Benzinga news aggregator.

    To activate:
      1. Set BENZINGA_API_KEY in your .env
      2. Implement get_news() using the Benzinga REST API
      3. Register it in get_default_aggregator()
    """

    def __init__(self, api_key: str | None = None):
        import os
        self._api_key = api_key or os.environ.get('BENZINGA_API_KEY')

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        raise NotImplementedError(
            'BenzingaNewsSource is a stub. Implement get_news() with your API credentials.'
        )


# ---------------------------------------------------------------------------
# Aggregator — fan-out orchestrator
# ---------------------------------------------------------------------------

class NewsAggregator:
    """
    Runs multiple NewsSource providers in sequence, merges results, and
    de-duplicates by title prefix (first 40 chars, case-insensitive).
    """

    def __init__(self, sources: list[NewsSource]):
        if not sources:
            raise ValueError('NewsAggregator requires at least one NewsSource.')
        self.sources = sources

    def get_news(self, ticker: str, hours_back: int = 24) -> list[dict]:
        """Return merged, de-duplicated articles from all sources."""
        all_articles: list[dict] = []
        seen: set[str] = set()

        for source in self.sources:
            try:
                for article in source.get_news(ticker, hours_back=hours_back):
                    prefix = (article.get('title', '') or '')[:40].lower().strip()
                    if prefix and prefix not in seen:
                        all_articles.append(article)
                        seen.add(prefix)
            except NotImplementedError:
                log.debug(f'[NewsAggregator] {source.name} is not implemented, skipping.')
            except Exception as e:
                log.warning(f'[NewsAggregator] {source.name} error for {ticker}: {e}')

        return all_articles

    def has_news(self, ticker: str, hours_back: int = 24) -> bool:
        """
        Returns True if any news article was found within the last `hours_back` hours.
        Short-circuits on the first source that returns a result.
        """
        for source in self.sources:
            try:
                articles = source.get_news(ticker, hours_back=hours_back)
                if articles:
                    log.debug(
                        f'[NewsAggregator] {ticker}: confirmed via {source.name} '
                        f'({len(articles)} article(s))'
                    )
                    return True
            except NotImplementedError:
                continue
            except Exception as e:
                log.warning(f'[NewsAggregator] {source.name} error for {ticker}: {e}')
                continue

        log.debug(f'[NewsAggregator] {ticker}: no news found in last {hours_back}h')
        return False


# ---------------------------------------------------------------------------
# Default singleton — Massive primary, yfinance fallback
# ---------------------------------------------------------------------------

def get_default_aggregator() -> NewsAggregator:
    """
    Returns the production NewsAggregator.
    Massive is called first (real-time, no lag).
    yfinance is called only if Massive returns nothing.
    """
    return NewsAggregator(sources=[
        MassiveNewsSource(),
        YFinanceNewsSource(),
    ])
