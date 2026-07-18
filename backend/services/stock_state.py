"""
backend/services/stock_state.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Dataclass representing the current pipeline state of a stock.
"""
from dataclasses import dataclass

@dataclass
class StockState:
    ticker: str
    status: str = "active"  # "active", "suspended", "restricted", "watchlist_only"
    is_active: bool = True

    def should_enrich(self, is_watchlist_member: bool) -> bool:
        """
        Determine if the stock should undergo fundamental enrichment.
        """
        if not self.is_active:
            return False
        if self.status in ("suspended", "restricted"):
            return False
        if self.status == "watchlist_only":
            return is_watchlist_member
        if self.status == "active":
            return True
        return False
