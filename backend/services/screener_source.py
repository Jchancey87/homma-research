"""
Screener Candidate Sourcing Adapter.

Isolates Schwab Movers REST API calls and TradingView HTTP API fallback logic.
"""

import logging
from typing import Dict, List, Optional
from services.schwab_client import get_movers

logger = logging.getLogger(__name__)


class ScreenerCandidateSource:
    """Fetches candidate gainer tickers from Schwab Movers and TradingView."""

    def fetch_candidates(self, limit: int = 150) -> List[dict]:
        """
        Pull candidate movers from Schwab API with TradingView fallback/enrichment.
        Returns list of candidate dicts with ticker metadata.
        """
        candidates: Dict[str, dict] = {}

        # 1. Primary source: Schwab Movers (NYSE, NASDAQ, EQUITY_ALL)
        try:
            for exch in ['NYSE', 'NASDAQ', 'EQUITY_ALL']:
                movers = get_movers(exch)
                for m in movers:
                    sym = m.get('symbol')
                    if sym and sym not in candidates:
                        candidates[sym] = m
        except Exception as e:
            logger.warning(f"[ScreenerCandidateSource] Schwab get_movers failed: {e}")

        # 2. Secondary source: TradingView Screener HTTP API fallback
        try:
            from TradingView import TradingView
            tv = TradingView()
            tv_results = tv.get_top_gainers(limit=limit)
            for item in tv_results:
                sym = item.get('symbol')
                if not sym:
                    continue
                if sym not in candidates:
                    candidates[sym] = {
                        'symbol': sym,
                        'change': item.get('change', 0),
                        'source': 'tradingview'
                    }
                else:
                    schwab_change = candidates[sym].get('change', 0)
                    tv_change = item.get('change', 0)
                    if tv_change > schwab_change:
                        candidates[sym]['change'] = tv_change
        except Exception as e:
            logger.debug(f"[ScreenerCandidateSource] TradingView fallback skipped: {e}")

        return list(candidates.values())[:limit]
