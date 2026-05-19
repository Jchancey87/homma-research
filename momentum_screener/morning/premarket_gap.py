import threading
import time
import logging
from datetime import datetime
import pytz

log = logging.getLogger(__name__)
CENTRAL = pytz.timezone('US/Central')

class PremarketGapScanner:
    """
    8:00 AM CT pre-market gap scanner.
    Targets stocks with >= 10% gap and >= 50k pre-market volume.
    """
    def __init__(self):
        self.last_run_date = None

    def start(self):
        t = threading.Thread(target=self._loop, name='premarket-gap-scanner', daemon=True)
        t.start()
        log.info("[PremarketGapScanner] Background thread started")

    def _loop(self):
        while True:
            try:
                now_ct = datetime.now(CENTRAL)
                today = now_ct.strftime('%Y-%m-%d')

                # Run at 8:00 AM CT on weekdays
                if now_ct.weekday() < 5:
                    if now_ct.hour == 8 and now_ct.minute == 0:
                        if self.last_run_date != today:
                            self.scan_gaps()
                            self.last_run_date = today
                
                time.sleep(30)
            except Exception as e:
                log.error(f"[PremarketGapScanner] Loop error: {e}")
                time.sleep(60)

    def scan_gaps(self):
        log.info("[PremarketGapScanner] Starting 8:00 AM gap scan...")
        # 1. Fetch movers or broad quote list
        # 2. Filter for 10% gap and 50k volume
        # 3. Log or notify (Phase 2)
        log.info("[PremarketGapScanner] Gap scan complete.")

_scanner = PremarketGapScanner()

def start_premarket_scanner():
    _scanner.start()
