import math

def calculate_atr_14(candles):
    """
    Calculates 14-period Average True Range.
    candles: list of daily candle dicts with 'high', 'low', 'close'
    """
    if len(candles) < 15:
        return 0.0
    
    true_ranges = []
    for i in range(1, len(candles)):
        h = candles[i]['high']
        l = candles[i]['low']
        pc = candles[i-1]['close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        true_ranges.append(tr)
    
    # Simple average of the last 14 true ranges
    return sum(true_ranges[-14:]) / 14.0

def calculate_rel_vol(current_volume, avg_volume_14):
    """
    Calculates Relative Volume.
    """
    if not avg_volume_14 or avg_volume_14 == 0:
        return 1.0
    return current_volume / avg_volume_14

def get_float_category(shares_float):
    """
    Categorizes float size.
    """
    if not shares_float:
        return "Unknown"
    if shares_float <= 10_000_000:
        return "Micro-Float"
    if shares_float <= 20_000_000:
        return "Low-Float"
    if shares_float <= 50_000_000:
        return "Mid-Float"
    return "High-Float"

def calculate_gap_pct(last_close, pre_market_price):
    """
    Calculates percentage gap from previous close.
    """
    if not last_close or last_close == 0:
        return 0.0
    return ((pre_market_price - last_close) / last_close) * 100.0

def calculate_squeeze_score(short_interest_pct, rel_vol, gap_pct):
    """
    Heuristic squeeze score.
    """
    score = 0
    if short_interest_pct > 15: score += 40
    if rel_vol > 2.0: score += 30
    if gap_pct > 5.0: score += 30
    return score
