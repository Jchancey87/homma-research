import api, { BASE } from './client'
import {
  Gainer,
  LatestGainersSummary,
  LiveGainerSnapshot,
  TickerHistoryItem,
  TickerAppearance,
  RepeatRunner,
  FloatBucket,
  FollowThroughResult,
  SectorRotationItem,
  PipeScanResult,
} from './types'

export const getGainers = (params?: {
  date?: string
  min_gap?: number
  max_float?: number
  min_rvol?: number
  sector?: string
}) => api.get<Gainer[]>('/api/gainers', { params }).then(r => r.data)

export const getGainersSummary = () =>
  api.get<LatestGainersSummary>('/api/gainers/summary').then(r => r.data)

export const getGainersByDate = (date: string) =>
  api.get<Gainer[]>('/api/gainers', { params: { date } }).then(r => r.data)

export const getLiveGainers = (force = false) =>
  api.get<LiveGainerSnapshot>('/api/gainers/live', {
    params: force ? { force: 1 } : undefined
  }).then(r => r.data)

export const getLivePrices = (tickers: string[]) =>
  api.get<{ prices: Record<string, number | null> }>('/api/chart/live-price', {
    params: { tickers: tickers.join(',') },
  }).then(r => r.data.prices)

export const getTickerHistory = (params?: {
  period?: 'week' | 'month' | 'year' | 'all'
  search?: string
  sort?: 'appearances' | 'last_seen' | 'avg_gap' | 'first_seen'
  limit?: number
  date?: string
  min_gap?: number
  max_float?: number
  min_rvol?: number
  sector?: string
  min_price?: number
  max_price?: number
}) => api.get<TickerHistoryItem[]>('/api/gainers/ticker-history', { params }).then(r => r.data)

export const getTickerAppearances = (ticker: string, period?: string) =>
  api.get<TickerAppearance[]>(`/api/gainers/ticker/${ticker}`, {
    params: period ? { period } : undefined
  }).then(r => r.data)

export const getHeatmap = (params?: {
  period?: string
  view?: string
  date?: string
  min_gap?: number
  max_float?: number
  min_rvol?: number
  sector?: string
}) => api.get('/api/gainers/heatmap', { params }).then(r => r.data)

export const getGainersExportUrl = (params?: Record<string, string | number>) => {
  const q = new URLSearchParams(
    Object.entries(params ?? {}).map(([k, v]) => [k, String(v)])
  ).toString()
  return `${BASE}/api/gainers/export${q ? '?' + q : ''}`
}

export const getSectors = () =>
  api.get<string[]>('/api/gainers/sectors').then(r => r.data)

export const getRepeatRunners = () =>
  api.get<RepeatRunner[]>('/api/gainers/repeat-runners').then(r => r.data)

export const getFloatBuckets = (date?: string) =>
  api.get<{ date: string; buckets: FloatBucket[] }>('/api/gainers/float-buckets', {
    params: date ? { date } : undefined
  }).then(r => r.data)

export const getFollowThrough = () =>
  api.get<{ date: string; results: FollowThroughResult[] }>('/api/gainers/follow-through').then(r => r.data)

export const getSectorRotation = () =>
  api.get<SectorRotationItem[]>('/api/gainers/sector-rotation').then(r => r.data)

export const getPipeScan = (date: string) =>
  api.get<PipeScanResult[]>('/api/gainers/pipe-scan', { params: { date } }).then(r => r.data)
