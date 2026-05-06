from database import get_connection


def get_gainers_filtered(date=None, min_gap=None, max_float_m=None,
                          min_rvol=None, sector=None) -> list[dict]:
    """
    Return filtered daily_gainers rows as dicts.
    max_float_m is in millions (UI-friendly); converted to raw shares internally.
    """
    query  = "SELECT * FROM daily_gainers WHERE 1=1"
    params = []

    if date:
        query += " AND date = %s"
        params.append(date)
    if min_gap is not None:
        query += " AND gap_pct >= %s"
        params.append(float(min_gap))
    if max_float_m is not None:
        query += " AND float_shares <= %s"
        params.append(float(max_float_m) * 1_000_000)
    if min_rvol is not None:
        query += " AND rvol_15m >= %s"
        params.append(float(min_rvol))
    if sector:
        query += " AND sector = %s"
        params.append(sector)

    query += " ORDER BY date DESC, gap_pct DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]


def get_sectors() -> list[str]:
    """Return distinct sectors present in the gainers table."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT sector FROM daily_gainers WHERE sector IS NOT NULL ORDER BY sector"
        ).fetchall()
    return [r['sector'] for r in rows]
