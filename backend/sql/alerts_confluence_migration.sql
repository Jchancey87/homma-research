-- Migration: Add Confluence Engine priority score and priority tier to screener_alerts and screener_alerts_archive, and create alert_configs table.
BEGIN;

ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0;
ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(20) DEFAULT 'Tier 3';

ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0;
ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS priority_tier VARCHAR(20) DEFAULT 'Tier 3';

CREATE TABLE IF NOT EXISTS public.alert_configs (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMIT;
