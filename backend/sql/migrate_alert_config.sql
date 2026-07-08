-- Migration: Create alert_configs table and insert default configurations
BEGIN;

CREATE TABLE IF NOT EXISTS public.alert_configs (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default configurations if key 'global_config' doesn't exist
INSERT INTO public.alert_configs (key, value)
VALUES (
    'global_config',
    '{
        "alert_min_pct_increase": 0.03,
        "alert_min_time_cooldown_mins": 2,
        "watchlist_presence_weight": 20,
        "watchlist_priority_tag_weight": 20,
        "catalyst_confirmed_weight": 25,
        "catalyst_speculative_weight": 15,
        "catalyst_technical_weight": 10,
        "float_micro_weight": 20,
        "float_low_weight": 15,
        "float_mid_weight": 10,
        "session_regular_weight": 15,
        "session_pre_weight": 10,
        "session_post_weight": 5,
        "alert_high_weight": 15,
        "alert_mid_weight": 10,
        "alert_low_weight": 5,
        "rvol_high_weight": 15,
        "rvol_mid_weight": 10,
        "rvol_low_weight": 5,
        "tier_1_threshold": 75,
        "tier_2_threshold": 45,
        "enabled_alerts": {
            "VOLATILITY_HALT": true,
            "VOLATILITY_RESUME": true,
            "HOD_BREAKOUT": true,
            "VOLUME_SPIKE": true,
            "PREV_DAY_BREAKOUT": true,
            "VWAP_CROSSOVER": true,
            "VWAP_BOUNCE": true,
            "RUNNING_UP": true,
            "BULL_FLAG": true,
            "VWAP_RECLAIM": true,
            "MULTI_TF_CONFLUENCE": true,
            "HALT_RESUME_MOMENTUM": true
        }
    }'::jsonb
)
ON CONFLICT (key) DO NOTHING;

COMMIT;
