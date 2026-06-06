-- =============================================================================
-- Migration: Support alert_type in ticker cooldowns and return suppression reasons
-- =============================================================================

BEGIN;

DROP TABLE IF EXISTS alerts.ticker_cooldowns CASCADE;

CREATE TABLE alerts.ticker_cooldowns (
    ticker VARCHAR(12) NOT NULL,
    alert_type VARCHAR(30) NOT NULL,
    last_triggered_at TIMESTAMP WITH TIME ZONE NOT NULL,
    highest_trigger_price NUMERIC(12, 4) NOT NULL,
    lockout_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (ticker, alert_type)
);

CREATE INDEX idx_ticker_cooldowns_expiry 
    ON alerts.ticker_cooldowns (ticker, alert_type, lockout_expires_at);

DROP FUNCTION IF EXISTS alerts.should_fire_alert(VARCHAR, NUMERIC, INTERVAL, INTERVAL, INT, NUMERIC, INTERVAL);
DROP FUNCTION IF EXISTS alerts.should_fire_alert(VARCHAR, VARCHAR, NUMERIC, INTERVAL, INTERVAL, INT, NUMERIC, INTERVAL);
DROP FUNCTION IF EXISTS alerts.should_fire_alert(VARCHAR, VARCHAR, NUMERIC, INTERVAL, INTERVAL, INT, NUMERIC, INTERVAL, VARCHAR);

CREATE OR REPLACE FUNCTION alerts.should_fire_alert(
    p_ticker VARCHAR,
    p_alert_type VARCHAR,
    p_price NUMERIC,
    p_cooldown_interval INTERVAL,
    p_macro_window INTERVAL,
    p_macro_threshold INT,
    p_min_price_increase NUMERIC DEFAULT 0.03,
    p_min_time_cooldown INTERVAL DEFAULT INTERVAL '2 minutes',
    p_threshold_mode VARCHAR DEFAULT 'percent'
) RETURNS VARCHAR AS $$
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
        RETURN 'MACRO_THROTTLED';
    END IF;

    -- 2. Ticker and Alert Type Cooldown Check
    SELECT lockout_expires_at, highest_trigger_price, last_triggered_at
    INTO v_expiry, v_highest_price, v_last_triggered_at
    FROM alerts.ticker_cooldowns
    WHERE ticker = p_ticker AND alert_type = p_alert_type;

    -- If lockout hasn't expired:
    IF FOUND AND NOW() < v_expiry THEN
        -- Check if minimum time cooldown has elapsed since the last trigger
        IF NOW() < v_last_triggered_at + p_min_time_cooldown THEN
            RETURN 'COOLDOWN_ACTIVE';
        END IF;

        -- Check price threshold depending on mode (percent vs absolute)
        IF p_threshold_mode = 'absolute' THEN
            IF p_price < v_highest_price + p_min_price_increase THEN
                RETURN 'PRICE_INCREASE_INSUFFICIENT';
            END IF;
        ELSE -- 'percent' mode
            IF p_price < v_highest_price * (1.0 + p_min_price_increase) THEN
                RETURN 'PRICE_INCREASE_INSUFFICIENT';
            END IF;
        END IF;
    END IF;

    -- 3. Upsert Cooldown record and allow alert to fire
    INSERT INTO alerts.ticker_cooldowns (ticker, alert_type, last_triggered_at, highest_trigger_price, lockout_expires_at)
    VALUES (p_ticker, p_alert_type, NOW(), p_price, NOW() + p_cooldown_interval)
    ON CONFLICT (ticker, alert_type) DO UPDATE
    SET last_triggered_at = EXCLUDED.last_triggered_at,
        highest_trigger_price = EXCLUDED.highest_trigger_price,
        lockout_expires_at = EXCLUDED.lockout_expires_at;

    RETURN 'OK';
END;
$$ LANGUAGE plpgsql;

COMMIT;
