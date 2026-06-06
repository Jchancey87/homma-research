'use client'
import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  createChart, IChartApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, UTCTimestamp, createSeriesMarkers
} from 'lightweight-charts'
import {
  getAlertDates, getAlertsDailySummary, saveAlertFeedback,
  AlertDailySummary, AlertTickerSummary, AlertInstance
} from '@/lib/api'
import {
  Bell, ChevronLeft, ChevronRight, Loader2,
  AlertCircle, ThumbsUp, ThumbsDown, Save, CheckCircle, Info
} from 'lucide-react'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:5000'
const CHART_BG = '#0d0d14'
const GRID_COLOR = '#1a1a2a'
const TEXT_COLOR = '#64748b'
const UP_COLOR = '#22d3a7'
const DOWN_COLOR = '#f04d5a'
const EMA21_COL = '#4361ee'

interface OhlcBar { time: UTCTimestamp; open: number; high: number; low: number; close: number }
interface LinePt { time: UTCTimestamp; value: number }
interface HistoPt { time: UTCTimestamp; value: number; color?: string }

interface ChartData {
  ohlcv: OhlcBar[]
  volume: HistoPt[]
  ema_21: LinePt[]
}

function dedupSort<T extends { time: UTCTimestamp }>(data: T[]): T[] {
  const map = new Map<number, T>()
  for (const bar of data) map.set(bar.time as number, bar)
  return Array.from(map.values()).sort((a, b) => (a.time as number) - (b.time as number))
}

function shiftChartDataTime(data: ChartData, offsetSec: number): ChartData {
  if (offsetSec === 0) return data
  const shiftTime = (t: UTCTimestamp) => (typeof t === 'number' ? (t + offsetSec) as UTCTimestamp : t)
  return {
    ohlcv: data.ohlcv ? data.ohlcv.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    volume: data.volume ? data.volume.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
    ema_21: data.ema_21 ? data.ema_21.map(x => ({ ...x, time: shiftTime(x.time) })) : [],
  }
}

function getMarkerConfig(type: string): { shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square'; color: string } {
  switch (type) {
    case 'VOLUME_SPIKE':
      return { shape: 'arrowUp', color: '#10b981' } // green
    case 'VOLATILITY_HALT':
      return { shape: 'square', color: '#ef4444' } // red
    case 'VOLATILITY_RESUME':
      return { shape: 'circle', color: '#10b981' } // green
    case 'PREV_DAY_BREAKOUT':
      return { shape: 'arrowUp', color: '#3b82f6' } // blue
    case 'VWAP_BOUNCE':
      return { shape: 'arrowUp', color: '#8b5cf6' } // purple
    case 'VWAP_CROSSOVER':
      return { shape: 'arrowUp', color: '#f59e0b' } // amber
    default:
      return { shape: 'circle', color: '#f59e0b' }
  }
}

function formatFloat(n: number | null) {
  if (n == null) return '—'
  const m = n / 1_000_000
  return m >= 1000 ? `${(m / 1000).toFixed(1)}B` : `${m.toFixed(1)}M`
}

// ── Interactive Chart Component ──────────────────────────────────────────────
interface ChartProps {
  ticker: string
  date: string
  alerts: AlertInstance[]
}

function AlertSessionChart({ ticker, date, alerts }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [data, setData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_BASE}/api/research/chart-data?ticker=${ticker}&date=${date}&mini=true`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        if (!active) return

        const rawData = { ohlcv: json.ohlcv, volume: json.volume, ema_21: json.ema_21 }
        const localOffset = -new Date().getTimezoneOffset() * 60
        setData(shiftChartDataTime(rawData, localOffset))
      } catch (e) {
        if (!active) return
        setError((e as Error).message ?? 'No chart data')
      } finally {
        if (active) setLoading(false)
      }
    }
    fetchData()
    return () => { active = false }
  }, [ticker, date])

  useEffect(() => {
    if (!data || !containerRef.current) return

    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout: { background: { color: CHART_BG }, textColor: TEXT_COLOR, fontSize: 11 },
      grid: { vertLines: { color: GRID_COLOR }, horzLines: { color: GRID_COLOR } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: GRID_COLOR, textColor: TEXT_COLOR },
      timeScale: {
        borderColor: GRID_COLOR,
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: true,
        fixRightEdge: true,
      },
      handleScroll: true,
      handleScale: true,
      width: containerRef.current.clientWidth,
      height: 350,
    })
    chartRef.current = chart

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR, downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR, borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR, wickDownColor: DOWN_COLOR,
    })
    candles.setData(dedupSort(data.ohlcv))

    const vol = chart.addSeries(HistogramSeries, {
      color: 'rgba(100,116,139,0.3)',
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false })
    vol.setData(dedupSort(data.volume))

    if (data.ema_21?.length) {
      const ema = chart.addSeries(LineSeries, {
        color: EMA21_COL, lineWidth: 2,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema.setData(dedupSort(data.ema_21))
    }

    // Map alerts to markers
    const localOffset = -new Date().getTimezoneOffset() * 60
    const markers = alerts.map(alt => {
      const timeSec = Math.floor(new Date(alt.alert_time).getTime() / 1000) + localOffset
      const config = getMarkerConfig(alt.alert_type)
      return {
        time: timeSec as UTCTimestamp,
        position: 'aboveBar' as const,
        shape: config.shape,
        color: config.color,
        text: alt.alert_type.replace('_', ' '),
        size: 1.2
      }
    })

    if (markers.length > 0) {
      createSeriesMarkers(candles, markers)
    }

    chart.timeScale().fitContent()

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)

    return () => { ro.disconnect(); chart.remove() }
  }, [data, alerts])

  if (loading) {
    return (
      <div className="h-[350px] w-full flex items-center justify-center bg-gray-950 rounded-xl border border-gray-800/80">
        <Loader2 className="text-emerald-400 animate-spin" size={28} />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="h-[350px] w-full flex flex-col items-center justify-center bg-gray-950 rounded-xl border border-gray-800/80 p-4 text-center gap-2">
        <AlertCircle className="text-rose-400" size={32} />
        <span className="text-gray-400 text-sm">{error ?? 'No intraday chart data available'}</span>
        <span className="text-gray-600 text-xs">Run nightly backfill if this date is today.</span>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full bg-gray-950 rounded-xl border border-gray-800/80 overflow-hidden relative" style={{ height: '350px' }} />
  )
}

// ── Main Page ────────────────────────────────────────────────────────────────
function AlertJournalContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [dates, setDates] = useState<string[]>([])
  const [activeDate, setActiveDate] = useState<string>('')
  const [summary, setSummary] = useState<AlertDailySummary | null>(null)
  const [selectedTicker, setSelectedTicker] = useState<AlertTickerSummary | null>(null)
  
  // Feedback states
  const [selectedAlert, setSelectedAlert] = useState<AlertInstance | null>(null)
  const [feedbackScore, setFeedbackScore] = useState<'helpful' | 'noise' | 'neutral' | null>(null)
  const [feedbackNotes, setFeedbackNotes] = useState<string>('')
  const [savingFeedback, setSavingFeedback] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [loading, setLoading] = useState(true)

  // Fetch available dates on mount
  useEffect(() => {
    getAlertDates()
      .then(res => {
        setDates(res)
        const queryDate = searchParams.get('date')
        if (queryDate) {
          setActiveDate(queryDate)
        } else if (res.length > 0) {
          setActiveDate(res[0])
        } else {
          setActiveDate(new Date().toLocaleDateString('en-CA', { timeZone: 'America/New_York' }))
        }
      })
      .catch(() => {})
  }, [searchParams])

  // Fetch daily summary when date changes
  const loadDailySummary = useCallback(async () => {
    if (!activeDate) return
    setLoading(true)
    try {
      const res = await getAlertsDailySummary(activeDate)
      setSummary(res)
      if (res.tickers.length > 0) {
        // Maintain selection or select first
        const matched = res.tickers.find(t => t.symbol === selectedTicker?.symbol)
        setSelectedTicker(matched ?? res.tickers[0])
      } else {
        setSelectedTicker(null)
      }
    } catch {
      setSummary(null)
      setSelectedTicker(null)
    } finally {
      setLoading(false)
    }
  }, [activeDate, selectedTicker?.symbol])

  useEffect(() => {
    loadDailySummary()
  }, [loadDailySummary])

  // Sync selected alert feedback state when selectedAlert changes
  useEffect(() => {
    if (selectedAlert) {
      setFeedbackScore(selectedAlert.feedback_score)
      setFeedbackNotes(selectedAlert.feedback_notes ?? '')
      setSaveSuccess(false)
    } else {
      setFeedbackScore(null)
      setFeedbackNotes('')
      setSaveSuccess(false)
    }
  }, [selectedAlert])

  // Sync selected alert when ticker changes
  useEffect(() => {
    if (selectedTicker && selectedTicker.alerts.length > 0) {
      setSelectedAlert(selectedTicker.alerts[0])
    } else {
      setSelectedAlert(null)
    }
  }, [selectedTicker])

  const goDate = (dateStr: string) => {
    setActiveDate(dateStr)
    router.replace(`/alerts?date=${dateStr}`, { scroll: false })
  }

  const navigateDate = (dir: number) => {
    if (dates.length === 0 || !activeDate) return
    const idx = dates.indexOf(activeDate)
    if (idx === -1) return
    const nextIdx = idx - dir // DESC order: prev date is idx + 1, next date is idx - 1
    if (nextIdx >= 0 && nextIdx < dates.length) {
      goDate(dates[nextIdx])
    }
  }

  const handleSaveFeedback = async () => {
    if (!selectedAlert || !selectedTicker) return
    setSavingFeedback(true)
    setSaveSuccess(false)
    try {
      await saveAlertFeedback(selectedAlert.id, selectedAlert.alert_time, feedbackScore, feedbackNotes)
      setSaveSuccess(true)
      
      // Update local state in ticker/alerts
      const updatedAlerts = selectedTicker.alerts.map(a => 
        a.id === selectedAlert.id ? { ...a, feedback_score: feedbackScore, feedback_notes: feedbackNotes } : a
      )
      const updatedTicker = { ...selectedTicker, alerts: updatedAlerts }
      setSelectedTicker(updatedTicker)
      
      // Update inside summary
      if (summary) {
        const updatedTickers = summary.tickers.map(t => 
          t.symbol === selectedTicker.symbol ? updatedTicker : t
        )
        setSummary({ ...summary, tickers: updatedTickers })
      }
      
      // Update active selected alert reference
      setSelectedAlert({ ...selectedAlert, feedback_score: feedbackScore, feedback_notes: feedbackNotes })
      
      setTimeout(() => setSaveSuccess(false), 2000)
    } catch {
      alert('Failed to save feedback rating')
    } finally {
      setSavingFeedback(false)
    }
  }

  const totalAlerts = summary?.tickers.reduce((acc, t) => acc + t.alerts.length, 0) ?? 0

  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bell className="text-amber-400" size={22} />
            Alert Journal
          </h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Audit alert triggers, review chart patterns, and rate alert quality.
          </p>
        </div>

        {/* Date navigations */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigateDate(-1)}
            disabled={dates.indexOf(activeDate) >= dates.length - 1}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft size={16} />
          </button>

          {dates.length > 0 ? (
            <select
              value={activeDate}
              onChange={e => goDate(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-emerald-500"
            >
              {dates.map(d => (
                <option key={d} value={d}>
                  {new Date(d + 'T12:00:00').toLocaleDateString('en-US', {
                    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'
                  })}
                </option>
              ))}
            </select>
          ) : (
            <input
              type="date"
              value={activeDate}
              onChange={e => e.target.value && goDate(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-emerald-500 [color-scheme:dark]"
            />
          )}

          <button
            onClick={() => navigateDate(1)}
            disabled={dates.indexOf(activeDate) <= 0}
            className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 disabled:opacity-30 transition-colors"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Date metadata summary */}
      {!loading && summary && (
        <div className="flex items-center gap-4 px-4 py-2.5 bg-gray-900 border border-gray-800 rounded-xl">
          <span className="text-xs font-semibold text-gray-400">Date:</span>
          <span className="text-sm text-gray-200 font-mono">{activeDate}</span>
          <span className="h-4 w-px bg-gray-800" />
          <span className="px-2 py-0.5 rounded-full text-[10px] bg-amber-500/10 text-amber-400 font-medium border border-amber-500/20">
            {totalAlerts} Alerts
          </span>
          <span className="px-2 py-0.5 rounded-full text-[10px] bg-sky-500/10 text-sky-400 font-medium border border-sky-500/20">
            {summary.tickers.length} Stocks Alerted
          </span>
        </div>
      )}

      {/* Main split layout */}
      {loading ? (
        <div className="h-[400px] w-full flex items-center justify-center">
          <Loader2 className="text-emerald-400 animate-spin" size={36} />
        </div>
      ) : !summary || summary.tickers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3 bg-gray-900/40 border border-gray-850 rounded-2xl">
          <Bell className="text-gray-700 animate-bounce" size={40} />
          <p className="text-gray-400 text-sm">No alert records logged for this date.</p>
          <p className="text-gray-600 text-xs">Run schwab streaming client during market hours to capture alerts.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          {/* Left Ticker Sidebar */}
          <div className="lg:col-span-1 space-y-2 bg-gray-900/60 p-3 rounded-xl border border-gray-850 max-h-[750px] overflow-y-auto">
            <span className="text-xs font-semibold text-gray-500 px-1 uppercase tracking-wider block mb-1">Stocks</span>
            {summary.tickers.map(tk => {
              const helpfulCount = tk.alerts.filter(a => a.feedback_score === 'helpful').length
              const noiseCount = tk.alerts.filter(a => a.feedback_score === 'noise').length
              const unratedCount = tk.alerts.filter(a => !a.feedback_score).length
              const isSelected = selectedTicker?.symbol === tk.symbol
              
              return (
                <div
                  key={tk.symbol}
                  onClick={() => setSelectedTicker(tk)}
                  className={`p-3 rounded-lg cursor-pointer transition-all border ${
                    isSelected
                      ? 'bg-emerald-500/10 border-emerald-500/50 hover:bg-emerald-500/15'
                      : 'bg-gray-950/40 border-gray-800 hover:bg-gray-800/40 hover:border-gray-700'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold font-mono text-white text-sm">{tk.symbol}</span>
                    <span className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded font-mono">
                      {tk.alerts.length}x
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-500 truncate mt-0.5">
                    {tk.company_name ?? 'Unknown Company'}
                  </div>
                  
                  {/* Rating counts */}
                  <div className="flex items-center gap-2 mt-2">
                    {helpfulCount > 0 && (
                      <span className="text-[9px] bg-emerald-500/20 text-emerald-400 px-1 rounded flex items-center gap-0.5 font-semibold">
                        <ThumbsUp size={8} /> {helpfulCount}
                      </span>
                    )}
                    {noiseCount > 0 && (
                      <span className="text-[9px] bg-rose-500/20 text-rose-400 px-1 rounded flex items-center gap-0.5 font-semibold">
                        <ThumbsDown size={8} /> {noiseCount}
                      </span>
                    )}
                    {unratedCount > 0 && (
                      <span className="text-[9px] bg-gray-800 text-gray-500 px-1 rounded font-semibold">
                        {unratedCount} unrated
                      </span>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Right Detailed Analysis Panel */}
          {selectedTicker ? (
            <div className="lg:col-span-3 space-y-6">
              {/* Ticker header cards */}
              <div className="bg-gray-900 border border-gray-850 p-4 rounded-2xl flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    <span className="font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-lg">
                      {selectedTicker.symbol}
                    </span>
                    <span className="text-gray-300 text-sm font-medium">{selectedTicker.company_name}</span>
                  </h2>
                </div>

                <div className="flex flex-wrap items-center gap-4 text-xs font-mono">
                  {selectedTicker.float_shares != null && (
                    <div className="bg-gray-950 px-2.5 py-1 rounded-lg border border-gray-800">
                      <span className="text-gray-500 mr-1">Float:</span>
                      <span className="text-gray-300 font-semibold">{formatFloat(selectedTicker.float_shares)}</span>
                    </div>
                  )}
                  {selectedTicker.market_cap != null && (
                    <div className="bg-gray-950 px-2.5 py-1 rounded-lg border border-gray-800">
                      <span className="text-gray-500 mr-1">Cap:</span>
                      <span className="text-gray-300 font-semibold">${formatFloat(selectedTicker.market_cap)}</span>
                    </div>
                  )}
                  {selectedTicker.gap_pct != null && (
                    <div className="bg-gray-950 px-2.5 py-1 rounded-lg border border-gray-800">
                      <span className="text-gray-500 mr-1">Gap:</span>
                      <span className="text-emerald-400 font-semibold">+{selectedTicker.gap_pct.toFixed(1)}%</span>
                    </div>
                  )}
                  {selectedTicker.rvol != null && (
                    <div className="bg-gray-950 px-2.5 py-1 rounded-lg border border-gray-800">
                      <span className="text-gray-500 mr-1">RVOL:</span>
                      <span className="text-amber-400 font-semibold">{selectedTicker.rvol.toFixed(1)}x</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Chart container */}
              <AlertSessionChart
                key={`${selectedTicker.symbol}-${activeDate}`}
                ticker={selectedTicker.symbol}
                date={activeDate}
                alerts={selectedTicker.alerts}
              />

              {/* Alerts & feedback rating area */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
                {/* Alert occurrences list */}
                <div className="md:col-span-2 space-y-2 bg-gray-900/40 border border-gray-850 p-4 rounded-2xl max-h-[300px] overflow-y-auto">
                  <span className="text-xs font-semibold text-gray-500 block mb-2 uppercase tracking-wider">Alert Triggers</span>
                  {selectedTicker.alerts.map(alt => {
                    const localTime = new Date(alt.alert_time).toLocaleTimeString('en-US', {
                      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
                    })
                    const isSelected = selectedAlert?.id === alt.id
                    
                    return (
                      <div
                        key={alt.id}
                        onClick={() => setSelectedAlert(alt)}
                        className={`p-2.5 rounded-xl cursor-pointer transition-all border flex items-center justify-between text-xs ${
                          isSelected
                            ? 'bg-amber-500/10 border-amber-500/50 hover:bg-amber-500/15 text-white'
                            : 'bg-gray-950/40 border-gray-800 hover:bg-gray-800/40 hover:border-gray-700 text-gray-300'
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold">{alt.alert_type.replace('_', ' ')}</span>
                          </div>
                          <div className="text-[10px] text-gray-500 font-mono">
                            {localTime} · ${alt.trigger_price.toFixed(2)}
                          </div>
                        </div>

                        {/* rating badge indicator */}
                        {alt.feedback_score === 'helpful' ? (
                          <ThumbsUp size={12} className="text-emerald-400 fill-emerald-400/20" />
                        ) : alt.feedback_score === 'noise' ? (
                          <ThumbsDown size={12} className="text-rose-400 fill-rose-400/20" />
                        ) : alt.feedback_score === 'neutral' ? (
                          <span className="text-[9px] bg-gray-800 text-gray-400 px-1 rounded">Neutral</span>
                        ) : (
                          <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" title="Unrated" />
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Feedback Review panel */}
                <div className="md:col-span-3 bg-gray-900 border border-gray-850 p-4 rounded-2xl flex flex-col justify-between min-h-[300px]">
                  {selectedAlert ? (
                    <div className="space-y-4 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Alert Feedback</span>
                        <span className="text-[10px] text-gray-400 font-mono bg-gray-950 border border-gray-800 px-2 py-0.5 rounded">
                          ID: {selectedAlert.id}
                        </span>
                      </div>

                      {/* Info details */}
                      <div className="bg-gray-950 border border-gray-850 p-3 rounded-xl space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Trigger Type:</span>
                          <span className="text-gray-300 font-semibold">{selectedAlert.alert_type}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Price:</span>
                          <span className="text-gray-300 font-mono font-semibold">${selectedAlert.trigger_price.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Trigger Volume:</span>
                          <span className="text-gray-300 font-mono">{selectedAlert.trigger_volume.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">RVOL:</span>
                          <span className="text-amber-400 font-mono font-semibold">{selectedAlert.rel_vol.toFixed(1)}x</span>
                        </div>
                      </div>

                      {/* Helpful / Noise Rating */}
                      <div className="space-y-2">
                        <span className="text-xs text-gray-400">Rate Alert Quality:</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setFeedbackScore('helpful')}
                            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
                              feedbackScore === 'helpful'
                                ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-lg shadow-emerald-500/10'
                                : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800'
                            }`}
                          >
                            <ThumbsUp size={13} />
                            <span>Helpful</span>
                          </button>

                          <button
                            onClick={() => setFeedbackScore('noise')}
                            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold border transition-all ${
                              feedbackScore === 'noise'
                                ? 'bg-rose-500/20 border-rose-500 text-rose-400 shadow-lg shadow-rose-500/10'
                                : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800'
                            }`}
                          >
                            <ThumbsDown size={13} />
                            <span>Noise</span>
                          </button>

                          <button
                            onClick={() => setFeedbackScore('neutral')}
                            className={`px-3 py-2 rounded-xl text-xs font-semibold border transition-all ${
                              feedbackScore === 'neutral'
                                ? 'bg-gray-800 border-gray-700 text-gray-200'
                                : 'bg-gray-950 border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800'
                            }`}
                          >
                            <span>Neutral</span>
                          </button>
                        </div>
                      </div>

                      {/* Observations Notes */}
                      <div className="space-y-2">
                        <span className="text-xs text-gray-400">Trader Observations / Notes:</span>
                        <textarea
                          value={feedbackNotes}
                          onChange={e => setFeedbackNotes(e.target.value)}
                          placeholder="Why was this alert good or bad? Add notes on trend, float theme, support/resistance, etc."
                          rows={3}
                          className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-emerald-500 resize-none"
                        />
                      </div>

                      {/* Action Button */}
                      <div className="flex items-center justify-end gap-2 pt-2">
                        {saveSuccess && (
                          <div className="flex items-center gap-1 text-xs text-emerald-400 mr-auto transition-all animate-fade-in">
                            <CheckCircle size={13} />
                            <span>Feedback saved successfully</span>
                          </div>
                        )}
                        <button
                          onClick={handleSaveFeedback}
                          disabled={savingFeedback}
                          className="flex items-center gap-1.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-600/50 text-gray-950 font-bold px-4 py-2 rounded-xl text-xs transition-all border border-emerald-400/20 shadow-lg shadow-emerald-500/10"
                        >
                          {savingFeedback ? (
                            <Loader2 size={13} className="animate-spin" />
                          ) : (
                            <Save size={13} />
                          )}
                          <span>Save Review</span>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-4 text-gray-600 gap-1.5">
                      <Info size={24} />
                      <span className="text-xs">No alert trigger selected.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="lg:col-span-3 flex flex-col items-center justify-center py-24 gap-3 bg-gray-900/40 border border-gray-850 rounded-2xl">
              <AlertCircle className="text-gray-700" size={36} />
              <p className="text-gray-500 text-sm">No ticker selected.</p>
              <p className="text-gray-600 text-xs">Select a stock ticker from the left sidebar to analyze.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AlertJournalPage() {
  return (
    <Suspense fallback={
      <div className="h-[400px] w-full flex items-center justify-center">
        <Loader2 className="text-emerald-400 animate-spin" size={36} />
      </div>
    }>
      <AlertJournalContent />
    </Suspense>
  )
}
