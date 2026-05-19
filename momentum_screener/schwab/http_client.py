import os
import logging
from .auth import get_client
from schwab.client import Client

logger = logging.getLogger(__name__)

_client = None

def get_http_client():
    global _client
    if _client is None:
        _client = get_client()
    return _client

def get_quote(symbol):
    client = get_http_client()
    resp = client.get_quote(symbol)
    if resp.status_code != 200:
        logger.error(f"Error fetching quote for {symbol}: {resp.text}")
        return None
    return resp.json()

def get_quotes(symbols):
    if not symbols:
        return {}
    client = get_http_client()
    # symbols can be a list or comma-separated string
    resp = client.get_quotes(symbols)
    if resp.status_code != 200:
        logger.error(f"Error fetching quotes for {symbols}: {resp.text}")
        return {}
    return resp.json()

def get_movers(index_symbol, sort=Client.Movers.Sort.PERCENT_CHANGE_UP, frequency=None):
    """
    index_symbol: 'NASDAQ', 'NYSE', 'AMEX' or specific symbols like '$COMPX'
    sort: PERCENT_CHANGE_UP, PERCENT_CHANGE_DOWN, VOLUME
    """
    client = get_http_client()
    resp = client.get_movers(index_symbol, sort=sort, frequency=frequency)
    if resp.status_code != 200:
        logger.error(f"Error fetching movers for {index_symbol}: {resp.text}")
        return []
    return resp.json()

def get_price_history_every_minute(symbol, start_datetime=None, end_datetime=None):
    client = get_http_client()
    resp = client.get_price_history_every_minute(
        symbol, 
        start_datetime=start_datetime, 
        end_datetime=end_datetime,
        need_extended_hours_data=True
    )
    if resp.status_code != 200:
        logger.error(f"Error fetching minute bars for {symbol}: {resp.text}")
        return []
    return resp.json().get('candles', [])

def get_price_history_every_day(symbol, start_datetime=None, end_datetime=None):
    client = get_http_client()
    resp = client.get_price_history_every_day(
        symbol,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        need_extended_hours_data=True
    )
    if resp.status_code != 200:
        logger.error(f"Error fetching daily bars for {symbol}: {resp.text}")
        return []
    return resp.json().get('candles', [])

def get_instruments(symbols, projection=Client.Instrument.Projection.FUNDAMENTAL):
    client = get_http_client()
    resp = client.get_instruments(symbols, projection=projection)
    if resp.status_code != 200:
        logger.error(f"Error fetching instruments for {symbols}: {resp.text}")
        return {}
    return resp.json()

def get_option_chain(symbol):
    client = get_http_client()
    resp = client.get_option_chain(symbol)
    if resp.status_code != 200:
        logger.error(f"Error fetching option chain for {symbol}: {resp.text}")
        return {}
    return resp.json()
