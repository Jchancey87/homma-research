## 2026-07-08T13:22:54Z
Objective: Implement Confluence Engine and remove watchlist gate.
Details:
1. Write SQL migration backend/sql/alerts_confluence_migration.sql:
   - Add public.screener_alerts: priority_score INTEGER DEFAULT 0, priority_tier VARCHAR(20) DEFAULT 'Tier 3'.
   - Add public.screener_alerts_archive: priority_score INTEGER DEFAULT 0, priority_tier VARCHAR(20) DEFAULT 'Tier 3'.
   - Create public.alert_configs: key VARCHAR(100) PRIMARY KEY, value JSONB NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW().
2. Execute migration using psql and DATABASE_URL env var.
3. Update stream_client.py:
   - In get_candidate_symbols: Fetch watchlist ticker and tags. Store in self.watchlist_tags dict. Cache today's pump_classifications catalyst tags in self.catalyst_tags dict.
   - Remove watchlist check gate symbol not in self.watchlist_symbols.
   - In check_and_fire_alert: Calculate composite score (watchlist presence, priority tag, catalyst tag, float size, market session, alert type). Determine priority_tier (Tier 1: >=70, Tier 2: 40-69, Tier 3: <40).
   - In save_alert_to_db: Insert priority_score and priority_tier.
   - In alert_payload: Include priority_score, priority_tier, and strategy_label.
4. Update tasks/alerts.py: Add priority badge/info to Telegram message formatting.
5. Write unit tests in backend/tests/test_confluence.py verifying scoring engine, watchlist boost, gate bypass, DB save.
6. Run all pytest tests.
