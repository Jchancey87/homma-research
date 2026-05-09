"""
market.py — Market-wide intelligence endpoints for the morning dashboard.

Routes:
  GET /market/breadth      — SPY/QQQ/VIX live prices (cached 15 min)
  GET /market/calendar     — Economic events this week via FMP (cached 6h)
"""
import time
import logging
import threading
import requests as _req
from flask import Blueprint, jsonify
from config import Config

log = logging.getLogger(__name__)

market_bp = Blueprint('market', __name__)

# ── In-process caches ─────────────────────────────────────────────────────────

_breadth_cache: dict = {'data': None, 'fetched_at': 0}
_breadth_lock = threading.Lock()
BREADTH_TTL = 15 * 60  # 15 minutes

_calendar_cache: dict = {'data': None, 'fetched_at': 0}
_calendar_lock = threading.Lock()
CALENDAR_TTL = 6 * 60 * 60  # 6 hours

INDICES = ['SPY', 'QQQ', 'IWM']


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fetch_polygon_snapshot(ticker: str) -> dict | None:
    """Fetch Polygon v2 snapshot for a single ticker."""
    key = getattr(Config, 'POLYGON_API_KEY', None)
    if not key:
        return None
    try:
        url = f'https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}'
        resp = _req.get(url, params={'apiKey': key}, timeout=6)
        if resp.ok:
            return resp.json().get('ticker')
    except Exception as e:
        log.warning(f'[market] Polygon snapshot error for {ticker}: {e}')
    return None


def _bias_label(spy_chg: float | None, vix: float | None) -> str:
    """Derive a simple risk-on / risk-off bias label."""
    if spy_chg is None:
        return 'unknown'
    if spy_chg >= 0.5 and (vix is None or vix < 20):
        return 'risk_on'
    if spy_chg <= -0.5 or (vix is not None and vix > 25):
        return 'risk_off'
    return 'neutral'


# ── Routes ────────────────────────────────────────────────────────────────────

@market_bp.route('/market/breadth', methods=['GET'])
def market_breadth():
    """
    Live index prices for SPY, QQQ, IWM — cached for 15 minutes.
    Returns per-index price + % change, plus a derived bias label.
    """
    with _breadth_lock:
        now = time.time()
        if _breadth_cache['data'] and (now - _breadth_cache['fetched_at']) < BREADTH_TTL:
            return jsonify(_breadth_cache['data'])

    indices = {}
    spy_chg = None
    vix     = None

    for ticker in INDICES:
        snap = _fetch_polygon_snapshot(ticker)
        if snap:
            day   = snap.get('day', {})
            prev  = snap.get('prevDay', {})
            close = day.get('c') or snap.get('last', {}).get('price')
            prev_c = prev.get('c')
            chg_pct = round((close - prev_c) / prev_c * 100, 2) if close and prev_c else None
            if ticker == 'SPY':
                spy_chg = chg_pct
            indices[ticker] = {
                'ticker':  ticker,
                'price':   close,
                'chg_pct': chg_pct,
                'volume':  day.get('v'),
            }

    # Fetch VIX separately (^VIX not on Polygon stock snapshot — use a rough proxy)
    # We'll derive from the SPY data for now; replace with actual VIX source if available
    data = {
        'indices':  indices,
        'vix':      vix,
        'bias':     _bias_label(spy_chg, vix),
        'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'cache_ttl_s': BREADTH_TTL,
    }

    with _breadth_lock:
        _breadth_cache['data'] = data
        _breadth_cache['fetched_at'] = time.time()

    return jsonify(data)


@market_bp.route('/market/calendar', methods=['GET'])
def economic_calendar():
    """
    Economic events for the next 7 days via FMP.
    Cached for 6 hours to preserve FMP quota.
    Returns events sorted by date ascending, filtered to high/medium impact.
    """
    with _calendar_lock:
        now = time.time()
        if _calendar_cache['data'] and (now - _calendar_cache['fetched_at']) < CALENDAR_TTL:
            return jsonify(_calendar_cache['data'])

    from datetime import datetime, timedelta
    fmp_key = getattr(Config, 'FMP_API_KEY', None)

    if not fmp_key:
        return jsonify({'events': [], 'source': 'fmp_key_missing'})

    today = datetime.utcnow().date()
    end   = (today + timedelta(days=7)).isoformat()

    try:
        url = 'https://financialmodelingprep.com/api/v3/economic_calendar'
        resp = _req.get(url, params={
            'from': today.isoformat(),
            'to':   end,
            'apikey': fmp_key,
        }, timeout=10)
        resp.raise_for_status()
        raw = resp.json()

        # Filter to high/medium impact events; normalise fields
        events = []
        for e in (raw or []):
            impact = (e.get('impact') or '').lower()
            if impact not in ('high', 'medium'):
                continue
            events.append({
                'date':     e.get('date', '')[:10],
                'time':     e.get('date', '')[11:16],
                'event':    e.get('event'),
                'country':  e.get('country'),
                'impact':   impact,
                'actual':   e.get('actual'),
                'estimate': e.get('estimate'),
                'previous': e.get('previous'),
            })

        events.sort(key=lambda x: x['date'])
        data = {'events': events, 'source': 'fmp', 'fetched_at': today.isoformat()}

    except Exception as ex:
        log.warning(f'[market] FMP calendar error: {ex}')
        data = {'events': [], 'source': 'fmp_error', 'error': str(ex)}

    with _calendar_lock:
        _calendar_cache['data'] = data
        _calendar_cache['fetched_at'] = time.time()

    return jsonify(data)
