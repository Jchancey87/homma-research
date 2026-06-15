import logging

from .scheduler import ScheduledTask

log = logging.getLogger(__name__)


def scan_gaps() -> None:
    log.info("[PremarketGapScanner] Starting 8:00 AM gap scan...")
    log.info("[PremarketGapScanner] Gap scan complete.")


_scanner = ScheduledTask(
    hour=8,
    minute=0,
    fn=scan_gaps,
    name="premarket-gap-scanner",
)


def start_premarket_scanner() -> None:
    _scanner.start()
