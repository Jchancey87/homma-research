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
                        last_p = m.get('lastPrice') or m.get('last_price') or m.get('price')
                        net_pct = m.get('netPercentChange')
                        gap_pct = None
                        if net_pct is not None:
                            val = float(net_pct)
                            gap_pct = val * 100.0 if abs(val) < 5.0 else val
                        elif m.get('gap_pct') is not None:
                            gap_pct = float(m['gap_pct'])
                        elif m.get('change') is not None:
                            val = float(m['change'])
                            gap_pct = val * 100.0 if abs(val) < 5.0 else val

                        cand = dict(m)
                        if last_p is not None:
                            cand['last_price'] = float(last_p)
                            cand['price'] = float(last_p)
                        if gap_pct is not None:
                            cand['gap_pct'] = float(gap_pct)
                            cand['change'] = float(gap_pct)
                        cand['volume'] = int(m.get('totalVolume') or m.get('volume') or 0)
                        cand['company_name'] = m.get('description') or m.get('company_name') or sym
                        candidates[sym] = cand
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
