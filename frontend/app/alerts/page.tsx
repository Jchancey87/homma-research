'use client'
import { useEffect, useRef, useState, useCallback, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  createChart, IChartApi,
  CandlestickSeries, LineSeries, HistogramSeries,
  CrosshairMode, UTCTimestamp, createSeriesMarkers,
  LineStyle, ISeriesApi, IPriceLine
} from 'lightweight-charts'
import {
  getAlertDates, getAlertsDailySummary, saveAlertFeedback, getAlertsPerformance,
  getChartData,
  AlertDailySummary, AlertTickerSummary, AlertInstance, ScorecardRow
} from '@/lib/api'
import {
  Bell, ChevronLeft, ChevronRight, Loader2,
  AlertCircle, ThumbsUp, ThumbsDown, Save, CheckCircle, Info, BarChart2
} from 'lucide-react'
import {
  CHART_BG, GRID_COLOR, TEXT_COLOR, UP_COLOR, DOWN_COLOR, EMA21_COL,
  ChartData, OhlcBar, LinePt, HistoPt,
  dedupSort, shiftChartDataTime,
} from '@/lib/chart'
import { fmtFloat } from '@/lib/format'

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
    case 'RUNNING_UP':
      return { shape: 'arrowUp', color: '#10b981' } // green
    case 'BULL_FLAG':
      return { shape: 'arrowUp', color: '#ec4899' } // pink
    case 'VWAP_RECLAIM':
      return { shape: 'arrowUp', color: '#14b8a6' } // teal
    case 'MULTI_TF_CONFLUENCE':
      return { shape: 'arrowUp', color: '#a855f7' } // purple
    case 'HALT_RESUME_MOMENTUM':
      return { shape: 'arrowUp', color: '#eab308' } // amber
    default:
      return { shape: 'circle', color: '#f59e0b' }
  }
}

function updateChartDecorations(
  chart: IChartApi,
  candles: ISeriesApi<'Candlestick'>,
  alerts: AlertInstance[],
  selectedAlertId: number | null,
  priceLineRef: React.MutableRefObject<IPriceLine | null>
) {
  const localOffset = -new Date().getTimezoneOffset() * 60

  // 1. Update markers (highlight selected alert)
  const markers = alerts.map(alt => {
    const timeSec = Math.floor(new Date(alt.alert_time).getTime() / 1000) + localOffset
    const config = getMarkerConfig(alt.alert_type)
    const isSelected = alt.id === selectedAlertId
    return {
      time: timeSec as UTCTimestamp,
      position: 'aboveBar' as const,
      shape: config.shape,
      color: config.color,
      text: isSelected ? `🎯 ${alt.alert_type.replace('_', ' ')}` : alt.alert_type.replace('_', ' '),
      size: isSelected ? 2.2 : 1.2
    }
  })

  createSeriesMarkers(candles, markers)

  // 2. Clear old price line and draw new one if selected
  if (priceLineRef.current) {
    try {
      candles.removePriceLine(priceLineRef.current)
    } catch (e) {
      console.error("Error removing price line:", e)
    }
    priceLineRef.current = null
  }

  const selectedAlt = alerts.find(a => a.id === selectedAlertId)
  if (selectedAlt) {
    priceLineRef.current = candles.createPriceLine({
      price: selectedAlt.trigger_price,
      color: '#f59e0b', // Amber highlight
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      axisLabelVisible: true,
      title: `${selectedAlt.alert_type.replace('_', ' ')}: $${selectedAlt.trigger_price.toFixed(2)}`,
    })

    // 3. Scroll/zoom timescale to the selected alert (35 mins before, 35 mins after)
    const timeSec = Math.floor(new Date(selectedAlt.alert_time).getTime() / 1000) + localOffset
    chart.timeScale().setVisibleRange({
      from: (timeSec - 35 * 60) as UTCTimestamp,
      to: (timeSec + 35 * 60) as UTCTimestamp,
    })
  } else {
    chart.timeScale().fitContent()
  }
}

// ── Interactive Chart Component ──────────────────────────────────────────────
interface ChartProps {
  ticker: string
  date: string
  alerts: AlertInstance[]
  selectedAlertId: number | null
}

function AlertSessionChart({ ticker, date, alerts, selectedAlertId }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candlesSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const priceLineRef = useRef<IPriceLine | null>(null)

  const [data, setData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const fetchData = async () => {
      setLoading(true)
      setError(null)
      try {
        const json = await getChartData(ticker, date, true)
        if (!active) return

        const rawData = {
          ohlcv:  json.ohlcv  as OhlcBar[],
          volume: json.volume as HistoPt[],
          ema_21: json.ema_21 as LinePt[] ?? [],
        } as ChartData
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

  // 1. Chart creation effect
  useEffect(() => {
    if (!data || !containerRef.current) return

    chartRef.current?.remove()

    const chart = createChart(containerRef.current, {
      layout: { 
        background: { color: CHART_BG }, 
        textColor: TEXT_COLOR, 
        fontSize: 10,
        fontFamily: "Consolas, 'Roboto Mono', Monaco, ui-monospace, monospace"
      },
      grid: { 
        vertLines: { color: GRID_COLOR, style: 1 }, 
        horzLines: { color: GRID_COLOR, style: 1 } 
      },
      crosshair: { 
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#555555',
          width: 1,
          style: 1, // Dotted
          labelBackgroundColor: '#00ff00',
        },
        horzLine: {
          color: '#555555',
          width: 1,
          style: 1, // Dotted
          labelBackgroundColor: '#ff003c',
        }
      },
      rightPriceScale: { borderColor: '#262626', textColor: TEXT_COLOR },
      timeScale: {
        borderColor: '#262626',
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
    candlesSeriesRef.current = candles

    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 }, visible: false })

    const ohlcMap = new Map<number, OhlcBar>()
    data.ohlcv.forEach(c => ohlcMap.set(c.time as number, c))

    const volData = data.volume.map(v => {
      const candle = ohlcMap.get(v.time as number)
      const isUp = candle ? candle.close >= candle.open : true
      return {
        time: v.time,
        value: v.value,
        color: isUp ? 'rgba(0, 255, 0, 0.3)' : 'rgba(255, 0, 60, 0.3)',
      }
    })
    vol.setData(dedupSort(volData))

    if (data.ema_21?.length) {
      const ema = chart.addSeries(LineSeries, {
        color: EMA21_COL, lineWidth: 1,
        priceLineVisible: false, lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      ema.setData(dedupSort(data.ema_21))
    }

    // Apply decorations immediately on mount / data load
    updateChartDecorations(chart, candles, alerts, selectedAlertId, priceLineRef)

    const ro = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      chart.remove()
      chartRef.current = null
      candlesSeriesRef.current = null
      priceLineRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data])

  // 2. Decorations update effect (runs when active alerts or selected alert changes)
  useEffect(() => {
    if (chartRef.current && candlesSeriesRef.current && data) {
      updateChartDecorations(chartRef.current, candlesSeriesRef.current, alerts, selectedAlertId, priceLineRef)
    }
  }, [alerts, selectedAlertId, data])

  if (loading) {
    return (
      <div className="h-[350px] flex items-center justify-center bg-[#050505] border border-[#262626]">
        <Loader2 className="text-[#00ff00] animate-spin" size={28} />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="h-[350px] flex flex-col items-center justify-center bg-[#050505] border border-[#262626] gap-2">
        <AlertCircle className="text-[#ff003c]" size={32} />
        <span className="font-mono text-xs text-gray-500">{error ?? 'No intraday chart data available'}</span>
        <span className="font-mono text-xs text-gray-500">Run nightly backfill if this date is today.</span>
      </div>
    )
  }

  return (
    <div className="relative w-full h-[350px]">
      <div ref={containerRef} className="w-full h-full bg-black border border-[#262626] overflow-hidden" />
      {data && (
        <button
          onClick={() => chartRef.current?.timeScale().fitContent()}
          className="absolute top-2 right-2 z-10 px-2 py-0.5 bg-[#050505] border border-[#262626] text-gray-400 hover:text-white text-[10px] font-mono transition-colors rounded-none"
        >
          Fit Chart
        </button>
      )}
    </div>
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
  const [activeTab, setActiveTab] = useState<'journal' | 'scorecard'>('journal')
  const [scorecard, setScorecard] = useState<ScorecardRow[] | null>(null)
  const [scorecardLoading, setScorecardLoading] = useState(false)

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

  // Load performance scorecard when tab switches
  useEffect(() => {
    if (activeTab === 'scorecard' && scorecard === null) {
      setScorecardLoading(true)
      getAlertsPerformance(30)
        .then(res => setScorecard(res.scorecard))
        .catch(() => setScorecard([]))
        .finally(() => setScorecardLoading(false))
    }
  }, [activeTab, scorecard])

  return (
    <div className="space-y-2">
      {/* Header bar */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-sm font-bold text-white uppercase flex items-center gap-2">
            <Bell className="text-amber-400" size={14} />
            Alert Journal
          </h1>
          <p className="font-mono text-[10px] text-gray-500 mt-0.5">
            Audit alert triggers, review chart patterns, and rate alert quality.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Tab switcher */}
          <div className="flex bg-black border border-[#262626]">
            <button
              onClick={() => setActiveTab('journal')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono font-semibold transition-all ${
                activeTab === 'journal'
                  ? 'bg-[#0a0a0a] text-amber-400 border-b-2 border-amber-400'
                  : 'text-gray-500 hover:text-gray-300 transition-colors'
              }`}
            >
              <Bell size={12} />
              Journal
            </button>
            <button
              onClick={() => setActiveTab('scorecard')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono font-semibold transition-all ${
                activeTab === 'scorecard'
                  ? 'bg-[#0a0a0a] text-[#00f0ff] border-b-2 border-[#00f0ff]'
                  : 'text-gray-500 hover:text-gray-300 transition-colors'
              }`}
            >
              <BarChart2 size={12} />
              Performance
            </button>
          </div>
          <button
            onClick={() => navigateDate(-1)}
            disabled={dates.indexOf(activeDate) >= dates.length - 1}
            className="p-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white disabled:opacity-30 transition-colors rounded-none"
          >
            <ChevronLeft size={16} />
          </button>

          {dates.length > 0 ? (
            <select
              value={activeDate}
              onChange={e => goDate(e.target.value)}
              className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]"
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
              className="bg-black border border-[#262626] text-white font-mono text-[11px] px-2 py-1 focus:outline-none focus:border-[#00ff00] rounded-none [color-scheme:dark]"
            />
          )}

          <button
            onClick={() => navigateDate(1)}
            disabled={dates.indexOf(activeDate) <= 0}
            className="p-1.5 border border-[#262626] bg-black text-gray-400 hover:text-white disabled:opacity-30 transition-colors rounded-none"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* Date metadata summary */}
      {!loading && summary && (
        <div className="flex items-center gap-3 px-3 py-1.5 bg-[#0a0a0a] border border-[#262626]">
          <span className="font-mono text-[10px] text-gray-500 uppercase">Date:</span>
          <span className="font-mono text-xs text-gray-300">{activeDate}</span>
          <span className="h-4 w-px bg-[#262626]" />
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-amber-950/20 text-amber-400 border border-amber-500/25 rounded-none">
            {totalAlerts} Alerts
          </span>
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#001a1f] text-[#00f0ff] border border-[#00f0ff]/25 rounded-none">
            {summary.tickers.length} Stocks Alerted
          </span>
        </div>
      )}

      {/* Main split layout */}
      {loading ? (
        <div className="h-[400px] flex items-center justify-center">
          <Loader2 className="text-[#00ff00] animate-spin" size={36} />
        </div>
      ) : !summary || summary.tickers.length === 0 ? (
        <div className="bg-[#050505] border border-[#262626] py-16 flex flex-col items-center justify-center gap-2">
          <Bell className="text-gray-700 animate-bounce" size={40} />
          <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">No alert records logged for this date.</p>
          <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">Run schwab streaming client during market hours.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-2 items-start">
          {/* Left Ticker Sidebar */}
          <div className="lg:col-span-1 bg-[#050505] border border-[#262626] max-h-[750px] overflow-y-auto">
            <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider px-3 py-2 border-b border-[#262626] block">Stocks</span>
            {summary.tickers.map(tk => {
              const helpfulCount = tk.alerts.filter(a => a.feedback_score === 'helpful').length
              const noiseCount = tk.alerts.filter(a => a.feedback_score === 'noise').length
              const unratedCount = tk.alerts.filter(a => !a.feedback_score).length
              const isSelected = selectedTicker?.symbol === tk.symbol
              
              return (
                <div
                  key={tk.symbol}
                  onClick={() => setSelectedTicker(tk)}
                  className={`px-3 py-2.5 cursor-pointer border-b border-[#1a1a1a] transition-all hover:bg-[#0a0a0a] ${
                    isSelected ? 'bg-[#0a0a0a] border-l-2 border-[#00ff00]' : ''
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-white text-xs">{tk.symbol}</span>
                    <span className="text-[9px] bg-[#111] text-gray-500 border border-[#262626] px-1.5 py-0.5 font-mono rounded-none">
                      {tk.alerts.length}x
                    </span>
                  </div>
                  <div className="font-mono text-[10px] text-gray-500 truncate mt-0.5">
                    {tk.company_name ?? 'Unknown Company'}
                  </div>
                  
                  {/* Rating counts */}
                  <div className="flex items-center gap-2 mt-2">
                    {helpfulCount > 0 && (
                      <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 rounded-none flex items-center gap-0.5">
                        <ThumbsUp size={8} /> {helpfulCount}
                      </span>
                    )}
                    {noiseCount > 0 && (
                      <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-red-950/20 text-[#ff003c] border border-[#ff003c]/25 rounded-none flex items-center gap-0.5">
                        <ThumbsDown size={8} /> {noiseCount}
                      </span>
                    )}
                    {unratedCount > 0 && (
                      <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#111] text-gray-500 border border-[#262626] rounded-none">
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
            <div className="lg:col-span-3 space-y-2">
              {/* Ticker header cards */}
              <div className="bg-[#050505] border border-[#262626] p-3 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="flex items-center gap-2">
                    <span className="font-mono bg-emerald-950/20 text-[#00ff00] border border-[#00ff00]/25 px-2 py-0.5 text-xs font-bold rounded-none">
                      {selectedTicker.symbol}
                    </span>
                    <span className="font-mono text-gray-400 text-xs">{selectedTicker.company_name}</span>
                  </h2>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {selectedTicker.float_shares != null && (
                    <div className="bg-[#0a0a0a] border border-[#262626] px-2 py-0.5 font-mono text-[10px] rounded-none">
                      <span className="text-gray-600">Float:</span>
                      <span className="text-gray-300 font-bold ml-1">{fmtFloat(selectedTicker.float_shares)}</span>
                    </div>
                  )}
                  {selectedTicker.market_cap != null && (
                    <div className="bg-[#0a0a0a] border border-[#262626] px-2 py-0.5 font-mono text-[10px] rounded-none">
                      <span className="text-gray-600">Cap:</span>
                      <span className="text-gray-300 font-bold ml-1">${fmtFloat(selectedTicker.market_cap)}</span>
                    </div>
                  )}
                  {selectedTicker.gap_pct != null && (
                    <div className="bg-[#0a0a0a] border border-[#262626] px-2 py-0.5 font-mono text-[10px] rounded-none">
                      <span className="text-gray-600">Gap:</span>
                      <span className="text-[#00ff00] font-bold ml-1">+{selectedTicker.gap_pct.toFixed(1)}%</span>
                    </div>
                  )}
                  {selectedTicker.rvol != null && (
                    <div className="bg-[#0a0a0a] border border-[#262626] px-2 py-0.5 font-mono text-[10px] rounded-none">
                      <span className="text-gray-600">RVOL:</span>
                      <span className="text-amber-400 font-bold ml-1">{selectedTicker.rvol.toFixed(1)}x</span>
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
                selectedAlertId={selectedAlert?.id ?? null}
              />

              {/* Alerts & feedback rating area */}
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                {/* Alert occurrences list */}
                <div className="md:col-span-2 bg-[#050505] border border-[#262626] p-3 max-h-[300px] overflow-y-auto">
                  <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider border-b border-[#262626] pb-2 mb-2 block">Alert Triggers</span>
                  {selectedTicker.alerts.map(alt => {
                    const localTime = new Date(alt.alert_time).toLocaleTimeString('en-US', {
                      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
                    })
                    const isSelected = selectedAlert?.id === alt.id
                    // Forward return colour helper
                    const fwdColor = (v: number | null) => {
                      if (v == null) return 'text-gray-600'
                      return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-rose-400' : 'text-gray-500'
                    }
                    const fwdLabel = (v: number | null) => v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}%`

                    return (
                      <div
                        key={alt.id}
                        onClick={() => setSelectedAlert(alt)}
                        className={`p-2 cursor-pointer border hover:bg-[#0a0a0a] transition-colors mb-1 ${
                          isSelected
                            ? 'bg-[#0a0a0a] border border-amber-500/40'
                            : 'border-[#1a1a1a]'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-mono text-xs font-bold text-white">{alt.alert_type.replace(/_/g, ' ')}</span>
                              {/* Priority tier badge */}
                              <span className={`px-1 py-0.5 text-[9px] font-mono font-bold border rounded-none ${
                                alt.priority_tier === 'Tier 1' ? 'text-[#ff003c] border-[#ff003c]/40 bg-red-950/20'
                                : alt.priority_tier === 'Tier 2' ? 'text-amber-400 border-amber-500/40 bg-amber-950/20'
                                : 'text-gray-600 border-[#262626]'
                              }`}>{alt.priority_tier ?? 'T3'}</span>
                            </div>
                            <div className="font-mono text-[10px] text-gray-500">
                              {localTime} · ${alt.trigger_price.toFixed(2)}
                              {alt.priority_score ? <span className="ml-1 text-gray-700">· Score: {alt.priority_score}</span> : null}
                            </div>
                          </div>

                          {/* rating badge indicator */}
                          {alt.feedback_score === 'helpful' ? (
                            <ThumbsUp size={12} className="text-[#00ff00] fill-emerald-400/20" />
                          ) : alt.feedback_score === 'noise' ? (
                            <ThumbsDown size={12} className="text-[#ff003c] fill-rose-400/20" />
                          ) : alt.feedback_score === 'neutral' ? (
                            <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#111] text-gray-500 border border-[#262626] rounded-none">Neutral</span>
                          ) : (
                            <span className="h-1.5 w-1.5 bg-amber-500 animate-pulse" title="Unrated" />
                          )}
                        </div>

                        {/* Forward returns mini-row */}
                        {(alt.fwd_1m != null || alt.fwd_5m != null || alt.fwd_15m != null) && (
                          <div className="mt-1 pt-1 border-t border-[#1a1a1a] flex items-center gap-2 font-mono text-[9px]">
                            {alt.fwd_1m != null && (
                              <span><span className="text-gray-600">1m </span><span className={fwdColor(alt.fwd_1m)}>{fwdLabel(alt.fwd_1m)}</span></span>
                            )}
                            {alt.fwd_5m != null && (
                              <span><span className="text-gray-600">5m </span><span className={fwdColor(alt.fwd_5m)}>{fwdLabel(alt.fwd_5m)}</span></span>
                            )}
                            {alt.fwd_15m != null && (
                              <span><span className="text-gray-600">15m </span><span className={fwdColor(alt.fwd_15m)}>{fwdLabel(alt.fwd_15m)}</span></span>
                            )}
                            {alt.mfe != null && (
                              <span title="Max Favorable Excursion"><span className="text-gray-600">↑</span><span className="text-emerald-500">{fwdLabel(alt.mfe)}</span></span>
                            )}
                            {alt.mae != null && (
                              <span title="Max Adverse Excursion"><span className="text-gray-600">↓</span><span className="text-rose-500">{fwdLabel(alt.mae)}</span></span>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {/* Feedback Review panel */}
                <div className="md:col-span-3 bg-[#050505] border border-[#262626] p-3 flex flex-col min-h-[300px]">
                  {selectedAlert ? (
                    <div className="space-y-4 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider">Alert Feedback</span>
                        <span className="font-mono text-[10px] text-gray-400 bg-black border border-[#262626] px-2 py-0.5 rounded-none">
                          ID: {selectedAlert.id}
                        </span>
                      </div>

                      {/* Info details */}
                      <div className="bg-black border border-[#262626] p-3 space-y-1">
                        {/* Priority / Tier row */}
                        <div className="flex justify-between items-center pb-1 mb-1 border-b border-[#1a1a1a]">
                          <span className="font-mono text-[10px] text-gray-500">Priority:</span>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-[10px] font-mono font-bold border rounded-none ${
                              selectedAlert.priority_tier === 'Tier 1' ? 'text-[#ff003c] border-[#ff003c]/40 bg-red-950/20'
                              : selectedAlert.priority_tier === 'Tier 2' ? 'text-amber-400 border-amber-500/40 bg-amber-950/20'
                              : 'text-gray-600 border-[#262626]'
                            }`}>{selectedAlert.priority_tier ?? 'Tier 3'}</span>
                            <span className="font-mono text-[10px] text-gray-500">Score: <span className="text-gray-300">{selectedAlert.priority_score ?? 0}</span></span>
                          </div>
                        </div>
                        <div className="flex justify-between">
                          <span className="font-mono text-[10px] text-gray-500">Trigger Type:</span>
                          <span className="font-mono text-xs text-gray-300">{selectedAlert.alert_type.replace(/_/g, ' ')}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="font-mono text-[10px] text-gray-500">Price:</span>
                          <span className="font-mono text-xs text-gray-300">${selectedAlert.trigger_price.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="font-mono text-[10px] text-gray-500">Trigger Volume:</span>
                          <span className="font-mono text-xs text-gray-300">{selectedAlert.trigger_volume.toLocaleString()}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="font-mono text-[10px] text-gray-500">RVOL:</span>
                          <span className="font-mono text-xs text-amber-400">{selectedAlert.rel_vol.toFixed(1)}x</span>
                        </div>
                        {/* Context fields from confluence engine */}
                        {selectedAlert.catalyst && (
                          <div className="flex justify-between">
                            <span className="font-mono text-[10px] text-gray-500">Catalyst:</span>
                            <span className="font-mono text-xs text-[#00f0ff]">{selectedAlert.catalyst}</span>
                          </div>
                        )}
                        {selectedAlert.vwap_dist_pct != null && (
                          <div className="flex justify-between">
                            <span className="font-mono text-[10px] text-gray-500">VWAP Dist:</span>
                            <span className={`font-mono text-xs ${selectedAlert.vwap_dist_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                              {selectedAlert.vwap_dist_pct > 0 ? '+' : ''}{selectedAlert.vwap_dist_pct.toFixed(1)}%
                            </span>
                          </div>
                        )}
                        {selectedAlert.hod_dist_pct != null && (
                          <div className="flex justify-between">
                            <span className="font-mono text-[10px] text-gray-500">HOD Dist:</span>
                            <span className={`font-mono text-xs ${selectedAlert.hod_dist_pct >= 0 ? 'text-emerald-400' : 'text-gray-400'}`}>
                              {selectedAlert.hod_dist_pct > 0 ? '+' : ''}{selectedAlert.hod_dist_pct.toFixed(1)}%
                            </span>
                          </div>
                        )}
                        {selectedAlert.stop_price != null && selectedAlert.stop_price > 0 && (
                          <div className="flex justify-between">
                            <span className="font-mono text-[10px] text-gray-500">Stop Level:</span>
                            <span className="font-mono text-xs text-rose-400">
                              ${selectedAlert.stop_price.toFixed(2)}
                              {selectedAlert.stop_risk_pct != null && selectedAlert.stop_risk_pct > 0 && (
                                <span className="text-gray-600 ml-1">({selectedAlert.stop_risk_pct.toFixed(1)}% risk)</span>
                              )}
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Helpful / Noise Rating */}
                      <div className="space-y-2">
                        <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider">Rate Alert Quality:</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setFeedbackScore('helpful')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono border transition-all rounded-none ${
                              feedbackScore === 'helpful'
                                ? 'border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00]'
                                : 'bg-black border-[#262626] text-gray-500 hover:text-white hover:border-[#444] transition-colors'
                            }`}
                          >
                            <ThumbsUp size={13} />
                            <span>Helpful</span>
                          </button>

                          <button
                            onClick={() => setFeedbackScore('noise')}
                            className={`flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono border transition-all rounded-none ${
                              feedbackScore === 'noise'
                                ? 'border-[#ff003c]/40 bg-red-950/20 text-[#ff003c]'
                                : 'bg-black border-[#262626] text-gray-500 hover:text-white hover:border-[#444] transition-colors'
                            }`}
                          >
                            <ThumbsDown size={13} />
                            <span>Noise</span>
                          </button>

                          <button
                            onClick={() => setFeedbackScore('neutral')}
                            className={`px-3 py-1.5 text-[11px] font-mono border transition-all rounded-none ${
                              feedbackScore === 'neutral'
                                ? 'border-[#262626] bg-[#111] text-white'
                                : 'bg-black border-[#262626] text-gray-500 hover:text-white hover:border-[#444] transition-colors'
                            }`}
                          >
                            <span>Neutral</span>
                          </button>
                        </div>
                      </div>

                      {/* Observations Notes */}
                      <div className="space-y-2">
                        <span className="font-mono text-[10px] text-gray-500 uppercase tracking-wider">Trader Observations / Notes:</span>
                        <textarea
                          value={feedbackNotes}
                          onChange={e => setFeedbackNotes(e.target.value)}
                          placeholder="Why was this alert good or bad? Add notes on trend, float theme, support/resistance, etc."
                          rows={3}
                          className="w-full bg-black border border-[#262626] text-white font-mono text-[11px] p-2 focus:outline-none focus:border-[#00ff00] rounded-none resize-none"
                        />
                      </div>

                      {/* Action Button */}
                      <div className="flex items-center justify-end gap-2 pt-2">
                        {saveSuccess && (
                          <div className="flex items-center gap-1 text-xs text-[#00ff00] mr-auto transition-all animate-fade-in font-mono">
                            <CheckCircle size={13} />
                            <span>Feedback saved successfully</span>
                          </div>
                        )}
                        <button
                          onClick={handleSaveFeedback}
                          disabled={savingFeedback}
                          className="flex items-center gap-1.5 border border-[#00ff00]/40 bg-emerald-950/20 text-[#00ff00] font-mono text-[11px] px-4 py-1.5 rounded-none transition-colors disabled:opacity-50"
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
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-4 text-gray-700 gap-1.5">
                      <Info size={24} />
                      <span className="font-mono text-xs text-gray-500 uppercase tracking-wider">No alert trigger selected.</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="lg:col-span-3 flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
              <AlertCircle className="text-gray-700" size={36} />
              <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">No ticker selected.</p>
              <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">Select a stock ticker from the left sidebar to analyze.</p>
            </div>
          )}
        </div>
      )}
      {/* ── PERFORMANCE SCORECARD TAB ────────────────────────────────── */}
      {activeTab === 'scorecard' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <BarChart2 size={14} className="text-[#00f0ff]" />
            <span className="font-mono text-sm font-bold text-white uppercase">Performance Scorecard</span>
            <span className="font-mono text-[10px] text-gray-500">· Last 30 days · requires 1-min candle data</span>
          </div>

          {scorecardLoading ? (
            <div className="h-48 flex items-center justify-center bg-[#050505] border border-[#262626]">
              <Loader2 className="text-[#00ff00] animate-spin" size={28} />
            </div>
          ) : !scorecard || scorecard.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2 border border-[#262626] bg-[#050505]">
              <BarChart2 className="text-gray-700" size={36} />
              <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">No performance data yet.</p>
              <p className="text-gray-500 text-xs uppercase tracking-wider font-mono">1-minute candle data is required to compute forward returns.</p>
            </div>
          ) : (
            <div className="overflow-x-auto border border-[#262626]">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-[#050505] border-b border-[#262626]">
                    <th className="text-left px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Alert Type</th>
                    <th className="text-left px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Price Bucket</th>
                    <th className="text-left px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Float</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">N</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Win% (5m)</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Avg 5m</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Avg 15m</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Avg MFE</th>
                    <th className="text-right px-3 py-2 text-[10px] font-mono text-gray-500 uppercase tracking-wider">Avg MAE</th>
                  </tr>
                </thead>
                <tbody>
                  {scorecard.map((row, i) => {
                    const winColor = row.win_rate_5m_pct == null ? 'text-gray-500'
                      : row.win_rate_5m_pct >= 60 ? 'text-emerald-400 font-semibold'
                      : row.win_rate_5m_pct >= 45 ? 'text-amber-400'
                      : 'text-rose-400'
                    const retColor = (v: number | null) => v == null ? 'text-gray-600'
                      : v > 0 ? 'text-emerald-400' : v < 0 ? 'text-rose-400' : 'text-gray-400'
                    const fmt = (v: number | null, suffix = '%') => v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(1)}${suffix}`

                    return (
                      <tr key={i} className="border-b border-[#1a1a1a] hover:bg-[#0a0a0a] transition-colors">
                        <td className="px-3 py-2 font-mono text-xs text-gray-200">
                          {row.alert_type.replace(/_/g, ' ')}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-400">{row.price_bucket}</td>
                        <td className="px-3 py-2 font-mono text-xs text-gray-500">{row.float_category ?? '—'}</td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-gray-400">{row.sample_count}</td>
                        <td className={`px-3 py-2 text-right font-mono text-xs ${winColor}`}>
                          {row.win_rate_5m_pct == null ? '–' : `${row.win_rate_5m_pct.toFixed(0)}%`}
                        </td>
                        <td className={`px-3 py-2 text-right font-mono text-xs ${retColor(row.avg_fwd_5m)}`}>
                          {fmt(row.avg_fwd_5m)}
                        </td>
                        <td className={`px-3 py-2 text-right font-mono text-xs ${retColor(row.avg_fwd_15m)}`}>
                          {fmt(row.avg_fwd_15m)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-emerald-500">
                          {fmt(row.avg_mfe_pct)}
                        </td>
                        <td className="px-3 py-2 text-right font-mono text-xs text-rose-500">
                          {fmt(row.avg_mae_pct)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
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
      <div className="h-[400px] flex items-center justify-center">
        <Loader2 className="text-[#00ff00] animate-spin" size={36} />
      </div>
    }>
      <AlertJournalContent />
    </Suspense>
  )
}
