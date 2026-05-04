from database import get_connection


def get_archetype_stats() -> list[dict]:
    """
    For each unique pattern tag, compute: count, avg_gain, avg_float_m, avg_rvol, avg_cleanliness.
    Returns list of dicts sorted by count desc.

    Queries the chart_tags junction table instead of parsing JSON strings, which
    fixes the previous bug where ["gap","low-float"] and ["low-float","gap"] were
    counted as separate archetypes.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                ct.tag,
                COUNT(DISTINCT ct.chart_id)          AS count,
                AVG(cc.cleanliness_score)             AS avg_cleanliness,
                AVG(dg.gap_pct)                       AS avg_gap_pct,
                AVG(dg.float_shares / 1e6)            AS avg_float_m,
                AVG(dg.rvol_15m)                      AS avg_rvol
            FROM chart_tags ct
            JOIN chart_captures cc ON cc.id = ct.chart_id
            LEFT JOIN daily_gainers dg
                   ON dg.ticker = cc.ticker AND dg.date = cc.capture_date
            GROUP BY ct.tag
            ORDER BY count DESC
            """
        ).fetchall()

    results = []
    for row in rows:
        results.append({
            'tag':             row['tag'],
            'count':           row['count'],
            'avg_gap_pct':     round(row['avg_gap_pct'],    2) if row['avg_gap_pct']    is not None else None,
            'avg_float_m':     round(row['avg_float_m'],    2) if row['avg_float_m']    is not None else None,
            'avg_rvol':        round(row['avg_rvol'],        2) if row['avg_rvol']       is not None else None,
            'avg_cleanliness': round(row['avg_cleanliness'], 2) if row['avg_cleanliness'] is not None else None,
        })

    return results
