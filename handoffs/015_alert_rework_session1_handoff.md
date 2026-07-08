# Handoff: Alert System Overhaul — Session 1 (Quota Cutoff)

**Date**: 2026-07-08  
**Working directory**: `~/teamwork_projects/alert_system_rework`  
**Reference codebase (read-only)**: `/home/jackc/projects/homma-research`  
**Quota cutoff**: mid-Milestone 3. Resume immediately from Milestone 3.

---

## Milestone Status

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Initialize workspace & run 266 baseline tests | ✅ Complete |
| 2 | Fix 5 critical bugs (verified by reviewer agent) | ✅ Complete |
| 3 | Core engine — confluence scoring + watchlist gate removal | 🔄 Design done, implementation not started |
| 4 | 5 new alert types (RUNNING_UP, BULL_FLAG, VWAP_RECLAIM, MULTI_TF_CONFLUENCE, HALT_RESUME_MOMENTUM) | ⬜ Not started |
| 5 | Admin UI + dynamic config (no-restart threshold tuning) | ⬜ Not started |
| 6 | Strategy labels + context-rich alerts + distinct audio | ⬜ Not started |
| 7 | Final verification & hardening (all tests pass + new tests) | ⬜ Not started |

---

## What Was Done (Milestones 1–2 — Code Changes)

### Files Modified in the Workspace

#### 1. `momentum_screener/schwab/stream_client.py`

**Bug fixes applied:**

- **`gap_pct` fix** (line ~560): `prev_close = fund.get('low_52wk')` → `prev_close = fund.get('yesterday_close')`
- **`yesterday_close` loaded in `load_fundamentals()`**: SQL query now also fetches `close` from `price_history_daily`; cached as `yesterday_closes = {r['symbol']: r['close'] for r in daily_rows}` and stored as `fundamentals_cache[sym]['yesterday_close']`.
- **`short_int_float` loaded and populated**: `stock_fundamentals` SQL query now includes `short_int_float`; value cached as `fund['short_int_float']`; passed into `save_alert_to_db()` and inserted into `screener_alerts`.
- **`ALERT_MIN_PCT_INCREASE` wired**: Added `ALERT_MIN_PCT_INCREASE = Config.ALERT_MIN_PCT_INCREASE` module-level constant (with `os.getenv` fallback). `check_and_fire_alert()` now uses `min_pct = ALERT_MIN_PCT_INCREASE` instead of `0.03`.
- **`save_alert_to_db()` updated**: Now uses `RETURNING id, alert_time` and returns the row. Passes `short_int_float` as parameter. Signature: `save_alert_to_db(symbol, price, volume, rvol, gap_pct, float_shares, alert_type, short_int_float=None)`.
- **`sent` column tracking**: `check_and_fire_alert()` stores returned `alert_db_id` and `alert_db_time` into the Redis pub/sub payload dict.

> ⚠️ **Important**: The `explorer_confluence` agent had DESIGNED (but NOT yet implemented) a `calculate_confluence_score()` method and watchlist gate removal. Those designs are NOT in the code yet. The diff shows them as lines removed from the reference. The workspace file is a clean version without the confluence scoring method. Milestone 3 code is still needed.

#### 2. `backend/fastapi_app/tasks/alerts.py`

- **`sent` column update**: After successful Telegram delivery, now calls `UPDATE screener_alerts SET sent = TRUE WHERE id = %s AND alert_time = %s` using `alert_db_id` and `alert_db_time` from the alert payload.
- **Removed**: `priority_score` and `priority_tier` fields from `_format_alert_message()`. These will be re-added as part of Milestone 3 (confluence engine).

#### 3. `frontend/components/LiveGainers.tsx`

- **Price filter unified**: Changed filter from `price >= 2.00 && price <= 25.00` to `price >= 1.00 && price <= 30.00` to match backend.

#### 4. `backend/tests/test_bugs_fixes.py` (NEW)

New test file with 5 unit tests covering all bug fixes:
- `test_load_fundamentals_queries_close_and_short_int_float`
- `test_evaluate_and_fire_alert_computes_gap_pct_with_yesterday_close`
- `test_send_telegram_alert_task_updates_sent_status`
- `test_alert_min_pct_increase_wired_to_price_buckets`
- `test_save_alert_to_db_inserts_short_int_float`

---

## What To Do Next (Milestones 3–7)

### Milestone 3: Core Engine — Confluence Scoring + Watchlist Gate Removal

**In `momentum_screener/schwab/stream_client.py`:**

**Step A — Remove watchlist gate from `check_and_fire_alert()`:**
Find and delete these lines:
```python
# Only trigger alerts if stock is in the user's watchlist
if symbol not in self.watchlist_symbols:
    logger.debug(f"Skipping {alert_type} for {symbol} because it is not in watchlist")
    return False
```

**Step B — Add `calculate_confluence_score()` method to `SchwabStreamer` class:**

```python
def calculate_confluence_score(self, symbol: str, alert_type: str, rvol: float = 0.0, now_et=None) -> tuple[int, str]:
    """Compute confluence score (0-100). Returns (score, tier)."""
    if now_et is None:
        now_et = datetime.now(pytz.timezone('America/New_York'))
    score = 0

    # 1. Watchlist presence bonus (NOT a gate — just a score boost)
    if symbol in self.watchlist_symbols:
        score += 20

    # 2. Catalyst tag quality
    cat_tag = self.catalyst_tags.get(symbol)
    if cat_tag == 'Confirmed Catalyst':
        score += 25
    elif cat_tag == 'Speculative':
        score += 15
    elif cat_tag == 'Technical / No News':
        score += 10

    # 3. Float category
    fund = self.fundamentals_cache.get(symbol, {})
    float_cat = fund.get('float_category')
    if float_cat == 'Micro-Float':
        score += 20
    elif float_cat == 'Low-Float':
        score += 15
    elif float_cat == 'Mid-Float':
        score += 10

    # 4. Market session
    mkt_start = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    mkt_end   = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    if mkt_start <= now_et <= mkt_end:
        score += 15   # Regular session
    elif now_et < mkt_start:
        score += 10   # Pre-market
    else:
        score += 5    # Post-market

    # 5. Alert type weight
    if alert_type in ('HOD_BREAKOUT', 'VWAP_CROSSOVER', 'PREV_DAY_BREAKOUT',
                      'RUNNING_UP', 'BULL_FLAG', 'VWAP_RECLAIM'):
        score += 15
    elif alert_type in ('VOLUME_SPIKE', 'MULTI_TF_CONFLUENCE'):
        score += 10
    elif alert_type in ('VOLATILITY_HALT', 'VOLATILITY_RESUME', 'HALT_RESUME_MOMENTUM'):
        score += 5

    # 6. RVOL strength
    if rvol >= 5.0:
        score += 15
    elif rvol >= 3.0:
        score += 10
    elif rvol >= 1.5:
        score += 5

    # Tier assignment
    if score >= 75:
        tier = 'Tier 1'
    elif score >= 45:
        tier = 'Tier 2'
    else:
        tier = 'Tier 3'

    return score, tier
```

**Step C — Wire `calculate_confluence_score()` back into `check_and_fire_alert()`:**

After removing the watchlist gate and before saving to DB:
```python
priority_score, priority_tier = self.calculate_confluence_score(
    symbol, alert_type, rvol=rvol
)
```
Pass these into the Redis payload and `save_alert_to_db()`. Also restore `priority_score` and `priority_tier` fields in the Redis pub/sub dict.

**Step D — Restore catalyst_tags loading in `load_watchlist()`:**

The bug-fix agent removed the `catalyst_tags` dict and its loading query. Re-add:
```python
self.catalyst_tags = {}
...
today_date = datetime.now(pytz.timezone('US/Eastern')).date()
async with self.db_pool.acquire() as conn:
    rows_pump = await conn.fetch(
        "SELECT ticker, catalyst_tag FROM pump_classifications WHERE date = $1",
        today_date
    )
    for r in rows_pump:
        self.catalyst_tags[r['ticker']] = r['catalyst_tag']
```

**Step E — Restore `priority_score` and `priority_tier` in `tasks/alerts.py`:**

Re-add the priority line to `_format_alert_message()`:
```python
priority_score = alert_data.get("priority_score", 0)
priority_tier  = alert_data.get("priority_tier", "Tier 3")
priority_line = f"- *Priority:* {priority_tier} (Score: {priority_score})\n"
```
And add `{priority_line}` back into the formatted message body.

**Step F — Tier-based delivery gating:**

In `check_and_fire_alert()` after computing tier:
```python
# Tier 3: log to DB only, no Telegram, no SSE push
if priority_tier == 'Tier 3':
    await self.save_alert_to_db(...)
    return True  # saved but not dispatched

# Tier 2: SSE push only (no Telegram)
send_telegram = (priority_tier == 'Tier 1')
```

---

### Milestone 4: Five New Alert Types

Add to `stream_client.py` in `evaluate_and_fire_alert()`:

**1. `RUNNING_UP`**: Fire when price rises >= 3% from lowest close in last 5 candles, current candle volume >= 1.5x the 20-bar avg, NOT already at HOD.

**2. `BULL_FLAG`**: Detect 3-candle consolidation (declining volume, price within 2% range) after strong move up (>= 5% in 5 candles). Fire when next candle breaks consolidation high with volume.

**3. `VWAP_RECLAIM`**: Re-enable the commented-out `VWAP_BOUNCE` block (~line 587-618 in reference `/home/jackc/projects/homma-research/momentum_screener/schwab/stream_client.py`). Fire when `last_price` crosses above `vwap` with `rvol >= 1.5` and VWAP slope is positive. Remove the comment-out guard.

**4. `MULTI_TF_CONFLUENCE`**: If last 5-min candle is bullish (close > open >= 1%) AND a 1-min HOD_BREAKOUT fired for same symbol within past 60s, fire `MULTI_TF_CONFLUENCE`.

**5. `HALT_RESUME_MOMENTUM`**: In `VOLATILITY_RESUME` handler, after 30s check if price is >= 1% above resume price with volume >= 1.5x avg, fire `HALT_RESUME_MOMENTUM`.

For each new type:
- Add to `ALERT_TYPE_META` in `tasks/alerts.py`
- Add Journal marker (color + shape) in `frontend/app/alerts/page.tsx` (`alertTypeConfig` dict ~line 26)
- Integrate with cooldown system

---

### Milestone 5: Admin UI + Dynamic Config

**Backend — create these files:**

1. `backend/sql/migrate_alert_config.sql`:
```sql
CREATE TABLE IF NOT EXISTS alert_config (
    alert_type      VARCHAR(40) PRIMARY KEY,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    rvol_min        NUMERIC(6,2),
    volume_mult     NUMERIC(6,2),
    price_min       NUMERIC(8,2) DEFAULT 1.00,
    price_max       NUMERIC(8,2) DEFAULT 30.00,
    cooldown_mins   INTEGER DEFAULT 2,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_scoring_config (
    key             VARCHAR(60) PRIMARY KEY,
    value           NUMERIC(8,4) NOT NULL,
    description     TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO alert_config (alert_type) VALUES
  ('HOD_BREAKOUT'), ('VWAP_CROSSOVER'), ('PREV_DAY_BREAKOUT'),
  ('VOLUME_SPIKE'), ('VOLATILITY_HALT'), ('VOLATILITY_RESUME'),
  ('RUNNING_UP'), ('BULL_FLAG'), ('VWAP_RECLAIM'),
  ('MULTI_TF_CONFLUENCE'), ('HALT_RESUME_MOMENTUM')
ON CONFLICT DO NOTHING;

INSERT INTO alert_scoring_config (key, value, description) VALUES
  ('tier1_threshold', 75, 'Min score for Tier 1'),
  ('tier2_threshold', 45, 'Min score for Tier 2'),
  ('watchlist_boost', 20, 'Score bonus for watchlisted tickers'),
  ('confirmed_catalyst_bonus', 25, 'Score bonus for Confirmed Catalyst'),
  ('micro_float_bonus', 20, 'Score bonus for Micro-Float'),
  ('rvol_5x_bonus', 15, 'Score bonus for RVOL >= 5x')
ON CONFLICT DO NOTHING;
```

2. `backend/fastapi_app/db/alert_config.py` — async CRUD (asyncpg).
3. `backend/services/alert_config_service.py` — config cache with 30s TTL poll.
4. `backend/fastapi_app/routers/alert_config.py` — thin router (GET + PUT endpoints).
5. In `stream_client.py` — background 30s config poll loop (no restart needed).

**Frontend:**
- Create `frontend/app/alert-config/page.tsx` — toggles, sliders, scoring weights, reset button.
- Add "Alert Config" link to `frontend/components/NavBar.tsx`.

---

### Milestone 6: Strategy Labels + Distinct Audio

**Strategy Labels** — add to `check_and_fire_alert()` and include in Redis payload + Telegram:
```python
STRATEGY_LABELS = {
    'HOD_BREAKOUT':          'Gap and Go — HOD Break',
    'VWAP_CROSSOVER':        'VWAP Reclaim / Crossover',
    'PREV_DAY_BREAKOUT':     'Previous Day High Break',
    'VOLUME_SPIKE':          'Volume Surge',
    'VOLATILITY_HALT':       'Trading Halt',
    'VOLATILITY_RESUME':     'Halt Resume',
    'RUNNING_UP':            'Running Up — Momentum Surge',
    'BULL_FLAG':             'Bull Flag Breakout',
    'VWAP_RECLAIM':          'VWAP Reclaim',
    'MULTI_TF_CONFLUENCE':   'Multi-Timeframe Confluence',
    'HALT_RESUME_MOMENTUM':  'Halt Resume Momentum Play',
}
```

**Context fields** to add to Telegram: VWAP distance %, HOD distance %, catalyst tag, suggested stop level.

**Distinct Audio** in `frontend/components/live-gainers/useAlertStream.ts`:
- Replace single `playChime()` with tier-specific functions via Web Audio API
- Tier 1: urgent double-beep (880Hz → 1320Hz, 0.15s each)
- Tier 2: single warm tone (660Hz, 0.3s)
- Tier 3: silent

---

### Milestone 7: Final Verification

1. `cd backend && /opt/trading-journal/backend/venv/bin/pytest -p no:anyio` — all tests pass
2. `cd frontend && npm run build` — builds successfully
3. No raw SQL in router files (Router Layer Rules)
4. Write final handoff `handoffs/016_alert_rework_complete.md`

---

## Key Architecture Decisions

| Decision | Detail |
|---|---|
| Watchlist gate | Removed as hard gate; +20 score boost instead |
| Tier 1 threshold | Score >= 75 (max 100) |
| Tier 2 threshold | Score 45–74 |
| Tier 3 threshold | Score < 45 — DB log only, no dispatch |
| Tier 1 delivery | Telegram + SSE toast + loud audio |
| Tier 2 delivery | SSE toast + subtle audio only |
| Tier 3 delivery | DB insert only, no notification |
| Config hot-reload | Streamer polls DB every 30s |
| Audio | Web Audio API, no external files |
| DB migrations | Raw SQL files only |
| Router Layer Rules | All SQL in `db/` modules, all logic in `services/` |
| Test runner | `/opt/trading-journal/backend/venv/bin/pytest -p no:anyio` |

---

## Files Needing Creation

| File | Purpose |
|---|---|
| `backend/sql/migrate_alert_config.sql` | DB schema for admin config |
| `backend/fastapi_app/db/alert_config.py` | Async CRUD for alert_config tables |
| `backend/services/alert_config_service.py` | Config cache + business logic |
| `backend/fastapi_app/routers/alert_config.py` | Thin REST router |
| `frontend/app/alert-config/page.tsx` | Admin UI page |
| `backend/tests/test_confluence_engine.py` | Unit tests for scoring engine |
| `backend/tests/test_new_alert_types.py` | Unit tests for 5 new types |
| `backend/tests/test_alert_config.py` | CRUD + API tests |
| `handoffs/016_alert_rework_complete.md` | Final handoff after Milestone 7 |
