"""
Screener Candidate Sourcing Adapter.

Combines TradingView Extended Hours Scanner HTTP API (all ~8,000 US equities)
and Schwab Movers REST API calls.
"""

import logging
from typing import Dict, List, Optional
from services.schwab_client import get_movers, _get_tradingview_candidates

logger = logging.getLogger(__name__)


class ScreenerCandidateSource:
    """Fetches candidate gainer tickers from TradingView Scanner and Schwab Movers."""

    def fetch_candidates(self, limit: int = 150) -> List[dict]:
        """
        Pull candidate movers from TradingView Scanner API (pre/reg/post market)
        supplemented by Schwab Movers API.
        Returns list of candidate dicts with ticker metadata.
        """
        candidates: Dict[str, dict] = {}

        # 1. Primary source: TradingView Scanner (covers all ~8,000+ US stocks in pre/reg/post sessions)
        try:
            tv_candidates = _get_tradingview_candidates()
            for sym, info in tv_candidates.items():
                if sym and sym not in candidates:
                    price = info.get('price')
                    change = info.get('change')
                    candidates[sym] = {
                        'symbol': sym,
                        'last_price': price,
                        'price': price,
                        'gap_pct': change,
                        'change': change,
                        'volume': info.get('volume', 0),
                        'float_shares': info.get('float_shares'),
                        'market_cap': info.get('market_cap'),
                        'sector': info.get('sector'),
                        'company_name': sym,
                        'source': 'tradingview',
                    }
            logger.info(f"[ScreenerCandidateSource] TradingView returned {len(tv_candidates)} candidates")
        except Exception as e:
            logger.warning(f"[ScreenerCandidateSource] TradingView fetch failed: {e}")

        # 2. Secondary source: Schwab Movers (NYSE, NASDAQ, EQUITY_ALL)
        try:
            for exch in ['NYSE', 'NASDAQ', 'EQUITY_ALL']:
                movers = get_movers(exch)
                for m in movers:
                    sym = m.get('symbol')
                    if not sym:
                        continue
                    sym = sym.upper()
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
                    cand['symbol'] = sym
                    if last_p is not None:
                        cand['last_price'] = float(last_p)
                        cand['price'] = float(last_p)
                    if gap_pct is not None:
                        cand['gap_pct'] = float(gap_pct)
                        cand['change'] = float(gap_pct)
                    cand['volume'] = int(m.get('totalVolume') or m.get('volume') or 0)
                    cand['company_name'] = m.get('description') or m.get('company_name') or sym

                    if sym not in candidates:
                        candidates[sym] = cand
        except Exception as e:
            logger.warning(f"[ScreenerCandidateSource] Schwab get_movers failed: {e}")

        return list(candidates.values())[:limit]

