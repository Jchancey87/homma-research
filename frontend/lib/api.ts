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
  }>
}

export const getGainersSummary = () =>
  api.get<GainerSummary>('/api/gainers/summary').then(r => r.data)

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
  period?:  'week' | 'month' | 'year' | 'all'
  search?:  string
  sort?:    'appearances' | 'last_seen' | 'avg_gap' | 'first_seen'
  limit?:   number
}) => api.get<TickerHistoryItem[]>('/api/gainers/ticker-history', { params }).then(r => r.data)

export const getTickerAppearances = (ticker: string, period?: string) =>
  api.get<TickerAppearance[]>(`/api/gainers/ticker/${ticker}`, {
    params: period ? { period } : undefined
  }).then(r => r.data)

export const getHeatmap = (period?: string, view?: string) =>
  api.get('/api/gainers/heatmap', {
    params: { ...(period ? { period } : {}), ...(view ? { view } : {}) }
  }).then(r => r.data)

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

export const startContinuation = (date: string) =>
  api.post<{ job_id: string; status: string }>('/api/continuation', { date }).then(r => r.data)

export const startSentiment = (query: string) =>
  api.post<{ job_id: string; status: string }>('/api/sentiment', { query }).then(r => r.data)

export const startResearch = (ticker: string, date?: string) =>
  api.post<{ job_id: string; status: string }>('/api/research', { ticker, date }).then(r => r.data)

export const startRiskDetection = (ticker: string) =>
  api.post<{ job_id: string; status: string }>('/api/research/risk', { ticker }).then(r => r.data)

export const startCatalystAnalysis = (ticker: string, date?: string) =>
  api.post<{ job_id: string; status: string }>('/api/research/catalyst', { ticker, date }).then(r => r.data)

export const startDeepContext = (ticker: string) =>
  api.post<{ job_id: string; status: string }>('/api/research/context', { ticker }).then(r => r.data)

export const getJob = (jobId: string) =>
  api.get<LLMJob>(`/api/jobs/${jobId}`).then(r => r.data)


export const getJobStatus = getJob

export const listJobs = (type?: string, limit = 50) =>
  api.get<LLMJob[]>('/api/jobs', { params: { type, limit } }).then(r => r.data)

export const getArchetypes = () =>
  api.get<ArchetypeStat[]>('/api/archetypes').then(r => r.data)

export const retryJob = (jobId: string) =>
  api.post<{ job_id: string; status: string }>(`/api/jobs/${jobId}/retry`).then(r => r.data)

// ── Health ────────────────────────────────────────────────────────────────

export const getHealth = () => api.get('/api/health').then(r => r.data)

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
  api.post<{ job_id: string; status: string }>('/api/research/pipe', { ticker, date }).then(r => r.data)

export const getPipeScan = (date: string) =>
  api.get<PipeScanResult[]>('/api/gainers/pipe-scan', { params: { date } }).then(r => r.data)

