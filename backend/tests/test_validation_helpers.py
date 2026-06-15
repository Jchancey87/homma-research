"""
tests/test_validation_helpers.py
--------------------------------
Locks in the public surface of ``validation`` so the ticker / timezone
normalisers have a regression net and the project's single source of
truth stays the single source of truth.
"""
import datetime

import pytest
import pytz

from validation import EASTERN_TZ, normalize_ticker
from validation.constants import EASTERN_TZ as EASTERN_TZ_FROM_CONSTANTS
from validation.schemas import _upper_strip, normalize_ticker as from_schemas


# ---------------------------------------------------------------------------
# normalize_ticker — public + private-alias parity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("aapl", "AAPL"),                  # lowercase → uppercase
        ("  aapl  ", "AAPL"),              # surrounding whitespace stripped
        ("TSLA", "TSLA"),                  # already normalised
        ("brk.a", "BRK.A"),                # dot kept (not a word boundary)
        ("a b c", "A B C"),                # inner whitespace preserved
        ("  \tMsFt\n  ", "MSFT"),          # mixed whitespace
    ],
)
def test_normalize_ticker(raw, expected):
    assert normalize_ticker(raw) == expected


def test_normalize_ticker_re_exported_from_schemas():
    """Both the public re-export and the original module must agree."""
    assert normalize_ticker is from_schemas
    # Legacy private alias still works
    assert _upper_strip("aapl") == "AAPL"


# ---------------------------------------------------------------------------
# EASTERN_TZ — identity + behaviour
# ---------------------------------------------------------------------------
def test_eastern_tz_is_pytz_america_new_york():
    """EASTERN_TZ is a pytz timezone for America/New_York (canonical IANA name)."""
    assert isinstance(EASTERN_TZ, pytz.tzinfo.DstTzInfo) or isinstance(EASTERN_TZ, pytz.tzinfo.StaticTzInfo)
    # The canonical name pytz reports is "America/New_York" — that's the
    # same form Postgres accepts in raw SQL via "AT TIME ZONE '...'".
    assert EASTERN_TZ.zone == "America/New_York"


def test_eastern_tz_is_module_singleton():
    """EASTERN_TZ must be the same object every time it is imported."""
    assert EASTERN_TZ is EASTERN_TZ_FROM_CONSTANTS
    # And the same object that the re-exported public API returns
    from validation import EASTERN_TZ as second_import
    assert EASTERN_TZ is second_import


def test_eastern_tz_round_trips_via_localize():
    """Datetime arithmetic on a localized datetime must agree with offset math."""
    naive = datetime.datetime(2026, 6, 14, 10, 0, 0)  # 10:00 AM, June (EDT)
    localized = EASTERN_TZ.localize(naive)
    assert localized.utcoffset() == datetime.timedelta(hours=-4)  # EDT is UTC-4

    # Convert back to UTC and verify the math
    utc = localized.astimezone(pytz.utc)
    assert utc.hour == 14  # 10 AM ET + 4h = 14:00 UTC


def test_eastern_tz_handles_winter_est_offset():
    """January is EST (UTC-5), not EDT (UTC-4) — guard the DST behaviour."""
    naive = datetime.datetime(2026, 1, 14, 10, 0, 0)  # 10:00 AM, January (EST)
    localized = EASTERN_TZ.localize(naive)
    assert localized.utcoffset() == datetime.timedelta(hours=-5)


# ---------------------------------------------------------------------------
# Single source of truth — no rogue pytz.timezone('US/Eastern') calls remain
# ---------------------------------------------------------------------------
def test_no_rogue_eastern_tz_construction_outside_constants():
    """
    Guard: nothing in the active codebase should re-construct a US/Eastern
    tz object outside ``validation/constants.py`` (the single source of
    truth).  If a new caller sneaks in a ``pytz.timezone('US/Eastern')``
    or ``pytz.timezone('America/New_York')``, the grep on this test will
    catch it.
    """
    import os
    import re

    bad_pattern = re.compile(r"""pytz\.timezone\(\s*['"](?:US/Eastern|America/New_York)['"]\s*\)""")
    offenders: list[tuple[str, int, str]] = []

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root, _dirs, files in os.walk(backend_dir):
        # Skip scratch (informal scripts), __pycache__, and this test file
        # (which mentions the patterns in its own docstring).
        if "/scratch" in root or "__pycache__" in root:
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            if "test_validation_helpers.py" in fpath:
                continue
            with open(fpath) as f:
                for lineno, line in enumerate(f, start=1):
                    if bad_pattern.search(line):
                        # validation/constants.py is the single source of truth
                        if "validation/constants.py" in fpath:
                            continue
                        offenders.append((fpath, lineno, line.rstrip()))

    assert not offenders, (
        "Rogue pytz.timezone('US/Eastern'|'America/New_York') calls found — "
        "use ``from validation import EASTERN_TZ`` instead:\n"
        + "\n".join(f"  {p}:{ln}: {line}" for p, ln, line in offenders)
    )
