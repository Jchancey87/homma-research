# Ross Cameron Momentum Filter Constants
ROSS_MIN_PRICE = 1.00
ROSS_MAX_PRICE = 20.00
ROSS_MIN_GAP_PCT = 10.0
ROSS_MIN_REL_VOL = 2.0
ROSS_MAX_FLOAT = 20_000_000
ROSS_MAX_MARKET_CAP = 500_000_000
ROSS_MIN_ATR_14 = 0.50

def check_momentum_filters(price, gap_pct, rel_vol, shares_float, market_cap, atr_14):
    """
    Returns True if the stock passes the primary Ross Cameron momentum criteria.
    """
    if not (ROSS_MIN_PRICE <= price <= ROSS_MAX_PRICE):
        return False
    
    if gap_pct < ROSS_MIN_GAP_PCT:
        return False
        
    if rel_vol < ROSS_MIN_REL_VOL:
        return False
        
    if shares_float and shares_float > ROSS_MAX_FLOAT:
        return False
        
    if market_cap and market_cap > ROSS_MAX_MARKET_CAP:
        return False
        
    if atr_14 < ROSS_MIN_ATR_14:
        return False
        
    return True
