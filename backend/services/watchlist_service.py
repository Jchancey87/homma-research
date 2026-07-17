"""
backend/services/watchlist_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Service for watchlist bulk import and export operations.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from typing import List, Dict, Any, Tuple, Optional

import asyncpg
from fastapi_app.db import watchlist as db_watchlist
from validation import normalize_ticker

log = logging.getLogger(__name__)

async def export_watchlist_to_csv(conn: asyncpg.Connection, group_id: Optional[int] = None) -> str:
    """
    Exports the current watchlist to a CSV string.
    """
    rows = await db_watchlist.list_watchlist(conn, group_id=group_id)
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["ticker", "sector", "notes", "tags", "runway_months", "dilution_risk", "upcoming_catalyst", "catalyst_date"])
    
    for r in rows:
        ticker = r["ticker"]
        sector = r.get("sector") or ""
        notes = r.get("notes") or ""
        runway_months = r.get("runway_months") if r.get("runway_months") is not None else ""
        dilution_risk = r.get("dilution_risk") or ""
        upcoming_catalyst = r.get("upcoming_catalyst") or ""
        catalyst_date = r.get("catalyst_date") if r.get("catalyst_date") is not None else ""
        if catalyst_date:
            catalyst_date = str(catalyst_date)
        
        # Parse tags from JSON string/list
        tags_raw = r.get("tags")
        if isinstance(tags_raw, str):
            try:
                tags_list = json.loads(tags_raw)
            except Exception:
                tags_list = []
        elif isinstance(tags_raw, list):
            tags_list = tags_raw
        else:
            tags_list = []
            
        tags_str = ",".join(tags_list)
        writer.writerow([ticker, sector, notes, tags_str, runway_months, dilution_risk, upcoming_catalyst, catalyst_date])
        
    return output.getvalue()

async def import_watchlist_from_csv(
    conn: asyncpg.Connection,
    csv_content: str,
    group_id: Optional[int] = None,
) -> Tuple[int, int]:
    """
    Parses CSV content and imports/upserts symbols into the watchlist.
    CSV can have headers: ticker, sector, notes, tags, runway_months, dilution_risk, upcoming_catalyst, catalyst_date
    If no headers or unrecognized headers, treats the first column as ticker.
    
    Returns a tuple of (inserted_count, updated_count).
    """
    existing_tickers = {t.upper() for t in await db_watchlist.list_watchlist_tickers(conn, group_id=group_id)}
    
    # Read CSV
    f = io.StringIO(csv_content)
    # Peek to check if there is a header
    first_line = f.readline()
    f.seek(0)
    
    has_header = False
    if first_line:
        # Common check for header
        parts = [p.strip().lower() for p in first_line.split(",")]
        if "ticker" in parts or "symbol" in parts:
            has_header = True
            
    reader = csv.reader(f)
    
    header_map = {}
    if has_header:
        headers = [h.strip().lower() for h in next(reader)]
        for i, h in enumerate(headers):
            if h in ("ticker", "symbol"):
                header_map["ticker"] = i
            elif h == "sector":
                header_map["sector"] = i
            elif h == "notes":
                header_map["notes"] = i
            elif h in ("tags", "tag"):
                header_map["tags"] = i
            elif h in ("runway_months", "runway"):
                header_map["runway_months"] = i
            elif h in ("dilution_risk", "dilution"):
                header_map["dilution_risk"] = i
            elif h in ("upcoming_catalyst", "catalyst"):
                header_map["upcoming_catalyst"] = i
            elif h in ("catalyst_date", "catalystdate"):
                header_map["catalyst_date"] = i
    else:
        # Default mapping if no header
        header_map = {"ticker": 0}
        
    inserted = 0
    updated = 0
    
    for row in reader:
        if not row:
            continue
            
        # Extract ticker
        ticker_idx = header_map.get("ticker", 0)
        if ticker_idx >= len(row):
            continue
        raw_ticker = row[ticker_idx].strip()
        if not raw_ticker:
            continue
            
        try:
            ticker = normalize_ticker(raw_ticker)
        except Exception:
            # Fallback if normalize_ticker is strict
            ticker = raw_ticker.upper().strip()
            
        # Extract optional fields
        sector = None
        if "sector" in header_map:
            idx = header_map["sector"]
            if idx < len(row):
                sector = row[idx].strip() or None
                
        notes = None
        if "notes" in header_map:
            idx = header_map["notes"]
            if idx < len(row):
                notes = row[idx].strip() or None
                
        tags_list = []
        if "tags" in header_map:
            idx = header_map["tags"]
            if idx < len(row):
                raw_tags = row[idx].strip()
                if raw_tags:
                    # split by comma, semicolon, or space
                    tags_list = [t.strip() for t in raw_tags.replace(";", ",").split(",") if t.strip()]
                    
        tags_json = json.dumps(tags_list)
        
        runway_months = None
        if "runway_months" in header_map:
            idx = header_map["runway_months"]
            if idx < len(row) and row[idx].strip():
                try:
                    runway_months = float(row[idx].strip())
                except ValueError:
                    pass

        dilution_risk = None
        if "dilution_risk" in header_map:
            idx = header_map["dilution_risk"]
            if idx < len(row):
                dilution_risk = row[idx].strip() or None

        upcoming_catalyst = None
        if "upcoming_catalyst" in header_map:
            idx = header_map["upcoming_catalyst"]
            if idx < len(row):
                upcoming_catalyst = row[idx].strip() or None

        catalyst_date = None
        if "catalyst_date" in header_map:
            idx = header_map["catalyst_date"]
            if idx < len(row) and row[idx].strip():
                from datetime import datetime
                try:
                    catalyst_date = datetime.strptime(row[idx].strip(), "%Y-%m-%d").date()
                except ValueError:
                    try:
                        catalyst_date = datetime.fromisoformat(row[idx].strip()).date()
                    except ValueError:
                        pass
        
        # Check if updating or inserting
        is_update = ticker.upper() in existing_tickers
        
        # Perform upsert
        await db_watchlist.upsert_watchlist(
            conn,
            ticker=ticker,
            sector=sector,
            notes=notes,
            tags_json=tags_json,
            group_id=group_id,
            runway_months=runway_months,
            dilution_risk=dilution_risk,
            upcoming_catalyst=upcoming_catalyst,
            catalyst_date=catalyst_date,
        )
        
        if is_update:
            updated += 1
        else:
            inserted += 1
            
    return inserted, updated


async def enrich_watchlist_fundamentals(
    conn: asyncpg.Connection,
    group_id: Optional[int] = None,
    ticker: Optional[str] = None
) -> int:
    """
    Enrich watchlist tickers with fundamental metrics and extract milestones.
    Returns the number of tickers processed.
    """
    import yfinance as yf
    from datetime import datetime
    from fastapi_app.db import watchlist as db_watchlist
    from llm.llm_client import get_upcoming_catalyst
    from services.sec_service import search_filings_text
    from fastapi_app.tasks.alerts import send_telegram_message
    
    if ticker:
        if group_id is not None:
            if group_id == 0:
                rows = await conn.fetch("SELECT * FROM watchlist WHERE ticker = $1 AND group_id IS NULL", ticker)
            else:
                rows = await conn.fetch("SELECT * FROM watchlist WHERE ticker = $1 AND group_id = $2", ticker, group_id)
        else:
            rows = await conn.fetch("SELECT * FROM watchlist WHERE ticker = $1", ticker)
        rows = [dict(r) for r in rows]
    else:
        rows = await db_watchlist.list_watchlist(conn, group_id=group_id)
        
    if not rows:
        return 0
        
    processed = 0
    for r in rows:
        ticker = r["ticker"]
        prev_runway = r.get("runway_months")
        prev_dilution = r.get("dilution_risk")
        
        log.info(f"Enriching fundamentals for {ticker}")
        
        # 1. Fetch yfinance metrics
        cash_val = None
        net_income_val = None
        ocf_val = None
        runway_months = None
        dilution = "Low"
        shares_history = {}
        
        try:
            t = yf.Ticker(ticker)
            bs = t.quarterly_balance_sheet
            fin = t.quarterly_financials
            cf = t.quarterly_cashflow
            
            if bs is not None and not bs.empty:
                for k in ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents', 'Cash Financial', 'Cash']:
                    if k in bs.index:
                        val = bs.loc[k].dropna()
                        if not val.empty:
                            cash_val = float(val.iloc[0])
                            break
                            
                for k in ['Ordinary Shares Number', 'Share Issued']:
                    if k in bs.index:
                        row = bs.loc[k].dropna()
                        for d_idx, val in row.items():
                            shares_history[str(d_idx).split()[0]] = float(val)
                        break

            if fin is not None and not fin.empty:
                for k in ['Net Income', 'Net Income Common Stockholders']:
                    if k in fin.index:
                        val = fin.loc[k].dropna()
                        if not val.empty:
                            net_income_val = float(val.iloc[0])
                            break

            if cf is not None and not cf.empty:
                for k in ['Operating Cash Flow', 'Cash Flow From Operating Activities']:
                    if k in cf.index:
                        val = cf.loc[k].dropna()
                        if not val.empty:
                            ocf_val = float(val.iloc[0])
                            break
                            
            # Calculate Runway
            burn = None
            if ocf_val and ocf_val < 0:
                burn = abs(ocf_val)
            elif net_income_val and net_income_val < 0:
                burn = abs(net_income_val)
                
            if cash_val is not None and burn:
                runway_months = round(float((cash_val / burn) * 3), 1)
                
            # Dilution Risk
            if runway_months and runway_months < 6:
                dilution = '🔴 HIGH'
            elif len(shares_history) > 1:
                dates_sorted = sorted(list(shares_history.keys()))
                first_shares = shares_history[dates_sorted[0]]
                last_shares = shares_history[dates_sorted[-1]]
                if last_shares > first_shares * 1.10:
                    dilution = '🔴 HIGH'
                elif last_shares > first_shares * 1.02:
                    dilution = '🟡 MODERATE'
        except Exception as e:
            log.warning(f"Failed to fetch yfinance data for {ticker}: {e}")
            
        # 2. Extract milestone from SEC / news / LLM
        upcoming_catalyst = None
        catalyst_date = None
        
        try:
            sec_hits = search_filings_text(ticker, ["PDUFA", "clinical", "trial", "phase"], days_back=180, n=5)
            
            news_hits = []
            try:
                t_instance = yf.Ticker(ticker)
                news_hits = t_instance.news or []
            except Exception:
                pass
                
            catalyst_info = get_upcoming_catalyst(ticker, news_hits, sec_hits)
            upcoming_catalyst = catalyst_info.get("upcoming_catalyst")
            catalyst_date_str = catalyst_info.get("catalyst_date")
            
            if catalyst_date_str:
                try:
                    catalyst_date = datetime.strptime(catalyst_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass
        except Exception as e:
            log.warning(f"Failed to extract milestone for {ticker}: {e}")
            
        # 3. Update DB
        await db_watchlist.update_watchlist_metrics(
            conn,
            ticker=ticker,
            runway_months=runway_months,
            dilution_risk=dilution,
            upcoming_catalyst=upcoming_catalyst,
            catalyst_date=catalyst_date,
            group_id=r.get("group_id")
        )
        
        # 4. Check alert condition
        is_runway_alert = (runway_months is not None and runway_months < 6) and (prev_runway is None or prev_runway >= 6)
        is_dilution_alert = (dilution == '🔴 HIGH') and (prev_dilution != '🔴 HIGH')
        if is_runway_alert or is_dilution_alert:
            alert_msg = (
                f"⚠️ *Watchlist Risk Alert: {ticker}*\n"
                f"Runway: {f'{runway_months:.1f}' if runway_months is not None else 'N/A'} months (prev: {f'{prev_runway:.1f}' if prev_runway is not None else 'N/A'})\n"
                f"Dilution Risk: {dilution} (prev: {prev_dilution or 'N/A'})\n"
            )
            if upcoming_catalyst:
                alert_msg += f"Upcoming Catalyst: {upcoming_catalyst}\n"
            if catalyst_date:
                alert_msg += f"Catalyst Date: {catalyst_date}\n"
            
            log.info(f"Sending Telegram alert for {ticker}...")
            send_telegram_message(alert_msg)
            
        processed += 1
        
    return processed

