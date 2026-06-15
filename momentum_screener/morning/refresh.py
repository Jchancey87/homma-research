import logging

from .scheduler import ScheduledTask

log = logging.getLogger(__name__)


def run_full_refresh() -> None:
    log.info("[MorningRoutine] Starting morning refresh sequence...")
    log.info("[MorningRoutine] Morning refresh sequence complete.")


_routine = ScheduledTask(
    hour=8,
    minute=45,
    fn=run_full_refresh,
    name="morning-routine",
)


def start_morning_routine() -> None:
    _routine.start()
