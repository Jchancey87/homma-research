import api, { BASE } from './client'
import { ChartCapture, LLMJob, CachedReport } from './types'

interface JobResponse { job_id: string; status: string; cached?: false }
interface CacheResponse { cached: true; report: string; version: number; created_at: string }
type ResearchResponse = JobResponse | CacheResponse

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

export interface ChartDataPayload {
  ohlcv: Array<{ time: number; open: number; high: number; low: number; close: number }>
  volume: Array<{ time: number; value: number }>
  ema_9?: Array<{ time: number; value: number }>
  ema_20?: Array<{ time: number; value: number }>
  ema_21?: Array<{ time: number; value: number }>
  ema_50?: Array<{ time: number; value: number }>
  ema_55?: Array<{ time: number; value: number }>
  ema_100?: Array<{ time: number; value: number }>
  vwap?: Array<{ time: number; value: number }>
}

export const getChartData = (ticker: string, date: string, mini = true) =>
  api
    .get<ChartDataPayload>('/api/research/chart-data', { params: { ticker, date, mini } })
    .then(r => r.data)

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

export const startResearch = (ticker: string, date?: string, force = false) =>
  api.post<ResearchResponse>('/api/research', { ticker, date, force }).then(r => r.data)

export const startRiskDetection = (ticker: string, force = false) =>
  api.post<ResearchResponse>('/api/research/risk', { ticker, force }).then(r => r.data)

export const startCatalystAnalysis = (ticker: string, date?: string, force = false) =>
  api.post<ResearchResponse>('/api/research/catalyst', { ticker, date, force }).then(r => r.data)

export const startDeepContext = (ticker: string, force = false) =>
  api.post<ResearchResponse>('/api/research/context', { ticker, force }).then(r => r.data)

export const startPipeAnalysis = (ticker: string, date?: string) =>
  api.post<JobResponse>('/api/research/pipe', { ticker, date }).then(r => r.data)

export const getJobStatus = (jobId: string) =>
  api.get<LLMJob>(`/api/jobs/${jobId}`).then(r => r.data)

export const getResearchHistory = (ticker: string, type?: string, limit = 50) =>
  api.get<CachedReport[]>('/api/research/history', { params: { ticker, type, limit } }).then(r => r.data)

export const getCachedReport = (id: number) =>
  api.get<CachedReport>(`/api/research/history/${id}`).then(r => r.data)

export const getResearchExportUrl = (id: number) =>
  `${BASE}/api/research/export/${id}`

export const chartImageUrl = (imagePath: string) =>
  `${BASE}/storage/charts/${imagePath.split('/charts/').pop()}`
