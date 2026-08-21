export interface Gainer {
  id: number
  date: string
  ticker: string
  gap_pct: number | null
  float_shares: number | null
  rvol_15m: number | null
  sector: string | null
  market_cap: number | null
  news_headline: string | null
  news_fresh: boolean | null
  close_price: number | null
  open_price: number | null
  high_price: number | null
  extended_change_pct: number | null
  low_price: number | null
  prev_close: number | null
  vwap: number | null
  dollar_volume: number | null
  close_location: number | null
  rs_vs_spy: number | null
  shares_outstanding: number | null
  avg_volume: number | null
  created_at: string
}

export interface ChartCapture {
  id: number
  ticker: string
  capture_date: string
  timeframe: string | null
  image_path: string
  setup_type: string | null
  cleanliness_score: number | null
  tags: string
  notes: string | null
  gemini_annotation: string | null
  gemini_image_path: string | null
  gemini_imported_at: string | null
  created_at: string
}

export interface LLMJob {
  id: string
  type: string
  status: 'pending' | 'running' | 'done' | 'error'
  input_ref: string | null
  output: string | null
  model_used: string | null
  created_at: string
  updated_at: string
}

export interface LatestGainersSummary {
  date: string | null
  total: number
  gainers: Array<Omit<Gainer, 'id' | 'date' | 'created_at' | 'market_cap'>>
}

export interface MTFInPlayItem {
  ticker: string
  company_name?: string
  sector?: string
  score: number
  tier: 'HIGH_CONVICTION' | 'IN_PLAY' | 'NORMAL'
  mtf_in_play: boolean
  high_conviction: boolean
  is_coincident: boolean
  price: number
  gap_pct?: number
  volume?: number
  rvol?: number
  rvol_1m?: number
  float_shares?: number | null
  float_category?: string
  vwap?: number
  vwap_dist_pct?: number
  sr_price: number | null
  sr_type: string
  sr_dist_pct?: number
  sr_dist_dollars?: number
  breakout_status?: string
  sparkline?: number[]
  daily_atr?: number
  five_min_atr?: number
  tier1_daily_count?: number
  tier2_5min_count?: number
  coincident_count?: number
  signals: string[]
}

export interface MTFFilters {
  min_price?: number
  max_price?: number
  min_rvol?: number
  max_float?: number | null
  min_score?: number
  coincident_only?: boolean
  sort_by?: string
  force_refresh?: boolean
}

export interface MTFScannerData {
  timestamp: string | null
  filters_applied?: MTFFilters
  total_scanned?: number
  total_in_play?: number
  in_play: MTFInPlayItem[]
}

export interface GainerRow {
  ticker: string
  gap_pct: number | null
  extended_change_pct: number | null
  float_shares: number | null
  rvol_15m: number | null
  sector: string | null
  news_headline: string | null
  news_fresh: boolean | null
  close_price: number | null
  open_price: number | null
  mom_2m: number | null
}

export interface GainerSummary {
  date: string | null
  total: number
  source: 'live' | 'db' | null
  gainers: GainerRow[]
}

export interface LiveGainerRow {
  ticker: string
  company_name?: string | null
  gap_pct: number
  last_price: number | null
  open_price: number | null
  prev_close: number | null
  volume: number | null
  rvol_15m: number | null
  float_shares: number | null
  sector: string | null
  market_cap: number | null
  spread_pct: number | null
  trade_time: number | null
  is_hod: boolean | null
  news_headline: string | null
  news_fresh: boolean | null
  sparkline_5d?: number[]
  sparkline_intraday?: number[]
  sparkline_1h?: number[]
  sma20?: number | null
  sma50?: number | null
  sma100?: number | null
  above_sma20?: boolean
  above_sma50?: boolean
  above_sma100?: boolean
  is_repeat_runner?: boolean
  is_follow_through?: boolean
  mom_2m?: number | null
  atr_hod?: number | null
  atr_sprd?: number | null
  atr_vwap?: number | null
  zen_v?: number | null
  ask?: number | null
  bid?: number | null
  high_price?: number | null
  low_price?: number | null
  catalyst?: string | null
  consec_red_1m?: number
  ema9_1m?: number | null
  ema9_dist_pct?: number | null
  next_psych_level?: number | null
  psych_dist_cents?: number | null
  volume_ratio?: number | null
  rvol_1m?: number | null
  rvol_10m?: number | null
  atr_14?: number | null
  ema50?: number | null
  ema200?: number | null
  high20d?: number | null
  nearest_resistance_name?: string | null
  nearest_resistance_val?: number | null
  nearest_resistance_dist?: number | null
  active_patterns?: string[]
  pattern_score?: number
}

export interface LiveGainerSnapshot {
  session: 'pre_market' | 'open' | 'after_hours' | 'closed'
  session_label: string
  fetched_at: string | null
  gainers: LiveGainerRow[]
  top_n: number
  cache_ttl_s: number
  redis_connected?: boolean
  fast_mode_active?: boolean
  streaming_symbols_count?: number
}

export interface TickerHistoryItem {
  ticker: string
  sector: string | null
  appearances: number
  last_seen: string
  first_seen: string
  avg_gap_pct: number | null
  avg_rvol: number | null
  avg_float_m: number | null
  max_gap_pct: number | null
  last_close: number | null
  last_market_cap: number | null
}

export interface TickerAppearance {
  id: number
  date: string
  ticker: string
  gap_pct: number | null
  float_shares: number | null
  rvol_15m: number | null
  sector: string | null
  news_headline: string | null
  news_fresh: boolean | null
  close_price: number | null
  open_price: number | null
}

export interface CachedReport {
  id: number
  ticker: string
  date: string | null
  report_type: string
  version: number
  model_used: string | null
  created_at: string
  expires_at: string | null
  output?: string
}

export interface WatchlistGroup {
  id: number
  name: string
  created_at: string
}

export interface WatchlistItem {
  id: number
  ticker: string
  sector: string | null
  notes: string | null
  tags: string
  added_at: string
  last_viewed_at: string | null
  group_id: number | null
  runway_months: number | null
  dilution_risk: string | null
  upcoming_catalyst: string | null
  catalyst_date: string | null
  price?: number | null
  change_pct?: number | null
  volume?: number | null
}

export interface ContinuationPick {
  id: number
  ticker: string
  date: string
  reason: string | null
  gap_pct: number | null
  float_shares: number | null
  rvol_15m: number | null
  sector: string | null
  rank: number
  is_active: boolean
  deactivated_at: string | null
  deactivated_reason: string | null
  created_at: string
  today_last?: number | null
  today_open?: number | null
  today_volume?: number | null
  today_change_pct?: number | null
  close_d0?: number | null
  d1_open?: number | null
  d1_high?: number | null
  d1_low?: number | null
  d1_close?: number | null
  d1_volume?: number | null
  d2_open?: number | null
  d2_high?: number | null
  d2_low?: number | null
  d2_close?: number | null
  d2_volume?: number | null
  d3_open?: number | null
  d3_high?: number | null
  d3_low?: number | null
  d3_close?: number | null
  d3_volume?: number | null
  market_cap?: number | null
  shares_outstanding?: number | null
  cash?: number | null
  net_income?: number | null
  operating_cash_flow?: number | null
  runway_months?: number | null
  dilution_risk?: string | null
  news_headline?: string | null
  news_fresh?: boolean | null
}

export interface ContinuationPerformanceSummary {
  total_picks: number
  win_rate: number
  super_win_rate: number
  avg_max_ext: number
  avg_d1_ret: number
  avg_d3_ret: number
}

export interface ContinuationPerformanceGroupRow {
  group_value: string
  count: number
  win_rate: number
  super_win_rate: number
  avg_max_ext: number
}

export interface ContinuationPerformanceData {
  summary: ContinuationPerformanceSummary
  groups: {
    float_category: ContinuationPerformanceGroupRow[]
    gap_category: ContinuationPerformanceGroupRow[]
    sector: ContinuationPerformanceGroupRow[]
    dilution_risk: ContinuationPerformanceGroupRow[]
    news_freshness: ContinuationPerformanceGroupRow[]
  }
}

export interface Observation {
  id: number
  ticker: string
  date: string
  title: string | null
  body: string
  sentiment: 'bullish' | 'bearish' | 'neutral'
  tags: string
  linked_chart_id: number | null
  created_at: string
  updated_at: string
}

export interface PipeScanResult {
  ticker: string
  anchor_date: string
  is_pipe: boolean
  filing_date: string | null
  filing_url: string | null
  security_type: string | null
  pricing_type: string | null
  proceeds_amount: number | null
  use_of_proceeds: string | null
  toxic_signals: string[]
  deal_score: number | null
  item_codes: string[]
}

export interface RepeatRunner {
  ticker: string
  appearances: number
  avg_gap_pct: number | null
  best_gap_pct: number | null
  last_seen: string
  first_seen: string
  avg_rvol: number | null
  avg_float_m: number | null
  sparkline_5d?: number[]
  sparkline_intraday?: number[]
  sparkline_1h?: number[]
  sma20?: number | null
  sma50?: number | null
  sma100?: number | null
  above_sma20?: boolean
  above_sma50?: boolean
  above_sma100?: boolean
  today_last?: number | null
  today_gap_pct?: number | null
}

export interface FloatBucket {
  bucket: string
  count: number
  avg_gap_pct: number | null
  best_gap_pct: number | null
}

export interface FollowThroughResult {
  ticker: string
  prev_date: string
  prev_gap: number | null
  prev_close: number | null
  today_open: number | null
  change_pct: number | null
  status: 'following' | 'fading' | 'flat' | 'no_data'
  float_shares?: number | null
  today_last?: number | null
  today_volume?: number | null
}

export interface SectorRotationItem {
  sector: string
  count: number
  avg_gap_pct: number | null
  last_avg_gap: number | null
  last_rank: number | null
  this_rank: number
  trend: 'up' | 'down' | 'flat' | 'new'
}

export interface IndexData {
  ticker: string
  price: number | null
  chg_pct: number | null
  volume: number | null
}

export interface MarketBreadthData {
  indices: Record<string, IndexData>
  vix: number | null
  bias: 'risk_on' | 'neutral' | 'risk_off' | 'unknown'
  fetched_at: string
  cache_ttl_s: number
}

export interface EconomicEvent {
  date: string
  time: string
  event: string | null
  country: string | null
  impact: 'high' | 'medium'
  actual: number | null
  estimate: number | null
  previous: number | null
}

export interface WatchlistPrice {
  price: number | null
  chg_pct: number | null
  volume: number | null
  runway_months?: number | null
  dilution_risk?: string | null
  upcoming_catalyst?: string | null
  catalyst_date?: string | null
}

export interface DashboardOverviewData {
  live_gainers: LiveGainerSnapshot
  watchlist: WatchlistItem[]
  watchlist_prices: Record<string, WatchlistPrice>
  gainers_summary: LatestGainersSummary
}

export interface MomentumBreadthData {
  small_cap_ad: {
    advancing: number
    declining: number
    ratio_str: string
    is_bullish: boolean
  }
  top5_avg_rvol: {
    avg_rvol: number
    status: string
    is_high: boolean
  }
  dominant_float_theme: {
    theme: string
    counts: Record<string, number>
  }
  active_halts: {
    count: number
    tickers: string[]
  }
}

export interface VolumeAnomaly {
  ticker: string
  rvol: number
  gap_pct: number
  float_shares?: number | null
}

export interface MacroItem {
  value: number | null
  chg_pct: number | null
}

export interface SectorStrengthItem {
  sector: string
  etf: string
  price: number | null
  chg_pct: number | null
  rs_vs_spy: number | null
  status: 'leading' | 'lagging' | 'inline'
}

export interface SectorStrengthData {
  spy: { price: number | null; chg_pct: number | null }
  sectors: SectorStrengthItem[]
  leading_count: number
  lagging_count: number
  market_tone: 'bullish' | 'bearish' | 'mixed' | 'rotation'
  benchmark: string
}

export interface CommandSummaryData {
  regime: {
    tag: 'risk_on' | 'neutral' | 'risk_off'
    label: string
    indices: Record<string, { ticker: string; price: number | null; chg_pct: number | null; volume: number | null }>
    vix: {
      value: number | null
      direction: string
      vix3m?: number | null
      term_slope?: number | null
      percentile_rank?: number | null
      regime?: string | null
    } | null
  }
  breadth: {
    ad_ratio_str: string
    ad_ratio_val: number | null
    advancing: number
    declining: number
    pct_green: number | null
    is_bullish: boolean
    status: string
    up_down_vol_ratio: number | null
    above_40sma_pct: number | null
    above_20sma_pct?: number | null
    above_50sma_pct?: number | null
    above_200sma_pct?: number | null
    breadth_score?: number | null
    new_highs?: number | null
    new_lows?: number | null
    net_new_highs?: number | null
    high_low_index?: number | null
  }
  liquidity: {
    median_rvol: number | null
    avg_rvol_top5: number
    status: string
    is_high: boolean
    float_theme: string
    float_counts: Record<string, number>
    sector_clusters: Record<string, number>
  }
  risk: {
    tag: 'normal' | 'elevated' | 'high'
    label: string
    vix_value: number | null
    vix_direction: string | null
    halt_count: number
    halt_tickers: string[]
    halt_rate_per_hour: number | null
    signals: string[]
    anomaly_count?: number
    top_anomalies?: VolumeAnomaly[]
    confluence_score?: number
  }
  macro?: {
    us10y?: MacroItem
    dxy?: MacroItem
    crude?: MacroItem
    gold?: MacroItem
    put_call_ratio?: number | null
  }
  sector_strength?: SectorStrengthData
  fetched_at: string
  cache_ttl_s: number
}

export interface AlertInstance {
  id: number
  alert_time: string
  trigger_price: number
  trigger_volume: number
  rel_vol: number
  alert_type: string
  feedback_score: 'helpful' | 'noise' | 'neutral' | null
  feedback_notes: string | null
  priority_score: number
  priority_tier: string
  vwap_dist_pct: number | null
  hod_dist_pct: number | null
  catalyst: string | null
  stop_price: number | null
  stop_risk_pct: number | null
  fwd_1m: number | null
  fwd_3m: number | null
  fwd_5m: number | null
  fwd_15m: number | null
  mfe: number | null
  mae: number | null
  suppressed_reason: string | null
  group_id: string | null
}

export interface AlertTickerSummary {
  symbol: string
  company_name: string | null
  float_category: string | null
  float_shares: number | null
  market_cap: number | null
  gap_pct: number | null
  rvol: number | null
  alerts: AlertInstance[]
}

export interface AlertDailySummary {
  date: string
  tickers: AlertTickerSummary[]
}

export interface ScorecardRow {
  alert_type: string
  price_bucket: string
  float_category: string | null
  sample_count: number
  avg_fwd_5m: number | null
  avg_fwd_15m: number | null
  win_rate_5m_pct: number | null
  avg_mfe_pct: number | null
  avg_mae_pct: number | null
}

export interface AlertsPerformance {
  days: number
  scorecard: ScorecardRow[]
}

export interface AlarmMetricRow {
  date: string
  total_alarms: number
  tier1_count: number
  tier2_count: number
  tier3_count: number
  unique_tickers: number
  chattering_count: number
  peak_10min_rate: number | null
  noise_count: number
  helpful_count: number
  snr_pct: number | null
}

export interface BadActorRow {
  symbol: string
  alert_type: string
  fire_count: number
  noise_count: number
  helpful_count: number
  noise_pct: number
}

export interface RSSSource {
  id: number
  name: string
  feed_url: string
  category: 'biotech' | 'tech' | 'general'
  is_active: boolean
  last_polled_at: string | null
  created_at: string
}

export interface RSSFeedPoolItem {
  id: number
  source_id: number
  guid: string
  title: string
  description: string | null
  link: string
  published_at: string
  detected_tickers: string[]
  sector: string | null
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
}

export interface AlertConfig {
  alert_min_pct_increase: number
  alert_min_time_cooldown_mins: number
  tier_1_threshold: number
  tier_2_threshold: number
  watchlist_presence_weight: number
  watchlist_priority_tag_weight: number
  catalyst_confirmed_weight: number
  catalyst_speculative_weight: number
  catalyst_technical_weight: number
  float_micro_weight: number
  float_low_weight: number
  float_mid_weight: number
  session_regular_weight: number
  session_pre_weight: number
  session_post_weight: number
  rvol_high_weight: number
  rvol_mid_weight: number
  rvol_low_weight: number
  enabled_alerts: Record<string, boolean>
  alert_type?: string
  [key: string]: unknown
}

export interface MfeMaeWindow {
  mfe_pct: number
  mae_pct: number
  close_pct: number
}

export interface MfeMaeWindows {
  '5m': MfeMaeWindow
  '15m': MfeMaeWindow
  '30m': MfeMaeWindow
  eod: MfeMaeWindow
}

export interface AlertReviewItem {
  id: number
  symbol: string
  alert_time: string
  trigger_price: number
  trigger_volume: number
  rel_vol: number
  gap_pct: number | null
  alert_type: string
  sent: boolean
  priority_score: number
  priority_tier: string
  vwap_dist_pct: number | null
  hod_dist_pct: number | null
  catalyst: string | null
  stop_price: number | null
  stop_risk_pct: number | null
  suppressed_reason: string | null
  group_id: string | null
  mfe_mae?: MfeMaeWindows | null
}

export interface AlertReviewSymbol {
  symbol: string
  gap_pct: number | null
  rvol: number | null
  alert_count: number
  best_15m_mfe: number
  avg_15m_mfe: number
  alerts: AlertReviewItem[]
}

export interface AlertReviewSummary {
  date: string
  total_alerts: number
  unique_symbols: number
  tier_counts: {
    'Tier 1': number
    'Tier 2': number
    'Tier 3': number
  }
  alert_type_counts: Record<string, number>
  suppressed_count: number
  mfe_15m_hit_rate: number
  avg_mae_15m: number
}

export interface AlertReviewTop10Data {
  summary: AlertReviewSummary
  top10_gainers: AlertReviewSymbol[]
}

export interface AlertReviewGridData {
  summary: AlertReviewSummary
  top10_gainers?: AlertReviewSymbol[]
  alerted_symbols?: AlertReviewSymbol[]
  remaining_gainers?: AlertReviewSymbol[]
}

export interface AlertReviewDetailData {
  symbol: string
  date: string
  chart: any
  alerts: AlertReviewItem[]
}

