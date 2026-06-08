"""
pump_classifier.py — No-News Pump detection and catalyst tagging.

Classifies each live gainer into one of three catalyst tiers:
  'Confirmed Catalyst'  — has a verified news headline (fundamental driver)
  'Technical / No News' — no news + gap > threshold + high RVOL
  'Speculative'         — no news + low or unknown RVOL

Two-phase classification:
  Phase 1 (lightweight):  stamp_catalyst_tags() — instant, no I/O.
                           Called on every screener refresh cycle.

  Phase 2 (async verify): start_news_enrichment_loop() — background thread
                           with per-ticker retry state:
                             • First 10 minutes: checks every 60 seconds
                             • After 10 minutes: checks every 3 minutes
                             • Once confirmed, stops retrying that ticker
                           Uses Massive (primary) + yfinance (fallback).
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Dict

import pytz

log = logging.getLogger(__name__)

# ── Classification thresholds ──────────────────────────────────────────────────
NO_NEWS_GAP_PCT_MIN = 30.0   # Minimum gap to classify as 'Technical / No News'
NO_NEWS_RVOL_MIN    = 2.0    # Minimum RVOL for same
NEWS_LOOKBACK_HOURS = 6      # Look back 6 hours for live screener checks
                              # (24h is for historical catalyst analysis)

# ── Retry tuning ───────────────────────────────────────────────────────────────
AGGRESSIVE_INTERVAL_S   = 60    # Check every 60s for first AGGRESSIVE_WINDOW_S
AGGRESSIVE_WINDOW_S     = 600   # 10 minutes of aggressive retries per ticker
BACKOFF_INTERVAL_S      = 180   # Check every 3 min after aggressive window
MAX_CONFIRMED_AGE_S     = 3600  # Forget confirmed tickers after 1 hour (re-check if still live)

# ── Catalyst tag constants ─────────────────────────────────────────────────────
CATALYST_CONFIRMED   = 'Confirmed Catalyst'
CATALYST_NO_NEWS     = 'Technical / No News'
CATALYST_SPECULATIVE = 'Speculative'

EASTERN = pytz.timezone('US/Eastern')


# ── Phase 1: Lightweight in-memory classifier ─────────────────────────────────

def classify_catalyst(gainer: dict) -> str:
    """
    Classify a single gainer dict using only its existing fields (no API calls).

    Decision tree:
      1. Has news_headline → 'Confirmed Catalyst'
      2. No news + gap >= 30% + rvol >= 2x → 'Technical / No News'
      3. Anything else → 'Speculative'
    """
    headline = gainer.get('news_headline')
    gap_pct  = gainer.get('gap_pct') or 0.0
    rvol     = gainer.get('rvol_15m')

    if headline and str(headline).strip():
        return CATALYST_CONFIRMED

    if gap_pct >= NO_NEWS_GAP_PCT_MIN and rvol is not None and rvol >= NO_NEWS_RVOL_MIN:
        return CATALYST_NO_NEWS

    return CATALYST_SPECULATIVE


def stamp_catalyst_tags(gainers: list[dict]) -> list[dict]:
    """
    Lightweight pass: stamp a `catalyst` field on every gainer.
    Runs synchronously during every screener refresh (no I/O).
    Preserves async-verified tags so they are never downgraded.
    """
    for g in gainers:
        existing = g.get('catalyst')
        # Don't overwrite a verified tag that the async loop already confirmed
        if existing == CATALYST_CONFIRMED and not g.get('news_headline'):
            continue
        g['catalyst'] = classify_catalyst(g)
    return gainers


# ── Phase 2: Background enrichment with per-ticker retry state ────────────────

class _TickerRetryState:
    """
    Tracks the news-check retry state for a single ticker.

    Lifecycle:
      - Created when a ticker first appears as 'Technical / No News'
      - Checked aggressively (every 60s) for the first 10 minutes
      - Backs off to every 3 min after that
      - Marked `confirmed=True` once news is found (no further checks)
    """
    __slots__ = ('ticker', 'first_seen', 'last_checked', 'confirmed', 'confirmed_at')

    def __init__(self, ticker: str):
        self.ticker       = ticker
        self.first_seen   = time.monotonic()
        self.last_checked = 0.0       # never checked yet
        self.confirmed    = False
        self.confirmed_at = 0.0

    def is_due(self) -> bool:
        """Return True if this ticker is due for another news check."""
        if self.confirmed:
            return False
        now   = time.monotonic()
        age   = now - self.first_seen
        since = now - self.last_checked
        interval = AGGRESSIVE_INTERVAL_S if age < AGGRESSIVE_WINDOW_S else BACKOFF_INTERVAL_S
        return since >= interval

    def mark_checked(self):
        self.last_checked = time.monotonic()

    def mark_confirmed(self):
        self.confirmed    = True
        self.confirmed_at = time.monotonic()


def _is_market_hours() -> bool:
    """Return True during pre-market, open, and after-hours sessions."""
    now_et = datetime.now(EASTERN)
    if now_et.weekday() >= 5:
        return False
    hm = now_et.hour * 60 + now_et.minute
    return 4 * 60 <= hm < 20 * 60   # 04:00–19:59 ET


def _enrichment_loop(get_current_gainers_fn: Callable[[], list[dict]]):
    """
    Background thread body.

    Maintains a dict of _TickerRetryState keyed by ticker symbol.
    On each iteration (every ~10s polling interval):
      1. Get current gainers from the screener cache
      2. Register any new 'Technical / No News' tickers
      3. For each ticker that is due for a check, call the aggregator
      4. If news found → upgrade tag, persist to DB, mark confirmed
      5. Prune tickers that are no longer in the screener or are confirmed
    """
    from services.news_aggregator import get_default_aggregator
    aggregator  = get_default_aggregator()
    retry_state: Dict[str, _TickerRetryState] = {}

    log.info('[PumpClassifier] News enrichment loop started (Massive + yfinance)')

    while True:
        try:
            if not _is_market_hours():
                log.debug('[PumpClassifier] Market closed — enrichment loop idle')
                time.sleep(60)
                continue

            gainers = get_current_gainers_fn()
            if not gainers:
                time.sleep(10)
                continue

            # ── Index current screener tickers ──
            current_tickers = {g['ticker']: g for g in gainers}

            # ── Register new unconfirmed tickers ──
            for ticker, g in current_tickers.items():
                if g.get('catalyst') == CATALYST_NO_NEWS and ticker not in retry_state:
                    retry_state[ticker] = _TickerRetryState(ticker)
                    log.info(f'[PumpClassifier] Registered {ticker} for aggressive retry '
                             f'(gap={g.get("gap_pct", 0):.1f}%)')

            # ── Check tickers that are due ──
            due = [s for s in retry_state.values() if s.is_due()]
            if due:
                log.info(f'[PumpClassifier] Checking {len(due)} ticker(s) for news: '
                         f'{[s.ticker for s in due]}')

            for state in due:
                ticker = state.ticker
                g      = current_tickers.get(ticker)
                state.mark_checked()

                try:
                    has_news = aggregator.has_news(ticker, hours_back=NEWS_LOOKBACK_HOURS)
                except Exception as e:
                    log.warning(f'[PumpClassifier] News check failed for {ticker}: {e}')
                    continue

                if has_news:
                    log.info(f'[PumpClassifier] ✅ {ticker}: news FOUND → Confirmed Catalyst')
                    state.mark_confirmed()
                    if g is not None:
                        g['catalyst'] = CATALYST_CONFIRMED
                        _persist_classification(g, news_source='massive_verify')
                else:
                    age_s = time.monotonic() - state.first_seen
                    mode  = 'aggressive' if age_s < AGGRESSIVE_WINDOW_S else 'backoff'
                    log.debug(f'[PumpClassifier] ⬜ {ticker}: no news ({mode} mode, '
                              f'{age_s:.0f}s since first seen)')
                    if g is not None:
                        _persist_classification(g, news_source='massive_verify')

            # ── Prune stale state ──
            # Remove tickers no longer in screener OR confirmed >1h ago
            now = time.monotonic()
            to_remove = [
                t for t, s in retry_state.items()
                if t not in current_tickers
                or (s.confirmed and (now - s.confirmed_at) > MAX_CONFIRMED_AGE_S)
            ]
            for t in to_remove:
                del retry_state[t]
                log.debug(f'[PumpClassifier] Pruned retry state for {t}')

        except Exception as e:
            log.error(f'[PumpClassifier] Enrichment loop error: {e}', exc_info=True)

        # Short polling interval — individual ticker checks are rate-limited by _TickerRetryState
        time.sleep(10)


def _persist_classification(gainer: dict, news_source: str = 'lightweight_check'):
    """Upsert a row in pump_classifications for historical tracking."""
    try:
        from database import get_connection
        now_et = datetime.now(EASTERN)
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
                    ticker, today,
                    gainer.get('catalyst', CATALYST_SPECULATIVE),
                    gainer.get('gap_pct'),
                    gainer.get('rvol_15m'),
                    gainer.get('float_shares'),
                    news_source,
                ),
            )
    except Exception as e:
        log.warning(f'[PumpClassifier] DB persist failed for {gainer.get("ticker")}: {e}')


def start_news_enrichment_loop(
    get_current_gainers_fn: Callable[[], list[dict]],
    interval_seconds: int = 180,   # kept for API compat but no longer used (state machine drives timing)
):
    """
    Launch the background news enrichment thread.

    Args:
        get_current_gainers_fn: Callable returning the live screener gainer list.
                                 The list is mutated in-place with upgraded catalyst tags.
        interval_seconds:       Legacy param — ignored. Timing is now driven by
                                 per-ticker _TickerRetryState (60s aggressive, 3min backoff).
    """
    t = threading.Thread(
        target=_enrichment_loop,
        args=(get_current_gainers_fn,),
        name='pump-classifier-enrichment',
        daemon=True,
    )
    t.start()
    log.info('[PumpClassifier] News enrichment thread launched')
