#!/usr/bin/env python3
"""
Daily deep analysis report job.
Queries the database for today's top gainers, runs a continuation/catalyst analysis
on the top 10, does a deep technical dive on the top 3, and emails the result.

Triggered by cron at 8:00 PM Mon–Fri:
  0 20 * * 1-5 /home/jack/Documents/StockAnalysis/trading-journal/venv/bin/python /home/jack/Documents/StockAnalysis/trading-journal/backend/jobs/daily_analysis_report.py

Usage:
  python daily_analysis_report.py [--date 2026-05-01] [--dry-run]
"""

import sys
import os
import argparse
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date as date_cls
# Allow imports from backend/ and repo root
_backend = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
_repo = os.path.dirname(_backend)
if _repo not in sys.path:
    sys.path.insert(0, _repo)
if _backend not in sys.path:
    sys.path.insert(0, _backend)

import yfinance as yf
import pandas as pd
import markdown

from database import get_connection
from config import Config
from llm.llm_client import get_continuation_analysis, get_deep_analysis_report
from services.fmp_service import (
    get_earnings_calendar,
    get_company_profile,
    get_cash_position,
    get_income_statement,
    get_insider_transactions
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Generate and email deep daily analysis report')
    import pytz
    from datetime import datetime
    eastern = pytz.timezone('US/Eastern')
    default_date = datetime.now(eastern).strftime('%Y-%m-%d')
    parser.add_argument('--date', default=default_date, help='YYYY-MM-DD')
    parser.add_argument('--dry-run', action='store_true', help='Print report instead of emailing')
    args = parser.parse_args()

    target_date = args.date
    dry_run = args.dry_run

    log.info(f"Starting daily analysis report for {target_date} (dry_run={dry_run})")

    # 1. Fetch Top 10 Gainers from DB
    gainers = fetch_top_gainers_from_db(target_date, limit=10)
    if not gainers:
        log.warning(f"No gainers found in database for {target_date}. Did ingest_gainers.py run?")
        return

    # 2. Top 10 Continuation / Catalyst Analysis
    log.info("Generating Top 10 Continuation Report...")
    continuation_md, _ = get_continuation_analysis(target_date, gainers)

    # 2a. Parse Top Picks from the report and persist to DB
    parse_and_save_top_picks(continuation_md, target_date, gainers)

    # 3. Top 3 Deep Technical / Fundamental Analysis
    top_3_gainers = gainers[:3]
    log.info(f"Fetching deeper technical data for top 3: {[g['ticker'] for g in top_3_gainers]}")
    deep_data = enrich_deep_technicals(top_3_gainers)
    
    log.info("Generating Top 3 Deep Analysis Report...")
    deep_analysis_md, _ = get_deep_analysis_report(target_date, deep_data)

    # 4. Combine and Email
    full_report_md = f"# Daily Market Analysis — {target_date}\n\n"
    full_report_md += "## 🚀 Top 3 Gainers Deep Dive\n\n" + deep_analysis_md + "\n\n---\n\n"
    full_report_md += "## 📊 Top 10 Continuation & Catalyst Overview\n\n" + continuation_md

    if dry_run:
        print("\n\n" + "="*50)
        print(full_report_md)
        print("="*50 + "\n")
        log.info("Dry run complete. No email sent.")
        return

    send_email(target_date, full_report_md)


def parse_and_save_top_picks(continuation_md: str, date_str: str, gainers: list[dict]):
    """
    Parse the '## 🏆 Top Picks for Continuation Watch' section from the continuation
    report markdown and persist each ticker to the continuation_picks table.
    Format expected from the LLM:
        1. ERNA - High gap percentage and low float...
        2. OSS  - ...
    """
    import re
    # Find the section between '## 🏆 Top Picks' and the next ## heading
    section_match = re.search(
        r'##\s*🏆\s*Top Picks.*?\n(.*?)(?=\n##|\Z)',
        continuation_md,
        re.DOTALL | re.IGNORECASE,
    )
    if not section_match:
        log.warning('Could not find Top Picks section in continuation report')
        return

    section_text = section_match.group(1).strip()
    # Match lines like: 1. ERNA - reason or 1. ERNA — reason
    pick_pattern = re.findall(
        r'^\d+\.\s+([A-Z]{1,6})\s*[-—]\s*(.+)$',
        section_text,
        re.MULTILINE,
    )
    if not pick_pattern:
        log.warning(f'No pick lines found in section: {section_text[:200]}')
        return

    # Build a quick lookup of gainer data by ticker
    gainer_map = {g['ticker']: g for g in gainers}
    now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

    with get_connection() as conn:
        for rank, (ticker, reason) in enumerate(pick_pattern, start=1):
            ticker = ticker.upper().strip()
            g = gainer_map.get(ticker, {})
            conn.execute(
                """
                INSERT INTO continuation_picks
                    (ticker, date, reason, gap_pct, float_shares, rvol_15m, sector, rank, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ticker, date) DO UPDATE
                    SET reason = EXCLUDED.reason, rank = EXCLUDED.rank
                """,
                (
                    ticker, date_str, reason.strip(),
                    g.get('gap_pct'), g.get('float_shares'), g.get('rvol_15m'),
                    g.get('sector'), rank, now,
                )
            )
            log.info(f'Saved continuation pick #{rank}: {ticker}')


def fetch_top_gainers_from_db(target_date: str, limit: int) -> list[dict]:
    query = """
        SELECT ticker, gap_pct, float_shares, rvol_15m, sector, market_cap,
               news_headline, news_fresh, close_price, open_price, prev_close,
               COALESCE(extended_change_pct, gap_pct, 0) AS extended_change_pct
        FROM daily_gainers
        WHERE date = %s
        ORDER BY COALESCE(extended_change_pct, gap_pct, 0) DESC
        LIMIT %s
    """
    with get_connection() as conn:
        rows = conn.execute(query, (target_date, limit)).fetchall()
    return [dict(r) for r in rows]


def get_yf_quarterly_metric(df, keys: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    for k in keys:
        if k in df.index:
            row = df.loc[k]
            if hasattr(row, 'iloc'):
                val = row.iloc[0]
            else:
                val = row
            import pandas as pd
            if pd.notna(val):
                return float(val)
    return None


def get_yf_insider_net_shares(t, days_back=90) -> int | None:
    try:
        df = t.insider_transactions
        if df is None or df.empty:
            return None
        import pandas as pd
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_back)
        df['Start Date'] = pd.to_datetime(df['Start Date'])
        recent = df[df['Start Date'] >= cutoff]
        net_shares = 0
        found = False
        for idx, row in recent.iterrows():
            shares = row.get('Shares')
            text = str(row.get('Text') or '').lower()
            if not shares or pd.isna(shares):
                continue
            if 'purchase' in text or 'buy' in text:
                net_shares += int(shares)
                found = True
            elif 'sale' in text or 'sell' in text:
                net_shares -= int(shares)
                found = True
        return net_shares if found else None
    except Exception:
        return None


def enrich_deep_technicals(gainers: list[dict]) -> list[dict]:
    enriched = []
    for g in gainers:
        ticker = g['ticker']
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            
            # Fetch 6 months of daily data to calculate 20/50/200 SMA and RSI
            hist = t.history(period="6mo", interval="1d")
            
            sma_20 = "N/A"
            sma_50 = "N/A"
            sma_200 = "N/A"
            rsi_14 = "N/A"
            
            if len(hist) > 0:
                closes = hist['Close']
                if len(closes) >= 20:
                    sma_20 = round(closes.rolling(window=20).mean().iloc[-1], 2)
                if len(closes) >= 50:
                    sma_50 = round(closes.rolling(window=50).mean().iloc[-1], 2)
                if len(closes) >= 200:
                    sma_200 = round(closes.rolling(window=200).mean().iloc[-1], 2)
                
                if len(closes) >= 15:
                    delta = closes.diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    rsi = 100 - (100 / (1 + rs))
                    rsi_14 = round(rsi.iloc[-1], 2)
            
            # Fetch FMP deep fundamentals with individual try-except blocks
            profile = {}
            try:
                profile = get_company_profile(ticker)
            except Exception as e:
                log.warning(f"Failed to fetch FMP profile for {ticker}: {e}")

            earnings = {}
            try:
                earnings = get_earnings_calendar(ticker)
            except Exception as e:
                log.warning(f"Failed to fetch FMP earnings for {ticker}: {e}")

            cash = {}
            try:
                cash = get_cash_position(ticker)
            except Exception as e:
                log.warning(f"Failed to fetch FMP cash for {ticker}: {e}")

            income = []
            try:
                income = get_income_statement(ticker, quarters=1)
            except Exception as e:
                log.warning(f"Failed to fetch FMP income for {ticker}: {e}")

            insider = {}
            try:
                insider = get_insider_transactions(ticker, days_back=90)
            except Exception as e:
                log.warning(f"Failed to fetch FMP insider transactions for {ticker}: {e}")

            true_float = profile.get('float_shares')
            shares_out = profile.get('shares_outstanding')
            next_earnings = earnings.get('next_earnings_date')
            earnings_status = earnings.get('next_earnings_status')
            cash_val = cash.get('cash')
            net_income_val = income[0].get('net_income') if income else None
            insider_net = insider.get('net_shares')

            # --- YFinance fallbacks ---
            if true_float is None:
                true_float = info.get('floatShares')
            if shares_out is None:
                shares_out = info.get('sharesOutstanding')

            if not next_earnings or next_earnings == 'N/A':
                try:
                    calendar = t.calendar
                    if calendar and 'Earnings Date' in calendar:
                        dates = calendar['Earnings Date']
                        if isinstance(dates, list) and len(dates) > 0:
                            next_earnings = str(dates[0])
                            earnings_status = 'upcoming'
                        elif dates:
                            next_earnings = str(dates)
                            earnings_status = 'upcoming'
                except Exception:
                    pass

            if cash_val is None:
                try:
                    cash_val = get_yf_quarterly_metric(t.quarterly_balance_sheet, [
                        'Cash Cash Equivalents And Short Term Investments',
                        'Cash And Cash Equivalents',
                        'Cash Financial'
                    ])
                except Exception:
                    pass

            if net_income_val is None:
                try:
                    net_income_val = get_yf_quarterly_metric(t.quarterly_financials, [
                        'Net Income',
                        'Net Income Common Stockholders'
                    ])
                except Exception:
                    pass

            if insider_net is None:
                try:
                    insider_net = get_yf_insider_net_shares(t, days_back=90)
                except Exception:
                    pass

            fmp_data = {
                'FMP True Float': format_large_number(true_float),
                'FMP Shares Out': format_large_number(shares_out),
                'Next Earnings Date': next_earnings if next_earnings else 'N/A',
                'Next Earnings Status': earnings_status if earnings_status else 'N/A',
                'Cash Position': format_large_number(cash_val),
                'Net Income (Latest Q)': format_large_number(net_income_val),
                'Insider Net Shares (90d)': insider_net if insider_net is not None else 'N/A'
            }

            enriched.append({
                'ticker': ticker,
                'Current Price': f"${g.get('close_price', 'N/A')}",
                'Extended Change': f"{g.get('extended_change_pct', 'N/A')}%",
                'Gap': f"{g.get('gap_pct', 'N/A')}%",
                'Sector': g.get('sector', 'N/A'),
                'Market Cap': format_large_number(g.get('market_cap')),
                'SMA 20': f"${sma_20}",
                'SMA 50': f"${sma_50}",
                'SMA 200': f"${sma_200}",
                'RSI (14)': rsi_14,
                'Recent Headline': g.get('news_headline', 'N/A'),
                'Fresh Catalyst?': 'Yes' if g.get('news_fresh') else 'No',
                **fmp_data
            })
        except Exception as e:
            log.warning(f"Failed to fetch deeper data for {ticker}: {e}")
            enriched.append({'ticker': ticker, 'Error': str(e)})
            
    return enriched


def format_large_number(num):
    if num is None:
        return 'N/A'
    if num >= 1e9:
        return f"{num / 1e9:.2f}B"
    elif num >= 1e6:
        return f"{num / 1e6:.2f}M"
    return str(num)


def send_email(date_str: str, markdown_content: str):
    if not Config.SMTP_SERVER or not Config.SMTP_USER or not Config.NOTIFY_EMAIL:
        log.error("SMTP configuration is missing in config.py / .env. Cannot send email.")
        return

    html_content = markdown.markdown(markdown_content)

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Daily Market Deep Analysis - {date_str}"
    msg['From'] = Config.SMTP_USER
    msg['To'] = Config.NOTIFY_EMAIL

    part1 = MIMEText(markdown_content, 'plain')
    part2 = MIMEText(html_content, 'html')
    msg.attach(part1)
    msg.attach(part2)

    try:
        log.info(f"Connecting to SMTP server {Config.SMTP_SERVER}:{Config.SMTP_PORT}...")
        server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT)
        server.starttls()
        if Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        
        server.sendmail(Config.SMTP_USER, Config.NOTIFY_EMAIL, msg.as_string())
        server.quit()
        log.info("Email sent successfully!")
    except Exception as e:
        log.error(f"Failed to send email: {e}")


if __name__ == '__main__':
    main()
