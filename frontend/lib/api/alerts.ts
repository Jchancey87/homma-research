import api from './client'
import {
  AlertConfig,
  AlertDailySummary,
  AlertsPerformance,
  AlarmMetricRow,
  BadActorRow,
  RSSSource,
  RSSFeedPoolItem,
  AlertReviewSummary,
  AlertReviewGridData,
  AlertReviewDetailData,
} from './types'

export const getAlertConfig = () =>
  api.get<AlertConfig>('/api/alert-config').then(r => r.data)

export const updateAlertConfig = (data: AlertConfig) =>
  api.put<{ status: string }>('/api/alert-config', data).then(r => r.data)

export const getAlertHistory = (limit = 50) =>
  api.get('/api/alerts/history', { params: { limit } }).then(r => r.data)

export const getSuppressions = () =>
  api.get('/api/alerts/suppressions').then(r => r.data)

export const toggleSuppression = (ticker: string, suppress: boolean) =>
  api.post('/api/alerts/suppressions', { ticker, suppress }).then(r => r.data)

export const getAlertDates = () =>
  api.get<string[]>('/api/alerts/dates').then(r => r.data)

export const getAlertsDailySummary = (date?: string) =>
  api.get<AlertDailySummary>('/api/alerts/daily-summary', {
    params: date ? { date } : undefined
  }).then(r => r.data)

export const saveAlertFeedback = (
  alertId: number,
  alertTime: string,
  feedbackScore: 'helpful' | 'noise' | 'neutral' | null,
  feedbackNotes: string | null
) =>
  api.post<{ status: string; updated: string }>(`/api/alerts/${alertId}/feedback`, {
    alert_time: alertTime,
    feedback_score: feedbackScore,
    feedback_notes: feedbackNotes
  }).then(r => r.data)

export const getAlertsPerformance = (days = 30) =>
  api.get<AlertsPerformance>('/api/alerts/performance', {
    params: { days }
  }).then(r => r.data)

export const getAlarmMetrics = (days = 30) =>
  api.get<AlarmMetricRow[]>('/api/alerts/alarm-metrics', {
    params: { days }
  }).then(r => r.data)

export const getBadActors = (days = 30, topN = 10) =>
  api.get<BadActorRow[]>('/api/alerts/bad-actors', {
    params: { days, top_n: topN }
  }).then(r => r.data)

export const getRSSSources = () =>
  api.get<RSSSource[]>('/api/rss/sources').then(r => r.data)

export const createRSSSource = (data: { name: string; feed_url: string; category: string; is_active?: boolean }) =>
  api.post<{ id: number; message: string }>('/api/rss/sources', data).then(r => r.data)

export const updateRSSSource = (id: number, data: { name?: string; feed_url?: string; category?: string; is_active?: boolean }) =>
  api.put<{ message: string }>(`/api/rss/sources/${id}`, data).then(r => r.data)

export const deleteRSSSource = (id: number) =>
  api.delete<{ message: string }>(`/api/rss/sources/${id}`).then(r => r.data)

export const getRSSPool = (status = 'pending') =>
  api.get<RSSFeedPoolItem[]>('/api/rss/pool', { params: { status } }).then(r => r.data)

export const triggerRSSIngest = () =>
  api.post<{ message: string; stats: Record<string, unknown> }>('/api/rss/pool/trigger-ingest').then(r => r.data)

export const curateRSSItem = (id: number, data: { title: string; description: string; associated_tickers: string[]; curated_notes?: string }) =>
  api.post<{ message: string }>(`/api/rss/pool/${id}/curate`, data).then(r => r.data)

export const rejectRSSItem = (id: number) =>
  api.post<{ message: string }>(`/api/rss/pool/${id}/reject`).then(r => r.data)

export const getAlertReviewSummary = (date?: string) =>
  api.get<AlertReviewSummary>('/api/alerts/review/summary', {
    params: date ? { date } : undefined
  }).then(r => r.data)

export const getAlertReviewGrid = (date?: string) =>
  api.get<AlertReviewGridData>('/api/alerts/review/grid', {
    params: date ? { date } : undefined
  }).then(r => r.data)

export const getAlertReviewDetail = (symbol: string, date?: string) =>
  api.get<AlertReviewDetailData>('/api/alerts/review/detail', {
    params: { symbol, date }
  }).then(r => r.data)

