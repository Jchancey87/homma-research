-- =============================================================================
-- Migration: Alerts Cooldown and Throttling logic
-- Phase 1 of the Real-Time Breakout Alerts & Notifications plan
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS alerts;

CREATE TABLE IF NOT EXISTS alerts.ticker_cooldowns (
    ticker VARCHAR(12) PRIMARY KEY,
    last_triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    highest_trigger_price NUMERIC(12, 4) NOT NULL,
    lockout_expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ticker_cooldowns_expiry 
    ON alerts.ticker_cooldowns (ticker, lockout_expires_at);

CREATE OR REPLACE FUNCTION alerts.should_fire_alert(
    p_ticker VARCHAR,
    p_price NUMERIC,
    p_cooldown_interval INTERVAL,
    p_macro_window INTERVAL,
    p_macro_threshold INT
) RETURNS BOOLEAN AS $$
DECLARE
    v_macro_count INTEGER;
    v_expiry TIMESTAMP WITH TIME ZONE;
    v_highest_price NUMERIC(12, 4);
BEGIN
    -- 1. Macro Market Throttle: Count distinct symbols in last macro window
    SELECT COUNT(DISTINCT symbol)
    INTO v_macro_count
    FROM public.screener_alerts
    WHERE alert_time >= NOW() - p_macro_window;

    IF v_macro_count >= p_macro_threshold THEN
        RETURN FALSE;
    END IF;

    -- 2. Ticker Cooldown Check
    SELECT lockout_expires_at, highest_trigger_price
    INTO v_expiry, v_highest_price
    FROM alerts.ticker_cooldowns
    WHERE ticker = p_ticker;

    -- If lockout hasn't expired and the current price doesn't exceed the highest trigger price, block the alert.
    IF FOUND AND NOW() < v_expiry AND p_price <= v_highest_price THEN
        RETURN FALSE;
    END IF;

    -- 3. Upsert Cooldown record and allow alert to fire
    INSERT INTO alerts.ticker_cooldowns (ticker, last_triggered_at, highest_trigger_price, lockout_expires_at)
    VALUES (p_ticker, NOW(), p_price, NOW() + p_cooldown_interval)
    ON CONFLICT (ticker) DO UPDATE
    SET last_triggered_at = EXCLUDED.last_triggered_at,
        highest_trigger_price = EXCLUDED.highest_trigger_price,
        lockout_expires_at = EXCLUDED.lockout_expires_at;

    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

COMMIT;
