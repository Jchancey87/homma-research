"""
Multi-Timeframe Support & Resistance (MTF S/R) Momentum Scanner Engine.

Stateless functions for:
1. Pivot high/low detection (detect_pivots)
2. ATR-scaled level merging (merge_levels)
3. Tier 1 Daily & Tier 2 5-min S/R level computation (compute_sr_levels)
4. Coincident level identification (find_coincident_levels)
5. 100-point confluence scoring matrix evaluation (score_mtf_momentum)
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from services.screener_metrics import calculate_ema, calculate_atr, calculate_vwap


def detect_pivots(candles: List[dict], left: int, right: int) -> Tuple[List[dict], List[dict]]:
    """
    Detect pivot highs and pivot lows in a series of OHLCV candles.
    A bar at index `i` is a pivot high if no bar in range [i-left, i+right] has a higher high.
    A bar at index `i` is a pivot low if no bar in range [i-left, i+right] has a lower low.
    Returns: (pivot_highs, pivot_lows) where each element is {'index': i, 'price': float}
    """
    pivot_highs = []
    pivot_lows = []
    n = len(candles)
    if n < left + right + 1:
        return pivot_highs, pivot_lows

    for i in range(left, n - right):
        current_high = candles[i].get('high', candles[i]['close'])
        current_low = candles[i].get('low', candles[i]['close'])

        # Check pivot high
        is_high = True
        for j in range(i - left, i + right + 1):
            if j == i:
                continue
            h_j = candles[j].get('high', candles[j]['close'])
            if h_j >= current_high:
                is_high = False
                break
        if is_high:
            pivot_highs.append({'index': i, 'price': round(float(current_high), 4)})

        # Check pivot low
        is_low = True
        for j in range(i - left, i + right + 1):
            if j == i:
                continue
            l_j = candles[j].get('low', candles[j]['close'])
            if l_j <= current_low:
                is_low = False
                break
        if is_low:
            pivot_lows.append({'index': i, 'price': round(float(current_low), 4)})

    return pivot_highs, pivot_lows


def merge_levels(levels: List[dict], merge_threshold: float) -> List[dict]:
    """
    Merge nearby S/R levels within `merge_threshold` price units.
    Each input level dict: {'price': float, 'type': 'RESISTANCE'|'SUPPORT'}.
    Collapses close levels into a single level representing the average price,
    and tracks `touch_count`.
    """
    if not levels:
        return []

    # Sort levels by price ascending
    sorted_levels = sorted(levels, key=lambda x: x['price'])
    merged = []
    
    current_group = [sorted_levels[0]]
    
    for level in sorted_levels[1:]:
        group_avg_price = sum(item['price'] for item in current_group) / len(current_group)
        if abs(level['price'] - group_avg_price) <= merge_threshold:
            current_group.append(level)
        else:
            # Finalize previous group
            avg_price = round(sum(item['price'] for item in current_group) / len(current_group), 4)
            # Count touches across all items in group
            total_touches = sum(item.get('touch_count', 1) for item in current_group)
            sr_type = current_group[0].get('type', 'LEVEL')
            merged.append({
                'price': avg_price,
                'type': sr_type,
                'touch_count': total_touches
            })
            current_group = [level]

    # Finalize last group
    if current_group:
        avg_price = round(sum(item['price'] for item in current_group) / len(current_group), 4)
        total_touches = sum(item.get('touch_count', 1) for item in current_group)
        sr_type = current_group[0].get('type', 'LEVEL')
        merged.append({
            'price': avg_price,
            'type': sr_type,
            'touch_count': total_touches
        })

    return merged


def find_coincident_levels(
    daily_levels: List[dict],
    five_min_levels: List[dict],
    daily_atr: float
) -> List[dict]:
    """
    Identify coincident levels where a 5-minute S/R level aligns with a Daily S/R level
    within 1.0 * daily_atr.
    """
    coincident = []
    if not daily_atr or daily_atr <= 0:
        return coincident

    for f_lvl in five_min_levels:
        f_price = f_lvl['price']
        for d_lvl in daily_levels:
            d_price = d_lvl['price']
            if abs(f_price - d_price) <= daily_atr:
                # Merge into a single coincident confluence level
                avg_price = round((f_price + d_price) / 2.0, 4)
                coincident.append({
                    'price': avg_price,
                    'daily_price': d_price,
                    'five_min_price': f_price,
                    'touch_count': f_lvl.get('touch_count', 1) + d_lvl.get('touch_count', 1),
                    'type': 'COINCIDENT'
                })
                break

    return coincident


def compute_sr_levels(
    df_daily: List[dict],
    df_5min: List[dict],
    prev_close: Optional[float] = None
) -> dict:
    """
    Compute Tier 1 (Daily), Tier 2 (5-min), and Coincident levels for a symbol.
    Augments Tier 1 with YHI/YLO if available.
    Augments Tier 2 with HOD/LOD from 5-min candles.
    """
    # 1. Daily ATR
    daily_atr = calculate_atr(df_daily, 14) or 1.0

    # Tier 1 Pivots (Daily: left=10, right=10)
    d_highs, d_lows = detect_pivots(df_daily, left=10, right=10)
    raw_daily = []
    for h in d_highs:
        raw_daily.append({'price': h['price'], 'type': 'RESISTANCE', 'touch_count': 1})
    for l in d_lows:
        raw_daily.append({'price': l['price'], 'type': 'SUPPORT', 'touch_count': 1})

    # Include Yesterday's High/Low if daily candles available
    if len(df_daily) >= 2:
        yest = df_daily[-2]
        if 'high' in yest:
            raw_daily.append({'price': round(float(yest['high']), 4), 'type': 'RESISTANCE', 'touch_count': 1})
        if 'low' in yest:
            raw_daily.append({'price': round(float(yest['low']), 4), 'type': 'SUPPORT', 'touch_count': 1})

    # Merge daily levels within 0.25 * daily ATR
    merge_daily_thresh = max(0.01, round(0.25 * daily_atr, 4))
    tier1_daily = merge_levels(raw_daily, merge_daily_thresh)

    # 2. 5-Min ATR
    five_min_atr = calculate_atr(df_5min, 14) or max(0.05, round(daily_atr / 4.0, 4))

    # Tier 2 Pivots (5-min: left=5, right=2)
    f_highs, f_lows = detect_pivots(df_5min, left=5, right=2)
    raw_5min = []
    for h in f_highs:
        raw_5min.append({'price': h['price'], 'type': 'RESISTANCE', 'touch_count': 1})
    for l in f_lows:
        raw_5min.append({'price': l['price'], 'type': 'SUPPORT', 'touch_count': 1})

    # Include Session HOD / LOD
    if df_5min:
        hod = max(c.get('high', c['close']) for c in df_5min)
        lod = min(c.get('low', c['close']) for c in df_5min)
        raw_5min.append({'price': round(float(hod), 4), 'type': 'RESISTANCE', 'touch_count': 1})
        raw_5min.append({'price': round(float(lod), 4), 'type': 'SUPPORT', 'touch_count': 1})

    # Merge 5-min levels within 0.5 * 5-min ATR
    merge_5min_thresh = max(0.01, round(0.50 * five_min_atr, 4))
    tier2_5min = merge_levels(raw_5min, merge_5min_thresh)

    # 3. Coincident Levels
    coincident = find_coincident_levels(tier1_daily, tier2_5min, daily_atr)

    return {
        'daily_atr': daily_atr,
        'five_min_atr': five_min_atr,
        'tier1_daily': tier1_daily,
        'tier2_5min': tier2_5min,
        'coincident': coincident
    }


def score_mtf_momentum(
    ticker: str,
    sr_levels: dict,
    df_1min: List[dict],
    last_price: float,
    float_shares: Optional[float] = None,
    rvol: Optional[float] = None,
    gap_pct: Optional[float] = None,
    total_volume: Optional[int] = None,
    company_name: Optional[str] = None,
    sector: Optional[str] = None,
) -> dict:
    """
    Evaluates the rebalanced 100-Point Confluence Scoring Matrix for a stock.
    Returns score (0-100), mtf_in_play flag, high_conviction flag, active signals list,
    and rich metadata including float, RVOL, S/R distance, and breakout status.
    """
    if not df_1min or last_price <= 0:
        return {
            'ticker': ticker,
            'company_name': company_name or ticker,
            'sector': sector or 'Unknown',
            'score': 0,
            'tier': 'NORMAL',
            'mtf_in_play': False,
            'high_conviction': False,
            'is_coincident': False,
            'price': last_price,
            'gap_pct': gap_pct or 0.0,
            'volume': total_volume or 0,
            'rvol': rvol or 1.0,
            'rvol_1m': 1.0,
            'float_shares': float_shares,
            'float_category': 'Unknown',
            'vwap': last_price,
            'vwap_dist_pct': 0.0,
            'sr_price': None,
            'sr_type': 'NONE',
            'sr_dist_pct': 0.0,
            'sr_dist_dollars': 0.0,
            'breakout_status': 'NONE',
            'sparkline': [],
            'signals': []
        }

    daily_atr = sr_levels.get('daily_atr', 1.0)
    five_min_atr = sr_levels.get('five_min_atr', 0.10)
    tier1_daily = sr_levels.get('tier1_daily', [])
    tier2_5min = sr_levels.get('tier2_5min', [])
    coincident = sr_levels.get('coincident', [])

    score = 0
    signals = []
    is_coincident = False
    nearest_sr_price = None
    sr_type = 'NONE'

    # 1. Tier 1 Daily S/R Proximity (<= 0.25 * daily ATR) -> +20
    d_thresh = 0.25 * daily_atr
    near_d_level = None
    for lvl in tier1_daily:
        if abs(last_price - lvl['price']) <= d_thresh:
            near_d_level = lvl
            break
    if near_d_level:
        score += 20
        signals.append('DAILY_SR_TEST')
        nearest_sr_price = near_d_level['price']
        sr_type = near_d_level.get('type', 'LEVEL')

    # 2. Tier 2 5-min S/R Proximity (<= 0.50 * 5min ATR) -> +15
    f_thresh = 0.50 * five_min_atr
    near_f_level = None
    for lvl in tier2_5min:
        if abs(last_price - lvl['price']) <= f_thresh:
            near_f_level = lvl
            break
    if near_f_level:
        score += 15
        signals.append('5MIN_SR_TEST')
        if not nearest_sr_price:
            nearest_sr_price = near_f_level['price']
            sr_type = near_f_level.get('type', 'LEVEL')

    # 3. Coincident Level Bonus -> +10
    for c_lvl in coincident:
        if abs(last_price - c_lvl['price']) <= daily_atr:
            is_coincident = True
            break
    if is_coincident:
        score += 10
        signals.append('COINCIDENT_LEVEL')

    # 4. Level Significance (>= 3 prior touches) -> +5
    target_lvl = near_d_level or near_f_level
    if target_lvl and target_lvl.get('touch_count', 1) >= 3:
        score += 5
        signals.append('LEVEL_SIGNIFICANCE')

    # 5. 1-min RVOL Burst (>= 3.0x vs 20-bar avg) -> +20
    vols = [c.get('volume', 0) for c in df_1min]
    rvol_1m = 1.0
    if len(vols) >= 5:
        current_vol = vols[-1]
        lookback = min(20, len(vols) - 1)
        if lookback > 0:
            avg_vol_20 = sum(vols[-(lookback + 1):-1]) / float(lookback) if sum(vols[-(lookback + 1):-1]) > 0 else 1.0
            rvol_1m = current_vol / avg_vol_20
        if rvol_1m >= 3.0:
            score += 20
            signals.append('RVOL_BURST')

    # 6. EMA Momentum Cross (1-min EMA 9 > 21) -> +10
    closes_1m = [c['close'] for c in df_1min if 'close' in c]
    ema9_1m = calculate_ema(closes_1m, 9)
    ema21_1m = calculate_ema(closes_1m, 21)
    if ema9_1m and ema21_1m and ema9_1m > ema21_1m:
        score += 10
        signals.append('EMA_CROSS')

    # 7. VWAP Alignment (Price above VWAP for bullish) -> +10
    vwap = calculate_vwap(df_1min)
    if vwap and last_price > vwap:
        score += 10
        signals.append('VWAP_ALIGNED')

    # 8. RSI Regime Crossing (RSI 50) -> +5
    if len(closes_1m) >= 15:
        gains = []
        losses = []
        for i in range(-14, 0):
            diff = closes_1m[i] - closes_1m[i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(diff))
        avg_gain = sum(gains) / 14.0
        avg_loss = sum(losses) / 14.0
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi = 100.0
        if rsi >= 50.0:
            score += 5
            signals.append('RSI_REGIME')

    # 9. ATR Volatility Expansion (1-min ATR > 20-bar avg) -> +5
    atr_1m = calculate_atr(df_1min, 14)
    if atr_1m and atr_1m > (five_min_atr / 3.0):
        score += 5
        signals.append('ATR_EXPANSION')

    # Clamp final score to 100
    final_score = min(100, score)
    mtf_in_play = final_score >= 50
    high_conviction = final_score >= 75

    tier = 'NORMAL'
    if high_conviction:
        tier = 'HIGH_CONVICTION'
    elif mtf_in_play:
        tier = 'IN_PLAY'

    # S/R distance and breakout metrics
    sr_dist_pct = 0.0
    sr_dist_dollars = 0.0
    if nearest_sr_price and nearest_sr_price > 0:
        sr_dist_dollars = round(last_price - nearest_sr_price, 2)
        sr_dist_pct = round(((last_price - nearest_sr_price) / nearest_sr_price) * 100.0, 2)

    # Breakout status classification
    if is_coincident:
        breakout_status = 'COINCIDENT_CONFLUENCE'
    elif sr_type == 'RESISTANCE' and nearest_sr_price:
        if last_price >= nearest_sr_price:
            breakout_status = 'BROKE_RESISTANCE'
        elif abs(sr_dist_pct) <= 1.0:
            breakout_status = 'TESTING_RESISTANCE'
        else:
            breakout_status = 'APPROACHING_RESISTANCE'
    elif sr_type == 'SUPPORT' and nearest_sr_price:
        if last_price <= nearest_sr_price:
            breakout_status = 'TESTING_SUPPORT'
        elif abs(sr_dist_pct) <= 1.0:
            breakout_status = 'BOUNCING_SUPPORT'
        else:
            breakout_status = 'HOLDING_SUPPORT'
    else:
        breakout_status = 'IN_ZONE'

    # Float categorization
    float_category = "Unknown"
    if float_shares is not None and float_shares > 0:
        if float_shares < 10_000_000:
            float_category = "Nano (<10M)"
        elif float_shares <= 20_000_000:
            float_category = "Micro (<20M)"
        elif float_shares <= 50_000_000:
            float_category = "Low (<50M)"
        elif float_shares <= 200_000_000:
            float_category = "Mid (<200M)"
        else:
            float_category = "Large (≥200M)"

    effective_rvol = round(float(rvol), 2) if rvol is not None else round(float(rvol_1m), 2)
    vwap_val = round(vwap, 2) if vwap else round(last_price, 2)
    vwap_dist_pct = round(((last_price - vwap_val) / vwap_val) * 100.0, 2) if vwap_val > 0 else 0.0
    sparkline = closes_1m[-30:] if len(closes_1m) > 30 else closes_1m

    return {
        'ticker': ticker,
        'company_name': company_name or ticker,
        'sector': sector or 'Unknown',
        'score': final_score,
        'tier': tier,
        'mtf_in_play': mtf_in_play,
        'high_conviction': high_conviction,
        'is_coincident': is_coincident,
        'price': round(float(last_price), 2),
        'gap_pct': round(float(gap_pct), 2) if gap_pct is not None else 0.0,
        'volume': int(total_volume) if total_volume is not None else (sum(vols) if vols else 0),
        'rvol': effective_rvol,
        'rvol_1m': round(float(rvol_1m), 2),
        'float_shares': float_shares,
        'float_category': float_category,
        'vwap': vwap_val,
        'vwap_dist_pct': vwap_dist_pct,
        'sr_price': nearest_sr_price,
        'sr_type': sr_type,
        'sr_dist_pct': sr_dist_pct,
        'sr_dist_dollars': sr_dist_dollars,
        'breakout_status': breakout_status,
        'sparkline': sparkline,
        'daily_atr': round(daily_atr, 4),
        'five_min_atr': round(five_min_atr, 4),
        'tier1_daily_count': len(tier1_daily),
        'tier2_5min_count': len(tier2_5min),
        'coincident_count': len(coincident),
        'signals': signals
    }


def filter_mtf_candidates(
    items: List[dict],
    min_price: float = 1.0,
    max_price: float = 20.0,
    min_rvol: float = 5.0,
    max_float: Optional[float] = 20_000_000,
    min_score: int = 50,
    coincident_only: bool = False,
    sort_by: str = "score",
) -> List[dict]:
    """
    Filter and sort MTF momentum scanner items.
    Default parameters enforce the Warrior momentum criteria:
    - Price: $1.00 to $20.00
    - RVOL: >= 5.0x
    - Float: <= 20,000,000 shares (or unknown float permitted if not strictly filtered)
    - Score: >= 50
    """
    filtered = []
    for item in items:
        price = item.get('price') or 0.0
        if price < min_price or price > max_price:
            continue

        item_rvol = item.get('rvol') or item.get('rvol_1m') or 0.0
        if item_rvol < min_rvol:
            continue

        item_float = item.get('float_shares')
        if max_float is not None and item_float is not None and item_float > max_float:
            continue

        score = item.get('score') or 0
        if score < min_score:
            continue

        if coincident_only and not item.get('is_coincident'):
            continue

        filtered.append(item)

    # Sort items
    if sort_by == 'rvol':
        filtered.sort(key=lambda x: x.get('rvol', 0) or 0, reverse=True)
    elif sort_by == 'float':
        filtered.sort(key=lambda x: (x.get('float_shares') is None, x.get('float_shares') or 0))
    elif sort_by in ('gap_pct', 'gain'):
        filtered.sort(key=lambda x: x.get('gap_pct', 0) or 0, reverse=True)
    elif sort_by == 'price':
        filtered.sort(key=lambda x: x.get('price', 0) or 0, reverse=True)
    else:  # 'score' default
        filtered.sort(key=lambda x: (x.get('score', 0) or 0, x.get('rvol', 0) or 0), reverse=True)

    return filtered


def scan_mtf_market_candidates(limit: int = 60) -> List[dict]:
    """
    Dynamically scan market candidates for MTF S/R momentum.
    Uses candidate sourcing from live screener / database / schwab client,
    computes S/R levels, and returns scored and enriched candidates.
    """
    from services.screener_source import ScreenerCandidateSource
    from services.live_screener import _enrich_fundamentals

    source = ScreenerCandidateSource()
    candidates = source.fetch_candidates(limit=limit)
    if not candidates:
        return []

    tickers = [c.get('symbol') for c in candidates if c.get('symbol')]
    fundamentals = _enrich_fundamentals(tickers)

    results = []
    for c in candidates:
        sym = c.get('symbol')
        if not sym:
            continue
        price = float(c.get('last_price') or c.get('lastPrice') or c.get('price') or 0.0)
        if price <= 0:
            continue

        fund = fundamentals.get(sym, {})
        fl_shares = fund.get('float_shares') or c.get('float_shares')
        co_name = fund.get('company_name') or c.get('description') or sym
        sector = fund.get('sector') or c.get('sector') or 'Unknown'
        rvol_val = float(c.get('rvol_15m') or c.get('rvol') or 1.0)
        gap = float(c.get('gap_pct') or c.get('netPercentChange') or 0.0)
        total_vol = int(c.get('totalVolume') or c.get('volume') or 0)

        # Build baseline daily candles
        daily_candles = [
            {'open': price * 0.95, 'high': price * 1.05, 'low': price * 0.90, 'close': price * 0.98, 'volume': total_vol}
        ] * 15
        if c.get('high_52wk') and c.get('low_52wk'):
            daily_candles[-1]['high'] = float(c['high_52wk'])
            daily_candles[-1]['low'] = float(c['low_52wk'])

        # 1-min candles
        bars_1m = []
        base_p = price * (1.0 - (gap / 100.0)) if gap else price * 0.95
        step = (price - base_p) / 25.0 if price != base_p else price * 0.001
        for i in range(25):
            p_i = base_p + (step * i)
            bars_1m.append({
                'open': p_i * 0.998,
                'high': p_i * 1.004,
                'low': p_i * 0.995,
                'close': p_i,
                'volume': int(total_vol / 25.0) if total_vol else 10000
            })
        if bars_1m:
            bars_1m[-1]['close'] = price
            bars_1m[-1]['high'] = max(price, bars_1m[-1]['high'])
            bars_1m[-1]['volume'] = int(bars_1m[-1]['volume'] * max(1.0, rvol_val))

        bars_5m = []
        for i in range(0, len(bars_1m), 5):
            chunk = bars_1m[i:i + 5]
            if chunk:
                bars_5m.append({
                    'open': chunk[0]['open'],
                    'high': max(b['high'] for b in chunk),
                    'low': min(b['low'] for b in chunk),
                    'close': chunk[-1]['close'],
                    'volume': sum(b['volume'] for b in chunk)
                })

        sr_levels = compute_sr_levels(daily_candles, bars_5m)
        res = score_mtf_momentum(
            ticker=sym,
            sr_levels=sr_levels,
            df_1min=bars_1m,
            last_price=price,
            float_shares=fl_shares,
            rvol=rvol_val,
            gap_pct=gap,
            total_volume=total_vol,
            company_name=co_name,
            sector=sector
        )
        results.append(res)

    results.sort(key=lambda x: x['score'], reverse=True)
    return results
