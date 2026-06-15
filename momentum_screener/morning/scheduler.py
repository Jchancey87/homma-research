import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional
import pytz

log = logging.getLogger(__name__)

DEFAULT_TZ = pytz.timezone("US/Central")
DEFAULT_POLL_SECONDS = 30
ERROR_BACKOFF_SECONDS = 60


class ScheduledTask:
    """
    Daily one-shot scheduled task. Polls every `poll_seconds`; invokes `fn`
    once per calendar day when local time matches (hour, minute) on weekdays.

    Args:
        hour: Local hour 0-23.
        minute: Local minute 0-59.
        fn: No-argument callable to invoke at the scheduled time.
        name: Thread name (for logs + identification).
        tz: pytz timezone string or tz object. Default: US/Central.
        weekdays_only: Restrict firing to Mon-Fri. Default: True.
        poll_seconds: Idle poll interval. Default: 30.
        now_fn: Optional override for clock (testing). Returns aware datetime in `tz`.
    """

    def __init__(
        self,
        hour: int,
        minute: int,
        fn: Callable[[], None],
        *,
        name: str,
        tz=DEFAULT_TZ,
        weekdays_only: bool = True,
        poll_seconds: int = DEFAULT_POLL_SECONDS,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        if not 0 <= hour <= 23:
            raise ValueError(f"hour must be 0-23, got {hour}")
        if not 0 <= minute <= 59:
            raise ValueError(f"minute must be 0-59, got {minute}")
        if not callable(fn):
            raise TypeError("fn must be callable")
        if poll_seconds < 1:
            raise ValueError(f"poll_seconds must be >= 1, got {poll_seconds}")

        self.hour = hour
        self.minute = minute
        self.fn = fn
        self.name = name
        self.tz = pytz.timezone(str(tz)) if isinstance(tz, str) else tz
        self.weekdays_only = weekdays_only
        self.poll_seconds = poll_seconds
        self._now_fn = now_fn or (lambda: datetime.now(self.tz))
        self._last_run_date: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def should_run(self, now: Optional[datetime] = None) -> bool:
        """
        Return True iff the task should fire at `now` AND has not already
        fired today. Side effect: records `now`'s date as last-run on fire.
        Decoupled from threading for testability.
        """
        if now is None:
            now = self._now_fn()
        today = now.strftime("%Y-%m-%d")
        if self.weekdays_only and now.weekday() >= 5:
            return False
        if now.hour != self.hour or now.minute != self.minute:
            return False
        if self._last_run_date == today:
            return False
        self._last_run_date = today
        return True

    def start(self) -> None:
        """Spawn the daemon thread. Idempotent: subsequent calls are no-ops."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._loop, name=self.name, daemon=True
            )
            self._thread.start()
            log.info("[%s] Background thread started", self.name)

    def _loop(self) -> None:
        while True:
            try:
                if self.should_run():
                    self.fn()
            except Exception as exc:
                log.error("[%s] Loop error: %s", self.name, exc)
                time.sleep(ERROR_BACKOFF_SECONDS)
                continue
            time.sleep(self.poll_seconds)
