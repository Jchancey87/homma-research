-- =============================================================================
-- Migration: Alerts Feedback (Helpful / Noise rating & notes)
-- =============================================================================

BEGIN;

-- Add feedback columns to screener_alerts
ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS feedback_score VARCHAR(10) DEFAULT NULL;
ALTER TABLE public.screener_alerts ADD COLUMN IF NOT EXISTS feedback_notes TEXT DEFAULT NULL;

-- Add feedback columns to screener_alerts_archive
ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS feedback_score VARCHAR(10) DEFAULT NULL;
ALTER TABLE public.screener_alerts_archive ADD COLUMN IF NOT EXISTS feedback_notes TEXT DEFAULT NULL;

COMMIT;
