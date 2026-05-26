"""
pump_classifier.py — No-News Pump detection and catalyst tagging.

Classifies each live gainer into one of three catalyst tiers:
  'Confirmed Catalyst'  — has a news_headline (fundamental driver)
  'Technical / No News' — null news + gap > threshold + high RVOL
  'Speculative'         — null news + low or unknown RVOL

Two-phase classification:
  Phase 1 (lightweight):  `stamp_catalyst_tags()` — instant, uses only existing
                           in-memory gainer fields. Called on every screener refresh.

  Phase 2 (async verify): `start_news_enrichment_loop()` — background thread that
                           runs every 3 minutes during market hours, calls the
                           NewsAggregator to actively verify no-news tickers.
                           Upgrades 'Technical / No News' → 'Confirmed Catalyst'
                           if news is found. Also writes to pump_classifications DB.

Usage:
    from services.pump_classifier import stamp_catalyst_tags, start_news_enrichment_loop
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable

import pytz

log = logging.getLogger(__name__)

# ── Classification thresholds ──────────────────────────────────────────────────
NO_NEWS_GAP_PCT_MIN = 30.0   # Must clear screener entry threshold
NO_NEWS_RVOL_MIN    = 2.0    # Must show meaningful relative volume
NEWS_LOOKBACK_HOURS = 24     # Check for news within the last 24 hours

# ── Catalyst tag constants ─────────────────────────────────────────────────────
CATALYST_CONFIRMED  = 'Confirmed Catalyst'
CATALYST_NO_NEWS    = 'Technical / No News'
CATALYST_SPECULATIVE = 'Speculative'

EASTERN = pytz.timezone('US/Eastern')


# ── Phase 1: Lightweight in-memory classifier ─────────────────────────────────

def classify_catalyst(gainer: dict) -> str:
    """
    Classify a single gainer dict using only its existing fields (no API calls).

    Decision tree:
      1. Has news_headline → 'Confirmed Catalyst'
      2. No news + gap > 30% + rvol > 2x → 'Technical / No News'
      3. No news + any other case → 'Speculative'
    """
    headline = gainer.get('news_headline')
    gap_pct  = gainer.get('gap_pct') or 0.0
    rvol     = gainer.get('rvol_15m')

    if headline and str(headline).strip():
        return CATALYST_CONFIRMED

    # No news branch
    if gap_pct >= NO_NEWS_GAP_PCT_MIN and rvol is not None and rvol >= NO_NEWS_RVOL_MIN:
        return CATALYST_NO_NEWS

    return CATALYST_SPECULATIVE


def stamp_catalyst_tags(gainers: list[dict]) -> list[dict]:
    """
    Lightweight pass: classify all gainers and stamp a `catalyst` field on each.
    Runs synchronously during every screener refresh cycle (no blocking I/O).

    Preserves any existing `catalyst` value that was upgraded by the async
    enrichment loop (to avoid downgrading a verified tag back to lightweight).
    """
    for g in gainers:
        # Don't overwrite an async-verified tag
        existing = g.get('catalyst')
        if existing == CATALYST_CONFIRMED and not g.get('news_headline'):
            # Async loop upgraded this — keep it
            continue

        g['catalyst'] = classify_catalyst(g)

    return gainers


# ── Phase 2: Background async enrichment loop ─────────────────────────────────

def _is_market_hours() -> bool:
    """Return True during pre-market, open, and after-hours sessions."""
    now_et = datetime.now(EASTERN)
    if now_et.weekday() >= 5:   # weekend
        return False
    hm = now_et.hour * 60 + now_et.minute
    return 4 * 60 <= hm < 20 * 60   # 04:00–19:59 ET


def _verify_and_upgrade(gainers: list[dict], aggregator) -> list[dict]:
    """
    For each gainer tagged 'Technical / No News', call the NewsAggregator
    to verify. If news IS found, upgrade the tag to 'Confirmed Catalyst'.

    Returns gainers with upgraded tags (mutates in place).
    """
    candidates = [
        g for g in gainers
        if g.get('catalyst') == CATALYST_NO_NEWS
        and (g.get('gap_pct') or 0) >= NO_NEWS_GAP_PCT_MIN
    ]

    if not candidates:
        return gainers

    log.info(f'[PumpClassifier] Verifying {len(candidates)} no-news ticker(s) via NewsAggregator')

    for g in candidates:
        ticker = g.get('ticker', '')
        try:
            has_news = aggregator.has_news(ticker, hours_back=NEWS_LOOKBACK_HOURS)
            if has_news:
                log.info(f'[PumpClassifier] {ticker}: news FOUND → upgrading to Confirmed Catalyst')
                g['catalyst'] = CATALYST_CONFIRMED
                _persist_classification(g, news_source='yfinance_verify')
            else:
                log.debug(f'[PumpClassifier] {ticker}: no-news confirmed by aggregator')
                _persist_classification(g, news_source='yfinance_verify')
        except Exception as e:
            log.warning(f'[PumpClassifier] Verification failed for {ticker}: {e}')

    return gainers


def _persist_classification(gainer: dict, news_source: str = 'lightweight_check'):
    """
    Upsert a row in pump_classifications for historical tracking.
    Silently swallows DB errors to never block the enrichment loop.
    """
    try:
        import pytz
        from database import get_connection

        now_et = datetime.now(pytz.timezone('US/Eastern'))
        today  = now_et.strftime('%Y-%m-%d')
        ticker = gainer.get('ticker', '')

        if not ticker:
            return

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pump_classifications
                    (ticker, date, catalyst_tag, gap_pct, rvol, float_shares, news_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO UPDATE
                    SET catalyst_tag  = EXCLUDED.catalyst_tag,
                        gap_pct       = EXCLUDED.gap_pct,
                        rvol          = EXCLUDED.rvol,
                        float_shares  = EXCLUDED.float_shares,
                        classified_at = now(),
                        news_source   = EXCLUDED.news_source
                """,
                (
                    ticker,
                    today,
                    gainer.get('catalyst', CATALYST_SPECULATIVE),
                    gainer.get('gap_pct'),
                    gainer.get('rvol_15m'),
                    gainer.get('float_shares'),
                    news_source,
                ),
            )
    except Exception as e:
        log.warning(f'[PumpClassifier] DB persist failed for {gainer.get("ticker")}: {e}')


def _enrichment_loop(get_current_gainers_fn: Callable[[], list[dict]], interval_seconds: int = 180):
    """
    Background thread body: verify no-news tickers every `interval_seconds`
    during market hours. Runs indefinitely as a daemon thread.
    """
    from services.news_aggregator import get_default_aggregator

    aggregator = get_default_aggregator()
    log.info('[PumpClassifier] News enrichment loop started')

    while True:
        try:
            if _is_market_hours():
                gainers = get_current_gainers_fn()
                if gainers:
                    _verify_and_upgrade(gainers, aggregator)
            else:
                log.debug('[PumpClassifier] Market closed — enrichment loop idle')
        except Exception as e:
            log.error(f'[PumpClassifier] Enrichment loop error: {e}', exc_info=True)

        time.sleep(interval_seconds)


def start_news_enrichment_loop(
    get_current_gainers_fn: Callable[[], list[dict]],
    interval_seconds: int = 180,
):
    """
    Launch the background async enrichment thread.

    Args:
        get_current_gainers_fn: A callable that returns the current list of gainer
                                dicts from the live screener cache. The returned
                                list is mutated in-place with upgraded catalyst tags.
        interval_seconds:       Verification cadence (default 3 minutes).
    """
    t = threading.Thread(
        target=_enrichment_loop,
        args=(get_current_gainers_fn, interval_seconds),
        name='pump-classifier-enrichment',
        daemon=True,
    )
    t.start()
    log.info('[PumpClassifier] News enrichment thread launched')
