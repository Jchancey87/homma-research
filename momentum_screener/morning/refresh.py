import threading
import time
import logging
from datetime import datetime
import pytz

log = logging.getLogger(__name__)
CENTRAL = pytz.timezone('US/Central')

class MorningRoutine:
    """
    Orchestrates the 6-step morning routine at 8:45 AM CT.
    1. Seed candidates from Schwab movers + watchlist
    2. Bulk fundamentals upsert
    3. 60-day daily price history
    4. Options snapshots for high-SI symbols
    5. yfinance earnings supplement
    6. Open WebSocket stream (Phase 2)
    """
    def __init__(self):
        self.last_run_date = None

    def start(self):
        t = threading.Thread(target=self._loop, name='morning-routine', daemon=True)
        t.start()
        log.info("[MorningRoutine] Background thread started")

    def _loop(self):
        while True:
            try:
                now_ct = datetime.now(CENTRAL)
                today = now_ct.strftime('%Y-%m-%d')

                # Check if it's 8:45 AM CT on a weekday
                if now_ct.weekday() < 5:
                    if now_ct.hour == 8 and now_ct.minute == 45:
                        if self.last_run_date != today:
                            self.run_full_refresh()
                            self.last_run_date = today
                
                time.sleep(30)
            except Exception as e:
                log.error(f"[MorningRoutine] Loop error: {e}")
                time.sleep(60)

    def run_full_refresh(self):
        log.info("[MorningRoutine] Starting morning refresh sequence...")
        # Step 1: Seed candidates
        # Step 2: Fundamentals
        # Step 3: Daily bars
        # ... implementation will be added as we wire it to the DB
        log.info("[MorningRoutine] Morning refresh sequence complete.")

_routine = MorningRoutine()

def start_morning_routine():
    _routine.start()
