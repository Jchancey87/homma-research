import api from './client'
import {
  WatchlistGroup,
  WatchlistItem,
  WatchlistPrice,
  DashboardOverviewData,
  ContinuationPick,
  ContinuationPerformanceData,
  Observation,
  MarketBreadthData,
  MTFScannerData,
  MTFFilters,
  EconomicEvent,
  MomentumBreadthData,
  CommandSummaryData,
} from './types'

export const getMarketSession = () =>
  api.get<{ session: string; session_label: string }>('/api/market/session').then(r => r.data)

export const getBreadthMetrics = () =>
  api.get<{ rvol_above_5x: number; top_gap_pct: number; tape_quality: string }>('/api/market/breadth').then(r => r.data)

export const getCalendar = (params?: { date_from?: string; date_to?: string }) =>
  api.get('/api/market/calendar', { params }).then(r => r.data)

export const getEconomicCalendar = () =>
  api.get<{ events: EconomicEvent[]; source: string }>('/api/market/calendar').then(r => r.data)

export const getMarketBreadth = () =>
  api.get<MarketBreadthData>('/api/market/breadth').then(r => r.data)

export const getMTFScanner = (filters?: MTFFilters) =>
  api.get<MTFScannerData>('/api/market/mtf-scanner', { params: filters }).then(r => r.data)

export const getMomentumBreadth = (priceFilter = true) =>
  api.get<MomentumBreadthData>('/api/market/momentum-breadth', {
    params: { price_filter: priceFilter }
  }).then(r => r.data)

export const getCommandSummary = (priceFilter = true) =>
  api.get<CommandSummaryData>('/api/market/command-summary', {
    params: { price_filter: priceFilter }
  }).then(r => r.data)

export const getWatchlistGroups = () =>
  api.get<WatchlistGroup[]>('/api/watchlist/groups').then(r => r.data)

export const createWatchlistGroup = (name: string) =>
  api.post<WatchlistGroup>('/api/watchlist/groups', { name }).then(r => r.data)

export const deleteWatchlistGroup = (groupId: number) =>
  api.delete(`/api/watchlist/groups/${groupId}`).then(r => r.data)

export const getWatchlist = (groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.get<WatchlistItem[]>('/api/watchlist', { params }).then(r => r.data)
}

export const addToWatchlist = (data: {
  ticker: string
  sector?: string
  notes?: string
  tags?: string[]
  group_id?: number
}) => api.post<{ ticker: string }>('/api/watchlist', data).then(r => r.data)

export const updateWatchlistItem = (
  ticker: string,
  data: { notes?: string; tags?: string[]; sector?: string },
  groupId?: number
) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.put(`/api/watchlist/${ticker}`, data, { params }).then(r => r.data)
}

export const removeFromWatchlist = (ticker: string, groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.delete(`/api/watchlist/${ticker}`, { params }).then(r => r.data)
}

export const markWatchlistViewed = (ticker: string, groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.post(`/api/watchlist/${ticker}/viewed`, null, { params }).then(r => r.data)
}

export const enrichWatchlist = (groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.post<{ success: boolean; processed: number }>('/api/watchlist/enrich', null, { params }).then(r => r.data)
}

export const exportWatchlistCsv = (groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.get('/api/watchlist/export', { responseType: 'blob', params }).then(r => r.data)
}

export const importWatchlistCsv = (file: File, groupId?: number) => {
  const formData = new FormData()
  formData.append('file', file)
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.post<{ inserted: number; updated: number }>('/api/watchlist/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params
  }).then(r => r.data)
}

export const getWatchlistPrices = (groupId?: number) => {
  const params = groupId !== undefined ? { group_id: groupId } : {}
  return api.get<Record<string, WatchlistPrice>>('/api/watchlist/prices', { params }).then(r => r.data)
}

export const getDashboardOverview = () =>
  api.get<DashboardOverviewData>('/api/market/dashboard-overview').then(r => r.data)

export const getContinuationPicks = (includeInactive = false) =>
  api.get<ContinuationPick[]>('/api/continuation-picks', {
    params: { include_inactive: includeInactive }
  }).then(r => r.data)

export const deactivateContinuationPick = (id: number, reason?: string) =>
  api.post(`/api/continuation-picks/${id}/deactivate`, { reason }).then(r => r.data)

export const getContinuationPerformance = () =>
  api.get<ContinuationPerformanceData>('/api/continuation-picks/performance').then(r => r.data)

export const refreshContinuationPerformance = () =>
  api.post<{ updated: number }>('/api/continuation-picks/refresh-performance').then(r => r.data)

export const getObservations = (params?: {
  ticker?: string
  sentiment?: string
  tag?: string
  date_from?: string
  date_to?: string
  limit?: number
}) => api.get<Observation[]>('/api/observations', { params }).then(r => r.data)

export const createObservation = (data: {
  ticker: string
  date: string
  body: string
  title?: string
  sentiment?: 'bullish' | 'bearish' | 'neutral'
  tags?: string[]
  linked_chart_id?: number
}) => api.post<{ id: number }>('/api/observations', data).then(r => r.data)

export const deleteObservation = (id: number) =>
  api.delete(`/api/observations/${id}`).then(r => r.data)
