"""
validation/
-----------
Pydantic v2 request schemas, shared helpers, and project-wide constants.

Public re-exports
-----------------
``from validation import normalize_ticker`` for the canonical ticker
normaliser (uppercase + strip).
``from validation import EASTERN_TZ`` for the canonical US/Eastern tz
object (pytz-backed, ``America/New_York`` IANA name).
"""
from validation.constants import EASTERN_TZ
from validation.schemas import normalize_ticker

__all__ = ["EASTERN_TZ", "normalize_ticker"]
