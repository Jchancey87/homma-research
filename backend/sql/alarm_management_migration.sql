-- M1: Alarm metrics rollup table
CREATE TABLE IF NOT EXISTS alerts.alarm_metrics (
    id            SERIAL PRIMARY KEY,
    metric_date   DATE NOT NULL,
    metric_hour   SMALLINT,               -- NULL = daily rollup, 0-23 = hourly
    total_alarms  INT NOT NULL DEFAULT 0,
    tier1_count   INT NOT NULL DEFAULT 0,
    tier2_count   INT NOT NULL DEFAULT 0,
    tier3_count   INT NOT NULL DEFAULT 0,
    unique_tickers INT NOT NULL DEFAULT 0,
    chattering_count INT NOT NULL DEFAULT 0,  -- alarms that fired >3x in 1 min
    peak_10min_rate  INT,                     -- max alarms in any 10-min window
    noise_count   INT NOT NULL DEFAULT 0,     -- feedback_score='noise'
    helpful_count INT NOT NULL DEFAULT 0,     -- feedback_score='helpful'
    snr_pct       NUMERIC(5,1),               -- signal-to-noise ratio
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(metric_date, metric_hour)
);

-- M2: Add suppressed_reason and group_id columns to screener_alerts and archive
ALTER TABLE screener_alerts ADD COLUMN IF NOT EXISTS suppressed_reason VARCHAR(50);
ALTER TABLE screener_alerts ADD COLUMN IF NOT EXISTS group_id UUID;
ALTER TABLE screener_alerts_archive ADD COLUMN IF NOT EXISTS suppressed_reason VARCHAR(50);
ALTER TABLE screener_alerts_archive ADD COLUMN IF NOT EXISTS group_id UUID;
