"""
validation/constants.py
-----------------------
Shared, project-wide constants that don't fit cleanly into any single
domain module. Importers should prefer these over re-defining their own
copies so the project has one source of truth for canonical names.

Why a separate module:
- Keeps schemas.py focused on request/response validation.
- Avoids a circular import: constants are needed by both services and
  jobs, neither of which import from validation.schemas.
"""
import pytz


# Canonical US/Eastern timezone. Use this anywhere a Python tz object
# is needed (pytz.localize, datetime.now(tz), CronTrigger(timezone=...)).
# IANA-canonical name is "America/New_York" — that is the form Postgres
# accepts in raw SQL via "AT TIME ZONE 'America/New_York'" and the form
# pandas dt.tz_convert expects. Centralising the Python-side tz here
# eliminates the "US/Eastern" vs "America/New_York" dual-spelling bug.
EASTERN_TZ = pytz.timezone("America/New_York")
