"""
fastapi_app/routers/ts_alerts.py

TradeStation alert log import router.
Accepts exported alert logs from TradeStation and stores them in screener_alerts
using the same schema as the live Schwab alert system.

Endpoints:
  POST /api/ts-alerts/import/csv   — Upload a TradeStation CSV export
  POST /api/ts-alerts/import/json  — Upload a JSON array of alert records
  GET  /api/ts-alerts/fields       — Return expected CSV/JSON field names

Future: chart attachment will be appended per alert once chart-gen system is ready.

Column mapping (screener_alerts table):
  symbol          → symbol
  alert_type      → alert_type
  price           → trigger_price
  time            → alert_time (explicit; TIMESTAMPTZ, Eastern assumed if naive)
  rvol            → rel_vol
  gap_pct         → gap_pct
  volume          → trigger_volume
  priority_tier   → priority_tier (default 'Tier 3')
  notes           → feedback_notes
  source          → source (requires migration: ALTER TABLE screener_alerts ADD COLUMN IF NOT EXISTS source VARCHAR(64))
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
import asyncpg

from fastapi_app.db import get_db
from validation import EASTERN_TZ

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ts-alerts", tags=["ts-alerts"])


# ---------------------------------------------------------------------------
# Field contract — matches screener_alerts table columns we can populate
# ---------------------------------------------------------------------------

EXPECTED_CSV_FIELDS = [
    "symbol",
    "alert_type",
    "price",
    "time",           # ISO-8601 or 'YYYY-MM-DD HH:MM:SS' (Eastern assumed if naive)
    "rvol",           # optional → rel_vol
    "gap_pct",        # optional
    "volume",         # optional → trigger_volume
    "priority_tier",  # optional — default 'Tier 3' if absent
    "notes",          # optional → feedback_notes
]


class TSAlertRecord(BaseModel):
    """Single alert record from a TradeStation export."""
    symbol: str
    alert_type: str
    price: float
    time: str
    rvol: Optional[float] = 0.0
    gap_pct: Optional[float] = 0.0
    volume: Optional[int] = 0
    priority_tier: Optional[str] = "Tier 3"
    notes: Optional[str] = None


class TSImportResult(BaseModel):
    inserted: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts_time(raw: str) -> datetime:
    """Parse a TradeStation timestamp string into an aware UTC datetime."""
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
    ):
        try:
            naive = datetime.strptime(raw, fmt)
            # Assume Eastern if no tzinfo
            return EASTERN_TZ.localize(naive).astimezone(timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised timestamp format: {raw!r}")


async def _insert_alert(conn: asyncpg.Connection, rec: TSAlertRecord) -> bool:
    """
    Insert one record into screener_alerts using the real column schema.
    Returns True on insert, False on duplicate (same symbol + alert_type + time).

    Requires the source column migration to have been run:
      ALTER TABLE screener_alerts ADD COLUMN IF NOT EXISTS source VARCHAR(64);
    """
    try:
        alert_time = _parse_ts_time(rec.time)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    existing = await conn.fetchval(
        """
        SELECT id FROM screener_alerts
        WHERE symbol = $1 AND alert_type = $2 AND alert_time = $3
        """,
        rec.symbol.upper(), rec.alert_type, alert_time
    )
    if existing:
        return False

    await conn.execute(
        """
        INSERT INTO screener_alerts (
            symbol, alert_type, trigger_price, rel_vol, gap_pct,
            trigger_volume, priority_tier, alert_time, sent, feedback_notes,
            source
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, FALSE, $9,
            'tradestation'
        )
        """,
        rec.symbol.upper(),
        rec.alert_type,
        rec.price,
        rec.rvol or 0.0,
        rec.gap_pct or 0.0,
        rec.volume or 0,
        rec.priority_tier or "Tier 3",
        alert_time,
        rec.notes,
    )
    return True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/fields")
async def get_expected_fields():
    """Return the expected field names for CSV/JSON imports."""
    return {
        "csv_fields": EXPECTED_CSV_FIELDS,
        "notes": (
            "Required: symbol, alert_type, price, time. "
            "Optional: rvol, gap_pct, volume, priority_tier, notes. "
            "Timestamps accepted as ISO-8601 or 'YYYY-MM-DD HH:MM:SS' "
            "(Eastern assumed if no timezone)."
        )
    }


@router.post("/import/json", response_model=TSImportResult)
async def import_json_alerts(
    records: list[TSAlertRecord],
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Import a JSON array of TradeStation alert records.

    Example body:
    [
      {"symbol": "NVDA", "alert_type": "VOLUME_SPIKE", "price": 125.50, "time": "2026-08-06 09:45:00"},
      ...
    ]
    """
    inserted = 0
    skipped = 0
    errors: list[str] = []

    for rec in records:
        try:
            ok = await _insert_alert(db, rec)
            if ok:
                inserted += 1
            else:
                skipped += 1
        except HTTPException as exc:
            errors.append(f"{rec.symbol} @ {rec.time}: {exc.detail}")
        except Exception as exc:
            logger.error("TS alert import error for %s: %s", rec.symbol, exc)
            errors.append(f"{rec.symbol} @ {rec.time}: {exc}")

    logger.info(
        "[ts_alerts] JSON import done — inserted=%d skipped=%d errors=%d",
        inserted, skipped, len(errors)
    )
    return TSImportResult(inserted=inserted, skipped=skipped, errors=errors)


@router.post("/import/csv", response_model=TSImportResult)
async def import_csv_alerts(
    file: UploadFile = File(..., description="TradeStation CSV alert export"),
    db: asyncpg.Connection = Depends(get_db),
):
    """
    Import a TradeStation CSV alert export file.

    Expected columns (case-insensitive header row):
      symbol, alert_type, price, time
      [rvol, gap_pct, volume, priority_tier, notes]  ← optional
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # strip BOM if present
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise HTTPException(status_code=422, detail="CSV has no header row")

    inserted = 0
    skipped = 0
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        norm = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        try:
            rec = TSAlertRecord(
                symbol=norm["symbol"],
                alert_type=norm["alert_type"],
                price=float(norm["price"]),
                time=norm["time"],
                rvol=float(norm["rvol"]) if norm.get("rvol") else 0.0,
                gap_pct=float(norm["gap_pct"]) if norm.get("gap_pct") else 0.0,
                volume=int(float(norm["volume"])) if norm.get("volume") else 0,
                priority_tier=norm.get("priority_tier") or "Tier 3",
                notes=norm.get("notes"),
            )
            ok = await _insert_alert(db, rec)
            if ok:
                inserted += 1
            else:
                skipped += 1
        except KeyError as exc:
            errors.append(f"Row {row_num}: missing required field {exc}")
        except HTTPException as exc:
            errors.append(f"Row {row_num}: {exc.detail}")
        except Exception as exc:
            logger.error("TS CSV import error row %d: %s", row_num, exc)
            errors.append(f"Row {row_num}: {exc}")

    logger.info(
        "[ts_alerts] CSV import done — inserted=%d skipped=%d errors=%d",
        inserted, skipped, len(errors)
    )
    return TSImportResult(inserted=inserted, skipped=skipped, errors=errors)
