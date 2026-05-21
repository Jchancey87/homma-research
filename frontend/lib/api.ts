import axios from 'axios'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'

const api = axios.create({ baseURL: BASE })

// ── Types ─────────────────────────────────────────────────────────────────

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
  // Enrichment fields (2026-05)
  high_price: number | null
  low_price: number | null
  prev_close: number | null
  vwap: number | null
  dollar_volume: number | null
  close_location: number | null   // 0.0–1.0, where 1.0 = closed at HOD
  rs_vs_spy: number | null        // stock gap_pct minus SPY day return
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
  tags: string           // JSON array string
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

export interface ArchetypeStat {
  tag: string
  count: number
  avg_gap_pct: number | null
  avg_float_m: number | null
  avg_rvol: number | null
  avg_cleanliness: number | null
}

// ── Gainers ───────────────────────────────────────────────────────────────

export const getGainers = (params?: {
  date?: string
  min_gap?: number
  max_float?: number
  min_rvol?: number
  sector?: string
}) => api.get<Gainer[]>('/api/gainers', { params }).then(r => r.data)

export interface GainerSummary {
  date: string | null
  total: number
  gainers: Array<{
    ticker: string
    gap_pct: number | null
    float_shares: number | null
    rvol_15m: number | null
    sector: string | null
    news_headline: string | null
    news_fresh: boolean | null
    close_price: number | null
    open_price: number | null
    high_price: number | null
    low_price: number | null
    prev_close: number | null
    vwap: number | null
    dollar_volume: number | null
    close_location: number | null
    rs_vs_spy: number | null
    shares_outstanding: number | null
    avg_volume: number | null
  }>
}

export const getGainersSummary = () =>
  api.get<GainerSummary>('/api/gainers/summary').then(r => r.data)

// ── Live Screener ──────────────────────────────────────────────────────────

export interface LiveGainerRow {
  ticker:        string
  gap_pct:       number
  last_price:    number | null
  open_price:    number | null
  prev_close:    number | null
  volume:        number | null
  rvol_15m:      number | null
  float_shares:  number | null
  sector:        string | null
  market_cap:    number | null
  spread_pct:    number | null
  trade_time:    number | null
  is_hod:        boolean | null
  news_headline: string | null
  news_fresh:    boolean | null
}

export interface LiveGainerSnapshot {
  session:       'pre_market' | 'open' | 'after_hours' | 'closed'
  session_label: string
  fetched_at:    string | null   // ISO UTC
  gainers:       LiveGainerRow[]
  top_n:         number
  cache_ttl_s:   number
}

export const getLiveGainers = (force = false) =>
  api.get<LiveGainerSnapshot>('/api/gainers/live', {
    params: force ? { force: 1 } : undefined
  }).then(r => r.data)

export interface TickerHistoryItem {
  ticker:       string
  sector:       string | null
  appearances:  number
  last_seen:    string
  first_seen:   string
  avg_gap_pct:  number | null
  avg_rvol:     number | null
  avg_float_m:  number | null
  max_gap_pct:  number | null
  last_close:      number | null
  last_market_cap: number | null
}

export interface TickerAppearance {
  id:            number
  date:          string
  ticker:        string
  gap_pct:       number | null
  float_shares:  number | null
  rvol_15m:      number | null
  sector:        string | null
  news_headline: string | null
  news_fresh:    boolean | null
  close_price:   number | null
  open_price:    number | null
}

export const getTickerHistory = (params?: {
  period?:    'week' | 'month' | 'year' | 'all'
  search?:    string
  sort?:      'appearances' | 'last_seen' | 'avg_gap' | 'first_seen'
  limit?:     number
  date?:      string
  min_gap?:   number
  max_float?: number
  min_rvol?:  number
  sector?:    string
  min_price?: number
  max_price?: number
}) => api.get<TickerHistoryItem[]>('/api/gainers/ticker-history', { params }).then(r => r.data)

export const getTickerAppearances = (ticker: string, period?: string) =>
  api.get<TickerAppearance[]>(`/api/gainers/ticker/${ticker}`, {
    params: period ? { period } : undefined
  }).then(r => r.data)

export const getHeatmap = (params?: {
  period?:    string
  view?:      string
  date?:      string
  min_gap?:   number
  max_float?: number
  min_rvol?:  number
  sector?:    string
}) =>
  api.get('/api/gainers/heatmap', { params }).then(r => r.data)

export const getGainersExportUrl = (params?: Record<string, string | number>) => {
  const q = new URLSearchParams(
    Object.entries(params ?? {}).map(([k, v]) => [k, String(v)])
  ).toString()
  return `${BASE}/api/gainers/export${q ? '?' + q : ''}`
}

export const getSectors = () =>
  api.get<string[]>('/api/gainers/sectors').then(r => r.data)

// ── Charts ────────────────────────────────────────────────────────────────

export const getCharts = (params?: {
  ticker?: string
  setup_type?: string
  tag?: string
  date_from?: string
  date_to?: string
  min_cleanliness?: number
}) => api.get<ChartCapture[]>('/api/charts', { params }).then(r => r.data)

export const getChart = (id: number) =>
  api.get<ChartCapture>(`/api/charts/${id}`).then(r => r.data)

export const uploadChart = (formData: FormData) =>
  api.post<{ id: number; image_path: string }>('/api/charts', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data)

export const updateChart = (
  id: number,
  data: Partial<Pick<ChartCapture, 'notes' | 'cleanliness_score' | 'setup_type' | 'timeframe'> & { tags: string[] }>
) => api.put(`/api/charts/${id}`, data).then(r => r.data)

export const deleteChart = (id: number) =>
  api.delete(`/api/charts/${id}`).then(r => r.data)

export const importGeminiAnalysis = (
  chartId: number,
  analysisText: string,
  annotatedImage?: File
) => {
  if (annotatedImage) {
    const fd = new FormData()
    fd.append('analysis_text', analysisText)
    fd.append('annotated_image', annotatedImage)
    return api.post(`/api/charts/${chartId}/gemini-import`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data)
  }
  return api.post(`/api/charts/${chartId}/gemini-import`, { analysis_text: analysisText }).then(r => r.data)
}

// ── Analysis ──────────────────────────────────────────────────────────────

export interface JobResponse   { job_id: string; status: string; cached?: false }
export interface CacheResponse { cached: true; report: string; version: number; created_at: string }
export type ResearchResponse = JobResponse | CacheResponse

export const startContinuation = (date: string) =>
  api.post<{ job_id: string; status: string }>('/api/continuation', { date }).then(r => r.data)

export const startSentiment = (query: string) =>
  api.post<{ job_id: string; status: string }>('/api/sentiment', { query }).then(r => r.data)

export const startResearch = (ticker: string, date?: string, force = false) =>
  api.post<ResearchResponse>('/api/research', { ticker, date, force }).then(r => r.data)

export const startRiskDetection = (ticker: string, force = false) =>
  api.post<ResearchResponse>('/api/research/risk', { ticker, force }).then(r => r.data)

export const startCatalystAnalysis = (ticker: string, date?: string, force = false) =>
  api.post<ResearchResponse>('/api/research/catalyst', { ticker, date, force }).then(r => r.data)

export const startDeepContext = (ticker: string, force = false) =>
  api.post<ResearchResponse>('/api/research/context', { ticker, force }).then(r => r.data)

export const getJob = (jobId: string) =>
  api.get<LLMJob>(`/api/jobs/${jobId}`).then(r => r.data)

export const getJobStatus = getJob

export const listJobs = (type?: string, limit = 50) =>
  api.get<LLMJob[]>('/api/jobs', { params: { type, limit } }).then(r => r.data)

export const getArchetypes = () =>
  api.get<ArchetypeStat[]>('/api/archetypes').then(r => r.data)

export const retryJob = (jobId: string) =>
  api.post<{ job_id: string; status: string }>(`/api/jobs/${jobId}/retry`).then(r => r.data)

// ── Research History & Export ─────────────────────────────────────────────

export interface CachedReport {
  id:          number
  ticker:      string
  date:        string | null
  report_type: string
  version:     number
  model_used:  string | null
  created_at:  string
  expires_at:  string | null
  output?:     string   // only present when fetching single record
}

export const getResearchHistory = (ticker: string, type?: string, limit = 50) =>
  api.get<CachedReport[]>('/api/research/history', { params: { ticker, type, limit } }).then(r => r.data)

export const getCachedReport = (id: number) =>
  api.get<CachedReport>(`/api/research/history/${id}`).then(r => r.data)

export const getResearchExportUrl = (id: number) =>
  `${BASE}/api/research/export/${id}`

// ── Helpers ───────────────────────────────────────────────────────────────

export const chartImageUrl = (imagePath: string) =>
  `${BASE}/storage/charts/${imagePath.split('/charts/').pop()}`

// ── Watchlist ─────────────────────────────────────────────────────────────

export interface WatchlistItem {
  id: number
  ticker: string
  sector: string | null
  notes: string | null
  tags: string          // JSON array string
  added_at: string
  last_viewed_at: string | null
}

export const getWatchlist = () =>
  api.get<WatchlistItem[]>('/api/watchlist').then(r => r.data)

export const addToWatchlist = (data: {
  ticker: string
  sector?: string
  notes?: string
  tags?: string[]
}) => api.post<{ ticker: string }>('/api/watchlist', data).then(r => r.data)

export const updateWatchlistItem = (
  ticker: string,
  data: { notes?: string; tags?: string[]; sector?: string }
) => api.put(`/api/watchlist/${ticker}`, data).then(r => r.data)

export const removeFromWatchlist = (ticker: string) =>
  api.delete(`/api/watchlist/${ticker}`).then(r => r.data)

export const markWatchlistViewed = (ticker: string) =>
  api.post(`/api/watchlist/${ticker}/viewed`).then(r => r.data)

// ── Continuation Picks ────────────────────────────────────────────────────

export interface ContinuationPick {
  id:                   number
  ticker:               string
  date:                 string
  reason:               string | null
  gap_pct:              number | null
  float_shares:         number | null
  rvol_15m:             number | null
  sector:               string | null
  rank:                 number
  is_active:            boolean
  deactivated_at:       string | null
  deactivated_reason:   string | null
  created_at:           string
}

export const getContinuationPicks = (includeInactive = false) =>
  api.get<ContinuationPick[]>('/api/continuation-picks', {
    params: { include_inactive: includeInactive }
  }).then(r => r.data)

export const addContinuationPick = (data: {
  ticker: string
  date: string
  reason?: string
  gap_pct?: number
  float_shares?: number
  rvol_15m?: number
  sector?: string
  rank?: number
}) => api.post<{ inserted: number }>('/api/continuation-picks', [data]).then(r => r.data)

export const deactivateContinuationPick = (id: number, reason?: string) =>
  api.post(`/api/continuation-picks/${id}/deactivate`, { reason }).then(r => r.data)

export const deleteContinuationPick = (id: number) =>
  api.delete(`/api/continuation-picks/${id}`).then(r => r.data)

// ── Observations ──────────────────────────────────────────────────────────

export interface Observation {
  id: number
  ticker: string
  date: string
  title: string | null
  body: string
  sentiment: 'bullish' | 'bearish' | 'neutral'
  tags: string          // JSON array string
  linked_chart_id: number | null
  created_at: string
  updated_at: string
}

export const getObservations = (params?: {
  ticker?: string
  sentiment?: string
  tag?: string
  date_from?: string
  date_to?: string
  limit?: number
}) => api.get<Observation[]>('/api/observations', { params }).then(r => r.data)

export const getObservationsForTicker = (ticker: string) =>
  api.get<Observation[]>(`/api/observations/${ticker}`).then(r => r.data)

export const createObservation = (data: {
  ticker: string
  date: string
  body: string
  title?: string
  sentiment?: 'bullish' | 'bearish' | 'neutral'
  tags?: string[]
  linked_chart_id?: number
}) => api.post<{ id: number }>('/api/observations', data).then(r => r.data)

export const updateObservation = (
  id: number,
  data: Partial<{
    title: string
    body: string
    sentiment: 'bullish' | 'bearish' | 'neutral'
    tags: string[]
    date: string
    linked_chart_id: number
  }>
) => api.put(`/api/observations/${id}`, data).then(r => r.data)

export const deleteObservation = (id: number) =>
  api.delete(`/api/observations/${id}`).then(r => r.data)

// ── PIPE Detection ────────────────────────────────────────────────────────

export interface PipeScanResult {
  ticker:           string
  anchor_date:      string
  is_pipe:          boolean
  filing_date:      string | null
  filing_url:       string | null
  security_type:    string | null     // common_stock | preferred_stock | convertible_note | warrant
  pricing_type:     string | null     // fixed | variable | unknown
  proceeds_amount:  number | null
  use_of_proceeds:  string | null
  toxic_signals:    string[]
  deal_score:       number | null     // 1–5
  item_codes:       string[]
}

export const startPipeAnalysis = (ticker: string, date?: string) =>
  api.post<JobResponse>('/api/research/pipe', { ticker, date }).then(r => r.data)

export const getPipeScan = (date: string) =>
  api.get<PipeScanResult[]>('/api/gainers/pipe-scan', { params: { date } }).then(r => r.data)


// ── Dashboard Intelligence ────────────────────────────────────────────────

export interface RepeatRunner {
  ticker:       string
  appearances:  number
  avg_gap_pct:  number | null
  best_gap_pct: number | null
  last_seen:    string
  first_seen:   string
  avg_rvol:     number | null
  avg_float_m:  number | null
}
export const getRepeatRunners = () =>
  api.get<RepeatRunner[]>('/api/gainers/repeat-runners').then(r => r.data)

export interface FloatBucket {
  bucket:       string
  count:        number
  avg_gap_pct:  number | null
  best_gap_pct: number | null
}
export const getFloatBuckets = (date?: string) =>
  api.get<{ date: string; buckets: FloatBucket[] }>('/api/gainers/float-buckets', {
    params: date ? { date } : undefined
  }).then(r => r.data)

export interface FollowThroughResult {
  ticker:     string
  prev_date:  string
  prev_gap:   number | null
  prev_close: number | null
  today_open: number | null
  change_pct: number | null
  status:     'following' | 'fading' | 'flat' | 'no_data'
}
export const getFollowThrough = () =>
  api.get<{ date: string; results: FollowThroughResult[] }>('/api/gainers/follow-through').then(r => r.data)

export interface SectorRotationItem {
  sector:       string
  count:        number
  avg_gap_pct:  number | null
  last_avg_gap: number | null
  last_rank:    number | null
  this_rank:    number
  trend:        'up' | 'down' | 'flat' | 'new'
}
export const getSectorRotation = () =>
  api.get<SectorRotationItem[]>('/api/gainers/sector-rotation').then(r => r.data)

export interface IndexData {
  ticker:  string
  price:   number | null
  chg_pct: number | null
  volume:  number | null
}
export interface MarketBreadthData {
  indices:     Record<string, IndexData>
  vix:         number | null
  bias:        'risk_on' | 'neutral' | 'risk_off' | 'unknown'
  fetched_at:  string
  cache_ttl_s: number
}
export const getMarketBreadth = () =>
  api.get<MarketBreadthData>('/api/market/breadth').then(r => r.data)

export interface EconomicEvent {
  date:     string
  time:     string
  event:    string | null
  country:  string | null
  impact:   'high' | 'medium'
  actual:   number | null
  estimate: number | null
  previous: number | null
}
export const getEconomicCalendar = () =>
  api.get<{ events: EconomicEvent[]; source: string }>('/api/market/calendar').then(r => r.data)

export interface WatchlistPrice {
  price:   number | null
  chg_pct: number | null
  volume:  number | null
}
export const getWatchlistPrices = () =>
  api.get<Record<string, WatchlistPrice>>('/api/watchlist/prices').then(r => r.data)
