"""
tests/test_scheduled_task.py
----------------------------
Locks in the contract of ``ScheduledTask`` from
``momentum_screener.morning.scheduler``.

Pure-logic tests exercise ``should_run`` (no threading, no sleeping).
One integration test verifies that ``start()`` is idempotent — a contract
the original stub classes violated.
"""
from __future__ import annotations

import datetime
import threading
from unittest.mock import MagicMock

import pytest
import pytz

from validation import EASTERN_TZ
from momentum_screener.morning.scheduler import (
    DEFAULT_POLL_SECONDS,
    DEFAULT_TZ,
    ScheduledTask,
)


CENTRAL = pytz.timezone("US/Central")  # noqa: validation/ owns Eastern; Central has no helper yet.
WED_8AM = CENTRAL.localize(datetime.datetime(2026, 6, 10, 8, 0, 0))   # Wed
WED_8_45 = CENTRAL.localize(datetime.datetime(2026, 6, 10, 8, 45, 0))
WED_7_59 = CENTRAL.localize(datetime.datetime(2026, 6, 10, 7, 59, 0))
WED_8_01 = CENTRAL.localize(datetime.datetime(2026, 6, 10, 8, 1, 0))
SAT_8AM = CENTRAL.localize(datetime.datetime(2026, 6, 13, 8, 0, 0))   # Sat
SUN_8AM = CENTRAL.localize(datetime.datetime(2026, 6, 14, 8, 0, 0))   # Sun
THU_8AM = CENTRAL.localize(datetime.datetime(2026, 6, 11, 8, 0, 0))   # Thu (next day)


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------
def test_rejects_invalid_hour():
    with pytest.raises(ValueError, match="hour must be 0-23"):
        ScheduledTask(hour=24, minute=0, fn=lambda: None, name="x")


def test_rejects_invalid_minute():
    with pytest.raises(ValueError, match="minute must be 0-59"):
        ScheduledTask(hour=0, minute=60, fn=lambda: None, name="x")


def test_rejects_non_callable_fn():
    with pytest.raises(TypeError, match="fn must be callable"):
        ScheduledTask(hour=0, minute=0, fn="not a fn", name="x")  # type: ignore[arg-type]


def test_rejects_poll_seconds_below_one():
    with pytest.raises(ValueError, match="poll_seconds must be >= 1"):
        ScheduledTask(hour=0, minute=0, fn=lambda: None, name="x", poll_seconds=0)


def test_defaults_match_legacy_stubs():
    """US/Central + weekdays_only + 30s poll — matches the old PremarketGapScanner."""
    assert DEFAULT_TZ == CENTRAL
    assert DEFAULT_POLL_SECONDS == 30
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.weekdays_only is True
    assert task.tz == CENTRAL
    assert task.poll_seconds == 30


# ---------------------------------------------------------------------------
# should_run — happy path
# ---------------------------------------------------------------------------
def test_fires_on_exact_minute_match():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(WED_8AM) is True


def test_does_not_fire_off_minute():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(WED_7_59) is False
    assert task.should_run(WED_8_01) is False


def test_does_not_fire_on_wrong_hour():
    task = ScheduledTask(hour=8, minute=45, fn=lambda: None, name="x")
    assert task.should_run(WED_8AM) is False


def test_fires_on_correct_minute_for_other_time():
    task = ScheduledTask(hour=8, minute=45, fn=lambda: None, name="x")
    assert task.should_run(WED_8_45) is True


# ---------------------------------------------------------------------------
# should_run — once-per-day guard
# ---------------------------------------------------------------------------
def test_fires_only_once_per_day():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(WED_8AM) is True
    assert task.should_run(WED_8AM) is False


def test_fires_again_next_day():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(WED_8AM) is True
    assert task.should_run(THU_8AM) is True


# ---------------------------------------------------------------------------
# should_run — weekday gate
# ---------------------------------------------------------------------------
def test_does_not_fire_on_saturday_when_weekdays_only():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(SAT_8AM) is False


def test_does_not_fire_on_sunday_when_weekdays_only():
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    assert task.should_run(SUN_8AM) is False


def test_weekend_fires_when_weekdays_only_false():
    task = ScheduledTask(
        hour=8, minute=0, fn=lambda: None, name="x", weekdays_only=False
    )
    assert task.should_run(SAT_8AM) is True
    assert task.should_run(SUN_8AM) is True


# ---------------------------------------------------------------------------
# should_run — clock injection
# ---------------------------------------------------------------------------
def test_uses_now_fn_when_no_arg():
    sentinel = MagicMock(return_value=WED_8AM)
    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x", now_fn=sentinel)
    assert task.should_run() is True
    sentinel.assert_called_once()


# ---------------------------------------------------------------------------
# tz resolution
# ---------------------------------------------------------------------------
def test_accepts_tz_string():
    task = ScheduledTask(
        hour=8, minute=0, fn=lambda: None, name="x", tz="America/New_York"
    )
    assert task.tz == EASTERN_TZ


def test_accepts_tz_object():
    task = ScheduledTask(
        hour=8, minute=0, fn=lambda: None, name="x", tz=EASTERN_TZ
    )
    assert task.tz is EASTERN_TZ


# ---------------------------------------------------------------------------
# start() — idempotency (the contract the original stubs violated)
# ---------------------------------------------------------------------------
def test_start_is_idempotent(monkeypatch):
    """Calling start() twice must spawn only one thread."""
    started: list[threading.Thread] = []
    real_thread = threading.Thread

    def fake_thread_factory(*args, **kwargs):
        t = real_thread(*args, **kwargs)
        started.append(t)
        return t

    monkeypatch.setattr(
        "momentum_screener.morning.scheduler.threading.Thread", fake_thread_factory
    )

    task = ScheduledTask(hour=8, minute=0, fn=lambda: None, name="x")
    task.start()
    task.start()
    task.start()

    assert len(started) == 1
    started[0].join(timeout=0.5)
