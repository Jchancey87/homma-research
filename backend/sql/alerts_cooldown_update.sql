-- =============================================================================
-- Migration: Update alerts.should_fire_alert to implement a percentage-based
-- price increase and minimum time cooldown criteria during active lockout.
-- =============================================================================

BEGIN;

DROP FUNCTION IF EXISTS alerts.should_fire_alert(VARCHAR, NUMERIC, INTERVAL, INTERVAL, INT);

CREATE OR REPLACE FUNCTION alerts.should_fire_alert(
    p_ticker VARCHAR,
    p_price NUMERIC,
    p_cooldown_interval INTERVAL,
    p_macro_window INTERVAL,
    p_macro_threshold INT,
    p_min_pct_increase NUMERIC DEFAULT 0.03,
    p_min_time_cooldown INTERVAL DEFAULT INTERVAL '2 minutes'
) RETURNS BOOLEAN AS $$
DECLARE
    v_macro_count INTEGER;
    v_expiry TIMESTAMP WITH TIME ZONE;
    v_highest_price NUMERIC(12, 4);
    v_last_triggered_at TIMESTAMP WITH TIME ZONE;
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
    SELECT lockout_expires_at, highest_trigger_price, last_triggered_at
    INTO v_expiry, v_highest_price, v_last_triggered_at
    FROM alerts.ticker_cooldowns
    WHERE ticker = p_ticker;

    -- If lockout hasn't expired:
    -- Only allow the alert to fire if the price is at least p_min_pct_increase (default 3%) higher
    -- than the previous highest trigger price AND at least p_min_time_cooldown (default 2 mins) has passed.
    IF FOUND AND NOW() < v_expiry THEN
        IF p_price >= v_highest_price * (1.0 + p_min_pct_increase) 
           AND NOW() >= v_last_triggered_at + p_min_time_cooldown THEN
            -- Meets criteria, allow to fire
            NULL;
        ELSE
            RETURN FALSE;
        END IF;
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
