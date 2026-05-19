"""
services/polygon_client.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
DEPRECATED: Now delegates to schwab_client.py.
This shim is kept to avoid breaking existing imports.
"""
import logging
from typing import Optional, List, Dict
from . import schwab_client

log = logging.getLogger(__name__)

# Delegate all public functions to schwab_client
get_gainers_snapshot = schwab_client.get_gainers_snapshot
get_ticker_snapshot  = schwab_client.get_ticker_snapshot
get_grouped_daily    = schwab_client.get_grouped_daily
get_minute_bars      = schwab_client.get_minute_bars
get_daily_bars       = schwab_client.get_daily_bars
get_last_trade       = schwab_client.get_last_trade
get_last_quote       = schwab_client.get_last_quote
get_latest_headline  = schwab_client.get_latest_headline
get_ticker_details   = schwab_client.get_ticker_details
