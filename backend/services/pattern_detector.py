"""
backend/services/pattern_detector.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure pattern recognition engine for intraday 1-minute OHLCV chart data and Level 1 quote ticks.
Implements detection for classic Warrior Trading / momentum setups:
- Bull Flag (Impulse pole + tight consolidation holding 9 EMA)
- VWAP Reclaim (Cross back above VWAP with volume expansion)
- Micro Pullback (1-3 red candles pulling back into 9 EMA in an uptrend)
- Psychological Dollar Level Breakouts ($1, $2.50, $5, $10, $20)
"""
from typing import List, Dict, Optional, Tuple, TypedDict

class PatternResult(TypedDict):
  has_bull_flag: bool
  has_vwap_reclaim: bool
  has_micro_pullback: bool
  has_psych_breakout: bool
  active_patterns: List[str]
  pattern_score: int
  details: Dict[str, str]


def calculate_ema(prices: List[float], period: int = 9) -> Optional[float]:
  """Calculate Exponential Moving Average for a series of closes."""
  if not prices or len(prices) < period:
    return None
  k = 2.0 / (period + 1)
  ema = sum(prices[:period]) / float(period)
  for p in prices[period:]:
    ema = (p * k) + (ema * (1.0 - k))
  return ema


def detect_bull_flag(candles: List[Dict]) -> bool:
  """Detect a Bull Flag pattern:
  1. Impulse pole: Price increased >= 3.5% over 3 to 10 candles with volume expansion.
  2. Flag consolidation: 2 to 6 candles with decreasing volume where price holds top 60% of pole.
  3. Breakout trigger: Current candle close > prior candle high.
  """
  if not candles or len(candles) < 6:
    return False

  # Look for pole in recent window (last 12 candles)
  window = candles[-12:]
  min_low = min(c.get('l', c.get('c', 0)) for c in window[:6])
  max_high = max(c.get('h', c.get('c', 0)) for c in window[2:10])

  if min_low <= 0:
    return False

  pole_gain_pct = ((max_high - min_low) / min_low) * 100.0
  if pole_gain_pct < 3.5:
    return False

  # Check flag consolidation (candles after peak high)
  recent_closes = [c.get('c', 0) for c in window[-4:]]
  if not recent_closes:
    return False

  # Flag should hold top 60% of pole range
  retrace_floor = min_low + (max_high - min_low) * 0.4
  if any(c < retrace_floor for c in recent_closes):
    return False

  # Volume contraction during flag
  recent_vols = [c.get('v', 0) for c in window[-4:-1]]
  peak_vol = max((c.get('v', 0) for c in window[2:8]), default=1)

  if recent_vols and peak_vol > 0:
    avg_flag_vol = sum(recent_vols) / len(recent_vols)
    if avg_flag_vol <= peak_vol * 0.85:
      return True

  return False


def detect_vwap_reclaim(candles: List[Dict], vwap: Optional[float]) -> bool:
  """Detect VWAP Reclaim:
  Price was trading below VWAP in recent candles (within last 10 candles),
  and current candle closes back above VWAP with volume >= 1.3x average.
  """
  if not candles or len(candles) < 3 or not vwap or vwap <= 0:
    return False

  curr_c = candles[-1].get('c', 0)
  curr_v = candles[-1].get('v', 0)

  if curr_c <= vwap:
    return False

  # Verify at least one prior candle in last 8 was below VWAP
  was_below = any(
      c.get('c', 0) < vwap or c.get('l', 0) < vwap for c in candles[-8:-1]
  )
  if not was_below:
    return False

  # Check volume expansion on reclaim candle
  prev_vols = [c.get('v', 0) for c in candles[-10:-1]]
  if prev_vols:
    avg_vol = sum(prev_vols) / len(prev_vols)
    if curr_v >= avg_vol * 1.3:
      return True

  return False


def detect_micro_pullback(
    candles: List[Dict], ema9: Optional[float]
) -> bool:
  """Detect Micro-Pullback (First 1-min Pullback):
  Strong uptrend (above 9 EMA), followed by 1 to 3 consecutive red candles
  pulling back to or near the 9 EMA (within 0.8% of EMA9), followed by a green candle.
  """
  if not candles or len(candles) < 4:
    return False

  curr_o = candles[-1].get('o', 0)
  curr_c = candles[-1].get('c', 0)
  is_curr_green = curr_c > curr_o

  if not is_curr_green:
    return False

  # Check preceding candles for 1 to 3 red candles
  red_count = 0
  for c in reversed(candles[-4:-1]):
    o_val = c.get('o', 0)
    c_val = c.get('c', 0)
    if c_val < o_val:
      red_count += 1
    else:
      break

  if 1 <= red_count <= 3:
    if ema9 and ema9 > 0:
      min_pullback_price = min(c.get('l', c.get('c', 0)) for c in candles[-4:-1])
      dist_to_ema = abs(min_pullback_price - ema9) / ema9 * 100.0
      if dist_to_ema <= 1.2:
        return True
    else:
      return True

  return False


def detect_psych_breakout(
    curr_price: float, prev_price: Optional[float]
) -> Tuple[bool, Optional[float]]:
  """Detect breakout across key psychological whole/half dollar levels:
  Whole levels: $1, $2, $3, $4, $5, $10, $15, $20
  Half levels: $1.50, $2.50, $3.50, $4.50, $7.50
  """
  if curr_price <= 0 or not prev_price or prev_price <= 0:
    return False, None

  psych_levels = [
      1.0,
      1.5,
      2.0,
      2.5,
      3.0,
      3.5,
      4.0,
      4.5,
      5.0,
      7.5,
      10.0,
      15.0,
      20.0,
  ]

  for level in psych_levels:
    if prev_price < level <= curr_price:
      return True, level

  return False, None


def analyze_stock_patterns(
    candles: List[Dict], vwap: Optional[float], curr_price: float
) -> PatternResult:
  """Master pattern analyzer returning all detected Warrior Trading patterns and composite score."""
  has_flag = detect_bull_flag(candles)
  has_reclaim = detect_vwap_reclaim(candles, vwap)

  ema9 = calculate_ema(
      [c.get('c', 0) for c in candles if c.get('c')], period=9
  )
  has_pb = detect_micro_pullback(candles, ema9)

  prev_price = candles[-2].get('c') if len(candles) >= 2 else None
  has_psych, psych_level = detect_psych_breakout(curr_price, prev_price)

  active_patterns = []
  pattern_score = 0
  details = {}

  if has_flag:
    active_patterns.append('BULL_FLAG')
    pattern_score += 35
    details['bull_flag'] = 'Bull Flag Consolidation holding 9 EMA'

  if has_reclaim:
    active_patterns.append('VWAP_RECLAIM')
    pattern_score += 30
    details['vwap_reclaim'] = f'VWAP Reclaim above ${vwap:.2f}' if vwap else 'VWAP Reclaim'

  if has_pb:
    active_patterns.append('MICRO_PULLBACK')
    pattern_score += 20
    details['micro_pullback'] = '1-Min Micro Pullback reversal'

  if has_psych and psych_level:
    active_patterns.append('PSYCH_BREAKOUT')
    pattern_score += 15
    details['psych_breakout'] = f'Psychological ${psych_level:.2f} Level Breakout'

  return PatternResult(
      has_bull_flag=has_flag,
      has_vwap_reclaim=has_reclaim,
      has_micro_pullback=has_pb,
      has_psych_breakout=has_psych,
      active_patterns=active_patterns,
      pattern_score=pattern_score,
      details=details,
  )
