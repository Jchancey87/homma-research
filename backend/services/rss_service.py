"""
backend/services/rss_service.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Core business logic for self-hosted curated RSS feed.
Includes feed ingestion, XML generation (with live quote enrichment),
and Telegram notification syndication.
"""
from __future__ import annotations

import re
import logging
import email.utils
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import html

import httpx
import asyncpg

from fastapi_app.config import settings
from fastapi_app.db import rss as db_rss
from services.live_quotes_service import get_live_quotes

log = logging.getLogger(__name__)

CATALYST_KEYWORDS = {
    "fda", "phase", "clinical", "trial", "pdufa", "clearance", 
    "approval", "breakthrough", "ind", "bla", "nda", "study", 
    "data", "patent", "acquisition", "merger", "earnings",
    "biopharma", "therapeutic", "vaccine", "oncology"
}

COMMON_WORDS_OR_ABBREVIATIONS = {
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IF", "IN", "IS", "IT", "ME", "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE",
    "ALL", "AND", "ANY", "ARE", "BAD", "BIG", "BOY", "BUS", "BUT", "BUY", "CAN", "CAR", "CAT", "DAY", "DID", "DOG", "DRY", "END", "EST", "FAR", 
    "FAT", "FIT", "FLY", "FOR", "FUN", "GAS", "GET", "HAD", "HAS", "HER", "HIM", "HIS", "HOT", "HOW", "ICE", "ITS", "JOB", "KEY", "LAW", "LOW", 
    "MAN", "MAP", "MAY", "MET", "MIN", "MAX", "NET", "NEW", "NOT", "NOW", "OFF", "OIL", "ONE", "OUT", "PAY", "RED", "RUN", "SAD", "SEA", "SEE", 
    "SIX", "SON", "TAX", "TEN", "THE", "TOP", "TRY", "TWO", "WAS", "WAY", "WEB", "WET", "WHO", "WHY", "HOW",
    "ALSO", "BACK", "BEEN", "BEST", "BLUE", "CAME", "COME", "COOK", "DEAR", "DONE", "DOES", "DRUG", "EACH", "EVER", "FEED", "FIND", "FINE", 
    "FISH", "FIVE", "FOUR", "FROM", "GAVE", "GLUE", "GOLD", "GOOD", "HAVE", "HEAR", "HERE", "HIGH", "HILL", "HIT", "HOME", "HOOD", "INTO", 
    "JUST", "KNEW", "KNOW", "LAND", "LAST", "LESS", "LIFE", "LIVE", "LONG", "LOOK", "LOOP", "LUNG", "MADE", "MAKE", "MANY", "MARK", "MASS", 
    "MATH", "MEET", "MIND", "MORE", "MOVE", "MUST", "NAME", "NEXT", "ONCE", "ONLY", "OPEN", "OVER", "PACK", "PART", "PLAY", "PLUG", "REAL", 
    "RIDE", "SAID", "SAME", "SEEM", "SEND", "SHOW", "SIDE", "SOME", "SOON", "SPEC", "SUCH", "SURE", "TAKE", "TALK", "THAT", "THEM", "THEN", 
    "THEY", "THIS", "TIME", "TOLD", "TOOK", "TOWN", "UPON", "VERY", "WANT", "WARM", "WAVE", "WENT", "WERE", "WHAT", "WHEN", "WHOM", "WILD", 
    "WILL", "WIND", "WITH", "WORK", "YOUR",
    "AI", "CEO", "CFO", "FDA", "IPO", "SEC", "PR", "PE", "EPS", "ETF", "USA", "UK", "CISO", "DOCS", "GPUS", "CSPC"
}

def clean_company_name(name: str) -> str:
    """Extract core company name by removing suffixes and descriptors."""
    name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', name)
    name = re.sub(r'[.,\/#!$%\^&\*;:{}=\-_`~()]', ' ', name)
    words = name.upper().split()
    
    suffixes = {
        "INC", "INCORPORATED", "CORP", "CORPORATION", "LTD", "LIMITED",
        "CO", "COMPANY", "HOLDING", "HOLDINGS", "HLDG", "HLDGS", "GROUP",
        "PLC", "AG", "SA", "S.A.", "S.A", "NV", "N.V.", "SE", "KGAA", "PARTNERS",
        "CORPORATE", "INTERNATIONAL", "INTL", "AMERICA", "USA", "UK",
        "CLASS", "SERIES", "COMMON", "STOCK", "EQUITY", "SHS", "ADS", "GDR",
        "PHARMACEUTICALS", "PHARMACEUTICAL", "PHARMA", "THERAPEUTICS", "THERAPEUTIC",
        "MEDICINES", "MEDICINE", "BIOSCIENCES", "BIOSCIENCE", "BIOPHARMACEUTICALS",
        "BIOPHARMA", "BIOTECHNOLOGY", "BIOTECH", "LABORATORIES", "LABS", "LAB",
        "SYSTEMS", "SYSTEM", "DEVICES", "DEVICE", "GLOBAL", "INDUSTRIES", "INDUSTRY",
        "SERVICES", "SERVICE", "SOLUTIONS", "SOLUTION", "HEALTHCARE", "HEALTH",
        "MED", "TECH", "TECHNOLOGY", "TECHNORIES", "SCIENCES", "SCIENCE"
    }
    
    cleaned_words = [w for w in words if w not in suffixes]
    if not cleaned_words:
        cleaned_words = [w for w in words if w]
        
    return " ".join(cleaned_words[:2])

def get_company_search_phrases(ticker: str, full_name: str) -> list[str]:
    """Get candidate matching phrases for a company name."""
    phrases = []
    if full_name and full_name.upper() != "UNKNOWN":
        cleaned = clean_company_name(full_name)
        if cleaned:
            phrases.append(cleaned)
        words = full_name.upper().split()
        first_word = words[0] if words else ""
        if len(first_word) > 3 and first_word not in COMMON_WORDS_OR_ABBREVIATIONS:
            phrases.append(first_word)
    return list(set(phrases))

# ---------------------------------------------------------------------------
# Feed Parsing (Built-in XML parsing to avoid external dependencies)
# ---------------------------------------------------------------------------

def parse_xml_feed(xml_content: bytes) -> list[dict]:
    """Parse RSS 2.0 or Atom XML feed into standard article structures."""
    articles = []
    try:
        root = ET.fromstring(xml_content)
        # Check if RSS 2.0
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                guid_el = item.find("guid")
                pub_date_el = item.find("pubDate")
                
                title = title_el.text if title_el is not None else ""
                link = link_el.text if link_el is not None else ""
                description = desc_el.text if desc_el is not None else ""
                guid = guid_el.text if guid_el is not None else link
                pub_date_str = pub_date_el.text if pub_date_el is not None else ""
                
                pub_dt = None
                if pub_date_str:
                    try:
                        pub_dt = email.utils.parsedate_to_datetime(pub_date_str)
                    except Exception:
                        pass
                if not pub_dt:
                    pub_dt = datetime.now(timezone.utc)
                    
                articles.append({
                    "guid": guid.strip() if guid else link.strip(),
                    "title": title.strip() if title else "",
                    "description": description.strip() if description else "",
                    "link": link.strip() if link else "",
                    "published_at": pub_dt
                })
        else:
            # Maybe Atom feed
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            # Handle with or without namespace
            entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
            for entry in entries:
                title_el = entry.find("atom:title", ns) or entry.find("title")
                link_el = entry.find("atom:link", ns) or entry.find("link")
                summary_el = entry.find("atom:summary", ns) or entry.find("summary") or entry.find("atom:content", ns) or entry.find("content")
                id_el = entry.find("atom:id", ns) or entry.find("id")
                published_el = entry.find("atom:published", ns) or entry.find("published") or entry.find("atom:updated", ns) or entry.find("updated")
                
                title = title_el.text if title_el is not None else ""
                
                link = ""
                if link_el is not None:
                    link = link_el.attrib.get("href", "")
                    if not link:
                        link = link_el.text or ""
                        
                description = summary_el.text if summary_el is not None else ""
                guid = id_el.text if id_el is not None else link
                pub_date_str = published_el.text if published_el is not None else ""
                
                pub_dt = None
                if pub_date_str:
                    try:
                        pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                    except Exception:
                        pass
                if not pub_dt:
                    pub_dt = datetime.now(timezone.utc)
                    
                articles.append({
                    "guid": guid.strip() if guid else link.strip(),
                    "title": title.strip() if title else "",
                    "description": description.strip() if description else "",
                    "link": link.strip() if link else "",
                    "published_at": pub_dt
                })
    except Exception as e:
        log.warning(f"Failed to parse XML feed: {e}")
    return articles


# ---------------------------------------------------------------------------
# Core Service Functions
# ---------------------------------------------------------------------------

async def fetch_and_ingest_feeds(conn: asyncpg.Connection) -> dict[str, int]:
    """
    Poll all active RSS sources, extract stock tickers, perform auto-curation
    based on Option B (ticker + keywords), and populate staging pool.
    """
    log.info("[rss_service] Starting feed ingestion...")
    
    # 1. Fetch target tickers to match against (Watchlist + Daily Gainers)
    watchlist_rows = await conn.fetch("SELECT ticker FROM watchlist")
    gainers_rows = await conn.fetch("SELECT DISTINCT ticker FROM daily_gainers")
    target_tickers = {r["ticker"].upper() for r in watchlist_rows} | {r["ticker"].upper() for r in gainers_rows}
    
    # Map tickers to company names using stock_fundamentals table
    fundamentals_rows = await conn.fetch(
        "SELECT symbol, company_name FROM stock_fundamentals WHERE symbol = ANY($1)",
        list(target_tickers)
    )
    ticker_to_company = {r["symbol"].upper(): r["company_name"] for r in fundamentals_rows}
    
    # 2. Get active sources
    sources = await db_rss.list_rss_sources(conn)
    active_sources = [s for s in sources if s["is_active"]]
    
    stats = {"processed": 0, "inserted": 0, "auto_approved": 0}
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        for src in active_sources:
            try:
                res = await client.get(src["feed_url"], follow_redirects=True)
                if res.status_code != 200:
                    log.warning(f"[rss_service] Feed {src['name']} returned HTTP {res.status_code}")
                    continue
                
                articles = parse_xml_feed(res.content)
                for art in articles:
                    stats["processed"] += 1
                    
                    # Ticker extraction
                    text_to_search = f"{art['title']} {art['description']}".upper()
                    detected = []
                    for ticker in target_tickers:
                        is_common = ticker in COMMON_WORDS_OR_ABBREVIATIONS or len(ticker) <= 2
                        if is_common:
                            ticker_regex = r'(?:\$' + re.escape(ticker) + r'\b|\b' + re.escape(ticker) + r'\b(?:\s*[\)\]:]|\s+COMMON))'
                        else:
                            ticker_regex = r'\b' + re.escape(ticker) + r'\b'
                        
                        has_ticker_match = re.search(ticker_regex, text_to_search)
                        
                        has_company_match = False
                        company_name = ticker_to_company.get(ticker)
                        if company_name and company_name.upper() != "UNKNOWN":
                            search_phrases = get_company_search_phrases(ticker, company_name)
                            for phrase in search_phrases:
                                if phrase and re.search(r'\b' + re.escape(phrase) + r'\b', text_to_search):
                                    has_company_match = True
                                    break
                                    
                        if has_ticker_match or has_company_match:
                            detected.append(ticker)
                    
                    # Auto-curation logic (Option B)
                    is_catalyst = any(
                        re.search(r'\b' + re.escape(kw) + r'\b', text_to_search.lower())
                        for kw in CATALYST_KEYWORDS
                    )
                    should_approve = len(detected) > 0 and is_catalyst
                    status = "approved" if should_approve else "pending"
                    
                    inserted = await db_rss.insert_rss_feed_pool_item(
                        conn,
                        source_id=src["id"],
                        guid=art["guid"],
                        title=art["title"],
                        description=art["description"],
                        link=art["link"],
                        published_at=art["published_at"],
                        detected_tickers=detected,
                        status=status
                    )
                    
                    if inserted:
                        stats["inserted"] += 1
                        if should_approve:
                            stats["auto_approved"] += 1
                            # Move directly to curated feed
                            await db_rss.insert_curated_rss_item(
                                conn,
                                pool_item_id=None,  # Handled inline
                                guid=art["guid"],
                                title=art["title"],
                                description=art["description"] or "Auto-approved market update.",
                                link=art["link"],
                                published_at=art["published_at"],
                                curated_by="system",
                                associated_tickers=detected,
                                curated_notes="System auto-curated: regulatory/catalyst match."
                            )
                
                # Stamp last polled
                await db_rss.update_rss_source(conn, src["id"], {"last_polled_at": datetime.now(timezone.utc)})
                
            except Exception as e:
                log.exception(f"[rss_service] Failed to poll feed {src['name']}: {e}")
                
    log.info(
        f"[rss_service] Feed ingestion complete. "
        f"Processed={stats['processed']} Inserted={stats['inserted']} Auto-Approved={stats['auto_approved']}"
    )
    return stats


async def generate_rss_xml(conn: asyncpg.Connection) -> str:
    """
    Generate standard RSS 2.0 XML dynamically, enriching approved feed items
    with live quotes (price, change %, volume) from live_quotes_service.
    """
    items = await db_rss.list_curated_rss_items(conn, limit=50)
    
    # Batch lookup quotes
    all_tickers = list({ticker for row in items for ticker in row["associated_tickers"]})
    quotes = {}
    if all_tickers:
        try:
            quotes = await get_live_quotes(all_tickers)
        except Exception as e:
            log.warning(f"[rss_service] Failed to fetch live quotes for enrichment: {e}")
            quotes = {}

    build_date = email.utils.format_datetime(datetime.now(timezone.utc))

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8" ?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '<channel>',
        f'  <title>{html.escape("TradeJournal Curated Feed")}</title>',
        f'  <link>{html.escape("https://homma.research")}</link>',
        f'  <description>{html.escape("Curated catalysts enriched with live stock quotes.")}</description>',
        f'  <language>en-us</language>',
        f'  <lastBuildDate>{build_date}</lastBuildDate>'
    ]

    for item in items:
        # Build enriched quote header
        metrics_html = []
        for ticker in item["associated_tickers"]:
            q = quotes.get(ticker)
            if q:
                metrics_html.append(
                    f"<b>${ticker}</b>: ${q.last_price:.2f} ({q.change_pct:+.2f}%) | Vol: {q.volume:,}"
                )
            else:
                metrics_html.append(f"<b>${ticker}</b>")
                
        metrics_str = " | ".join(metrics_html)
        enriched_desc = item["description"]
        if metrics_str:
            enriched_desc = f"📊 {metrics_str}<br/><br/>{enriched_desc}"

        pub_date = email.utils.format_datetime(item["published_at"])

        xml_lines.append('  <item>')
        xml_lines.append(f'    <title>{html.escape(item["title"])}</title>')
        xml_lines.append(f'    <link>{html.escape(item["link"])}</link>')
        xml_lines.append(f'    <description>{html.escape(enriched_desc)}</description>')
        xml_lines.append(f'    <guid isPermaLink="false">{html.escape(item["guid"])}</guid>')
        xml_lines.append(f'    <pubDate>{pub_date}</pubDate>')
        xml_lines.append('  </item>')

    xml_lines.append('</channel>')
    xml_lines.append('</rss>')

    return "\n".join(xml_lines)


async def send_pending_telegram_alerts(conn: asyncpg.Connection) -> int:
    """Send Telegram alerts for recently curated research items."""
    unsent = await db_rss.get_unsent_telegram_curated_items(conn)
    if not unsent:
        return 0

    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        log.warning("[rss_service] Telegram bot not configured. Skipping notifications.")
        return 0

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    sent_count = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for item in unsent:
            try:
                tickers_str = " ".join([f"${t}" for t in item["associated_tickers"]])
                
                # Strip HTML tags and truncate to prevent "message too long" errors
                desc = item['description'] or ""
                desc = re.sub(r'<[^>]*>', '', desc)
                if len(desc) > 500:
                    desc = desc[:500] + "..."
                
                # Escape markdown special characters in titles
                title_escaped = item['title'].replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                desc_escaped = desc.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
                
                message = (
                    f"📢 *CURATED RESEARCH APPROVED*\n"
                    f"Tickers: {tickers_str}\n\n"
                    f"*{title_escaped}*\n\n"
                    f"{desc_escaped}\n\n"
                    f"[Read Full Article]({item['link']})"
                )
                
                res = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                })
                
                if res.status_code == 200:
                    await db_rss.mark_telegram_sent(conn, item["id"])
                    sent_count += 1
                else:
                    log.warning(f"[rss_service] Telegram sent status {res.status_code}: {res.text}")
                    
            except Exception as e:
                log.exception(f"[rss_service] Failed to send Telegram alert for item {item['id']}: {e}")

    return sent_count
