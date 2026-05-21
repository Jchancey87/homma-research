import pandas as pd
from database import get_connection

FLOAT_BINS   = [0, 5e6, 10e6, 50e6, float('inf')]
FLOAT_LABELS = ['<5M', '5–10M', '10–50M', '50M+']

RVOL_BINS    = [0, 3, 5, 10, float('inf')]
RVOL_LABELS  = ['<3x', '3–5x', '5–10x', '10x+']


def build_heatmap_spec(
    cutoff_date: str | None = None,
    exact_date:  str | None = None,
    min_gap:     float | None = None,
    max_float_m: float | None = None,
    min_rvol:    float | None = None,
    sector:      str | None = None
) -> dict:
    """
    Query daily_gainers, bucket float and RVOL, compute average gap_pct per cell.
    Returns a Plotly-compatible figure dict ready to JSON-serialize.
    """
    query  = ["SELECT float_shares, rvol_15m, gap_pct FROM daily_gainers", "WHERE float_shares IS NOT NULL AND rvol_15m IS NOT NULL AND gap_pct IS NOT NULL"]
    params = []

    if exact_date:
        query.append("AND date = %s")
        params.append(exact_date)
    elif cutoff_date:
        query.append("AND date >= %s")
        params.append(cutoff_date)

    if min_gap:
        query.append("AND gap_pct >= %s")
        params.append(min_gap)
    if max_float_m:
        query.append("AND float_shares <= %s")
        params.append(max_float_m * 1_000_000)
    if min_rvol:
        query.append("AND rvol_15m >= %s")
        params.append(min_rvol)
    if sector:
        query.append("AND sector = %s")
        params.append(sector)

    full_query = " ".join(query)
    with get_connection() as conn:
        rows = conn.execute(full_query, params).fetchall()

    if not rows:
        return _empty_heatmap()

    df = pd.DataFrame([dict(r) for r in rows])
    df['float_bucket'] = pd.cut(df['float_shares'], bins=FLOAT_BINS, labels=FLOAT_LABELS, right=False)
    df['rvol_bucket']  = pd.cut(df['rvol_15m'],     bins=RVOL_BINS,  labels=RVOL_LABELS,  right=False)

    pivot = (
        df.groupby(['rvol_bucket', 'float_bucket'], observed=True)['gap_pct']
        .agg(['mean', 'count'])
        .unstack()
    )

    mean_pivot  = pivot['mean'].reindex(index=RVOL_LABELS[::-1], columns=FLOAT_LABELS)
    count_pivot = pivot['count'].reindex(index=RVOL_LABELS[::-1], columns=FLOAT_LABELS)

    z     = mean_pivot.astype(object).where(mean_pivot.notnull(), None).values.tolist()
    count = count_pivot.fillna(0).astype(int).values.tolist()
    x     = FLOAT_LABELS
    y     = RVOL_LABELS[::-1]

    # Build hover text with count + avg gap
    hover_text = []
    for ri, row_y in enumerate(y):
        row_texts = []
        for ci, col_x in enumerate(x):
            val = z[ri][ci]
            cnt = count[ri][ci]
            if val is None or (isinstance(val, float) and val != val):
                row_texts.append(f'Float: {col_x}<br>RVOL: {row_y}<br>No data')
            else:
                row_texts.append(
                    f'<b>Float:</b> {col_x}<br>'
                    f'<b>RVOL:</b> {row_y}<br>'
                    f'<b>Avg Gap:</b> +{val:.1f}%<br>'
                    f'<b>Samples:</b> {int(cnt) if cnt == cnt else 0}'
                )
        hover_text.append(row_texts)

    return {
        'data': [{
            'type':         'heatmap',
            'z':            z,
            'x':            x,
            'y':            y,
            'text':         hover_text,
            'hoverinfo':    'text',
            'colorscale':   [
                [0.00, '#0f2027'],   # very dark teal-black (low gap)
                [0.20, '#1a3a4a'],   # dark slate
                [0.40, '#1a5c4e'],   # dark emerald
                [0.60, '#16a085'],   # medium teal
                [0.80, '#22d3a7'],   # bright emerald
                [1.00, '#86efcf'],   # pale mint (highest gap)
            ],
            'colorbar': {
                'title':       {'text': 'Avg Gap %', 'font': {'color': '#94a3b8', 'size': 11}},
                'tickfont':    {'color': '#94a3b8', 'size': 10},
                'outlinecolor': 'rgba(0,0,0,0)',
                'bgcolor':     'rgba(0,0,0,0)',
                'thickness':   14,
                'len':         0.85,
            },
            'xgap': 3,
            'ygap': 3,
            'zsmooth': False,
        }],
        'layout': {
            'title': None,
            'xaxis': {
                'title':     {'text': 'Float Size', 'font': {'color': '#64748b', 'size': 11}},
                'tickfont':  {'color': '#94a3b8', 'size': 11},
                'gridcolor': 'rgba(0,0,0,0)',
                'linecolor': 'rgba(0,0,0,0)',
                'showline':  False,
            },
            'yaxis': {
                'title':     {'text': 'RVOL at 15-min', 'font': {'color': '#64748b', 'size': 11}},
                'tickfont':  {'color': '#94a3b8', 'size': 11},
                'gridcolor': 'rgba(0,0,0,0)',
                'linecolor': 'rgba(0,0,0,0)',
                'showline':  False,
            },
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor':  'rgba(0,0,0,0)',
            'font':          {'color': '#94a3b8', 'family': 'Inter, system-ui, sans-serif', 'size': 11},
            'margin':        {'t': 10, 'b': 50, 'l': 65, 'r': 10},
        },
    }


def _empty_heatmap() -> dict:
    return {
        'data':   [{'type': 'heatmap', 'z': [], 'x': FLOAT_LABELS, 'y': RVOL_LABELS}],
        'layout': {'title': None, 'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': 'rgba(0,0,0,0)'},
    }


def get_sector_spec(
    cutoff_date: str | None = None,
    exact_date:  str | None = None,
    min_gap:     float | None = None,
    max_float_m: float | None = None,
    min_rvol:    float | None = None,
    sector:      str | None = None
) -> dict:
    """
    Return a Plotly horizontal bar chart of average gap % per sector.
    """
    query  = ["SELECT sector, gap_pct FROM daily_gainers", "WHERE sector IS NOT NULL AND gap_pct IS NOT NULL AND sector != ''"]
    params = []

    if exact_date:
        query.append("AND date = %s")
        params.append(exact_date)
    elif cutoff_date:
        query.append("AND date >= %s")
        params.append(cutoff_date)

    if min_gap:
        query.append("AND gap_pct >= %s")
        params.append(min_gap)
    if max_float_m:
        query.append("AND float_shares <= %s")
        params.append(max_float_m * 1_000_000)
    if min_rvol:
        query.append("AND rvol_15m >= %s")
        params.append(min_rvol)
    if sector:
        query.append("AND sector = %s")
        params.append(sector)

    full_query = " ".join(query)
    with get_connection() as conn:
        rows = conn.execute(full_query, params).fetchall()

    if not rows:
        return _empty_sector()

    import pandas as pd
    df = pd.DataFrame([dict(r) for r in rows])

    agg = (
        df.groupby('sector')['gap_pct']
        .agg(avg_gap='mean', count='count')
        .reset_index()
        .sort_values('avg_gap', ascending=True)   # ascending → highest on top in horizontal bar
    )

    sectors  = agg['sector'].tolist()
    avg_gaps = [round(v, 1) for v in agg['avg_gap'].tolist()]
    counts   = agg['count'].tolist()

    # Map avg_gap to a shade from the same emerald palette
    max_gap = max(avg_gaps) if avg_gaps else 1.0
    bar_colors = [
        _gap_to_color(g / max_gap) for g in avg_gaps
    ]

    hover = [
        f'<b>{s}</b><br>Avg Gap: +{g:.1f}%<br>Samples: {c}'
        for s, g, c in zip(sectors, avg_gaps, counts)
    ]

    return {
        'data': [{
            'type':        'bar',
            'orientation': 'h',
            'x':           avg_gaps,
            'y':           sectors,
            'text':        [f'+{g:.1f}%' for g in avg_gaps],
            'textposition': 'outside',
            'textfont':    {'color': '#94a3b8', 'size': 10},
            'hovertext':   hover,
            'hoverinfo':   'text',
            'marker': {
                'color':     bar_colors,
                'line':      {'color': 'rgba(0,0,0,0)', 'width': 0},
            },
        }],
        'layout': {
            'title': None,
            'xaxis': {
                'title':    {'text': 'Avg Gap %', 'font': {'color': '#64748b', 'size': 11}},
                'tickfont': {'color': '#94a3b8', 'size': 10},
                'gridcolor': 'rgba(255,255,255,0.05)',
                'linecolor': 'rgba(0,0,0,0)',
                'ticksuffix': '%',
                'zeroline': False,
            },
            'yaxis': {
                'tickfont':  {'color': '#94a3b8', 'size': 10},
                'gridcolor': 'rgba(0,0,0,0)',
                'linecolor': 'rgba(0,0,0,0)',
                'automargin': True,
            },
            'paper_bgcolor': 'rgba(0,0,0,0)',
            'plot_bgcolor':  'rgba(0,0,0,0)',
            'font':          {'color': '#94a3b8', 'family': 'Inter, system-ui, sans-serif', 'size': 11},
            'margin':        {'t': 8, 'b': 50, 'l': 10, 'r': 60},
            'bargap':        0.28,
        },
    }


def _gap_to_color(ratio: float) -> str:
    """Map a 0–1 ratio to the emerald gradient used in the heatmap."""
    stops = [
        (0.00, (15,  32,  39)),
        (0.25, (26,  58,  74)),
        (0.50, (26,  92,  78)),
        (0.75, (22, 163, 133)),
        (1.00, (34, 211, 167)),
    ]
    ratio = max(0.0, min(1.0, ratio))
    for i in range(len(stops) - 1):
        lo_r, lo_c = stops[i]
        hi_r, hi_c = stops[i + 1]
        if ratio <= hi_r:
            t = (ratio - lo_r) / (hi_r - lo_r)
            r = int(lo_c[0] + t * (hi_c[0] - lo_c[0]))
            g = int(lo_c[1] + t * (hi_c[1] - lo_c[1]))
            b = int(lo_c[2] + t * (hi_c[2] - lo_c[2]))
            return f'rgba({r},{g},{b},0.85)'
    return 'rgba(34,211,167,0.85)'


def _empty_sector() -> dict:
    return {
        'data':   [{'type': 'bar', 'x': [], 'y': [], 'orientation': 'h'}],
        'layout': {'paper_bgcolor': 'rgba(0,0,0,0)', 'plot_bgcolor': 'rgba(0,0,0,0)'},
    }
