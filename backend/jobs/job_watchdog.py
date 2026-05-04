"""
job_watchdog.py — Background daemon that detects stale LLM jobs and resets them.

Started automatically by app.py on startup. Any job stuck in 'running' status
for longer than JOB_TIMEOUT_MINUTES is marked 'error' with an explanatory message,
so the frontend can offer a retry instead of hanging indefinitely.
"""
import threading
import time
from datetime import datetime, timezone, timedelta

from database import get_connection

JOB_TIMEOUT_MINUTES = 10
POLL_INTERVAL_SECONDS = 60


def _reset_stale_jobs():
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=JOB_TIMEOUT_MINUTES)).isoformat()
    with get_connection() as conn:
        stale = conn.execute(
            "SELECT id FROM llm_jobs WHERE status = 'running' AND updated_at < ?",
            (cutoff,),
        ).fetchall()

        for row in stale:
            job_id = row['id']
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "UPDATE llm_jobs SET status='error', output=?, updated_at=? WHERE id=?",
                (f"Timed out after {JOB_TIMEOUT_MINUTES} min — process may have crashed. "
                 "Use the retry endpoint to re-run.", now, job_id),
            )
            print(f"[watchdog] Reset stale job {job_id}")


def _watchdog_loop():
    # Also reset any stale jobs left over from a previous crash on startup
    try:
        _reset_stale_jobs()
    except Exception as e:
        print(f"[watchdog] Startup reset error: {e}")

    while True:
        time.sleep(POLL_INTERVAL_SECONDS)
        try:
            _reset_stale_jobs()
        except Exception as e:
            print(f"[watchdog] Poll error: {e}")


def start_watchdog():
    """Call once from app.py to launch the watchdog daemon thread."""
    t = threading.Thread(target=_watchdog_loop, name="job-watchdog", daemon=True)
    t.start()
    print("[watchdog] Job watchdog started.")
