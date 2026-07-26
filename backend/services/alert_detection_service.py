"""
Alert Detection Service.

Pure, side-effect-free alert detection engine for Homma Research.
Decoupled from WebSocket streaming, database persistence, Redis PubSub, and Celery tasks.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
from validation import EASTERN_TZ


@dataclass
class QuoteTick:
    symbol: str
    last_price: float
    total_volume: int
    high_price: float = 0.0
    low_price: float = 0.0
    open_price: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AlertConfig:
    min_rvol: float = 1.5
    min_gap_pct: float = 5.0
    volume_spike_multiplier: float = 2.0


@dataclass
class AlertCandidate:
    symbol: str
    alert_type: str
    price: float
    total_volume: int
    rvol: float
    gap_pct: float
    high_price: float = 0.0
    low_price: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class SymbolState:
    symbol: str
    vwap_state: dict = field(default_factory=lambda: {
        'cum_vp': 0.0,
        'cum_vol': 0,
        'last_total_vol': 0,
        'status': None
    })
    bars_1m: Optional[dict] = None
    completed_bars_1m: List[dict] = field(default_factory=list)
    prev_session_high: float = 0.0
    prev_day_breakout_fired: bool = False
    last_hod_breakout_time: float = 0.0
    halt_resume_ts: Optional[float] = None


def get_cumulative_volume_fraction(now_et: Optional[datetime] = None) -> float:
    """Calculate exact expected cumulative volume fraction at current ET time based on the intraday U-curve volume profile."""
    if now_et is None:
        now_et = datetime.now(EASTERN_TZ)
    h, m = now_et.hour, now_et.minute

    # Pre-market (4:00 AM - 9:30 AM ET)
    if h < 8:
        return 0.02
    elif h < 9:
        return 0.05 + ((m / 60.0) * 0.03)
    elif h == 9 and m < 30:
        return 0.08 + ((m / 30.0) * 0.07)

    # Regular Market Hours (9:30 AM - 4:00 PM ET)
    if h < 16:
        mins = (h - 9) * 60 + m - 30
        if mins <= 0:
            return 0.05
        elif mins <= 30:   # 9:30 - 10:00 AM (Opening Rush ~20%)
            frac = 0.05 + (mins / 30.0) * 0.20
        elif mins <= 60:   # 10:00 - 10:30 AM (~13%)
            frac = 0.25 + ((mins - 30) / 30.0) * 0.13
        elif mins <= 90:   # 10:30 - 11:00 AM (~9%)
            frac = 0.38 + ((mins - 60) / 30.0) * 0.09
        elif mins <= 150:  # 11:00 AM - 12:00 PM (~12%)
            frac = 0.47 + ((mins - 90) / 60.0) * 0.12
        elif mins <= 210:  # 12:00 PM - 1:00 PM (~8%)
            frac = 0.59 + ((mins - 150) / 60.0) * 0.08
        elif mins <= 270:  # 1:00 PM - 2:00 PM (~8%)
            frac = 0.67 + ((mins - 210) / 60.0) * 0.08
        elif mins <= 330:  # 2:00 PM - 3:00 PM (~10%)
            frac = 0.75 + ((mins - 270) / 60.0) * 0.10
        else:              # 3:00 PM - 4:00 PM (Power Hour ~15%)
            frac = 0.85 + ((mins - 330) / 60.0) * 0.15
        return max(0.01, min(1.0, frac))

    # Post-market (4:00 PM ET onwards)
    return 1.0



def volume_spike_threshold(now_et: Optional[datetime] = None) -> float:
    """Dynamic VOLUME_SPIKE multiplier matching stream_client.py."""
    if now_et is None:
        now_et = datetime.now(EASTERN_TZ)
    h = now_et.hour
    if h < 9:
        return 7.0
    elif h == 9:
        return 4.0
    elif h < 11:
        return 5.0
    elif h < 14:
        return 6.0
    elif h < 16:
        return 5.0
    else:
        return 7.0


def evaluate_alerts(
    tick: QuoteTick,
    state: SymbolState,
    fund: dict,
    config: Optional[AlertConfig] = None,
    now_et: Optional[datetime] = None
) -> Tuple[List[AlertCandidate], SymbolState]:
    """
    Pure state transition function evaluating 11 momentum alert strategies.
    Returns generated AlertCandidates and updated SymbolState.
    """
    if config is None:
        config = AlertConfig()
    if now_et is None:
        now_et = datetime.now(EASTERN_TZ)

    candidates: List[AlertCandidate] = []
    symbol = tick.symbol
    last_price = tick.last_price
    total_volume = tick.total_volume
    high_price = tick.high_price if tick.high_price > 0 else last_price
    low_price = tick.low_price if tick.low_price > 0 else last_price
    open_price = tick.open_price


    # Update VWAP
    vwap_state = dict(state.vwap_state)
    vwap = 0.0
    if vwap_state['last_total_vol'] > 0 and total_volume > vwap_state['last_total_vol']:
        delta_vol = total_volume - vwap_state['last_total_vol']
        vwap_state['cum_vp'] += last_price * delta_vol
        vwap_state['cum_vol'] += delta_vol

    vwap_state['last_total_vol'] = total_volume
    if vwap_state['cum_vol'] > 0:
        vwap = vwap_state['cum_vp'] / vwap_state['cum_vol']

    # Calculate RVOL
    cum_frac = get_cumulative_volume_fraction(now_et)
    vol_baseline = max(fund.get('vol_10d_avg', 0) * cum_frac, 5000)
    rvol = min(total_volume / vol_baseline, 99.9)

    # Gap calculation
    gap_pct = 0.0
    prev_close = fund.get('yesterday_close')
    if open_price and prev_close:
        gap_pct = ((open_price - prev_close) / prev_close) * 100.0

    # Post-halt suppression check
    post_halt_suppressed = False
    if state.halt_resume_ts is not None and (time.time() - state.halt_resume_ts) < 120:
        post_halt_suppressed = True

    # 1-minute candle update & volume spike / HOD radar checks
    current_min = int(tick.timestamp / 60)
    completed_bars = list(state.completed_bars_1m)
    current_bar = dict(state.bars_1m) if state.bars_1m else None
    prev_session_high = state.prev_session_high

    if not current_bar:
        current_bar = {
            'minute': current_min,
            'open': last_price,
            'high': last_price,
            'low': last_price,
            'close': last_price,
            'start_volume': total_volume,
            'last_volume': total_volume,
        }
    else:
        if current_min > current_bar['minute']:
            current_bar['close'] = last_price
            current_bar['last_volume'] = max(current_bar['last_volume'], total_volume)

            candle_volume = max(0, current_bar['last_volume'] - current_bar['start_volume'])

            # Volume Spike Trigger
            if len(completed_bars) == 20:
                avg_vol = sum(c['volume'] for c in completed_bars) / 20.0
                price_rise_pct = 0.0
                if current_bar['open'] > 0:
                    price_rise_pct = (current_bar['close'] - current_bar['open']) / current_bar['open']

                vol_mult = volume_spike_threshold(now_et)
                if avg_vol > 0 and candle_volume >= vol_mult * avg_vol and price_rise_pct >= 0.01:
                    candidates.append(AlertCandidate(
                        symbol=symbol,
                        alert_type="VOLUME_SPIKE",
                        price=current_bar['close'],
                        total_volume=total_volume,
                        rvol=rvol,
                        gap_pct=gap_pct
                    ))

            # NEAR_HOD_RADAR Trigger
            if not post_halt_suppressed:
                if prev_session_high <= 0.0:
                    prev_session_high = high_price if high_price > 0 else last_price

                if prev_session_high > 0.0 and current_bar['close'] > prev_session_high:
                    old_high = prev_session_high
                    prev_session_high = max(prev_session_high, current_bar['high'])
                    if rvol >= 1.5:
                        candidates.append(AlertCandidate(
                            symbol=symbol,
                            alert_type="NEAR_HOD_RADAR",
                            price=current_bar['close'],
                            total_volume=total_volume,
                            rvol=rvol,
                            gap_pct=gap_pct,
                            high_price=old_high,
                            low_price=low_price
                        ))

            completed_bars.append({
                'volume': candle_volume,
                'open': current_bar['open'],
                'close': current_bar['close'],
                'high': current_bar['high'],
                'low': current_bar['low']
            })
            if len(completed_bars) > 20:
                completed_bars.pop(0)

            current_bar = {
                'minute': current_min,
                'open': last_price,
                'high': last_price,
                'low': last_price,
                'close': last_price,
                'start_volume': total_volume,
                'last_volume': total_volume,
            }
        else:
            current_bar['high'] = max(current_bar['high'], last_price)
            current_bar['low'] = min(current_bar['low'], last_price)
            current_bar['close'] = last_price
            current_bar['last_volume'] = total_volume

    # VWAP Crossover Trigger
    if vwap > 0 and not post_halt_suppressed:
        if len(completed_bars) >= 5:
            recent = completed_bars[-14:]
            true_ranges = []
            for i, c in enumerate(recent):
                hi, lo = c.get('high', c['close']), c.get('low', c['close'])
                p_close = recent[i-1]['close'] if i > 0 else c['open']
                tr = max(hi - lo, abs(hi - p_close), abs(lo - p_close))
                true_ranges.append(tr)
            atr_val = sum(true_ranges) / len(true_ranges)
            atr_buffer = max(0.005, min(0.03, atr_val / vwap))
        else:
            atr_buffer = 0.015

        current_status = vwap_state.get('status')
        if current_status is None:
            if last_price <= vwap * (1.0 - atr_buffer):
                vwap_state['status'] = 'below'
            elif last_price >= vwap * (1.0 + atr_buffer):
                vwap_state['status'] = 'above'
        else:
            if current_status == 'below' and last_price >= vwap * (1.0 + atr_buffer):
                if rvol >= 2.0:
                    candidates.append(AlertCandidate(
                        symbol=symbol,
                        alert_type="VWAP_CROSSOVER",
                        price=last_price,
                        total_volume=total_volume,
                        rvol=rvol,
                        gap_pct=gap_pct,
                        high_price=high_price,
                        low_price=low_price
                    ))
                vwap_state['status'] = 'above'
            elif current_status == 'above' and last_price <= vwap * (1.0 - atr_buffer):
                vwap_state['status'] = 'below'

    # Previous Day High Breakout
    prev_day_fired = state.prev_day_breakout_fired
    yesterday_high = fund.get('yesterday_high', 0.0)
    if yesterday_high > 0.0 and last_price > yesterday_high and not prev_day_fired:
        candidates.append(AlertCandidate(
            symbol=symbol,
            alert_type="PREV_DAY_BREAKOUT",
            price=last_price,
            total_volume=total_volume,
            rvol=rvol,
            gap_pct=gap_pct,
            high_price=high_price,
            low_price=low_price
        ))
        prev_day_fired = True

    # RUNNING_UP Trigger
    if len(completed_bars) >= 5:
        lowest_close = min(c['close'] for c in completed_bars[-5:])
        if last_price >= lowest_close * 1.03:
            avg_vol = sum(c['volume'] for c in completed_bars) / len(completed_bars)
            curr_vol = current_bar['last_volume'] - current_bar['start_volume']
            if curr_vol >= 1.5 * avg_vol and avg_vol > 0:
                if last_price < high_price:
                    candidates.append(AlertCandidate(
                        symbol=symbol,
                        alert_type="RUNNING_UP",
                        price=last_price,
                        total_volume=total_volume,
                        rvol=rvol,
                        gap_pct=gap_pct,
                        high_price=high_price,
                        low_price=low_price
                    ))

    # BULL_FLAG Trigger
    last_hod_time = state.last_hod_breakout_time
    if len(completed_bars) >= 9:
        move_start = completed_bars[-9]['close']
        move_end = completed_bars[-5]['close']
        strong_move = move_start > 0 and (move_end - move_start) / move_start >= 0.05
        if strong_move:
            consolidation = completed_bars[-4:-1]
            declining_vol = consolidation[2]['volume'] <= consolidation[1]['volume'] <= consolidation[0]['volume']
            max_p = max(max(c['open'], c['close']) for c in consolidation)
            min_p = min(min(c['open'], c['close']) for c in consolidation)
            price_range_ok = min_p > 0 and (max_p - min_p) / min_p <= 0.02
            if declining_vol and price_range_ok:
                curr_vol = current_bar['last_volume'] - current_bar['start_volume']
                avg_vol = sum(c['volume'] for c in completed_bars) / len(completed_bars)
                if last_price > max_p and curr_vol >= 1.5 * avg_vol and avg_vol > 0:
                    candidates.append(AlertCandidate(
                        symbol=symbol,
                        alert_type="BULL_FLAG",
                        price=last_price,
                        total_volume=total_volume,
                        rvol=rvol,
                        gap_pct=gap_pct,
                        high_price=high_price,
                        low_price=low_price
                    ))

    # MULTI_TF_CONFLUENCE Trigger
    if len(completed_bars) >= 5:
        open_5m = completed_bars[-5]['open']
        close_5m = completed_bars[-1]['close']
        if open_5m > 0 and (close_5m - open_5m) / open_5m >= 0.01:
            if time.time() - last_hod_time <= 60:
                candidates.append(AlertCandidate(
                    symbol=symbol,
                    alert_type="MULTI_TF_CONFLUENCE",
                    price=last_price,
                    total_volume=total_volume,
                    rvol=rvol,
                    gap_pct=gap_pct,
                    high_price=high_price,
                    low_price=low_price
                ))

    # Construct new updated SymbolState
    new_state = SymbolState(
        symbol=symbol,
        vwap_state=vwap_state,
        bars_1m=current_bar,
        completed_bars_1m=completed_bars,
        prev_session_high=prev_session_high,
        prev_day_breakout_fired=prev_day_fired,
        last_hod_breakout_time=last_hod_time,
        halt_resume_ts=state.halt_resume_ts
    )

    return candidates, new_state
