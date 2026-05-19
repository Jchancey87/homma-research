"""
services/polygon_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Legacy shim — now delegates to schwab_client.
"""
from services.schwab_client import get_ticker_details  # re-export

__all__ = ["get_ticker_details"]
